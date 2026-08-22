import os
from playwright.sync_api import sync_playwright

BASE = "https://mobile-dev-3451.preview.emergentagent.com"
OUT = "/app/frontend/appstore-screenshots/ipad-raw"
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1024, "height": 1366}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto(BASE)
    page.wait_for_function("()=>{const r=document.querySelector('#root');return r&&r.innerText.includes('GHOSTREELS ALPHA')}", timeout=45000)
    page.get_by_test_id("email-input").fill("russngina@gmail.com")
    page.get_by_test_id("password-input").fill("1123581321$$")
    page.get_by_test_id("auth-submit").click()
    page.wait_for_timeout(6000)
    page.goto(BASE + "/paywall")
    page.wait_for_function("()=>{const r=document.querySelector('#root');return r&&r.innerText.includes('Go Pro')}", timeout=30000)
    page.wait_for_timeout(4000)
    page.screenshot(path=os.path.join(OUT, "03_paywall.png"), full_page=False)
    from PIL import Image
    print("ipad paywall", Image.open(os.path.join(OUT, "03_paywall.png")).size)
    ctx.close(); b.close()
print("DONE")
