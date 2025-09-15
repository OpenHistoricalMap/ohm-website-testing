import os
import time
import requests
from io import BytesIO
from datetime import datetime
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from dotenv import load_dotenv

# Load environment variables from .env if exists
load_dotenv()

# ======================= CONFIGURATION =======================

OHM_USERNAME = os.getenv("OHM_USERNAME", "your_username_here")
OHM_PASSWORD = os.getenv("OHM_PASSWORD", "your_password_here")

# Adjust during debugging if needed
# LANGUAGES_TO_TEST = ["ja", "es"]

LANGUAGES_TO_TEST = [
    # 🥇 Level 1 – Global must-have languages
    "en", "es",
    # "zh-CN", "zh-TW", "zh-hk",
    # "hi", "ar", "pt", "pt-BR", "pt-PT",
    # "fr", "de", "ru", "ja"

    # 🥈 Level 2 – High regional/population relevance
    # "it", "ko", "tr", "vi", "fa",
    # "pl", "uk", "id", "ms", "bn",
    # "ta", "te", "th",

    # 🥉 Level 3 – Medium-size European (EU, Nordic, Balkan)
    # "nl", "sv", "da", "fi", "nb", "nn",
    # "cs", "sk", "ro", "el", "hu",
    # "sr", "sr-Latn", "hr", "sl",
    # "bg", "lt", "lv", "et",

    # 🟡 Level 4 – Co-official languages and active communities
    # "ca", "eu", "gl", "cy", "ga",
    # "br", "oc", "ast", "scn", "fy", "gd",

    # ⚪ Level 5 – Local variants, dialects, minority languages
    # "arz", "az", "ba", "be", "be-Tarask",
    # "bs", "ce", "diq", "dsb", "gcf",
    # "gsw", "hsb", "ia", "is", "ka",
    # "kab", "kk-cyrl", "km", "kn", "ku-Latn",
    # "lb", "mk", "mo", "mr", "my",
    # "nds", "ne", "nqo", "pa", "pnb",
    # "ps", "sat", "sc", "sco", "sh",
    # "skr-arab", "sq", "tl", "tt", "xmf",
    # "yi", "yo",

    # ⚙️ Level 6 – Special / technical (not real user-facing languages)
    # "en-GB", "fit", "fur", "qqq", "README", "zh-TW.yml"
]

URLS_TO_CHECK = [
    "/",
    "/issues?status=open",
    "/issues?status=ignored",
    "/issues?status=resolved",
    "/history",
    "/history/friends",
    "/export",
    "/traces",
    "/diary",
    f"/user/{OHM_USERNAME}/diary",
    "/diary/new",
    "/copyright",
    "/help",
    "/about",
    "/welcome",
    "/directions",
    #Dashboard
    "/dashboard",
    "/messages/inbox",
    "/messages/outbox",
    # Profile
    f"/user/{OHM_USERNAME}",
    "/profile/description",
    "/profile/links",
    "/profile/image",
    "/profile/company",
    "/profile/location",
    # Account
    "/account",
    "/oauth2/applications",
    "/oauth2/authorized_applications",
    # Preferences
    "/preferences/basic",
    "/preferences/advanced",
    # Data
    "/changeset/118684",
    "/relation/2806419",
    "/way/200177764",
    "/node/2117127935",
    # Editing
    "/edit?editor=id#map=18/37.772776/-122.417049"
]


# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
if ENVIRONMENT.lower() == "staging":
    BASE_URL = "https://staging.openhistoricalmap.org"
    ERROR_LOG_FILE = "logs/error_log_staging.txt"
else:
    BASE_URL = "https://www.openhistoricalmap.org"
    ERROR_LOG_FILE = "logs/error_log_production.txt"

print(f"🚀 Running tests on: {ENVIRONMENT.upper()}")
print(f"🌐 Base URL: {BASE_URL}")

# ======================= UTILITIES =======================

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def capture_frame(driver, frames_list):
    """
    Capture a screenshot frame from Selenium driver and append to frames_list as a PIL Image.
    """
    try:
        png = driver.get_screenshot_as_png()
        img = Image.open(BytesIO(png)).convert("RGB")
        frames_list.append(img)
    except Exception:
        pass

