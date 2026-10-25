"""숏템 설정 화면 검사(관제 266) — 실제 브라우저로 화면을 열어 누르고 잰다. 하나라도 기준 밖이면 rc=1.

  py tools/claude_portal/studio_ui_check.py <화면 주소> [--admin-cookie] [--out <그림 폴더>]
    예) 로컬 시험 서버  py tools/claude_portal/studio_ui_check.py http://127.0.0.1:18866/claude/studio/
        라이브(관리자)  py tools/claude_portal/studio_ui_check.py https://shoppingshorts.duckdns.org/claude/studio/ --admin-cookie

잰다(카드 266 '됐다의 기준'):
  ① 프리셋 카드 수(19 이상)·형식 묶음 제목
  ② 글꼴 칸이 안 잘리나 — 버튼마다 내용 높이(scrollHeight) ≤ 보이는 높이(clientHeight)+1, 높이 ≥ 36px
  ③ 버튼 → 미리보기 다 그릴 때까지(window.__drawn 증가) 걸린 시간 ≤ 2초 + 미리보기 그림이 실제로 바뀌었나
  ④ 바꾼 값이 저장됐나(state.changed)
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
            ctx.add_cookies([{"name": "dash_auth", "value": admin_cookie(), "domain": host, "path": "/", "secure": True, "httpOnly": True}])
        pg = ctx.new_page()
        errs: list = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(a.url, wait_until="networkidle")
        pg.wait_for_function("(window.__drawn||0)>=1", timeout=60000)
        shot = lambda n: pg.locator("#phone").screenshot(path=str(out / f"{n}.png")) if out else pg.locator("#phone").screenshot()   # noqa: E731
        md5 = lambda bts: hashlib.md5(bts).hexdigest()[:8]   # noqa: E731

        # ① 프리셋
        n_cards = pg.locator(".card").count()
        groups = pg.locator(".grp").all_inner_texts()
        print(f"① 프리셋 카드 {n_cards}개 · 묶음 {len(groups)}: {' / '.join(groups)}")
        if n_cards < 19:
            bad.append(f"프리셋 {n_cards}개 < 19")
        if out:
            pg.screenshot(path=str(out / "0_preset.png"), full_page=True)

        def timed_click(sel, label):
            before = pg.evaluate("window.__drawn||0")
            img0 = md5(shot(label + "_전"))
            t = time.time()
            pg.locator(sel).first.click()
            pg.wait_for_function(f"(window.__drawn||0)>{before}", timeout=30000)
            ms = int((time.time() - t) * 1000)
            img1 = md5(shot(label + "_후"))
            ok = ms <= LIMIT_MS and img0 != img1
            print(f"③ {label}: {ms}ms · 미리보기 {img0}→{img1} {'바뀜' if img0 != img1 else '안 바뀜'} {'통과' if ok else '기준 밖'}")
            if not ok:
                bad.append(f"{label} {ms}ms / 그림 {'같음' if img0 == img1 else '바뀜'}")

        # 프리셋 하나 고르기(다른 카드) → 화면 단계로 넘어감
        timed_click(".card:not(.on)", "프리셋 고르기")
        # ② 글꼴 칸(화면 단계 = 제목 글꼴)
        pg.wait_for_selector(".fontgrid button")
        cut = pg.evaluate("""[...document.querySelectorAll('.fontgrid button')].map(b=>({h:b.clientHeight,s:b.scrollHeight}))""")
        clipped = [c for c in cut if c["s"] > c["h"] + 1 or c["h"] < 36]
        print(f"② 글꼴 칸 {len(cut)}개 · 잘린 칸 {len(clipped)}개 (예: {clipped[:2]})")
        if not cut or clipped:
            bad.append(f"글꼴 칸 잘림 {len(clipped)}/{len(cut)}")
        if out:
            pg.locator(".fontgrid").first.screenshot(path=str(out / "2_fontgrid.png"))
        timed_click(".fontgrid button:not(.on) >> nth=3", "제목 글꼴")
        # 자막 단계
        pg.locator('.step[data-k="cap"]').click()
        pg.locator('#scenes button[data-i="1"]').click()   # 자막 효과는 본문 장면에서 보인다(훅은 제목 장면)
        timed_click('button[data-emph]:not(.on):not([data-emph="none"])', "낱말 강조")   # 이미 켜진 칸을 누르면 그림이 안 바뀌는 게 맞다
        # ④ 저장
        st = pg.evaluate("fetch('api/state').then(r=>r.json())")
        chg = st.get("changed") or {}
        saved = (chg.get("text") or {}).get("title_font") and ((chg.get("text") or {}).get("caption") or {}).get("emphasis")
        print(f"④ 저장된 바꾼 칸: {json.dumps(chg, ensure_ascii=False)[:200]}")
        if not saved:
            bad.append("바꾼 값이 저장 안 됨")
        if errs:
            bad.append(f"화면 오류 {errs[:3]}")
        b.close()
    print("결과:", "통과" if not bad else "기준 밖 — " + " | ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
