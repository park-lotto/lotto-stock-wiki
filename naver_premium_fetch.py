from playwright.sync_api import sync_playwright

URL = "https://contents.premium.naver.com/smstockstudy/1028/contents/260531215905700ap"
CHROME_PROFILE = r"C:\Users\CH\AppData\Local\Google\Chrome\User Data"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=CHROME_PROFILE,
        channel="chrome",
        headless=False
    )
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_load_state("networkidle")

    content = page.inner_text("body")
    print(content[:3000])
    ctx.close()
