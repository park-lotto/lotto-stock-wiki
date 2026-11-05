# 진짜 회원 프로그램(MCP 서버)을 PC 3대·Claude 계정 2개로 흉내 내 끝까지 돌린다(관제 296). 준비는 srv.py.
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pc import BASE, R, Pc, api  # noqa: E402

A = Pc("A")
time.sleep(1.5)
print("1 PC-A 내 계정 첫 점검:", A.setup())
F = Pc("F", "친구")
time.sleep(1.5)
print("2 PC-F 친구 계정(빈자리 있음):", F.setup())
F.close()
print("  등록 기기 수:", len(api("/api/admin/claude/devices?cid=7")["devices"]))
print("  계정 변경 요청:", [(c["kind"], c["done_30d"]) for c in api("/api/admin/claude/changes")["changes"]])
c0 = api("/api/admin/claude/changes")["changes"][0]
api("/api/admin/claude/changes/decide", {"id": c0["id"], "approve": False})
B = Pc("B")
time.sleep(1.5)
print("3 PC-B 내 계정, PC-A 켜 둠:", B.setup())
A.close()
print("4 PC-A 닫은 뒤 PC-B:", B.setup())
B.close()
C = Pc("C")
time.sleep(1.5)
print("5 PC-C 3대째:", C.setup())
for _ in range(3):
    C.setup()
print("  같은 PC 반복 시도 뒤 정지 여부:", C.setup())

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    pg.on("dialog", lambda d: d.accept())
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/claude", wait_until="domcontentloaded")
    pg.wait_for_timeout(2500)
    print("6 회원 화면 안내:", pg.inner_text("#swapNote"))
    print("  버튼:", pg.locator("#devList [data-dev]").all_inner_texts(), "| 기기", pg.inner_text("#devCount"))
    pg.locator("#license").screenshot(path=str(R / "회원_요청전.png"))
    pg.locator("#devList [data-dev]").first.click()
    pg.wait_for_timeout(1500)
    print("7 요청 뒤 회원 화면:", pg.inner_text("#swapNote"))
    pg.locator("#license").screenshot(path=str(R / "회원_요청뒤.png"))
    print("8 승인 전 PC-C:", C.setup())
    ad = b.new_page(viewport={"width": 1400, "height": 900})
    ad.goto(BASE + "/admin", wait_until="domcontentloaded")
    ad.wait_for_timeout(2500)
    print("9 관리자 요청:", ad.inner_text("#claudeChangeBoard").replace("\n", " | "))
    ad.screenshot(path=str(R / "관리자_승인.png"))
    ad.locator("#claudeChangeBoard button:has-text('승인')").click()
    ad.wait_for_timeout(1200)
    print("  승인 뒤 남은 요청:", repr(ad.inner_text("#claudeChangeBoard")))
    print("  화면 오류:", errs)
    b.close()
print("10 승인 뒤 PC-C (재설치 없음):", C.setup())
print("  기기:", [(d["slot"], d["name"]) for d in api("/api/admin/claude/devices?cid=7")["devices"]])
C.close()
A = Pc("A")
time.sleep(1.5)
print("11 뺀 PC-A:", A.setup())
A.close()
