# 숏클 회원 관리 표(관제 329) 실측 — 진짜 회원 프로그램(MCP 서버)을 돌리며 관리자 화면 버튼을 직접 누른다.
# 회원 PC 가 실제로 막히고 풀리는지를 본다(화면 숫자만 보지 않는다).
# 준비: srv.py 를 먼저 띄운다(빈 C:\t\guard\t.db 로 시작해야 한다). 사진은 C:\t\guard\관리_*.png
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pc import BASE, R, Pc, api  # noqa: E402

bad = []


def once(name, who="나"):
    """잠깐 켜서 점검 한 번 하고 닫는다(회원이 PC 를 켰다 끈 것)."""
    pc = Pc(name, who)
    time.sleep(1.5)
    try:
        return pc.setup()
    finally:
        pc.close()


def check(label, got, want):
    ok = want in got
    print(("  ✅ " if ok else "  ❌ ") + label + " → " + got)
    if not ok:
        bad.append(label)


with sync_playwright() as p:
    b = p.chromium.launch()
    ad = b.new_page(viewport={"width": 1400, "height": 1000})
    ad.on("dialog", lambda d: d.accept())
    errs = []
    ad.on("pageerror", lambda e: errs.append(str(e)))

    def admin():
        ad.goto(BASE + "/admin", wait_until="domcontentloaded")
        ad.wait_for_timeout(1500)
        ad.evaluate("document.getElementById('claudeMembersCard').open=true")
        ad.wait_for_timeout(1500)
        return ad.inner_text("#claudeMembersCard")

    def row():
        return ad.inner_text("#cmTable tbody tr").replace("\n", " ")

    def click(sel):
        ad.locator(sel).first.click()
        ad.wait_for_timeout(1500)

    print("1 회원 PC 2대 등록(내 계정)")
    A = Pc("A")
    time.sleep(1.5)
    check("PC-A 점검", A.setup(), "정상 · 1번 칸")
    B = Pc("B")
    time.sleep(1.5)
    check("PC-B 점검", B.setup(), "정상 · 2번 칸")
    B.close()
    A.setup()                                 # PC-A 를 다시 쓴다(자리를 가져온다)
    admin()
    r = row()
    print("  표:", r)
    check("표에 계정 연결", r, "연결됨")
    check("표에 PC-A·PC-B", r, "PC-B")
    check("표에 엔진 판", r, "엔진 1.0.")
    check("표에 지금 사용", r, "🟢")
    ad.locator("#claudeMembersCard").screenshot(path=str(R / "관리_1_표.png"))

    print("2 접속 끊기")
    click("#cmTable button:has-text('접속 끊기')")
    check("표에서 사용 중 사라짐", row(), "—")
    check("끊긴 PC-A 다시 점검", A.setup(), "끊겼습니다")
    A.close()

    print("3 다른 Claude 계정 → 막힘 → 관리자 '연결 풀기'")
    F = Pc("A2", "친구")                      # 새 PC 지만 한도 2대가 찼다 → 먼저 한도부터 보여 준다
    time.sleep(1.5)
    check("친구 계정 PC", F.setup(), "account_mismatch")
    admin()
    click("#cmTable button:has-text('연결 풀기')")
    print("  풀기 뒤 표:", row())
    check("풀린 뒤 친구 계정 PC(한도 2대 찼음)", F.setup(), "device_limit")

    print("4 PC 한도 3대로 저장 → 3대째 등록")
    ad.select_option("#cmMax", "3")
    click("#cmRules button:has-text('규칙 저장')")
    check("저장 안내", ad.inner_text("#cmMsg"), "반영했습니다")
    check("한도 3에서 친구 계정 PC", F.setup(), "정상 · 3번 칸")
    F.close()
    check("이제 원래 계정은 막힘(친구 계정에 묶임)", once("B"), "account_mismatch")

    print("5 계정 검사 끄기 → 원래 계정도 통과")
    admin()
    ad.uncheck("#cmAcct")
    click("#cmRules button:has-text('규칙 저장')")
    check("검사 끈 뒤 원래 계정 PC-B", once("B"), "정상 · 2번 칸")
    ad.check("#cmAcct")
    click("#cmRules button:has-text('규칙 저장')")

    print("6 최소 엔진 올리기 → 옛 엔진 막힘 → 되돌리기")
    ad.fill("#cmEngine", "99.0.0")
    click("#cmRules button:has-text('규칙 저장')")
    admin()
    check("표에 옛 엔진 표시", row(), "옛 엔진")
    check("최소 엔진 99.0.0 에서 PC-B", once("B"), "engine_old")
    ad.fill("#cmEngine", "1.0.0")
    click("#cmRules button:has-text('규칙 저장')")
    ad.fill("#cmEngine", "x.y")
    click("#cmRules button:has-text('규칙 저장')")
    check("틀린 값은 거절", ad.inner_text("#cmMsg"), "실패")
    check("틀린 값이 있으면 아무것도 안 바뀜", api("/api/admin/claude/members")["settings"]["min_engine"], "1.0.0")
    ad.fill("#cmEngine", "1.0.0")

    print("7 PC 빼기 버튼 → 한도 2로 줄인 뒤 뺀 PC 는 못 들어옴")
    ad.select_option("#cmMax", "2")
    click("#cmRules button:has-text('규칙 저장')")
    check("한도 2 저장", str(api("/api/admin/claude/members")["settings"]["devices_max"]), "2")
    admin()
    n0 = ad.locator("#cmTable button:has-text('빼기')").count()
    click("#cmTable button:has-text('빼기')")
    n1 = ad.locator("#cmTable button:has-text('빼기')").count()
    check("빼기 뒤 PC 수", f"{n0}→{n1}", f"{n0}→{n0 - 1}")
    ad.locator("#claudeMembersCard").screenshot(path=str(R / "관리_2_조작뒤.png"))
    check("뺀 PC-A(한도 2·2대 남음, 묶인 친구 계정으로)", once("A", "친구"), "device_limit")
    check("화면 오류", str(errs), "[]")
    b.close()

print("\n결과:", "전부 통과" if not bad else f"실패 {len(bad)}건: {bad}")
sys.exit(1 if bad else 0)
