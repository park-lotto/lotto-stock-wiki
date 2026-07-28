"""인스타 세션 쿠키를 '진짜' 데일리 브라우저에서 그대로 가져오기 (Playwright 로그인 자동화 없이).

배경(2026-07-29): Playwright로 로그인 페이지를 열고 사람이 직접 타이핑해도, Meta가
CDP(크롬 원격제어)로 붙어있다는 사실 자체를 감지해 로그인 제출 시점에 캡차를 띄웠다
(스텔스 패치·--disable-blink-features=AutomationControlled로도 못 뚫음).

완전히 다른 접근: 로그인 자체를 Playwright 밖에서, 평소 쓰는 진짜 브라우저(Chrome/Edge/
Firefox)로 정상적으로 하고, 그 브라우저의 로컬 쿠키 저장소를 직접 읽어 Playwright
storage_state 포맷으로 변환한다. 로그인 시점에 자동화 흔적이 전혀 없으므로 캡차 벽 자체를
만날 일이 없다.

⚠️ Chrome·Edge는 최신 버전의 "앱 바운드 암호화"(정보탈취 악성코드 방지용) 때문에 관리자
권한 없이는 쿠키를 못 읽는다(2026-07-29 실측: RequiresAdminError). 관리자 권한으로 다시
실행해도 안 되면(Chrome 버전에 따라 그럴 수 있음) Firefox를 쓸 것 — 이 제약이 없다.

사용법:
    1. 아래 셋 중 하나로 부계정 인스타에 정상 로그인(그 브라우저는 완전히 종료하지 않아도
       보통 되지만, 쿠키 DB 잠금으로 실패하면 브라우저를 잠깐 껐다가 재시도):
       - Firefox (권장 — 관리자 권한 불필요)
       - Chrome/Edge (관리자 권한으로 이 스크립트를 실행해야 할 수 있음)
    2. python scripts/instagram_cookies_from_browser.py --browser firefox
       (또는 --browser chrome / --browser edge)
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import browser_cookie3  # noqa: E402

SESSION_PATH = os.path.join(os.path.dirname(__file__), "instagram_session.json")

_LOADERS = {
    "chrome": browser_cookie3.chrome,
    "edge": browser_cookie3.edge,
    "firefox": browser_cookie3.firefox,
}


def _to_playwright_cookie(c):
    return {
        "name": c.name,
        "value": c.value,
        "domain": c.domain,
        "path": c.path or "/",
        "expires": c.expires if c.expires else -1,
        "httpOnly": bool(getattr(c, "_rest", {}).get("HTTPOnly")),
        "secure": bool(c.secure),
        "sameSite": "Lax",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=sorted(_LOADERS), default="firefox")
    args = parser.parse_args()

    try:
        jar = _LOADERS[args.browser](domain_name="instagram.com")
        cookies = [_to_playwright_cookie(c) for c in jar]
    except Exception as e:
        print(f"[!] {args.browser} 쿠키를 못 읽었습니다: {e}")
        print("    - 관리자 권한이 필요하다고 나오면: 명령 프롬프트를 관리자 권한으로 다시 열어 재시도")
        print("    - 그래도 안 되면(Chrome 앱 바운드 암호화): Firefox로 로그인 후 --browser firefox")
        return

    names = {c["name"] for c in cookies}
    if "sessionid" not in names:
        print(f"[!] {args.browser}에 인스타 로그인 세션이 없습니다"
              f"(sessionid 없음, 쿠키 {len(cookies)}개: {sorted(names)}).")
        print(f"    {args.browser}에서 먼저 instagram.com에 정상 로그인한 뒤 다시 실행하세요.")
        return

    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump({"cookies": cookies, "origins": []}, f, ensure_ascii=False, indent=2)
    print(f"[OK] {args.browser}에서 세션 쿠키 {len(cookies)}개 저장 완료: {SESSION_PATH}")
    print("다음: 이 파일을 서버로 옮기고 INSTAGRAM_SESSION_PATH 환경변수로 지정하세요.")


if __name__ == "__main__":
    main()
