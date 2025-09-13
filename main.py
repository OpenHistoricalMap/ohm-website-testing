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
    "en", "es", "zh-CN", "zh-TW", "zh-hk",
    "hi", "ar", "pt", "pt-BR", "pt-PT",
    "fr", "de", "ru", "ja"

    # # 🥈 Level 2 – High regional/population relevance
    # "it", "ko", "tr", "vi", "fa",
    # "pl", "uk", "id", "ms", "bn",
    # "ta", "te", "th",

    # # 🥉 Level 3 – Medium-size European (EU, Nordic, Balkan)
    # "nl", "sv", "da", "fi", "nb", "nn",
    # "cs", "sk", "ro", "el", "hu",
    # "sr", "sr-Latn", "hr", "sl",
    # "bg", "lt", "lv", "et",

    # # 🟡 Level 4 – Co-official languages and active communities
    # "ca", "eu", "gl", "cy", "ga",
    # "br", "oc", "ast", "scn", "fy", "gd",

    # # ⚪ Level 5 – Local variants, dialects, minority languages
    # "arz", "az", "ba", "be", "be-Tarask",
    # "bs", "ce", "diq", "dsb", "gcf",
    # "gsw", "hsb", "ia", "is", "ka",
    # "kab", "kk-cyrl", "km", "kn", "ku-Latn",
    # "lb", "mk", "mo", "mr", "my",
    # "nds", "ne", "nqo", "pa", "pnb",
    # "ps", "sat", "sc", "sco", "sh",
    # "skr-arab", "sq", "tl", "tt", "xmf",
    # "yi", "yo",

    # # ⚙️ Level 6 – Special / technical (not real user-facing languages)
    # "en-GB", "fit", "fur", "qqq", "README", "zh-TW.yml"
]

