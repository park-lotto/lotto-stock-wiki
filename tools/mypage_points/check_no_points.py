"""마이페이지·API 설명서에 **보이는** 포인트 문구가 없는지 — 진짜 앱(격리 DB)·진짜 브라우저로 잰다.
  py tools/mypage_points/check_no_points.py <출력폴더>
사장님(2026-09-27): "지금 포인트 제도는 렌즈10회/랜더10회만 쓰고 나머지는 안 쓴다 — 마이페이지·API에 포인트 관련 내용이 있으면 삭제".
  ① 마이페이지 모든 탭의 보이는 글에 '포인트'·'NP'(예: 50P, 0P) 없음
  ② '포인트' 탭 버튼이 없다(누를 수 없다)
  ③ 키 등록 탭이 여전히 뜬다(서비스 카드 ≥5장·입력칸·버튼)
  ④ 내 계정 탭에 하루 한도(렌즈·렌더)가 그대로 보인다
  ⑤ API 설명서 보이는 글에 '포인트' 없음 ⑥ 두 페이지 콘솔 오류 0"""
import sys, re, time, shutil, threading, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / '_work'; shutil.rmtree(work, ignore_errors=True); work.mkdir()
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright
module.DB_PATH = str(work / 'qa.db'); module._AUTH_ON = False; module.keycrypt.enabled = lambda: True
PORT = 8799; BASE = f'http://127.0.0.1:{PORT}'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)
PT = re.compile(r'포인트|\b\d+\s?P\b')
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1400, 'height': 1000}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(f'{BASE}/settings.html', wait_until='networkidle'); pg.wait_for_timeout(1200)
    tabs = pg.evaluate("[...document.querySelectorAll('button.tab')].filter(b=>b.offsetParent!==null).map(b=>b.id+':'+b.innerText.trim())")
    print('   보이는 탭:', tabs)
    need(not any('포인트' in t for t in tabs), f'② 포인트 탭 버튼 없음 ({tabs})')
    hits = {}
    for t in tabs:
        tid = t.split(':')[0]
        pg.click('#' + tid); pg.wait_for_timeout(700)
        txt = pg.evaluate("document.querySelector('main')?document.querySelector('main').innerText:document.body.innerText")
        found = sorted(set(m.group(0) for m in PT.finditer(txt)))
        if found:
            lines = [l.strip() for l in txt.split('\n') if PT.search(l)][:4]
            hits[tid] = lines
        pg.screenshot(path=str(out / f'settings_{tid}.png'), full_page=True)
    need(not hits, f'① 마이페이지 보이는 글에 포인트 문구 없음 {hits}')
    kt = next((t.split(':')[0] for t in tabs if '키' in t), None)
    if kt:
        pg.click('#' + kt); pg.wait_for_timeout(800)
        cards = pg.locator('#paneKeys .svcCard:visible').count()
        inputs = pg.locator('#paneKeys textarea:visible, #paneKeys input:visible').count()
        need(cards >= 5 and inputs >= 4, f'③ 키 등록 탭 정상 (카드 {cards}·입력칸 {inputs})')
    else:
        need(False, '③ 키 등록 탭을 못 찾음')
    at = next((t.split(':')[0] for t in tabs if '계정' in t), None)
    if at:
        pg.click('#' + at); pg.wait_for_timeout(800)
        txt = pg.evaluate("document.body.innerText")
        need(('렌즈' in txt) and ('영상 제작' in txt), f'④ 내 계정 탭에 하루 한도(영상 제작·렌즈) 보임')
    need(not errs, f'⑥ 마이페이지 콘솔 오류 {errs[:3]}'); errs.clear()
    pg.goto(f'{BASE}/api_manual.html', wait_until='networkidle'); pg.wait_for_timeout(600)
    txt = pg.inner_text('body')
    lines = [l.strip() for l in txt.split('\n') if PT.search(l)][:4]
    need(not lines, f'⑤ API 설명서 보이는 글에 포인트 없음 {lines}')
    need(not errs, f'⑥ 설명서 콘솔 오류 {errs[:3]}')
    # ⑦ 마이페이지 '설치와 준비' 카드가 데려가는 /setup 전문에도 포인트 문구 없음 + 하루 한도 안내 있음
    pg.goto(f'{BASE}/setup', wait_until='networkidle'); pg.wait_for_timeout(600)
    txt = pg.inner_text('body')
    lines = [l.strip() for l in txt.split(chr(10)) if PT.search(l)][:4]
    need(not lines, f'⑦ /setup 보이는 글에 포인트 없음 {lines}')
    need('하루 이용 한도' in txt and '렌즈로 찾기 하루 10번' in txt, '⑦ /setup에 하루 한도(렌즈 10번·영상 10편) 안내')
    pg.screenshot(path=str(out / 'setup.png'), full_page=True)
    b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
