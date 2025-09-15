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

LANGUAGES_TO_TEST = [
    # Level 1 – Global must-have languages
    "en", "es",
    "zh-CN", "zh-TW", "zh-hk",
    "hi", "ar", "pt", "pt-BR", "pt-PT",
    "fr", "de", "ru", "ja"

    # Level 2 – High regional/population relevance
    "it", "ko", "tr", "vi", "fa",
    "pl", "uk", "id", "ms", "bn",
    "ta", "te", "th",

    # Level 3 – Medium-size European (EU, Nordic, Balkan)
    "nl", "sv", "da", "fi", "nb", "nn",
    "cs", "sk", "ro", "el", "hu",
    "sr", "sr-Latn", "hr", "sl",
    "bg", "lt", "lv", "et",

    # Level 4 – Co-official languages and active communities
    # "ca", "eu", "gl", "cy", "ga",
    # "br", "oc", "ast", "scn", "fy", "gd",

    # Level 5 – Local variants, dialects, minority languages
    # "arz", "az", "ba", "be", "be-Tarask",
    # "bs", "ce", "diq", "dsb", "gcf",
    # "gsw", "hsb", "ia", "is", "ka",
    # "kab", "kk-cyrl", "km", "kn", "ku-Latn",
    # "lb", "mk", "mo", "mr", "my",
    # "nds", "ne", "nqo", "pa", "pnb",
    # "ps", "sat", "sc", "sco", "sh",
    # "skr-arab", "sq", "tl", "tt", "xmf",
    # "yi", "yo",

    # Level 6 – Special / technical (not real user-facing languages)
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

print(f" Running tests on: {ENVIRONMENT.upper()}")
print(f" Base URL: {BASE_URL}")

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
        print(f" Failed to write GIF '{out_path}': {e}")

# =============================================================

def get_driver():
    """Connect to the Selenium container with retries and improved timeouts."""
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")

    endpoint = "http://chrome:4444/wd/hub"
    last_err = None
    for attempt in range(1, 6):  # Reduced attempts for faster failure
        try:
            print(f" Connecting to Selenium ({endpoint}) attempt {attempt}/5 ...")
            driver = webdriver.Remote(command_executor=endpoint, options=options)
            
            # Set timeouts to prevent hanging
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(20)
            driver.implicitly_wait(10)
            
            print(" Connected to Selenium with timeouts configured.")
            return driver
        except Exception as e:
            last_err = e
            time.sleep(3)  # Shorter wait between retries

    raise RuntimeError(f"Could not connect to Selenium at {endpoint}: {last_err}")

def login(driver, wait):
    """Perform login using form with id='login_form'."""
    try:
        driver.get(f"{BASE_URL}/login")

        # Wait for the form with shorter timeout
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

        # Wait to leave /login with shorter timeout
        try:
            WebDriverWait(driver, 10).until(lambda d: "/login" not in d.current_url)
        except Exception:
            pass

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, f"//a[contains(@href, '/user/{OHM_USERNAME}')]")
                )
            )
            print(f" Session started as '{OHM_USERNAME}'.")
            return True
        except Exception:
            print(" Could not visually confirm login, but continuing...")
            return False
    except Exception as e:
        print(f" Login failed: {e}")
        return False

def set_language_fast(driver, lang_code):
    """
    Fast language switching using cookie + URL method only.
    Avoids the slow preferences page that causes timeouts.
    """
    print(f"🔧 Setting language to '{lang_code}' via cookie + URL...")

    try:
        # Method 1: Set locale cookie
        driver.add_cookie({"name": "locale", "value": lang_code})
        print(f" Set locale cookie to '{lang_code}'")
    except Exception as e:
        print(f" Failed to set locale cookie: {e}")

    try:
        # Method 2: Navigate with locale parameter
        driver.get(f"{BASE_URL}/?locale={lang_code}")
        time.sleep(2)  # Brief wait for page load
        print(f" Navigated with locale parameter '{lang_code}'")
        return True
    except Exception as e:
        print(f" Failed to navigate with locale parameter: {e}")
        return False

def test_urls_with_language(driver, http_session, lang_code, frames):
    """
    Test all URLs with the specified language, focusing on HTTP status codes.
    """
    print(f" Testing URLs with language '{lang_code}'...")

    for url_path in URLS_TO_CHECK:
        # Properly handle URLs that already have query parameters
        if '?' in url_path:
            # URL already has query parameters, use & to add locale
            full_url_with_param = f"{BASE_URL}{url_path}&locale={lang_code}"
        else:
            # URL has no query parameters, use ? to add locale
            full_url_with_param = f"{BASE_URL}{url_path}?locale={lang_code}"

        try:
            print(f" Testing: {full_url_with_param}")

            # Navigate via browser (for recording) with timeout protection
            try:
                driver.get(full_url_with_param)
                wait = WebDriverWait(driver, 15)  # Shorter timeout
                wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                time.sleep(1)  # Allow content to render
                capture_frame(driver, frames)
            except Exception as nav_e:
                print(f" Browser navigation timeout for {full_url_with_param}: {nav_e}")
                capture_frame(driver, frames)  # Capture whatever we have

            # Test via HTTP session for status codes
            try:
                response = http_session.get(full_url_with_param, timeout=15)
                if response.status_code >= 400:
                    error_message = f" ERROR | Lang: {lang_code} | URL: {full_url_with_param} | Status: {response.status_code}"
                    print(error_message)
                    with open(ERROR_LOG_FILE, "a") as f:
                        f.write(error_message + "\n")
                else:
                    print(f" OK | Lang: {lang_code} | URL: {full_url_with_param} | Status: {response.status_code}")
            except requests.exceptions.RequestException as e:
                msg = f" CONNECTION FAIL | Lang: {lang_code} | URL: {full_url_with_param} | Error: {e}"
                print(msg)
                with open(ERROR_LOG_FILE, "a") as f:
                    f.write(msg + "\n")

        except Exception as e:
            msg = f" Browser navigation failed | Lang: {lang_code} | URL: {full_url_with_param} | Error: {e}"
            print(msg)
            with open(ERROR_LOG_FILE, "a") as f:
                f.write(msg + "\n")

        time.sleep(0.3)  # Brief pause between requests

