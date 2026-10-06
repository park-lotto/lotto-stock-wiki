"""자막 스타일 카드 + 등장 효과팩 — 편집기 화면에서 고객이 누르는 그대로 점검(관제 127·144).

  py tools/caption_pack/check_editor_packs.py <스크린샷폴더>

[다음 ›] → 본문 모션 펼치기 →
  ① 스타일 카드 6장: 누르면 카드가 켜지고 자막 글꼴이 그 스타일 글꼴, 스타일 단어 강조가 같이 켜지고, ★움직임(motionPack)은 그대로
  ⑦ ★고객이 자막 상자를 이미 골라 둔 작업에서도 스타일을 누르면 스타일 모양(글꼴·글자색·상자)으로 바뀐다
     (10-06 라이브 실측: 고객 작업은 장면마다 look 이 저장돼 있어 상자·색이 막혔다)
  ② 효과팩 번호: 누른 직후 자막이 움직이고, '번호 · 이 장면 · 칸 → 효과' 줄이 편집기 장면 계획(motionPlan)과 같다 — 장면을 넘기며 전부
  ⑥ ★[다음 ›] 직후에도 자막이 움직인다(10-05 사장님 '팩을 누르면 작동은 안 하는 거지' — 표시 줄만 재고 움직임을 안 재서 놓쳤다)
  ③ 자동 = 서버가 준 회원 번호(context.motionPackAuto)가 버튼·저장값에 / 끔 = 줄 숨김·저장값 off / 효과를 직접 고르면 효과팩이 꺼진다
  ④ 새로고침해도 고른 스타일·효과팩이 남는다(브라우저 기억)
  ⑤ 페이지 오류 0
"""
import json, pathlib, re, sys
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "tools/caption_pack"))
import _plan
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
fails = []
def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok: fails.append(msg)

RUNNING = """()=>{const t=document.querySelector('.precision-text[data-edit-bind="caption"]');
  return [t,...t.querySelectorAll('.cap-u')].reduce((n,e)=>n+e.getAnimations().filter(a=>a.playState==='running').length,0)}"""
CAPFONT = """()=>getComputedStyle(document.querySelector('.precision-text[data-edit-bind="caption"]')).fontFamily"""

def open_body(pg):
    pg.locator("button:visible", has_text="다음").first.click(); pg.wait_for_timeout(400)
    s = pg.locator("summary", has_text="본문 모션").first
    if s.evaluate("e=>!e.parentElement.open"): s.click()
    pg.wait_for_timeout(300)

