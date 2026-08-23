import os
from playwright.sync_api import sync_playwright

BASE = "https://mobile-dev-3451.preview.emergentagent.com"
EMAIL = "russngina@gmail.com"
PASSWORD = "1123581321$$"
OUT = "/app/frontend/appstore-screenshots/android-raw"
os.makedirs(OUT, exist_ok=True)

# Android phone: logical 360x640 * DSR 3 = 1080x1920 (9:16, Play-safe)
VP = {"width": 360, "height": 640}


def wait_root(page, contains=None, timeout=45000):
    page.wait_for_function("()=>{const r=document.querySelector('#root');return r&&r.innerText&&r.innerText.length>0}", timeout=timeout)
    if contains:
        page.wait_for_function("(t)=>{const r=document.querySelector('#root');return r&&r.innerText&&r.innerText.includes(t)}", arg=contains, timeout=timeout)


def shot(page, name):
    page.wait_for_timeout(2500)
    path = os.path.join(OUT, name)
    page.screenshot(path=path, full_page=False)
    from PIL import Image
    print("  saved", name, Image.open(path).size)


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox"])
    ctx = browser.new_context(viewport=VP, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto(BASE)
    wait_root(page, "GHOSTREELS ALPHA")
    shot(page, "01_welcome.png")
    page.get_by_test_id("email-input").fill(EMAIL)
    page.get_by_test_id("password-input").fill(PASSWORD)
    page.get_by_test_id("auth-submit").click()
    page.wait_for_timeout(6000)

    def go(path, contains, name):
        try:
            page.goto(BASE + path)
            wait_root(page, contains, timeout=30000)
            shot(page, name)
        except Exception as e:
            print("  FAIL", name, e)
            try: page.screenshot(path=os.path.join(OUT, name), full_page=False)
            except Exception: pass

    go("/", "GHOSTREELS ALPHA", "02_create.png")
    go("/paywall", "Go Pro", "03_paywall.png")
    go("/library", None, "04_library.png")
    go("/series", None, "05_series.png")
    go("/settings", "LEGAL", "06_settings.png")
    ctx.close(); browser.close()
print("DONE")
