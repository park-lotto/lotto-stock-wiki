"""자막팩 등장 효과 — 편집기 화면에서 버튼을 눌렀을 때 실제로 움직이나(관제 127).

  py tools/caption_pack/check_editor_live.py <스크린샷폴더> [효과키,...]

편집기(out/scene-style-ui-showcase.html)를 렌더러와 같은 방식(file://)으로 열되 qa 없이 연다 → 실제 시간으로 흐르는 미리보기.
효과 버튼마다: 누름 → 0.12초 뒤 글자 단위가 움직이는 중인가(애니메이션 수·불투명도 제각각) → 끝난 뒤 애니메이션이 남지 않았나
→ 자막 글자가 그대로인가. 페이지 오류 0 이어야 한다. 중간 장면 스크린샷을 남긴다.
"""
import json, pathlib, sys
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
motions = json.loads((ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8").split("/*JSON*/")[1])
keys = sys.argv[2].split(",") if len(sys.argv) > 2 else list(motions)
fails = []
def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok: fails.append(msg)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1500, "height": 1100})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((ROOT / "out/scene-style-ui-showcase.html").as_uri()); pg.wait_for_timeout(1500)
    # 고객이 가는 길 그대로: [다음 ›]으로 본문 장면 → '본문 모션' 단락 펼치기
    pg.locator("button:visible", has_text="다음").first.click(); pg.wait_for_timeout(400)
    pg.locator("summary", has_text="본문 모션").first.click(); pg.wait_for_timeout(300)
    labels = pg.eval_on_selector_all("[data-body-caption-motion]", "bs=>bs.map(b=>b.dataset.bodyCaptionMotion)")
    need(all(k in labels for k in motions), f"효과 버튼 {len(labels) - 1}개 = 계약 파일 {len(motions)}개")
    for key in keys:
        pg.click(f'[data-body-caption-motion="{key}"]')
        pg.wait_for_timeout(120)
        st = pg.evaluate("""()=>{const t=document.querySelector('.layout-a .precision-text[data-edit-bind="caption"]')||document.querySelector('.precision-text[data-edit-bind="caption"]');
          const units=[...t.querySelectorAll('.cap-u')];const live=[t,...units].reduce((n,e)=>n+e.getAnimations().filter(a=>a.playState==='running').length,0);
          const ops=units.map(u=>getComputedStyle(u).opacity);return {text:t.textContent,units:units.length,live,ops:[...new Set(ops)].length}}""")
        unit = motions[key].get("unit")
        need(st["live"] > 0, f"[{key}] 누르면 움직인다 (돌고 있는 애니메이션 {st['live']}, 단위 {st['units']})")
        if unit:
            need(st["units"] > 1, f"[{key}] {unit} 단위로 쪼갰다 ({st['units']}개)")
        pg.screenshot(path=str(out / f"live_{key}.png"), clip={"x": 0, "y": 0, "width": 1500, "height": 1100})
        pg.wait_for_timeout(2600)
        end = pg.evaluate("""()=>{const t=document.querySelector('.precision-text[data-edit-bind="caption"]');
          return {text:t.textContent,left:[t,...t.querySelectorAll('.cap-u')].reduce((n,e)=>n+e.getAnimations().length,0)}}""")
        need(end["left"] == 0 and end["text"] == st["text"], f"[{key}] 끝나면 애니메이션 0개 남음({end['left']}) · 자막 글자 그대로")
    need(not errs, f"페이지 오류 {len(errs)}건 {errs[:2]}")
    b.close()
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
