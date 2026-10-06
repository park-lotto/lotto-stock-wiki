"""구매링크 롱폼 라이브 실측(관제 133) — 관리자로 실제 작업에 안내를 저장하고, 서버에서 롱폼을 실제로 구워, 받은 영상을 검사 도구로 대조한다.

  py tools/live_link_longform.py <관리자 소유 작업 id> <결과 폴더> [세트 id=time]

  ① 편집기(라이브 자산): 탭·문구 6가지가 보이고, 문구를 고르면 서버에 저장된다(저장은 편집기 화면이 직접 보낸다)
  ② 9단계 상태: custom=true · 아직 안 만든 상태 → 「롱폼으로 렌더」 시작 → ready 까지 기다린다
  ③ 서버의 완성 쇼츠·롱폼을 받아 tools/link_longform_check.py 로 대조(자리·문구·시계 숫자)
★남의 작업에 쓰지 마라 — 안내 저장과 롱폼 파일이 그 작업 폴더에 남는다. 관리자(사장님) 시험 작업으로만.
"""
import sys, json, time, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from tools.live_admin import admin_page, KEY, HOST, BASE

job, out = sys.argv[1], pathlib.Path(sys.argv[2]).resolve(); out.mkdir(parents=True, exist_ok=True)
set_id = sys.argv[3] if len(sys.argv) > 3 else 'time'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg, flush=True)
    if not ok: fails.append(msg)

J = "(u,o)=>fetch(u,o).then(async r=>({s:r.status,d:await r.json().catch(()=>null)}))"
with admin_page("produce") as pg:
    r = pg.evaluate(J, f'/api/mix/longform_layout/{job}')
    need(r['s'] == 200 and r['d'] and r['d'].get('ok'), f"⓪ 저장 경로가 열려 있다 (HTTP {r['s']})")
    if r['s'] != 200: sys.exit(2)
    # ① 편집기: 이 작업의 장면꾸미기를 라이브 자산으로 연다
    ctx = pg.evaluate(J, f'/api/produce/scene-style/context/{job}')
    if ctx['s'] == 200:
        c = ctx['d']
        pg.goto(BASE + '/api/produce/scene-style/assets/out/scene-style-ui-showcase.html', wait_until='networkidle'); pg.wait_for_timeout(1500)
        pg.evaluate('([c,s])=>window.sceneStyle.load(c,s)', [c['context'], c['snapshot']]); pg.wait_for_timeout(1500)
        need(c['context'].get('linkGuide') is True and pg.locator('[data-lf-tabs] button').count() == 2, '① 편집기에 숏폼/롱폼 탭이 있다')
        pg.wait_for_function("document.querySelectorAll('[data-lf-set]').length>0", timeout=20000)
        need(pg.evaluate("document.querySelectorAll('[data-lf-set]').length") == 6, '① 효과 탭에 롱폼 문구 6가지')
        pg.evaluate(f"document.querySelector('[data-lf-set=\"{set_id}\"]').click()"); pg.wait_for_timeout(2500)
        need('저장됐어요' in pg.evaluate("document.querySelector('[data-lf-status]').textContent"), f"① 문구를 고르면 저장된다 ({pg.evaluate('document.querySelector(`[data-lf-status]`).textContent')[:30]})")
        pg.locator('.scene-longform').screenshot(path=str(out / 'live_롱폼탭.png'))
        pg.goto(BASE + '/produce', wait_until='domcontentloaded'); pg.wait_for_timeout(1500)
    else:
        print(f"  (편집기 context HTTP {ctx['s']} — 이 작업은 편집기로 못 연다. 저장 경로로 직접 넣는다)")
        lf = pg.context.new_page(); lf.goto(BASE + '/api/produce/scene-style/assets/out/link-longform-stage.html', wait_until='networkidle')
        items = lf.evaluate(f"(linkLongform.useSet('{set_id}'), linkLongform.items())"); lf.close()
        r = pg.evaluate(J, [f'/api/mix/longform_layout/{job}', {'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': json.dumps({'items': items})}]) if False else \
            pg.evaluate("([u,b])=>fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:b}).then(async r=>({s:r.status,d:await r.json()}))", [f'/api/mix/longform_layout/{job}', json.dumps({'items': items})])
        need(r['s'] == 200 and len(r['d']['items']) == 3, f"① 저장 경로로 안내 3개 저장 (HTTP {r['s']})")
    saved = pg.evaluate(J, f'/api/mix/longform_layout/{job}')['d']['items']
    need([m['block'] for m in saved] == ['arrow', 'arrow', 'band'], f"① 서버에 저장된 항목 {[m['block'] for m in saved]}" + (' · 시계 ' + str(saved[2].get('clock')) if saved and saved[-1].get('clock') else ''))
    (out / 'layout.json').write_text(json.dumps({'items': saved}, ensure_ascii=False), encoding='utf-8')
    # ② 굽기
    st = pg.evaluate(J, f'/api/mix/longform_link/{job}')['d']
    need(st.get('custom') is True, f"② 9단계 상태: 꾸민 안내 있음(custom) · 상태 {st.get('state')}")
    t0 = time.time()
    st = pg.evaluate("u=>fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.json())", f'/api/mix/longform_link/{job}')
    while st.get('state') == 'running' and time.time() - t0 < 900:
        pg.wait_for_timeout(5000); st = pg.evaluate(J, f'/api/mix/longform_link/{job}')['d']
    need(st.get('state') == 'ready', f"② 서버가 롱폼을 구웠다 — {st.get('state')} ({time.time() - t0:.0f}초) {st.get('error') or ''}")
if fails: print('\n결과: 실패', len(fails), '건'); sys.exit(1)
# ③ 받은 영상 대조
q = ("python3 -c \"import sqlite3;c=sqlite3.connect('file:/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db?mode=ro',uri=True);"
     f"print(c.execute('select video_path from mix_jobs where job_id=?',('{job}',)).fetchone()[0])\"")
vp = subprocess.run(['ssh', '-o', 'ConnectTimeout=15', '-i', KEY, HOST, q], capture_output=True, text=True, timeout=60).stdout.strip()
for remote, name in ((vp, 'src.mp4'), (f'/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs/{job}/final_longform.mp4', 'longform.mp4')):
    subprocess.run(['scp', '-q', '-o', 'ConnectTimeout=15', '-i', KEY, f'{HOST}:{remote}', str(out / name)], check=True, timeout=600)
run = subprocess.run([sys.executable, str(ROOT / 'tools/link_longform_check.py'), str(out / 'src.mp4'), str(out / 'longform.mp4'), str(out / 'layout.json')],
                     capture_output=True, text=True, encoding='utf-8', errors='replace', env={**__import__('os').environ, 'PYTHONIOENCODING': 'utf-8'})
print(run.stdout[-1500:], run.stderr[-500:])
need(run.returncode == 0, '③ 받은 롱폼 = 원본 쇼츠 + 저장한 안내(검사 도구 전부 통과)')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건'); sys.exit(1 if fails else 0)
