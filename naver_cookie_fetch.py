import browser_cookie3
from playwright.sync_api import sync_playwright

URL = "https://contents.premium.naver.com/smstockstudy/1028/contents/260531215905700ap"

# Chrome에서 naver.com 쿠키 추출
jar = browser_cookie3.chrome(domain_name=".naver.com")
cookies = []
for c in jar:
    cookies.append({
        "name": c.name,
        "value": c.value,
        "domain": c.domain if c.domain else ".naver.com",
        "path": c.path or "/",
    })

print(f"쿠키 {len(cookies)}개 추출 완료")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    ctx.add_cookies(cookies)

    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_load_state("networkidle")

    # 본문 추출
    body = page.inner_text("body")

    # 프리미엄 게이트 체크
    if "프리미엄 구독자 전용" in body:
        print("❌ 로그인 실패 또는 미구독 상태")
    else:
        print("✅ 본문 접근 성공!\n")
        print(body[:5000])

    browser.close()
