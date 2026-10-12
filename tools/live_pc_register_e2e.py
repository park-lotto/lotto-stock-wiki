# -*- coding: utf-8 -*-
"""PC 등록 칸 교체를 라이브에서 **실제 버튼 클릭**으로 확인한다(관제 184).

사장님 보조 계정(cid 12 '박2')으로 헤드리스 브라우저 4개를 띄워 마이페이지 '이 PC 등록하기'를 누른다.
  A(브라우저1)→1번  B(브라우저2)→2번  C(브라우저1, 쿠키 지워진 같은 PC)→1번 교체  D(브라우저3, 다른 PC)→막힘
끝나면 cid 12 의 칸을 비운다(관리자 API). 다른 회원 데이터는 건드리지 않는다.

    py tools/live_pc_register_e2e.py
"""
import subprocess
import sys

sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parent.parent.as_posix())
from tools.live_admin import BASE, HOST, KEY, admin_page  # noqa: E402

CID = 12
DOMAIN = "shoppingshorts.duckdns.org"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.%d.0 Safari/537.36"
_MINT = r'''set -a; . /etc/shopping-shorts.env; set +a; python3 -c "
import hmac,hashlib,os,time
e=int(time.time())+3600; p='%d:%%d'%%e
print(p+':'+hmac.new(os.environ['DASH_SECRET'].encode(),p.encode(),hashlib.sha256).hexdigest())"''' % CID


def cookie():
    r = subprocess.run(["ssh", "-i", KEY, HOST, _MINT], capture_output=True, text=True, timeout=60)
    return r.stdout.strip().splitlines()[-1]


def reset():
    with admin_page("admin") as pg:
        return pg.evaluate("""c => fetch('/api/admin/customer/device_reset',{method:'POST',
            headers:{'Content-Type':'application/json'},body:JSON.stringify({customer_id:c})}).then(r=>r.status)""", CID)


def click(b, ck, ua_n, label):
    ctx = b.new_context(user_agent=UA % ua_n)
    ctx.add_cookies([{"name": "dash_auth", "value": ck, "domain": DOMAIN, "path": "/",
                      "httpOnly": True, "secure": True, "sameSite": "Lax"}])
    pg = ctx.new_page()
    pg.goto(BASE + "/settings", wait_until="domcontentloaded")
    pg.reload(wait_until="domcontentloaded")          # 첫 화면 요청에서 기기 도장(ss_pc)을 받는다
    pg.wait_for_selector("#pcBtn")
    pg.wait_for_timeout(1500)
    btn = pg.locator("#pcBtn")
    before = (btn.inner_text().strip(), btn.is_enabled())
    if before[1]:
        btn.click()
        pg.wait_for_function("document.getElementById('pcMsg').textContent.trim() && "
                             "!document.getElementById('pcMsg').textContent.includes('등록 중')")
    msg = pg.locator("#pcMsg").inner_text().strip()
    pg.wait_for_timeout(800)
    lst = pg.locator("#pcList").inner_text().strip().replace("\n", " | ")
    print("[%s] 버튼=%s 활성=%s → %s\n      목록: %s" % (label, before[0], before[1], msg, lst))
    ctx.close()
    return before[1], msg


def main():
    from playwright.sync_api import sync_playwright
    print("시작 전 칸 비우기:", reset())
    ck = cookie()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ra = click(b, ck, 1, "A 1번 PC")
        rb = click(b, ck, 2, "B 2번 PC")
        rc = click(b, ck, 1, "C 같은 PC 쿠키 지워짐")
        rd = click(b, ck, 3, "D 다른 PC")
        b.close()
    print("끝난 뒤 칸 비우기:", reset())
    ok = ("1번" in ra[1] or "등록" in ra[1]) and rb[0] and rc[0] and "같은 PC" in rc[1] and rd[0] and "2대" in rd[1]
    print("판정:", "통과" if ok else "실패")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
