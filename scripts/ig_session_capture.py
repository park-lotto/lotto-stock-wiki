"""브라우저에 로그인된 인스타 계정 세션을 전부 슬롯으로 적립한다(계정 로테이션용).

배경(2026-08-05): 히트작 아카이브는 채널당 400여 개를 통째로 긁어야 해서(최신
100개만 긁으면 조회수 상위 100개 중 0~5개밖에 안 걸린다 — 실측) 한 계정이 몇
시간 만에 `accounts/scraping_warning`에 걸린다. 그래서 계정 여러 개를 적립해두고
크롤러가 막힐 때마다 다음 계정으로 넘긴다(channel_archive.session_slots).

★한 프로필에서 계정을 바꾸면 안 된다: 로그아웃하는 순간 인스타가 직전 계정의
sessionid를 무효화한다(실측 — 적립해둔 세션이 홈으로 리다이렉트됐다). 계정마다
**별도 Firefox 프로필**(about:profiles → 새 프로필 만들기)이나 컨테이너 탭을 쓰면
세션이 동시에 살아 있어 로테이션이 성립한다. 이 스크립트는 모든 프로필·컨테이너를
훑어 살아 있는 세션을 전부 적립한다.

사용법:
    python scripts/ig_session_capture.py
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_HERE = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR = os.path.join(_HERE, "ig_sessions")
_MAX_EXPIRES_SECONDS = 253402300799   # Playwright 상한(서기 9999년)

# storage_state에 실어야 하는 인스타 쿠키. sessionid만으로는 로그인 판정이 안 된다.
_WANTED = {"sessionid", "ds_user_id", "csrftoken", "mid", "ig_did", "datr", "rur", "shbid", "shbts"}


def _firefox_cookie_dbs():
    for p in glob.glob(os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles\*")):
        db = os.path.join(p, "cookies.sqlite")
        if os.path.exists(db):
            yield os.path.basename(p), db


def _read_sessions(db_path):
    """(originAttributes 별로) 인스타 쿠키 묶음을 돌려준다. WAL 포함 복사 — 안 그러면
    방금 로그인한 세션이 안 보인다(2026-08-05 실측)."""
    tmpd = tempfile.mkdtemp()
    for suf in ("", "-wal", "-shm"):
        if os.path.exists(db_path + suf):
            shutil.copy2(db_path + suf, os.path.join(tmpd, "cookies.sqlite" + suf))
    conn = sqlite3.connect(os.path.join(tmpd, "cookies.sqlite"))
    rows = conn.execute(
        "SELECT name, value, host, path, expiry, isSecure, isHttpOnly, originAttributes "
        "FROM moz_cookies WHERE host LIKE '%instagram.com'").fetchall()
    conn.close()

    by_origin = {}
    for name, value, host, path, expiry, secure, http_only, origin in rows:
        if name not in _WANTED:
            continue
        exp = expiry or -1
        if exp > _MAX_EXPIRES_SECONDS:
            exp = exp / 1000
        by_origin.setdefault(origin or "", []).append({
            "name": name, "value": value, "domain": host, "path": path or "/",
            "expires": exp, "httpOnly": bool(http_only), "secure": bool(secure),
            "sameSite": "Lax",
        })
    return by_origin


def _uid(cookies):
    for c in cookies:
        if c["name"] == "sessionid" and "%3A" in c["value"]:
            return c["value"].split("%3A")[0]
    for c in cookies:
        if c["name"] == "ds_user_id":
            return c["value"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true",
                    help="브라우저에 없는 슬롯 파일을 지운다(죽은 세션 정리)")
    a = ap.parse_args()

    os.makedirs(SESSION_DIR, exist_ok=True)
    found = {}
    for prof, db in _firefox_cookie_dbs():
        try:
            for origin, cookies in _read_sessions(db).items():
                uid = _uid(cookies)
                if uid:
                    found[uid] = (cookies, prof, origin)
        except Exception as e:                     # noqa: BLE001 — 잠긴 프로필은 건너뛴다
            print("[!] %s 읽기 실패: %s" % (prof, str(e)[:60]))

    if not found:
        print("[!] 로그인된 인스타 세션이 없습니다. Firefox에서 로그인 후 다시 실행하세요.")
        return 1

    for uid, (cookies, prof, origin) in sorted(found.items()):
        dest = os.path.join(SESSION_DIR, "%s.json" % uid)
        existed = os.path.exists(dest)
        json.dump({"cookies": cookies, "origins": []}, open(dest, "w", encoding="utf-8"))
        print("[OK] %s  (%s%s)  %s" % (
            uid, prof, "/" + origin if origin else "", "갱신" if existed else "신규"))

    if a.prune:
        for f in os.listdir(SESSION_DIR):
            if f.endswith(".json") and f[:-5] not in found:
                os.remove(os.path.join(SESSION_DIR, f))
                print("[--] %s 슬롯 삭제(브라우저에 없음)" % f[:-5])

    slots = sorted(f[:-5] for f in os.listdir(SESSION_DIR) if f.endswith(".json"))
    print("적립된 계정 %d개: %s" % (len(slots), ", ".join(slots)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
