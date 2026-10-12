# -*- coding: utf-8 -*-
"""라이브 숏템메이커를 **관리자(cid 0)로** 여는 도구 — 확인 작업마다 사장님께 로그인·스위치를 시키지 않으려고(2026-10-05 사장님
"너가 할 수 있던 걸 왜 갑자기 시켜 / 클로드코드에 박아놔").

비밀번호는 PC로 가져오지 않는다. 서버에서 앱과 같은 방식(_sign_session: HMAC(DASH_SECRET, "0:만료"))으로 2시간짜리 관리자
세션 쿠키 `dash_auth` 만 만들어 받아, 헤드리스 크롬에 넣는다.

    py tools/live_admin.py shot /produce out.png          # 관리자로 열어 화면 저장
    py tools/live_admin.py js /produce "document.title"    # 관리자로 열어 JS 한 줄 결과
    py tools/live_admin.py setting storyboard_enabled admin # 관리자 설정 값 저장(서버 /api/admin/settings, 허용 키만)

파이썬에서: from tools.live_admin import admin_page  →  with admin_page("/produce") as pg: ...
"""
import contextlib
import json
import os
import subprocess
import sys

HOST = "ubuntu@3.35.251.172"      # IP 가 바뀌면 nslookup shoppingshorts.duckdns.org
# 키는 PC마다 사용자 폴더가 다르다(TheRose·CH). 경로를 박아두면 다른 PC에서 "Permission denied"로 죽는다.
KEY = os.path.join(os.path.expanduser("~"), "crawling_bot_client", "LightsailDefaultKey-ap-northeast-2.pem").replace("\\", "/")
BASE = "https://shoppingshorts.duckdns.org"

_MINT = r'''set -a; . /etc/shopping-shorts.env; set +a; python3 -c "
import hmac,hashlib,os,time
e=int(time.time())+7200; p='0:%d'%e
print(p+':'+hmac.new(os.environ['DASH_SECRET'].encode(),p.encode(),hashlib.sha256).hexdigest())"'''


def admin_cookie():
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", KEY, HOST, _MINT], capture_output=True, text=True, timeout=60)
    c = (r.stdout or "").strip().splitlines()[-1:] or [""]
    if r.returncode or c[0].count(":") != 2:
        raise RuntimeError("관리자 쿠키를 못 만들었다: %s" % (r.stderr or r.stdout)[-300:])
    return c[0]


@contextlib.contextmanager
def admin_page(path="/", viewport=(1500, 1000)):
    from playwright.sync_api import sync_playwright
    ck = admin_cookie()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        ctx.add_cookies([{"name": "dash_auth", "value": ck, "domain": "shoppingshorts.duckdns.org", "path": "/",
                          "httpOnly": True, "secure": True, "sameSite": "Lax"}])
        pg = ctx.new_page()
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e)[:200]))
        pg.goto(BASE + "/" + path.lstrip("/"), wait_until="domcontentloaded")   # git bash 가 /produce 를 경로로 바꾸니 produce 도 받는다
        pg.wait_for_timeout(2500)
        try:
            yield pg
        finally:
            b.close()


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "shot":
        with admin_page(argv[1]) as pg:
            pg.screenshot(path=argv[2], full_page=True)
            print("저장", argv[2], "주소", pg.url, "페이지 오류", pg.errors)
    elif cmd == "js":
        with admin_page(argv[1]) as pg:
            print(json.dumps(pg.evaluate(argv[2]), ensure_ascii=False))
            print("페이지 오류", pg.errors)
    elif cmd == "setting":
        with admin_page("/admin") as pg:
            out = pg.evaluate("""([k, v]) => fetch('/api/admin/settings', {method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({[k]: v})}).then(r => r.json()).then(d => (d.settings || {})[k])""", [argv[1], argv[2]])
            print(argv[1], "=", out)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
