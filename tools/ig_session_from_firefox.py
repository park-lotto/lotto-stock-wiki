# -*- coding: utf-8 -*-
"""파이어폭스 프로필 하나의 인스타 쿠키 → Playwright storage_state + 생사 판정.

    py tools/ig_session_from_firefox.py <프로필이름> <출력경로>
    예) py tools/ig_session_from_firefox.py 신규1 out/ig_44744647812.json

출력 첫 줄: ALIVE|<uid>|200|<쿠키수>  또는  DEAD|... / NOLOGIN|... / NOPROFILE
적립: scp <출력경로> ubuntu@<서버>:/home/ubuntu/ig_sessions/reference/<uid>.json

■ 왜 파이어폭스인가
크롬은 App-Bound Encryption 때문에 브라우저를 닫아도 쿠키를 못 뽑는다(실측).
파이어폭스 cookies.sqlite는 암호화가 없어 그냥 읽힌다. 틱톡도 같은 방식이다
(tools/tiktok_session_from_firefox.py — 이 파일은 그것의 인스타판).
★파이어폭스를 켜 둔 채로도 된다: DB를 WAL까지 임시폴더로 복사해 읽는다.

■ 생사 판정은 쿠키 존재가 아니라 인스타에 물어서 한다
sessionid·ds_user_id가 멀쩡해도 인스타가 능동 회수한 경우가 있다(2026-08-24 실사고).
판정은 channel_archive.session_alive와 **똑같이** 한다 — sessionid만 실어
instagram.com 루트를 리다이렉트 없이 열어 200이면 살아있음, 302면 죽음.
⚠️api/v1/users/... 같은 엔드포인트로 판정하지 마라(2026-09-08 실측: 429가 떠서
  13개 전부 '오류'로 나왔다 — 판정 자체가 무효가 된다).

■ ★계정을 한꺼번에 살리지 마라 (2026-09-08 사장님 화면 실측)
`21649455asd` 계정에 인스타 조치가 걸려 있었다: "여러 세션을 만들 수 없습니다"
(2026-08-31 조치), 사유 "민감한 정보를 수집… 사이버 보안 커뮤니티 규정 위반".
서버 세션 파일 10개가 전부 **8/31 20:41**에 만들어졌다 — 같은 날이다.
한 PC·한 IP에서 계정 여러 개를 연달아 로그인하면 인스타가 한 기계로 묶어 본다
(channel_archive.slot_proxy의 "계정↔IP 1:1" 주석과 같은 원리). 수집할 때는
계정마다 프록시가 붙지만 **로그인하는 순간의 IP는 그 PC 것**이다.
→ 되살릴 때는 하루 1~2개씩 나눠라. (인과는 날짜 일치·제재 문구에 근거한 추정이다)
"""
import io, json, os, pathlib, shutil, sqlite3, sys, tempfile
import urllib.request, urllib.error

prof_name, out_path = sys.argv[1], sys.argv[2]
root = pathlib.Path(os.environ["APPDATA"]) / "Mozilla/Firefox/Profiles"
cands = [d for d in root.iterdir() if d.name.endswith("." + prof_name) or d.name == prof_name]
if not cands:
    print("NOPROFILE"); raise SystemExit(1)
prof = cands[0]

def _exp(v):
    try: v = int(v or 0)
    except Exception: return -1
    if v <= 0: return -1
    if v > 2**31: v //= 1000
    return v

rows = []
with tempfile.TemporaryDirectory() as td:
    dst = pathlib.Path(td) / "cookies.sqlite"
    shutil.copy2(prof / "cookies.sqlite", dst)
    for sfx in ("-wal", "-shm"):
        src = prof / ("cookies.sqlite" + sfx)
        if src.exists(): shutil.copy2(src, str(dst) + sfx)
    con = sqlite3.connect("file:%s?mode=ro" % dst.as_posix(), uri=True)
    for n, v, h, p_, e, s, ho in con.execute(
            "SELECT name,value,host,path,expiry,isSecure,isHttpOnly "
            "FROM moz_cookies WHERE host LIKE '%instagram%'"):
        rows.append({"name": n, "value": v, "domain": h, "path": p_ or "/",
                     "expires": _exp(e), "httpOnly": bool(ho), "secure": bool(s),
                     "sameSite": "Lax"})
    con.close()

by = {r["name"]: r["value"] for r in rows}
uid, sid = by.get("ds_user_id", ""), by.get("sessionid", "")
if not sid:
    print("NOLOGIN|%s|" % uid); raise SystemExit(2)

class _NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw): return None
req = urllib.request.Request("https://www.instagram.com/", headers={
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Cookie": "sessionid=%s" % sid})
try:
    with urllib.request.build_opener(_NR).open(req, timeout=20) as r:
        code = r.status
except urllib.error.HTTPError as e:
    code = e.code
except Exception:
    code = 0
io.open(out_path, "w", encoding="utf-8").write(
    json.dumps({"cookies": rows, "origins": []}, ensure_ascii=False, indent=1))
print("%s|%s|%s|%d" % ("ALIVE" if code == 200 else "DEAD", uid, code, len(rows)))
