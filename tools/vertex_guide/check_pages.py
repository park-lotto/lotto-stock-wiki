"""Vertex 안내 — 설명서·설정 화면을 진짜 앱(격리 DB)·진짜 브라우저로 확인한다.
  py tools/vertex_guide/check_pages.py <출력폴더>
  ① api_manual.html#vertex: 영상이 실제로 재생(시간 흐름)·새 문구(Agent Platform·2단계 인증·개인) 있음·옛 문구 없음
  ② /landing/vertex_guide.mp4·jpg 비로그인으로 200(로그인 켠 상태에서)
  ③ settings.html#keys: 「▶ 받는 방법 영상」 → 새 탭으로 영상 주소가 열린다
  ④ 두 페이지 콘솔 오류 0
  ⑧ 자동 설정(관제 096): 설명서·설정의 명령 글자 = 스크립트 머리말 명령, 「명령 복사」가 클립보드에 그 글자를 넣는다,
     클라우드 셸 버튼은 실제로 열리는 주소(show=ide,terminal — show=terminal만은 안 열림 2026-10-03), /landing/vertex_setup.sh 비로그인 200·파일과 같다,
     옛 5단계는 「직접 하기」로 접혀 처음엔 안 보인다
  ⑨ 4단계(관제 119): 설명서 ⑧ 보이는 단계 1·2·3·4 + 제목 = 마이페이지 ①~④ 순서, 영상 = 4단계판(약 73초)"""
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
for path in ('/landing/vertex_guide.mp4', '/landing/vertex_guide.jpg', '/api_manual.html', '/landing/vertex_setup.sh'):
    try:
        r = urllib.request.urlopen(BASE + path); code = r.status; n = len(r.read())
    except urllib.error.HTTPError as e:
        code, n = e.code, 0
    need(code == 200 and n > 1000, f'② 비로그인 {path} → {code} ({n}바이트)')
SCRIPT = ROOT / 'shopping_shorts/static/landing/vertex_setup.sh'
served = urllib.request.urlopen(BASE + '/landing/vertex_setup.sh').read()
need(served == SCRIPT.read_bytes(), '⑧ 서버가 주는 스크립트 = 파일 그대로(줄바꿈 포함)')
CMD = next(l for l in SCRIPT.read_text(encoding='utf-8').splitlines() if l.startswith('#   curl ')).lstrip('# ').strip()
module._AUTH_ON = False

