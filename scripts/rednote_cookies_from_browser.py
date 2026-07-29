"""샤오홍슈(rednote) 세션 쿠키를 '진짜' 데일리 브라우저에서 그대로 가져오기.

배경(2026-07-29): 서버 헤드리스 QR 재로그인이 불안정해(rednote가 web_session 게스트
쿠키도 발급해 로그인 감지 오탐) instagram 선례와 같은 방식으로 전환.
로그인 자체는 Playwright 밖에서 평소 쓰는 진짜 브라우저(Firefox 권장)로 정상 로그인하고,
그 브라우저의 쿠키 저장소를 직접 읽어 Playwright storage_state 포맷으로 변환한다.
자동화 흔적이 없어 캡차·감지 벽을 만나지 않는다.

⚠️ Chrome·Edge는 앱 바운드 암호화로 관리자 권한 없이 쿠키를 못 읽을 수 있다 →
   그럴 땐 Firefox를 쓸 것(이 제약 없음, 인스타에서 실증됨).

사용법:
    1. Firefox에서 https://www.rednote.com (또는 xiaohongshu.com)에 정상 로그인.
    2. py scripts/rednote_cookies_from_browser.py --browser firefox
    3. 생성된 scripts/rednote_session.json 을 서버 /home/ubuntu/rednote_session.json 로 복사.
       (담당자가 scp로 옮겨줌)
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import browser_cookie3  # noqa: E402

SESSION_PATH = os.path.join(os.path.dirname(__file__), "rednote_session.json")

_LOADERS = {
    "chrome": browser_cookie3.chrome,
    "edge": browser_cookie3.edge,
    "firefox": browser_cookie3.firefox,
}

# rednote/xiaohongshu는 두 도메인을 쓴다 — 둘 다 긁어 합친다(로그인 쿠키가 어느 쪽에
# 붙는지 브라우저·플로우마다 달라서).
_DOMAINS = ("rednote.com", "xiaohongshu.com")

# Playwright storage_state 최대 만료값(서기 9999년). Firefox가 ms로 저장하는 경우 보정.
_MAX_EXPIRES_SECONDS = 253402300799

# 로그인됐다면 있어야 하는 핵심 인증 쿠키(하나라도 있으면 로그인으로 본다).
_AUTH_HINTS = ("web_session", "customerClientId", "access-token", "galaxy_creator_session_id")


def _to_playwright_cookie(c):
    expires = c.expires if c.expires else -1
    if expires and expires > _MAX_EXPIRES_SECONDS:
        expires = expires / 1000
    return {
        "name": c.name,
        "value": c.value,
        "domain": c.domain,
        "path": c.path or "/",
        "expires": expires,
        "httpOnly": bool(getattr(c, "_rest", {}).get("HTTPOnly")),
        "secure": bool(c.secure),
        "sameSite": "Lax",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=sorted(_LOADERS), default="firefox")
    args = parser.parse_args()

    cookies = []
    seen = set()
    for dom in _DOMAINS:
        try:
            for c in _LOADERS[args.browser](domain_name=dom):
                key = (c.name, c.domain)
                if key in seen:
                    continue
                seen.add(key)
                cookies.append(_to_playwright_cookie(c))
        except Exception as e:  # 한 도메인 실패해도 다른 도메인은 시도
            print(f"[!] {args.browser} {dom} 쿠키 읽기 실패: {e}")

    if not cookies:
        print(f"[!] {args.browser}에서 rednote/xiaohongshu 쿠키를 못 읽었습니다.")
        print("    - 관리자 권한 필요 메시지면: 명령창을 관리자로 다시 열어 재시도")
        print("    - Chrome/Edge 앱바운드 암호화면: Firefox로 로그인 후 --browser firefox")
        return

    names = {c["name"] for c in cookies}
    if not (names & set(_AUTH_HINTS)):
        print(f"[!] 로그인 세션 쿠키가 안 보입니다(쿠키 {len(cookies)}개: {sorted(names)}).")
        print(f"    {args.browser}에서 먼저 rednote.com에 정상 로그인한 뒤 다시 실행하세요.")
        return

    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump({"cookies": cookies, "origins": []}, f, ensure_ascii=False, indent=2)
    print(f"[OK] {args.browser}에서 세션 쿠키 {len(cookies)}개 저장 완료: {SESSION_PATH}")
    print("다음: 이 파일을 서버 /home/ubuntu/rednote_session.json 로 복사하면 발굴·해외HOT이 살아납니다.")


if __name__ == "__main__":
    main()