with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1500, "height": 1100}); pg = ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    url = (ROOT / "out/scene-style-ui-showcase.html").as_uri()
    fresh = lambda: (pg.goto(url), pg.wait_for_timeout(1200), pg.evaluate("localStorage.clear()"), pg.reload(), pg.wait_for_timeout(1500), open_body(pg))
    fresh()
    # ① 스타일 카드
    cards = pg.eval_on_selector_all("[data-caption-pack]", "bs=>bs.map(b=>b.dataset.captionPack)")
    need(cards == list(_plan.STYLES), f"① 스타일 카드 {len(cards)}장 = 계약 파일 {len(_plan.STYLES)}개")
    pg.click('[data-motion-pack="7"]'); pg.wait_for_timeout(300)
    for key, st in _plan.STYLES.items():
        pg.click(f'[data-caption-pack="{key}"]'); pg.wait_for_timeout(600)
        snap = pg.evaluate("()=>window.sceneStyle.snapshot()")
        active = pg.eval_on_selector_all("[data-word-fx].active", "bs=>bs.map(b=>b.dataset.wordFx)")
        font = pg.evaluate(CAPFONT)
        need(pg.locator(f'[data-caption-pack="{key}"].active').count() == 1 and font.startswith(st["font"]) and active == [st["wordFx"].get("style", "")]
             and snap.get("captionPack") == key and snap.get("motionPack") == "7",
             f"① [{key}] 카드 켜짐 · 글꼴 {font[:16]} · 단어 강조 {active} · 저장 captionPack={snap.get('captionPack')} · 움직임 그대로 motionPack={snap.get('motionPack')}")
    # ⑦ 상자를 먼저 고른 작업(흰 띠 look 0)에 예능 텐션(상자 없음·흰 글씨·어그로체)
    fresh()
    pg.evaluate("()=>{const b=document.querySelector('[data-caption-look=\"0\"]');b&&b.click()}"); pg.wait_for_timeout(300)
    before = pg.evaluate("()=>(window.sceneStyle.snapshot().captionLayouts||{})")
    pg.click('[data-caption-pack="tension"]'); pg.wait_for_timeout(800)
    look = pg.evaluate("""()=>{const t=document.querySelector('.precision-text[data-edit-bind="caption"]'),cs=getComputedStyle(t),m=document.querySelector('.caption-mask');
      return {font:cs.fontFamily,color:cs.color,mask:m?getComputedStyle(m).backgroundImage:'none',looks:Object.values(window.sceneStyle.snapshot().captionLayouts||{}).filter(v=>'look' in v).length}}""")
    need(any("look" in v for v in before.values()) and look["font"].startswith("SBAggroB") and look["color"] == "rgb(255, 255, 255)" and look["mask"] == "none" and look["looks"] == 0,
         f"⑦ 상자를 골라 둔 작업에 스타일 → 스타일 모양 (고르기 전 look 저장 {sum(1 for v in before.values() if 'look' in v)}칸 → 글꼴 {look['font'][:10]} · 색 {look['color']} · 상자 {look['mask'][:12]} · 남은 look {look['looks']})")
    # ② ⑥ 효과팩 번호
    btns = pg.eval_on_selector_all("[data-motion-pack]", "bs=>bs.map(b=>b.dataset.motionPack)")
    need(btns == ["", "off"] + [str(k) for k in range(1, len(_plan.MPACKS) + 1)], f"② 효과팩 버튼 자동·끔 + {len(btns) - 2}개 = 계약 파일 {len(_plan.MPACKS)}팩")
    for k in (1, 7, 14, 20):
        fresh()
        pg.click(f'[data-motion-pack="{k}"]'); pg.wait_for_timeout(100)
        need(pg.evaluate(RUNNING) > 0, f"⑥ [{k}번] 누른 직후 자막이 움직인다 ({pg.evaluate(RUNNING)})")
        pg.wait_for_timeout(1300)
        plan = pg.evaluate("()=>window.sceneStyle.motionPlan()"); total = len(plan); bad = []
        for _ in range(total - 1):
            cur = int(pg.locator(".layout-a [data-scene-current]").first.inner_text()) - 1
            line = pg.locator("[data-caption-pack-now]").inner_text()
            m = re.search(r"^(\d+)번 · 이 장면\((\d+)장\) · (.+?) → (.+)$", line)
            want = _plan.MOTIONS[plan[cur]]["label"] if plan[cur] else "없음"
            if not (m and int(m.group(1)) == k and int(m.group(2)) == cur + 1 and m.group(4) == want): bad.append((cur + 1, line, want))
            if cur + 1 >= total: break
            pg.locator("button:visible", has_text="다음").first.click(); pg.wait_for_timeout(120)
            run = pg.evaluate(RUNNING)
            if run <= 0: bad.append((cur + 2, "움직임 0", ""))
            pg.wait_for_timeout(1100)
        need(not bad, f"② ⑥ [{k}번] {total - 1}장면 넘기며 표시 줄 = 편집기 계획 · [다음] 직후 움직임 (어긋남 {bad[:3]})")
        need(pg.evaluate("()=>window.sceneStyle.snapshot().motionPack") == str(k), f"② [{k}번] 저장값 motionPack={k}")
    # ③ 자동·끔·직접
    fresh()
    ctx_auto = pg.evaluate("()=>null")   # 견본 편집기는 서버 context 가 없다 → 자동 번호를 실어 load
    req = {"scenes": None}
    snap0 = pg.evaluate("()=>window.sceneStyle.snapshot()")
    have_ctx = pg.evaluate("()=>!!window.sceneStyle.context")
    pg.click('[data-motion-pack=""]'); pg.wait_for_timeout(300)
    need(pg.locator('[data-caption-pack-now]').is_hidden() and "motionPack" not in pg.evaluate("()=>window.sceneStyle.snapshot()"),
         "③ 자동인데 서버 번호가 없으면(견본 화면·스위치 꺼짐) 움직임 없음·저장값 없음 — 고객 화면 불변")
    pg.click('[data-motion-pack="5"]'); pg.wait_for_timeout(300); pg.click('[data-motion-pack="off"]'); pg.wait_for_timeout(300)
    need(pg.locator('[data-caption-pack-now]').is_hidden() and pg.evaluate("()=>window.sceneStyle.snapshot().motionPack") == "off", "③ 끔 → 줄 숨김 · 저장값 off")
    pg.click('[data-motion-pack="5"]'); pg.wait_for_timeout(300); pg.click('[data-body-caption-motion="fade"]'); pg.wait_for_timeout(300)
    s3 = pg.evaluate("()=>window.sceneStyle.snapshot()")
    need(s3.get("motionPack") == "off" and s3.get("bodyCaptionMotion") == "fade" and pg.locator('[data-motion-pack="off"].active').count() == 1,
         "③ 효과를 직접 고르면 효과팩이 꺼진다(끔 버튼 켜짐)")
    # ④ 새로고침 유지
    pg.click('[data-caption-pack="story"]'); pg.wait_for_timeout(200); pg.click('[data-motion-pack="12"]'); pg.wait_for_timeout(300)
    pg.reload(); pg.wait_for_timeout(1500); open_body(pg)
    need(pg.locator('[data-caption-pack="story"].active').count() == 1 and pg.locator('[data-motion-pack="12"].active').count() == 1,
         "④ 새로고침해도 고른 스타일(썰 이야기)·효과팩(12번)이 남는다")
    pg.screenshot(path=str(out / "editor.png"))
    need(not errs, f"⑤ 페이지 오류 {len(errs)}건 {errs[:2]}")
    b.close()
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