def test_single_language(lang_code, http_session):
    """
    Test a single language with its own isolated driver session.
    This prevents one language from blocking others if it hangs.
    """
    print(f"\n ===== TESTING LANGUAGE: '{lang_code}' =====")
    
    driver = None
    frames = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_gif = f"logs/recordings/lang_{lang_code}_{ts}.gif"
    
    try:
        # Get fresh driver for this language
        driver = get_driver()
        wait = WebDriverWait(driver, 15)  # Shorter timeout
        
        # Login
        print("Logging in...")
        login_success = login(driver, wait)
        if not login_success:
            print(f" Login failed for language '{lang_code}', skipping...")
            return
        
        # Transfer cookies to requests session
        print("Transferring session cookies...")
        for cookie in driver.get_cookies():
            http_session.cookies.set(cookie["name"], cookie["value"])
        
        # Set language using fast method
        print(f"🔧 Setting language to '{lang_code}'...")
        lang_success = set_language_fast(driver, lang_code)
        if not lang_success:
            print(f" Language setting failed for '{lang_code}', but continuing...")
        
        # Capture initial frame
        capture_frame(driver, frames)
        
        # Update session cookies after language change
        for cookie in driver.get_cookies():
            http_session.cookies.set(cookie["name"], cookie["value"])
        
        # Test all URLs with current language setup
        test_urls_with_language(driver, http_session, lang_code, frames)
        
        print(f" Completed testing for language '{lang_code}'")
        
    except Exception as e:
        # Enhanced error handling with diagnostics
        ts_err = datetime.now().strftime("%Y%m%d_%H%M%S")
        shot = f"logs/screens/error_{ENVIRONMENT}_{lang_code}_{ts_err}.png"
        html = f"logs/screens/error_{ENVIRONMENT}_{lang_code}_{ts_err}.html"
        
        # Save diagnostic information
        if driver:
            try:
                driver.save_screenshot(shot)
                print(f" Error screenshot saved: {shot}")
            except Exception:
                pass
            
            try:
                with open(html, "w", encoding="utf-8") as fh:
                    fh.write(driver.page_source)
                print(f" Error HTML saved: {html}")
            except Exception:
                pass
            
            # Get current state information
            current_url = ""
            try:
                current_url = driver.current_url
            except Exception:
                pass
        
        # Log detailed error information
        msg = f"Error testing language '{lang_code}': {e}\n"
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
            print(f" Failed to save recording for {lang_code}: {e}")
        
        # Always close driver for this language
        if driver:
            try:
                driver.quit()
                print(f" Closed driver for language '{lang_code}'")
            except Exception:
                pass

def verify_site_languages():
    """
    Enhanced language verification with isolated sessions per language.
    Each language gets its own fresh driver to prevent hanging issues.
    """
    print(" Starting language verification with isolated sessions...")
    
    # Create shared HTTP session for status code testing
    http_session = requests.Session()
    
    # Setup directories
    ensure_dir(os.path.dirname(ERROR_LOG_FILE))
    ensure_dir("logs/screens")
    ensure_dir("logs/recordings")
    
    # Initialize log file
    with open(ERROR_LOG_FILE, "w") as f:
        f.write(f"Language verification test started - {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write(f"Environment: {ENVIRONMENT.upper()}\n")
        f.write(f"Base URL: {BASE_URL}\n")
        f.write(f"User: {OHM_USERNAME}\n")
        f.write(f"Languages to test: {', '.join(LANGUAGES_TO_TEST)}\n")
        f.write("=" * 50 + "\n")
    
    try:
        # Test each language with its own isolated session
        for i, lang_code in enumerate(LANGUAGES_TO_TEST, 1):
            print(f"\n Progress: {i}/{len(LANGUAGES_TO_TEST)} languages")
            test_single_language(lang_code, http_session)
            
            # Brief pause between languages to let system recover
            if i < len(LANGUAGES_TO_TEST):
                print(" Brief pause before next language...")
                time.sleep(2)
    
    except KeyboardInterrupt:
        print("\n Test interrupted by user")
    except Exception as e:
        msg = f"\n Critical error during language verification: {e}"
        print(msg)
        with open(ERROR_LOG_FILE, "a") as f:
            f.write(msg + "\n")
    
    finally:
        # Show final summary
        print(f"\nLanguage verification completed on {ENVIRONMENT.upper()}.")
        print(f"\n===== FINAL SUMMARY =====")
        
        if os.path.exists(ERROR_LOG_FILE):
            with open(ERROR_LOG_FILE, "r") as f:
                log_content = f.read()
                error_count = log_content.count("ERROR")
                fail_count = log_content.count("FAIL")
                
                if error_count > 0 or fail_count > 0:
                    print(f"Found {error_count} errors and {fail_count} failures")
                    print(f"Check detailed log: {ERROR_LOG_FILE}")
                else:
                    print(" All language tests completed without critical errors!")
        
        print(f" Recordings saved in: logs/recordings/")
        print(f" Screenshots saved in: logs/screens/")

if __name__ == "__main__":
    verify_site_languages()