URLS_TO_CHECK = [
    "/",
    "/about",
    "/history",
    "/export",
    "/traces",
    "/copyright",
    "/help",
    f"/user/{OHM_USERNAME}",
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

def verify_language_change(driver, lang_code, http_session):
    """
    Verify the language change by:
    1) Checking <html lang="..."> via Selenium
    2) Falling back to the Content-Language response header via requests
    3) As a tertiary fallback, searching for language-specific text on the homepage
    """
    try:
        # Go to homepage to verify language in a neutral page
        driver.get(BASE_URL)
        # Let the page fully render
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(1.0)

        # 1) Check <html lang="...">
        try:
            html_lang = driver.execute_script(
                "return document.documentElement.getAttribute('lang') || "
                "document.documentElement.getAttribute('xml:lang') || ''"
            )
            html_lang = (html_lang or "").strip().lower()
        except Exception:
            html_lang = ""

        if html_lang:
            print(f"🔎 Detected <html lang> = '{html_lang}' (target: '{lang_code}')")
            # Allow region variants like 'es-ES'
            if html_lang == lang_code.lower() or html_lang.startswith(lang_code.lower() + "-"):
                return True

        # 2) Check Content-Language header from a fresh request
        try:
            r = http_session.get(BASE_URL, timeout=10)
            content_lang = r.headers.get("Content-Language", "").strip().lower()
            if content_lang:
                print(f"🔎 Detected Content-Language header = '{content_lang}' (target: '{lang_code}')")
                if content_lang == lang_code.lower() or content_lang.startswith(lang_code.lower() + "-"):
                    return True
        except Exception:
            pass

        # 3) Tertiary text indicators (loose)
        language_indicators = {
            "en": ["About", "History", "Export", "Help"],
            "es": ["Acerca de", "Historia", "Exportar", "Ayuda"],
            "fr": ["À propos", "Histoire", "Exporter", "Aide"],
            "de": ["Über", "Geschichte", "Exportieren", "Hilfe"],
            "it": ["Informazioni", "Storia", "Esporta", "Aiuto"],
            "pt": ["Sobre", "História", "Exportar", "Ajuda"],
            "ru": ["О проекте", "История", "Экспорт", "Справка"],
            "ja": ["について", "歴史", "エクスポート", "ヘルプ"],
        }

        if lang_code in language_indicators:
            found = 0
            page_lower = driver.page_source.lower()
            for txt in language_indicators[lang_code]:
                if txt.lower() in page_lower:
                    found += 1
            print(f"🔎 Text indicators found for '{lang_code}': {found}")
            return found > 0

        print(f"⚠️ Unable to verify language '{lang_code}' via <html lang>, headers, or text indicators.")
        return False

    except Exception as e:
        print(f"❌ Language verification failed for '{lang_code}': {e}")
        return False

def verify_site_languages():
    """
    Automate login, language switching, per-language recording, verification of the applied language, and URL checks.
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

        # Iterate through languages
        preferences_url = f"{BASE_URL}/preferences/advanced"

        for lang_code in LANGUAGES_TO_TEST:
            print(f"\n🌍 --- Changing language to: '{lang_code}' ---")
            frames = []
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_gif = f"logs/recordings/lang_{lang_code}_{ts}.gif"

            try:
                # Go to preferences
                driver.get(preferences_url)
                wait.until(EC.presence_of_element_located((By.ID, "user_languages")))
                capture_frame(driver, frames)

                # 🔧 FIXED: Change language using proper Select handling
                try:
                    # Try as a <select> dropdown first
                    lang_select = Select(driver.find_element(By.ID, "user_languages"))
                    
                    # Clear previous selections (if multi-select)
                    try:
                        lang_select.deselect_all()
                    except Exception:
                        pass  # Not a multi-select, that's fine
                    
                    # Select the new language
                    lang_select.select_by_value(lang_code)
                    print(f"🔧 Selected language '{lang_code}' via dropdown")
                    
                except Exception:
                    # Fallback: treat as text input (original method)
                    print(f"🔧 Fallback: treating as text input for '{lang_code}'")
                    lang_input = driver.find_element(By.ID, "user_languages")
                    lang_input.clear()
                    lang_input.send_keys(lang_code)

                capture_frame(driver, frames)  # after language selection

                # Submit the form
                commit_btn = driver.find_element(By.CSS_SELECTOR, "input[name='commit']")
                commit_btn.click()

                # 🔄 Esperar a que realmente se apliquen los cambios
                try:
                    # Esperar un mensaje flash
                    wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "flash-notice")))
                except Exception:
                    # Si no hay flash, esperar a que la página recargue
                    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

                # 🔄 Pausa adicional para que el servidor guarde la preferencia
                time.sleep(2)
                # Navigate to homepage to reflect new language
                print(f"✅ Language updated to '{lang_code}'. Verifying change...")
                driver.get(BASE_URL)
                wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                time.sleep(3)
                capture_frame(driver, frames)

                # Verify language change actually worked
                language_verified = verify_language_change(driver, lang_code, http_session)
                if not language_verified:
                    error_msg = f"⚠️ Language change verification failed for '{lang_code}'"
                    print(error_msg)
                    with open(ERROR_LOG_FILE, "a") as f:
                        f.write(error_msg + "\n")

                # Test URLs with the new language (also capture screens)
                print(f"🔍 Testing URLs with language '{lang_code}'...")
                for url_path in URLS_TO_CHECK:
                    full_url = BASE_URL + url_path
                    try:
                        # Navigate via browser (for recording)
                        driver.get(full_url)
                        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
                        capture_frame(driver, frames)

                        # Verify status via requests session
                        response = http_session.get(full_url, timeout=10)
                        if response.status_code >= 400:
                            error_message = f"❌ ERROR | Lang: {lang_code} | URL: {full_url} | Status: {response.status_code}"
                            print(error_message)
                            with open(ERROR_LOG_FILE, "a") as f:
                                f.write(error_message + "\n")
                        else:
                            print(f"✅ OK    | Lang: {lang_code} | URL: {full_url} | Status: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        msg = f"🔥 CONNECTION FAIL | Lang: {lang_code} | URL: {full_url} | Error: {e}"
                        print(msg)
                        with open(ERROR_LOG_FILE, "a") as f:
                            f.write(msg + "\n")
                    time.sleep(0.2)

            except Exception as e:
                # Detailed diagnostics: save screenshot and HTML
                ts_err = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot = f"logs/screens/error_{ENVIRONMENT}_{lang_code}_{ts_err}.png"
                html = f"logs/screens/error_{ENVIRONMENT}_{lang_code}_{ts_err}.html"
                try:
                    driver.save_screenshot(shot)
                except Exception:
                    pass
                try:
                    with open(html, "w", encoding="utf-8") as fh:
                        fh.write(driver.page_source)
                except Exception:
                    pass
                current_url = ""
                try:
                    current_url = driver.current_url
                except Exception:
                    pass
                msg = f"💥 Error changing language to '{lang_code}': {e} | Current URL: {current_url} | Screenshot: {shot}"
                print(msg)
                with open(ERROR_LOG_FILE, "a") as f:
                    f.write(msg + "\n")
            finally:
                # Save per-language GIF recording even if errors occurred
                try:
                    save_gif(frames, out_gif, fps=2)
                except Exception:
                    pass

    except Exception as e:
        msg = f"\n💥 Critical error: {e}"
        print(msg)
        with open(ERROR_LOG_FILE, "a") as f:
            f.write(msg + "\n")

    finally:
        print(f"\n🏁 Test completed on {ENVIRONMENT.upper()}. Closing browser...")
        driver.quit()

        # Show summary
        if os.path.exists(ERROR_LOG_FILE):
            with open(ERROR_LOG_FILE, "r") as f:
                log_content = f.read()
                if "ERROR" in log_content or "FAIL" in log_content:
                    print(f"⚠️  Errors found, check: {ERROR_LOG_FILE}")
                else:
                    print("🎉 All tests passed without errors!")

if __name__ == "__main__":
    verify_site_languages()