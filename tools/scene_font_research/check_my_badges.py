# -*- coding: utf-8 -*-
"""내 배지: 배지 문구·색·모양을 저장해 버튼으로 다시 쓰기 (2026-09-22 사장님). 실제 편집기에서 고객 순서대로 눌러 본다.
  py tools/scene_font_research/check_my_badges.py <출력폴더>      (8773 서버 필요)
  ※ ?qa=1 없이 연다 — 고객과 같은 조건(브라우저 기억이 켜진 상태).
"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
URL = 'http://127.0.0.1:8773/out/scene-style-ui-showcase.html'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
def open_badges(pg):
    pg.evaluate("[...document.querySelectorAll('.tool-tabs:not(.left-pane-tabs) button')].find(b=>b.textContent.includes('효과')).click()"); pg.wait_for_timeout(300)
    pg.evaluate("(()=>{const d=[...document.querySelectorAll('details')].find(x=>x.querySelector('summary')?.textContent.includes('스티커'));if(!d.open)d.querySelector('summary').click()})()"); pg.wait_for_timeout(300)
    pg.click('[data-dec-kit="badge"]'); pg.wait_for_timeout(300)
mine = lambda pg: pg.evaluate("[...document.querySelectorAll('[data-add-my-badge]')].map(b=>[b.textContent,getComputedStyle(b).backgroundColor])")
badge_on_stage = lambda pg: pg.evaluate("(()=>{const m=(window.sceneStyle.effect().masks||[]).filter(x=>x.kind==='badge');return m.map(x=>[x.text,x.color,x.badgeStyle])})()")
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 1600, 'height': 1700}); pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until='networkidle'); pg.evaluate("localStorage.removeItem('scene_style_my_badges')"); pg.reload(wait_until='networkidle')
    open_badges(pg); need(pg.evaluate("document.querySelector('.dec-my-badges').hidden"), '처음엔 내 배지 칸이 안 보인다(저장한 게 없으므로)')
    # ① 기본 배지 추가 → 문구·색·모양 바꾸기 → 저장
    pg.click('[data-add-badge="주목"]'); pg.wait_for_timeout(400)
    need(pg.locator('[data-save-badge]').is_visible(), '① 배지를 고르면 「내 버튼으로 저장」이 보인다')
    pg.fill('[data-dec="text"]', '아래 구매링크확인'); pg.dispatch_event('[data-dec="text"]', 'input'); pg.dispatch_event('[data-dec="text"]', 'change')
    pg.select_option('[data-dec="badgeStyle"]', 'ticket')
    pg.evaluate("(()=>{const c=document.querySelector('.dec-edit [data-dec=color]');c.value='#1f4bff';c.dispatchEvent(new Event('input',{bubbles:true}));c.dispatchEvent(new Event('change',{bubbles:true}))})()"); pg.wait_for_timeout(300)
    print('  화면의 배지:', badge_on_stage(pg))
    pg.click('[data-save-badge]'); pg.wait_for_timeout(300); m = mine(pg)
    need(m == [['아래 구매링크확인', 'rgb(31, 75, 255)']], f'① 저장하면 내 배지에 문구·색 그대로 생긴다 {m}')
    need('저장했습니다' in pg.inner_text('[data-save-badge]'), '① 저장 확인 문구가 뜬다')
    pg.locator('.scene-decoration-panel, .dec-panel, details:has(.dec-my-badges)').first.screenshot(path=str(out / 'my_badges_panel.png'))
    # ② 도형(배지 아님)을 고르면 저장 버튼이 안 보인다
    pg.click('[data-dec-kit="graphic"]') if pg.locator('[data-dec-kit="graphic"]').count() else pg.evaluate("[...document.querySelectorAll('[data-dec-kit]')].find(b=>b.textContent.includes('도형')).click()")
    pg.wait_for_timeout(200); pg.evaluate("[...document.querySelectorAll('[data-add-graphic]')][1].click()"); pg.wait_for_timeout(300)
    need(not pg.locator('[data-save-badge]').is_visible(), '② 도형을 고르면 저장 버튼이 숨는다')
    # ③ 새로고침해도 남고, 눌러서 추가하면 문구·색·모양이 그대로
    pg.reload(wait_until='networkidle'); open_badges(pg); m = mine(pg); need(len(m) == 1 and m[0][0] == '아래 구매링크확인', f'③ 새로고침 뒤에도 내 배지가 남는다 {m}')
    before = len(badge_on_stage(pg)); pg.click('[data-add-my-badge="0"]'); pg.wait_for_timeout(400); st = badge_on_stage(pg)
    need(len(st) == before + 1 and st[-1] == ['아래 구매링크확인', '#1f4bff', 'ticket'], f'③ 내 배지를 누르면 같은 문구·색·모양으로 추가된다 {st[-1:]}')
    # ④ 같은 문구를 다시 저장하면 늘지 않고 바뀐다 / 다른 문구는 앞에 쌓인다
    pg.select_option('[data-dec="badgeStyle"]', 'burst'); pg.click('[data-save-badge]'); pg.wait_for_timeout(300)
    saved = json.loads(pg.evaluate("localStorage.getItem('scene_style_my_badges')")); need(len(saved) == 1 and saved[0]['badgeStyle'] == 'burst', f'④ 같은 문구 재저장 = 1개 유지·내용 갱신 {saved}')
    pg.fill('[data-dec="text"]', '오늘만 특가'); pg.dispatch_event('[data-dec="text"]', 'input'); pg.dispatch_event('[data-dec="text"]', 'change'); pg.click('[data-save-badge]'); pg.wait_for_timeout(300)
    need([x[0] for x in mine(pg)] == ['오늘만 특가', '아래 구매링크확인'], f'④ 새 문구는 맨 앞에 {[x[0] for x in mine(pg)]}')
    # ⑤ 저장값 서버 검증 + 지우기
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); from shopping_shorts import scene_style
    snap = pg.evaluate('window.sceneStyle.snapshot()'); scene_style.validate_snapshot(json.loads(json.dumps(snap))); need(True, '⑤ 내 배지로 넣은 장면 저장값이 서버 검증을 통과한다')
    pg.click('[data-del-my-badge="0"]'); pg.wait_for_timeout(300); need([x[0] for x in mine(pg)] == ['아래 구매링크확인'], f'⑤ ×로 지우면 그 배지만 사라진다 {[x[0] for x in mine(pg)]}')
    pg.click('[data-del-my-badge="0"]'); pg.wait_for_timeout(300); need(pg.evaluate("document.querySelector('.dec-my-badges').hidden"), '⑤ 다 지우면 내 배지 칸이 다시 숨는다')
    # ⑥ 깨진 저장값이 있어도 편집기가 죽지 않는다
    pg.evaluate("localStorage.setItem('scene_style_my_badges','{깨진값')"); pg.reload(wait_until='networkidle'); open_badges(pg)
    need(pg.locator('[data-add-badge="주목"]').is_visible(), '⑥ 깨진 저장값이어도 배지 목록이 정상으로 뜬다')
    need(not errs, f'페이지 오류 {errs[:3]}'); b.close()
print('\n실패', fails or '없음'); sys.exit(1 if fails else 0)