def save_gif(frames_list, out_path, fps=2):
    """
    Save a list of PIL Images as an animated GIF.
    fps: frames per second (approx). GIF uses duration ms per frame.
    """
    if not frames_list:
        return
    duration_ms = int(1000 / max(1, fps))
    try:
        frames_list[0].save(
            out_path,
            save_all=True,
            append_images=frames_list[1:],
            duration=duration_ms,
            loop=0,
            optimize=False,
            disposal=2,
        )
        print(f"🎥 Saved recording: {out_path}")
    except Exception as e:
        print(f"⚠️ Failed to write GIF '{out_path}': {e}")

# =============================================================

def get_driver():
    """Connect to the Selenium container with retries."""
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")

    endpoint = "http://chrome:4444/wd/hub"
    last_err = None
    for attempt in range(1, 13):  # ~1 minute
        try:
            print(f"🕐 Connecting to Selenium ({endpoint}) attempt {attempt}/12 ...")
            driver = webdriver.Remote(command_executor=endpoint, options=options)
            print("✅ Connected to Selenium.")
            return driver
        except Exception as e:
            last_err = e
            time.sleep(5)

    raise RuntimeError(f"Could not connect to Selenium at {endpoint}: {last_err}")

def login(driver, wait):
    """Perform login using form with id='login_form'."""
    driver.get(f"{BASE_URL}/login")

    # Wait for the form
    login_form = wait.until(EC.presence_of_element_located((By.ID, "login_form")))

    # Fill username/password
    username_field = login_form.find_element(By.ID, "username")
    username_field.clear()
    username_field.send_keys(OHM_USERNAME)

    password_field = login_form.find_element(By.ID, "password")
    password_field.clear()
    password_field.send_keys(OHM_PASSWORD)

    # Click commit button or submit form
    try:
        submit_btn = login_form.find_element(By.CSS_SELECTOR, "input[name='commit']")
        submit_btn.click()
    except Exception:
        password_field.submit()

    # Wait to leave /login or user link to appear
    try:
        wait.until(lambda d: "/login" not in d.current_url)
    except Exception:
        pass

    try:
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, f"//a[contains(@href, '/user/{OHM_USERNAME}')]")
            )
        )
        print(f"✅ Session started as '{OHM_USERNAME}'.")
    except Exception:
        print("⚠️ Could not visually confirm login, but continuing...")

def force_language_via_cookie_and_url(driver, lang_code):
    """
    Force language change using multiple methods:
    1. Set locale cookie
    2. Use URL parameter
    3. Refresh to apply changes
    """
    print(f"🔧 Forcing language '{lang_code}' via cookie and URL...")

    # Method 1: Set locale cookie
    try:
        driver.add_cookie({"name": "locale", "value": lang_code})
        print(f"✅ Set locale cookie to '{lang_code}'")
    except Exception as e:
        print(f"⚠️ Failed to set locale cookie: {e}")

    # Method 2: Navigate with locale parameter
    try:
        driver.get(f"{BASE_URL}/?locale={lang_code}")
        time.sleep(2)
        print(f"✅ Navigated with locale parameter '{lang_code}'")
    except Exception as e:
        print(f"⚠️ Failed to navigate with locale parameter: {e}")



