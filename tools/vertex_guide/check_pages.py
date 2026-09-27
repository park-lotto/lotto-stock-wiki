"""Vertex 안내 — 설명서·설정 화면을 진짜 앱(격리 DB)·진짜 브라우저로 확인한다.
  py tools/vertex_guide/check_pages.py <출력폴더>
  ① api_manual.html#vertex: 영상이 실제로 재생(시간 흐름)·새 문구(Agent Platform·2단계 인증·개인) 있음·옛 문구 없음
  ② /landing/vertex_guide.mp4·jpg 비로그인으로 200(로그인 켠 상태에서)
  ③ settings.html#keys: 「▶ 받는 방법 영상」 → 새 탭으로 영상 주소가 열린다
  ④ 두 페이지 콘솔 오류 0"""
import sys, time, shutil, threading, pathlib, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
work = out / '_work'; shutil.rmtree(work, ignore_errors=True); work.mkdir()
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright
module.DB_PATH = str(work / 'qa.db'); module.keycrypt.enabled = lambda: True
import subprocess
DUR = float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(ROOT/'shopping_shorts/static/landing/vertex_guide.mp4')],capture_output=True,text=True).stdout)
PORT = 8798; BASE = f'http://127.0.0.1:{PORT}'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=PORT, log_level='warning'))
threading.Thread(target=server.run, daemon=True).start(); time.sleep(1.5)

# ② 로그인 켠 상태에서 비로그인 요청
auth_was = module._AUTH_ON; module._AUTH_ON = True
for path in ('/landing/vertex_guide.mp4', '/landing/vertex_guide.jpg', '/api_manual.html'):
    try:
        r = urllib.request.urlopen(BASE + path); code = r.status; n = len(r.read())
    except urllib.error.HTTPError as e:
        code, n = e.code, 0
    need(code == 200 and n > 1000, f'② 비로그인 {path} → {code} ({n}바이트)')
module._AUTH_ON = False

with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(viewport={'width': 1300, 'height': 1000})
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(f'{BASE}/api_manual.html#vertex', wait_until='networkidle'); pg.wait_for_timeout(800)
    txt = pg.inner_text('body')
    for s in ('Agent Platform API', 'Agent Platform 사용자', '2단계 인증', '「개인」', '마이페이지 › 🔑 내 키 등록', '결제 계정 폐쇄', '무료 체험판 계정'):
        need(s in txt, f'① 새 문구 있음: {s}')
    need('Vertex AI API 열기' not in txt, '① 옛 버튼 문구(Vertex AI API 열기) 없음')
    need('⑧ 구글 버텍스 API' in txt and '사람이 몰리는' not in txt and '그대로 쓰실 수 있습니다' not in txt, '⑦ 설명서 ⑧ 제목·문구')
    v = pg.locator('video[src="/landing/vertex_guide.mp4"]')
    need(v.count() == 1, '① 영상 태그 1개')
    v.scroll_into_view_if_needed()
    t = pg.evaluate("""async()=>{const v=document.querySelector('video[src="/landing/vertex_guide.mp4"]');v.muted=true;
        await v.play();await new Promise(r=>setTimeout(r,2500));return {t:v.currentTime,d:v.duration,w:v.videoWidth,err:v.error&&v.error.code}}""")
    need(t['t'] > 1 and t['w'] == 1920 and abs(t['d'] - DUR) < 1 and not t['err'], f'① 영상이 실제로 재생된다 {t}')
    pg.screenshot(path=str(out / 'manual_vertex.png'))
    # ⑤ 되감기 — 앞으로 갔다가 뒤로(2026-09-27 사장님 "뒤로 이동이 안 먹힌다"): 요청한 위치로 실제로 가는지
    sk = pg.evaluate("""async()=>{const v=document.querySelector('video[src="/landing/vertex_guide.mp4"]');
        const go=t=>new Promise(r=>{v.addEventListener('seeked',()=>r(v.currentTime),{once:true});v.currentTime=t;});
        const a=await go(60); const b=await go(5); return {fwd:a,back:b,seekable:v.seekable.length?v.seekable.end(0):0}}""")
    need(abs(sk['fwd'] - 60) < 1 and abs(sk['back'] - 5) < 1 and sk['seekable'] > DUR - 1, f'⑤ 앞·뒤로 이동된다 {sk}')
    need(not errs, f'④ 설명서 콘솔 오류 {errs[:3]}')
    errs.clear()
    pg2 = ctx.new_page(); pg2.on('pageerror', lambda e: errs.append(str(e)))
    pg2.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg2.goto(f'{BASE}/settings.html#keys', wait_until='networkidle'); pg2.wait_for_timeout(1200)
    btn = pg2.locator('#vertexCard button', has_text='받는 방법 영상')
    need(btn.count() == 1 and btn.is_visible(), '③ 설정 Vertex 카드에 「▶ 받는 방법 영상」 버튼이 보인다')
    with ctx.expect_page() as newp:
        btn.click()
    np_ = newp.value; np_.wait_for_load_state()
    need(np_.url.endswith('/landing/vertex_guide.mp4'), f'③ 누르면 영상이 새 탭으로 열린다 ({np_.url})')
    pg2.locator('#vertexCard').screenshot(path=str(out / 'settings_vertex_card.png'))
    # ⑦ 2026-09-27 사장님 문구: 제목 「구글 버텍스 API」, (선택)·'사람이 몰리는'·'안 하셔도 지금처럼' 없음
    vt = pg2.inner_text('#vertexCard')
    need('구글 버텍스 API' in vt and '(선택)' not in vt and '사람이 몰리는' not in vt and '안 하셔도' not in vt and '오류와 버그' in vt,
         f'⑦ 버텍스 카드 문구({vt.splitlines()[0] if vt else ""})')
    need(not errs, f'④ 설정 콘솔 오류 {errs[:3]}')
    b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
