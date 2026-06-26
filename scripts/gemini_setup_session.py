"""
Step 1: 최초 1회 실행 — Google 로그인 후 세션 저장
이후에는 gemini_briefing_playwright.py만 실행하면 됩니다.
"""
from playwright.sync_api import sync_playwright
import os

SESSION_PATH = os.path.join(os.path.dirname(__file__), "gemini_session")

def setup():
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_PATH,
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = browser.new_page()
        page.goto("https://accounts.google.com")

        print("=" * 50)
        print("브라우저가 열렸습니다.")
        print("Google 계정으로 로그인 후 Enter를 누르세요.")
        print("=" * 50)
        input("로그인 완료 후 Enter ▶ ")

        # 로그인 확인
        page.goto("https://gemini.google.com")
        page.wait_for_load_state("networkidle", timeout=15000)
        print(f"현재 URL: {page.url}")
        print("✅ 세션 저장 완료:", SESSION_PATH)

        browser.close()

if __name__ == "__main__":
    setup()
