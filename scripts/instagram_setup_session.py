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
import sys
import traceback

# cmd.exe 기본 코드페이지(cp949 등)에서 이모지·화살표 출력 시 UnicodeEncodeError로
# 스크립트가 조용히 죽고 브라우저만 자동으로 닫히는 문제 방지(2026-07-29 실사고).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright  # noqa: E402
from playwright_stealth import Stealth  # noqa: E402

SESSION_PATH = os.path.join(os.path.dirname(__file__), "instagram_session.json")


def setup():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        ctx = browser.new_context(no_viewport=True)
        # 2026-07-29 실사고: 스텔스 없이 로그인 시도 시 Meta가 자동화 브라우저로 감지해
        # /auth_platform/recaptcha/로 튕겼다(navigator.webdriver 등 자동화 흔적 때문).
        # navigator.webdriver·plugins·languages 등을 정상 브라우저처럼 위장해 재시도.
        Stealth().apply_stealth_sync(ctx)
        page = ctx.new_page()
        page.goto("https://www.instagram.com/accounts/login/")

        print("=" * 50)
        print("브라우저가 열렸습니다.")
        print("인스타 계정으로 로그인 후(2단계 인증 포함) Enter를 누르세요.")
        print("=" * 50)
        input("로그인 완료 후 Enter > ")

        page.goto("https://www.instagram.com/")
        page.wait_for_timeout(3000)
        # URL만으로는 로그인 여부를 못 가른다 — 비로그인 상태에서도 /accounts/login/으로
        # 안 튕기고 그냥 홈에 머무는 경우가 실측됨(2026-07-29, anon 쿠키 7개만 저장돼
        # 세션이 무효였던 실사고). 실제 인증 쿠키(sessionid) 존재로 판정한다.
        cookie_names = {c["name"] for c in ctx.cookies()}
        if "sessionid" not in cookie_names:
            print(f"[!] 로그인이 안 된 상태입니다(sessionid 쿠키 없음, URL: {page.url}) "
                  "- 세션을 저장하지 않습니다. 다시 실행해 로그인을 마친 뒤 Enter를 누르세요.")
            browser.close()
            return

        ctx.storage_state(path=SESSION_PATH)
        print(f"[OK] 세션 저장 완료: {SESSION_PATH}")
        print("다음: 이 파일을 서버로 옮기고 INSTAGRAM_SESSION_PATH 환경변수로 지정하세요.")
        browser.close()


if __name__ == "__main__":
    try:
        setup()
    except Exception:
        # 브라우저가 말없이 닫히는 것처럼 보이는 문제 방지 - 원인을 화면에 그대로 남긴다.
        traceback.print_exc()
        input("\n에러 발생. 위 내용을 확인하고 Enter로 종료 > ")
