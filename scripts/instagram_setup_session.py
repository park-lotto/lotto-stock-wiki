"""인스타 로그인 세션 캡처 — 최초 1회(또는 세션 만료 시) 로컬에서 수동 실행.

샤오홍슈(rednote)에서 검증된 B안과 동일한 패턴: 서버 데이터센터 IP가 막히는 진짜 이유는
IP 품질이 아니라 로그인 여부였다. 실제 계정으로 수동 로그인 → storage_state(쿠키)를
파일로 저장 → 그 파일을 서버로 옮기면, 서버 헤드리스가 그 세션을 로드해 데이터센터 IP
직결로도 로그인 상태를 유지한 채 접근할 수 있다(이론상 — 이 스크립트로 만든 세션을
1채널 스파이크 테스트로 먼저 검증할 것).

사용법:
    python scripts/instagram_setup_session.py
    → 브라우저가 뜨면 인스타 계정으로 수동 로그인(비번+2단계인증 등 전부 직접) →
      터미널로 돌아와 Enter.

⚠️ 계정은 정지될 수 있다 — 재사용 가능한 부계정으로 로그인할 것(사장님 확인: 계정 여유 있음).
"""
import os

from playwright.sync_api import sync_playwright

SESSION_PATH = os.path.join(os.path.dirname(__file__), "instagram_session.json")


def setup():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        ctx = browser.new_context(no_viewport=True)
        page = ctx.new_page()
        page.goto("https://www.instagram.com/accounts/login/")

        print("=" * 50)
        print("브라우저가 열렸습니다.")
        print("인스타 계정으로 로그인 후(2단계 인증 포함) Enter를 누르세요.")
        print("=" * 50)
        input("로그인 완료 후 Enter ▶ ")

        page.goto("https://www.instagram.com/")
        page.wait_for_timeout(3000)
        current_url = page.url
        if "login" in current_url:
            print(f"⚠️ 아직 로그인 화면입니다(URL: {current_url}) — 세션을 저장하지 않습니다.")
            browser.close()
            return

        ctx.storage_state(path=SESSION_PATH)
        print(f"✅ 세션 저장 완료: {SESSION_PATH}")
        print("다음: 이 파일을 서버로 옮기고 INSTAGRAM_SESSION_PATH 환경변수로 지정하세요.")
        browser.close()


if __name__ == "__main__":
    setup()