with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(viewport={'width': 1300, 'height': 1000}, permissions=['clipboard-read', 'clipboard-write'])
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(f'{BASE}/api_manual.html#vertex', wait_until='networkidle'); pg.wait_for_timeout(800)
    # ⑧ 자동 설정 카드
    need(pg.locator('#vertex-auto').is_visible(), '⑧ 설명서: 자동 설정 카드가 보인다')
    need(pg.inner_text('#vertexCmd').strip() == CMD, f'⑧ 설명서 명령 = 스크립트 명령 ({CMD})')
    need(pg.get_attribute('#vertexShellLink', 'href') == 'https://shell.cloud.google.com/?show=ide%2Cterminal', '⑧ 설명서 클라우드 셸 버튼 = 열리는 주소(편집기+터미널, 2026-10-03 show=terminal만은 안 열림)')
    pg.evaluate("navigator.clipboard.writeText('')"); pg.click('#vertexCmdCopy'); pg.wait_for_timeout(300)
    need(pg.evaluate('navigator.clipboard.readText()') == CMD, '⑧ 설명서 「명령 복사」 → 클립보드에 명령')
    need(not pg.locator('#vertex-manual').evaluate('d=>d.open') and not pg.locator('#vertex-manual .card').first.is_visible(),
         '⑧ 옛 5단계는 처음엔 접혀 있다')
    pg.screenshot(path=str(out / 'manual_vertex_auto.png'), full_page=False)
    pg.locator('#vertex-auto').screenshot(path=str(out / 'manual_vertex_auto_card.png'))
    pg.locator('#vertex-manual > summary').click(); pg.wait_for_timeout(200)
    txt = pg.inner_text('body')
    for s in ('Agent Platform API', 'Agent Platform 사용자', '2단계 인증', '「개인」', '마이페이지 › 🔑 내 키 등록', '결제 계정 폐쇄', '무료 체험판 계정', '결제 연결 확인', '결제 계정 연결'):
        need(s in txt, f'① 새 문구 있음: {s}')
    need('Vertex AI API 열기' not in txt, '① 옛 버튼 문구(Vertex AI API 열기) 없음')
    need('⑧ 구글 버텍스 API' in txt and '사람이 몰리는' not in txt and '그대로 쓰실 수 있습니다' not in txt, '⑦ 설명서 ⑧ 제목·문구')
    v = pg.locator('video[src^="/landing/vertex_guide.mp4"]')
    need(v.count() == 1, '① 영상 태그 1개')
    v.scroll_into_view_if_needed()
    t = pg.evaluate("""async()=>{const v=document.querySelector('video[src^="/landing/vertex_guide.mp4"]');v.muted=true;
        await v.play();await new Promise(r=>setTimeout(r,2500));return {t:v.currentTime,d:v.duration,w:v.videoWidth,err:v.error&&v.error.code}}""")
    need(t['t'] > 1 and t['w'] == 1920 and abs(t['d'] - DUR) < 1 and not t['err'], f'① 영상이 실제로 재생된다 {t}')
    pg.screenshot(path=str(out / 'manual_vertex.png'))
    # ⑤ 되감기 — 앞으로 갔다가 뒤로(2026-09-27 사장님 "뒤로 이동이 안 먹힌다"): 요청한 위치로 실제로 가는지
    sk = pg.evaluate("""async()=>{const v=document.querySelector('video[src^="/landing/vertex_guide.mp4"]');
        const go=t=>new Promise(r=>{v.addEventListener('seeked',()=>r(v.currentTime),{once:true});v.currentTime=t;});
        const a=await go(60); const b=await go(5); return {fwd:a,back:b,seekable:v.seekable.length?v.seekable.end(0):0}}""")
    need(abs(sk['fwd'] - 60) < 1 and abs(sk['back'] - 5) < 1 and sk['seekable'] > DUR - 1, f'⑤ 앞·뒤로 이동된다 {sk}')
    need(not errs, f'④ 설명서 콘솔 오류 {errs[:3]}')
    # ⑨ 4단계(관제 119, 2026-10-05 사장님 "4단계 설명법으로 모두"): 설명서 ⑧의 보이는 번호 카드 = 1·2·3·4 순서, 5 없음,
    #    제목이 마이페이지 ①~④(가입·셸 열기·명령 붙여넣기·붙여넣고 연결)와 같은 뜻
    steps = pg.evaluate("""()=>{const sec=document.getElementById('vertex');const out=[];let el=sec.nextElementSibling;
        while(el && !(el.classList.contains('svc') && el.id!=='vertex')){
          if(el.classList.contains('card') && !el.closest('details')){const n=el.querySelector('.num');const h=el.querySelector('h3');
            if(n && /^[0-9]$/.test(n.textContent.trim())) out.push([n.textContent.trim(), h? h.innerText.replace(/\s+/g,' '):'']);}
          el=el.nextElementSibling;}
        return out}""")
    need([x[0] for x in steps] == ['1', '2', '3', '4'], f'⑨ 설명서 ⑧ 보이는 단계 = 1·2·3·4 ({steps})')
    want = ['무료 체험', '클라우드 셸', '명령 복사', '연결']
    need(len(steps) == 4 and all(w in steps[i][1] for i, w in enumerate(want)), f'⑨ 단계 제목이 마이페이지 ①~④와 같은 순서 ({[x[1] for x in steps]})')
    need(70 < DUR < 80, f'⑨ 영상 = 4단계판(약 73초, 지금 {DUR:.1f}초 — 옛 5단계판은 132.7초)')
    errs.clear()
    pg2 = ctx.new_page(); pg2.on('pageerror', lambda e: errs.append(str(e)))
    pg2.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg2.goto(f'{BASE}/settings.html#keys', wait_until='networkidle'); pg2.wait_for_timeout(1200)
    btn = pg2.locator('#vertexCard button', has_text='받는 방법 영상')
    need(btn.count() == 1 and btn.is_visible(), '③ 설정 Vertex 카드에 「▶ 받는 방법 영상」 버튼이 보인다')
    with ctx.expect_page() as newp:
        btn.click()
    np_ = newp.value; np_.wait_for_load_state()
    need('/landing/vertex_guide.mp4' in np_.url, f'③ 누르면 영상이 새 탭으로 열린다 ({np_.url})')
    pg2.locator('#vertexCard').screenshot(path=str(out / 'settings_vertex_card.png'))
    # ⑦ 2026-09-27 사장님 문구: 제목 「구글 버텍스 API」, (선택)·'사람이 몰리는'·'안 하셔도 지금처럼' 없음
    vt = pg2.inner_text('#vertexCard')
    need('구글 버텍스 API' in vt and '(선택)' not in vt and '사람이 몰리는' not in vt and '안 하셔도' not in vt and '오류와 버그' in vt,
         f'⑦ 버텍스 카드 문구({vt.splitlines()[0] if vt else ""})')
    # ⑧ 설정 자동 설정 칸
    need(pg2.locator('#vertexAuto').is_visible(), '⑧ 설정: 자동 설정 칸이 보인다')
    need(pg2.inner_text('#vertexCmd').strip() == CMD, '⑧ 설정 명령 = 스크립트 명령')
    need(pg2.get_attribute('#vertexShellBtn', 'href') == 'https://shell.cloud.google.com/?show=ide%2Cterminal', '⑧ 설정 클라우드 셸 버튼 = 열리는 주소(편집기+터미널)')
    pg2.evaluate("navigator.clipboard.writeText('')"); pg2.click('#vertexCmdBtn'); pg2.wait_for_timeout(300)
    need(pg2.evaluate('navigator.clipboard.readText()') == CMD, '⑧ 설정 「명령 복사」 → 클립보드에 명령')
    pg2.locator('#vertexCard').screenshot(path=str(out / 'settings_vertex_card.png'))
    at = pg2.inner_text('#vertexAuto')
    need(all(c in at for c in '①②③④') and '⑤' not in at, '⑨ 마이페이지 버텍스 칸 = ①~④ 4단계')
    need(not errs, f'④ 설정 콘솔 오류 {errs[:3]}')
    b.close()
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건 {fails}')
sys.exit(1 if fails else 0)