def change_language_preferences(driver, wait, lang_code):
    """
    Attempt to change language through preferences page with multiple fallback methods.
    """
    preferences_url = f"{BASE_URL}/preferences/advanced"

    try:
        print(f"🔧 Attempting to change language to '{lang_code}' via preferences...")

        # Go to preferences page
        driver.get(preferences_url)
        wait.until(EC.presence_of_element_located((By.ID, "user_languages")))
        time.sleep(1)

        # Method 1: Try as Select dropdown
        try:
            lang_select = Select(driver.find_element(By.ID, "user_languages"))

            # Clear previous selections if multi-select
            try:
                lang_select.deselect_all()
                print("🔧 Cleared previous language selections")
            except Exception:
                pass  # Not a multi-select or already empty

            # Select the new language
            lang_select.select_by_value(lang_code)
            print(f"🔧 Selected language '{lang_code}' via dropdown")

        except Exception as e:
            print(f"🔧 Dropdown method failed: {e}")

            # Method 2: Fallback to text input
            try:
                print(f"🔧 Fallback: treating as text input for '{lang_code}'")
                lang_input = driver.find_element(By.ID, "user_languages")
                lang_input.clear()
                lang_input.send_keys(lang_code)
                print(f"🔧 Set text input to '{lang_code}'")
            except Exception as e2:
                print(f"🔧 Text input method also failed: {e2}")
                raise e2

        # Submit the form
        commit_btn = driver.find_element(By.CSS_SELECTOR, "input[name='commit']")
        commit_btn.click()
        print("🔧 Submitted preferences form")

        # Wait for form submission to complete
        try:
            # Wait for flash message or page reload
            wait.until(EC.any_of(
                EC.presence_of_element_located((By.CLASS_NAME, "flash")),
                EC.presence_of_element_located((By.CLASS_NAME, "flash-notice")),
                EC.presence_of_element_located((By.CLASS_NAME, "notice"))
            ))
            print("✅ Form submission confirmed (flash message detected)")
        except Exception:
            # If no flash message, wait for page to be ready
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            print("✅ Form submission completed (page ready)")

        # Additional wait for server-side processing
        time.sleep(3)

        # Verify what was actually saved
        try:
            driver.get(preferences_url)
            wait.until(EC.presence_of_element_located((By.ID, "user_languages")))

            # Check what's currently selected
            try:
                lang_element = driver.find_element(By.ID, "user_languages")
                current_value = lang_element.get_attribute("value")
                print(f"🔍 Current language preference value: '{current_value}'")

                # For select elements, check selected options
                try:
                    select_element = Select(lang_element)
                    selected_options = [opt.get_attribute("value") for opt in select_element.all_selected_options]
                    print(f"🔍 Selected options: {selected_options}")
                except Exception:
                    pass

            except Exception as e:
                print(f"⚠️ Could not verify saved preferences: {e}")
        except Exception as e:
            print(f"⚠️ Could not return to preferences page for verification: {e}")

        return True

    except Exception as e:
        print(f"❌ Failed to change language preferences: {e}")
        return False

def test_urls_with_language(driver, http_session, lang_code, frames):
    """
    Test all URLs with the specified language, focusing on HTTP status codes.
    """
    print(f"🔍 Testing URLs with language '{lang_code}'...")

    for url_path in URLS_TO_CHECK:
        # Properly handle URLs that already have query parameters
        if '?' in url_path:
            # URL already has query parameters, use & to add locale
            full_url_with_param = f"{BASE_URL}{url_path}&locale={lang_code}"
        else:
            # URL has no query parameters, use ? to add locale
            full_url_with_param = f"{BASE_URL}{url_path}?locale={lang_code}"

        try:
            print(f"🌐 Testing: {full_url_with_param}")

            # Navigate via browser (for recording)
            driver.get(full_url_with_param)
            wait = WebDriverWait(driver, 10)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            time.sleep(1)  # Allow content to render
            capture_frame(driver, frames)

            # Test via HTTP session for status codes
            try:
                response = http_session.get(full_url_with_param, timeout=10)
                if response.status_code >= 400:
                    error_message = f"❌ ERROR | Lang: {lang_code} | URL: {full_url_with_param} | Status: {response.status_code}"
                    print(error_message)
                    with open(ERROR_LOG_FILE, "a") as f:
                        f.write(error_message + "\n")
                else:
                    print(f"✅ OK | Lang: {lang_code} | URL: {full_url_with_param} | Status: {response.status_code}")
            except requests.exceptions.RequestException as e:
                msg = f"🔥 CONNECTION FAIL | Lang: {lang_code} | URL: {full_url_with_param} | Error: {e}"
                print(msg)
                with open(ERROR_LOG_FILE, "a") as f:
                    f.write(msg + "\n")

        except Exception as e:
            msg = f"💥 Browser navigation failed | Lang: {lang_code} | URL: {full_url_with_param} | Error: {e}"
            print(msg)
            with open(ERROR_LOG_FILE, "a") as f:
                f.write(msg + "\n")

        time.sleep(0.5)  # Brief pause between requests
        
