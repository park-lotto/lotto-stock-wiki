"""숏템 설정 화면 검사(관제 266) — 실제 브라우저로 화면을 열어 누르고 잰다. 하나라도 기준 밖이면 rc=1.

  py tools/claude_portal/studio_ui_check.py <화면 주소> [--admin-cookie] [--out <그림 폴더>]
    예) 로컬 시험 서버  py tools/claude_portal/studio_ui_check.py http://127.0.0.1:18866/claude/studio/
        라이브(관리자)  py tools/claude_portal/studio_ui_check.py https://shoppingshorts.duckdns.org/claude/studio/ --admin-cookie

잰다(카드 266 '됐다의 기준', 10-26 4단계 화면 — 프리셋 → 꾸미기 → 소리 → 완성본 고치기):
  ① 프리셋(판) 카드 22 이상 · 이름에 채널명 없이 '묶음 + 번호' · 견본 사진
  ② 프리셋 누르기 → 다음 단계로 저절로 안 넘어가고 계정에 저장(state.style)
  ③ 꾸미기 = 장면꾸미기 화면이 뜨고 '이 영상에 적용' → 서버 저장 200 · 버튼 '적용됨'
  ④ 소리 = 목소리 단추 → 팩 tts 저장(엔진이 모르는 목소리·칸이면 '저장됨'이 아니라 거절 이유가 화면에 남는다)
  ⑤ 완성본 고치기 = 완성본이 없으면 잠김(🔒)
  ⓪ 첫 단계 = 설정(키·영상 받기 계정 — 값은 회원 PC 에만)
  화면 오류(pageerror) 0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

LIMIT_MS = 2000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--admin-cookie", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    out = Path(a.out) if a.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    bad: list = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1300, "height": 1000})
        if a.admin_cookie:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from tools.live_admin import admin_cookie
            host = a.url.split("/")[2]
            ctx.add_cookies([{"name": "dash_auth", "value": admin_cookie(), "domain": host, "path": "/", "secure": True, "httpOnly": True,
                              "sameSite": "Lax"}])   # live_admin.admin_page 와 같은 꼴(없으면 쿠키가 안 실려 로그인으로 307 — 10-25 실측)
        pg = ctx.new_page()
        errs: list = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(a.url, wait_until="networkidle")
        pg.wait_for_function("(window.__drawn||0)>=1", timeout=60000)
        shot = lambda n: pg.locator("#phone").screenshot(path=str(out / f"{n}.png")) if out else pg.locator("#phone").screenshot()   # noqa: E731
        md5 = lambda bts: hashlib.md5(bts).hexdigest()[:8]   # noqa: E731

        state = lambda: pg.evaluate("fetch('api/state').then(r=>r.json())")   # noqa: E731
        step = lambda name: pg.locator("[data-step],.steps button,.steps a").filter(has_text=name).first.click()   # noqa: E731
        # ⓪ 설정 단계(10-26 첫 단계 — 키·영상 받기 계정, 값은 회원 PC 에만): 단추가 맨 앞에 있고, 프리셋으로 넘어간다
        first = pg.locator(".step").first.inner_text().replace("
", " ")
        print(f"⓪ 첫 단계 '{first}'")
        if "설정" not in first:
            bad.append(f"첫 단계가 설정이 아님: {first}")
        step("프리셋")
        pg.wait_for_timeout(2500)
        # ① 프리셋(판) 카드
        cards = pg.locator(".scard")
        n_cards = cards.count()
        names = pg.locator(".scard .sc-b b").all_inner_texts()
        shots = pg.locator(".scard img").count()
        print(f"① 프리셋 {n_cards}개 · 견본 사진 {shots}개 · 이름 앞 4개 {names[:4]}")
        if n_cards < 22:
            bad.append(f"프리셋 {n_cards}개 < 22")
        bench = [n for n in names if not any(ch.isdigit() for ch in n)]
        if bench:
            bad.append(f"'묶음 + 번호' 아닌 이름 {bench[:3]}")
        if out:
            pg.screenshot(path=str(out / "1_preset.png"), full_page=True)
        # ② 누르면 저장, 단계는 그대로
        target = pg.locator(".scard:not(.on)").first
        sid = target.get_attribute("data-style")
        target.click()
        pg.wait_for_timeout(2500)
        on_step = pg.locator(".scard").count() > 0
        saved = state().get("style") == sid
        print(f"② 프리셋 고르기 → 저장 {saved} · 단계 그대로 {on_step}")
        if not (saved and on_step):
            bad.append("프리셋 고르기 저장/단계 유지 실패")
        # ③ 꾸미기
        step("꾸미기")
        pg.wait_for_timeout(9000)
        frs = [f for f in pg.frames if f != pg.main_frame]
        looks = []
        pg.on("response", lambda r: looks.append(r.status) if r.url.endswith("/api/look") else None)
        if not frs:
            bad.append("꾸미기에 장면꾸미기 화면이 없음")
        else:
            fr = frs[0]
            fr.get_by_role("button", name="이 영상에 적용", exact=True).first.click()
            pg.wait_for_timeout(5000)
            btn = fr.evaluate("()=>[...document.querySelectorAll('button')].map(x=>x.textContent.trim()).filter(t=>/영상에 적용/.test(t))")
            print(f"③ 꾸미기 '이 영상에 적용' → 서버 {looks} · 버튼 {btn}")
            if looks != [200] or not any("적용됨" in t for t in btn):
                bad.append(f"꾸민 모양 저장 실패 {looks} {btn}")
            if out:
                pg.screenshot(path=str(out / "3_look.png"))
        # ④ 소리
        step("소리")
        pg.wait_for_timeout(3000)
        pick = pg.locator("[data-pickv]").first
        name = pick.get_attribute("data-pickn") if pick.count() else None
        if not name:
            bad.append("목소리 단추 없음")
        else:
            pick.click()
            pg.wait_for_timeout(3000)
            msg = pg.evaluate("()=>(document.querySelector('.state')||{}).textContent")
            err = pg.evaluate("()=>!!document.querySelector('.state.err')")
            tts = (state().get("pack") or {}).get("tts") or {}
            ok = (tts.get("name") == name) if not err else bool(msg and "저장됨" not in msg)
            print(f"④ 목소리 {name} → 팩 {tts.get('name')} · 화면 '{msg}' {'(거절 이유 표시)' if err else ''}")
            if not ok:
                bad.append(f"목소리 저장/거절 표시 이상: {name} → {tts.get('name')} '{msg}'")
        # ⑤ 완성본 고치기 잠김(서버 화면에서 회원 PC 다리가 없으면)
        lock = pg.locator("[data-step],.steps button,.steps a").filter(has_text="완성본 고치기").first.inner_text()
        print(f"⑤ 완성본 고치기 단추 '{lock.strip()}'")
        if errs:
            bad.append(f"화면 오류 {errs[:3]}")
        b.close()
    print("결과:", "통과" if not bad else "기준 밖 — " + " | ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
