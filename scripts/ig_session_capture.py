"""브라우저에 지금 로그인된 인스타 계정을 세션 슬롯으로 적립한다(계정 로테이션용).

배경(2026-08-05): 히트작 아카이브 크롤은 채널당 400여 개를 통째로 긁어야 해서
(조회수 상위 100개 중 최신 100개 안에 드는 건 0~5개뿐 — 최신만 긁으면 히트작을
통째로 놓친다) 한 계정으로는 몇 시간 만에 `accounts/scraping_warning`에 걸린다.
반면 **재로그인해서 세션을 새로 뽑으면 즉시 되살아난다**(당일 실측). 그래서
계정 여러 개의 세션을 미리 적립해두고 크롤러가 막힐 때마다 다음 세션으로
넘어가게 한다.

사용법 — 계정 하나당 한 번씩:
    1. Firefox에서 해당 계정으로 로그인
    2. python scripts/ig_session_capture.py
    3. 로그아웃 → 다음 계정 로그인 → 2번 반복

파일명은 계정 uid로 정해지므로 같은 계정을 두 번 담아도 슬롯이 늘지 않는다
(재로그인 후 다시 실행하면 그 계정 세션이 갱신된다 — 막혔을 때의 복구 경로).
"""
import argparse
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_HERE = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(_HERE, "ig_sessions")
SINGLE = os.path.join(_HERE, "instagram_session.json")


def _uid_of(cookies):
    for c in cookies:
        if c["name"] == "sessionid" and "%3A" in c["value"]:
            return c["value"].split("%3A")[0]
    for c in cookies:
        if c["name"] == "ds_user_id":
            return c["value"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", default="firefox")
    a = ap.parse_args()

    # 추출 자체는 기존 검증된 스크립트를 그대로 쓴다(중복 구현 금지).
    r = subprocess.run(
        [sys.executable, os.path.join(_HERE, "instagram_cookies_from_browser.py"),
         "--browser", a.browser],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(SINGLE):
        print(r.stdout.strip() or r.stderr.strip())
        return 1

    state = json.load(open(SINGLE, encoding="utf-8"))
    uid = _uid_of(state.get("cookies", []))
    if not uid:
        print("[!] sessionid가 없습니다 — 브라우저에서 인스타에 로그인돼 있는지 확인하세요.")
        return 1

    os.makedirs(SESSION_DIR, exist_ok=True)
    dest = os.path.join(SESSION_DIR, "%s.json" % uid)
    existed = os.path.exists(dest)
    json.dump(state, open(dest, "w", encoding="utf-8"))

    slots = sorted(f for f in os.listdir(SESSION_DIR) if f.endswith(".json"))
    print("[OK] 계정 %s 세션 %s: %s" % (uid, "갱신" if existed else "신규 적립", dest))
    print("     현재 적립된 계정 %d개: %s" % (len(slots), ", ".join(s[:-5] for s in slots)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