def verify_site_languages():
    """
    Enhanced language verification with multiple fallback methods and better error handling.
    """
    print("🔧 Setting up Chrome driver...")
    driver = get_driver()
    wait = WebDriverWait(driver, 20)

    http_session = requests.Session()

    ensure_dir(os.path.dirname(ERROR_LOG_FILE))
    ensure_dir("logs/screens")
    ensure_dir("logs/recordings")

    with open(ERROR_LOG_FILE, "w") as f:
        f.write(f"Language verification test started - {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"Environment: {ENVIRONMENT.upper()}\n")
        f.write(f"Base URL: {BASE_URL}\n")
        f.write(f"User: {OHM_USERNAME}\n")
        f.write("=" * 50 + "\n")

    try:
        # Login
        print("🔐 Accessing login page...")
        login(driver, wait)

        # Transfer cookies to requests session
        print("🍪 Transferring session cookies...")
        for cookie in driver.get_cookies():
            http_session.cookies.set(cookie["name"], cookie["value"])
        print("✅ Cookies transferred successfully.")

        # Test each language with multiple methods
        for lang_code in LANGUAGES_TO_TEST:
            print(f"\n🌍 ===== TESTING LANGUAGE: '{lang_code}' =====")
            frames = []
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_gif = f"logs/recordings/lang_{lang_code}_{ts}.gif"

            try:
                # Method 1: Try changing via preferences (traditional method)
                print(f"📝 Method 1: Changing language via preferences...")
                preferences_success = change_language_preferences(driver, wait, lang_code)

                if preferences_success:
                    # Test if preferences method worked
                    driver.get(BASE_URL)
                    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                    time.sleep(2)
                    capture_frame(driver, frames)
                    print(f"✅ Preferences method completed for '{lang_code}'")

                # Method 2: Force via cookie and URL parameter (fallback)
                if not preferences_success:
                    print(f"🔧 Method 2: Forcing language via cookie and URL parameter...")
                    force_language_via_cookie_and_url(driver, lang_code)
                    capture_frame(driver, frames)

                    # Update session cookies
                    for cookie in driver.get_cookies():
                        http_session.cookies.set(cookie["name"], cookie["value"])

                # Test all URLs with current language setup
                test_urls_with_language(driver, http_session, lang_code, frames)

                print(f"✅ Completed testing for language '{lang_code}'")

            except Exception as e:
                # Enhanced error handling with diagnostics
                ts_err = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot = f"logs/screens/error_{ENVIRONMENT}_{lang_code}_{ts_err}.png"
                html = f"logs/screens/error_{ENVIRONMENT}_{lang_code}_{ts_err}.html"

                # Save diagnostic information
                try:
                    driver.save_screenshot(shot)
                    print(f"📸 Error screenshot saved: {shot}")
                except Exception:
                    pass

                try:
                    with open(html, "w", encoding="utf-8") as fh:
                        fh.write(driver.page_source)
                    print(f"📄 Error HTML saved: {html}")
                except Exception:
                    pass

                # Get current state information
                current_url = ""
                try:
                    current_url = driver.current_url
                except Exception:
                    pass

                # Log detailed error information
                msg = f"💥 Error testing language '{lang_code}': {e}\n"
                msg += f"   Current URL: {current_url}\n"
                msg += f"   Screenshot: {shot}\n"
                msg += f"   HTML dump: {html}\n"
                print(msg)

                with open(ERROR_LOG_FILE, "a") as f:
                    f.write(msg + "\n")

            finally:
                # Always save recording, even if errors occurred
                try:
                    save_gif(frames, out_gif, fps=2)
                except Exception as e:
                    print(f"⚠️ Failed to save recording for {lang_code}: {e}")

    except Exception as e:
        msg = f"\n💥 Critical error during language verification: {e}"
        print(msg)
        with open(ERROR_LOG_FILE, "a") as f:
            f.write(msg + "\n")

    finally:
        print(f"\n🏁 Language verification completed on {ENVIRONMENT.upper()}. Closing browser...")
        try:
            driver.quit()
        except Exception:
            pass

        # Show final summary
        print(f"\n📊 ===== FINAL SUMMARY =====")
        if os.path.exists(ERROR_LOG_FILE):
            with open(ERROR_LOG_FILE, "r") as f:
                log_content = f.read()
                error_count = log_content.count("ERROR")
                fail_count = log_content.count("FAIL")

                if error_count > 0 or fail_count > 0:
                    print(f"⚠️  Found {error_count} errors and {fail_count} failures")
                    print(f"📋 Check detailed log: {ERROR_LOG_FILE}")
                else:
                    print("🎉 All language tests completed without critical errors!")

        print(f"📁 Recordings saved in: logs/recordings/")
        print(f"📸 Screenshots saved in: logs/screens/")

if __name__ == "__main__":
    verify_site_languages()
