"""자막팩 카드 — 편집기 화면에서 고객이 누르는 그대로 점검(관제 127 3단계).

  py tools/caption_pack/check_editor_packs.py <스크린샷폴더>

[다음 ›] → 본문 모션 펼치기 → 팩 카드 누름 →
  ① 카드가 켜지고 '이 장면 · 칸 → 효과' 줄이 그 팩의 칸 효과와 맞다(장면을 넘기며 전부)
  ② 팩이 정한 단어 강조가 같이 켜진다
  ③ 저장값(window.sceneStyle.snapshot)에 captionPack 이 실리고, 효과를 직접 고르면 팩이 꺼진다
  ④ 새로고침해도 고른 팩이 남는다(브라우저 기억)
  ⑤ 페이지 오류 0
"""
import json, pathlib, re, sys
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
text = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
MOTIONS = json.loads(text.split("/*JSON*/")[1]); PACKS = json.loads(text.split("/*PACKS*/")[1])
SLOTS = {"첫 장면": "first", "일반 줄": "body", "가격·숫자": "price", "마지막 장면": "end"}
fails = []
def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok: fails.append(msg)

def open_body(pg):
    pg.locator("button:visible", has_text="다음").first.click(); pg.wait_for_timeout(400)
    s = pg.locator("summary", has_text="본문 모션").first
    if s.evaluate("e=>!e.parentElement.open"): s.click()
    pg.wait_for_timeout(300)

with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1500, "height": 1100}); pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    url = (ROOT / "out/scene-style-ui-showcase.html").as_uri()
    pg.goto(url); pg.wait_for_timeout(1500); open_body(pg)
    cards = pg.eval_on_selector_all("[data-caption-pack]", "bs=>bs.map(b=>b.dataset.captionPack)")
    need(cards == list(PACKS), f"팩 카드 {len(cards)}장 = 계약 파일 {len(PACKS)}개")
    for key, pack in PACKS.items():
        pg.click(f'[data-caption-pack="{key}"]'); pg.wait_for_timeout(250)
        need(pg.locator(f'[data-caption-pack="{key}"].active').count() == 1, f"① [{key}] 카드가 켜진다")
        seen = set()
        total = int(pg.locator(".layout-a [data-scene-total]").first.inner_text())
        for _ in range(total - 2):   # 2장에서 시작해 마지막 장 앞까지 — 마지막 장은 아래에서 따로
            line = pg.locator("[data-caption-pack-now]").inner_text()
            m = re.search(r"(\d+)장\) · (.+?) → (.+)$", line)
            slot = SLOTS.get(m.group(2)) if m else None
            want = MOTIONS[pack["slots"][slot]]["label"] if slot else None
            need(bool(m) and m.group(3) == want, f"① [{key}] {line}  (팩 칸 효과 {want})")
            seen.add(slot)
            pg.locator("button:visible", has_text="다음").first.click(); pg.wait_for_timeout(250)
        line = pg.locator("[data-caption-pack-now]").inner_text(); m = re.search(r" · (.+?) → ", line); seen.add(SLOTS.get(m.group(1)) if m else None)
        need({"first", "body", "end"} <= seen, f"① [{key}] 장면을 넘기며 본 칸 {sorted(s for s in seen if s)}")
        wf = pack.get("wordFx") or {}
        active = pg.eval_on_selector_all("[data-word-fx].active", "bs=>bs.map(b=>b.dataset.wordFx)")
        need(active == [wf.get("style", "")], f"② [{key}] 단어 강조 같이 켜짐 {active} (팩 {wf.get('style', '')!r})")
        snap = pg.evaluate("()=>window.sceneStyle.snapshot()")
        need(snap.get("captionPack") == key and not snap.get("bodyCaptionMotion"), f"③ [{key}] 저장값 captionPack={snap.get('captionPack')}")
        pg.screenshot(path=str(out / f"pack_{key}.png"))
        # 처음 장면으로 되돌림
        pg.goto(url); pg.wait_for_timeout(1200); open_body(pg)
    pg.click('[data-caption-pack="clean"]'); pg.wait_for_timeout(200)
    pg.click('[data-body-caption-motion="fade"]'); pg.wait_for_timeout(200)
    snap = pg.evaluate("()=>window.sceneStyle.snapshot()")
    need("captionPack" not in snap and snap.get("bodyCaptionMotion") == "fade" and pg.locator("[data-caption-pack].active").count() == 0,
         "③ 효과를 직접 고르면 팩이 꺼진다")
    pg.click('[data-caption-pack="story"]'); pg.wait_for_timeout(200)
    pg.reload(); pg.wait_for_timeout(1500); open_body(pg)
    need(pg.locator('[data-caption-pack="story"].active').count() == 1, "④ 새로고침해도 고른 팩(썰 이야기)이 남는다")
    need(not errs, f"⑤ 페이지 오류 {len(errs)}건 {errs[:2]}")
    b.close()
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
