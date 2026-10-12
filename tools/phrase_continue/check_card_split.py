# -*- coding: utf-8 -*-
"""구절 맞춤 칸: 카드가 이어지고, X는 그 카드 한 장만 빼는지 — 라이브 작업 그대로·진짜 화면·진짜 저장·진짜 렌더 계획.
  ../../.venv/Scripts/python.exe tools/phrase_continue/check_card_split.py <dump.sqlite> [--job 44cdff8f7502 --beat 4]

2026-09-26 사장님 제보(작업 c0c8fa382d07 = job 44cdff8f7502 칸5): 0.9초 조각에 구절 2개(1.6+1.5초)가 붙어
  ① 두 번째 카드가 미리보기에서 멈추고(0.1초를 1.5초로) ② 카드 두 장이 같은 그림 ③ 1.5초 카드만 X를 눌러도 둘 다 사라졌다.
확인:
  ① 두 카드가 원본을 이어서 튼다(뒤 카드 시작 = 앞 카드 끝, 멈춤 없음)
  ② 두 카드 썸네일 주소가 다르다(뒤 카드는 자기 구간의 그림)
  ③ 뒤 카드 X → 앞 카드는 그대로 남고 칸이 비지 않는다
  ④ 저장(/apply)까지 실제로 태운 뒤 서버 렌더 계획 = 화면 계획
  ⑤ 앞 카드 📦 → 교체 대상이 쪼갠 조각 하나(다른 카드와 안 묶임)
POST는 /apply만 통과(격리 DB, 유료 호출 없음).
"""
import sys, os, json, time, shutil, sqlite3, threading, pathlib, argparse
ROOT = pathlib.Path(os.environ.get("PC_ROOT") or pathlib.Path(__file__).resolve().parents[2]); sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser()
ap.add_argument('dump'); ap.add_argument('--job', default='44cdff8f7502'); ap.add_argument('--beat', type=int, default=4)
ap.add_argument('--port', type=int, default=8795); ap.add_argument('--out', default='')
args = ap.parse_args()
work = pathlib.Path(args.out or (pathlib.Path(args.dump).parent / 'card_split')).resolve()
shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
db = work / 'qa.db'; shutil.copyfile(args.dump, db)
con = sqlite3.connect(db); DUR = {}; SRC = {}
for jid, kind, key, sec in con.execute('select job_id, kind, key, sec from durations'):
    if kind == 'src': SRC.setdefault(jid, {})[key] = sec; DUR[f'/fake/{jid}/{key}.mp4'] = sec
    else: DUR[key] = sec
con.close()
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright
module.DB_PATH = str(db); module._AUTH_ON = False
module._MIX_WORK_DIR = work / 'mixwork'; module._THUMB_DIR = work / 'thumbs'
va._probe_duration = lambda p: DUR.get(str(p).replace('\\', '/'), 0.0) or DUR.get(str(p), 0.0)
module._resolve_sources = lambda job, w: {v: pathlib.Path(f'/fake/{job["job_id"]}/{v}.mp4') for v in SRC.get(job['job_id'], {})}
server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=args.port, log_level='error'))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started: break
    time.sleep(.2)
BASE = f'http://127.0.0.1:{args.port}'; J, I = args.job, args.beat
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
CLIPS = f'''() => planClips(lists[{I}] || [], beatDur({I}), STRETCH[{I}], {I}).map(c => ({{seg: c.seg_id, vid: c.video_id,
    start: +(+c.start).toFixed(3), src: +(+(c.src_dur || c.dur)).toFixed(3), out: +(+c.dur).toFixed(3)}}))'''
IMGS = f'''() => [...document.querySelectorAll('button.delx[onclick*="dropCardAt({I}, "]')].map(b => b.closest('.tbcut').querySelector('img').getAttribute('src'))'''
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 1500, 'height': 1000})
        ctx.route('**/*', lambda r: r.continue_() if (r.request.method in ('GET', 'HEAD') or r.request.url.endswith('/apply')) else r.abort())
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'{BASE}/scene_lab.html?job={J}', wait_until='domcontentloaded')
        pg.wait_for_function('typeof _booting!=="undefined" && _booting===false', timeout=30000)
        c0 = pg.evaluate(CLIPS); imgs0 = pg.evaluate(IMGS)
        print('  처음 카드:', c0)
        need(len(c0) == 2 and abs(c0[1]['start'] - (c0[0]['start'] + c0[0]['src'])) < 0.02 and all(c['src'] >= c['out'] * 0.95 for c in c0),
             f'① 두 카드가 원본을 이어서 튼다(뒤 시작=앞 끝, 멈춤 없음) — 고치기 전엔 뒤 카드가 0.1초를 늘려 틀었다')
        need(len(imgs0) == 2 and imgs0[0] != imgs0[1], f'② 카드 썸네일 주소가 서로 다르다 {imgs0}')
        # ⑥ 앞 카드 📦(진짜 버튼) → 교체 → 앞 카드만 바뀌고 뒤 카드는 그대로
        pg.click(f'button.boxbtn[onclick*="tlReplaceToggle({I},0)"]'); pg.wait_for_timeout(500)
        ids_b = pg.evaluate(f'lists[{I}].slice()'); cb = pg.evaluate(CLIPS)
        need(len(ids_b) == 2 and all(x.startswith('film_') for x in ids_b) and abs(cb[1]['start'] - c0[1]['start']) < 0.02,
             f'⑥ 📦를 누르면 카드마다 조각이 따로 된다(화면은 그대로) {ids_b}')
        L = round(cb[0]['out'], 2)
        pg.evaluate(f"replaceRoll(lists[{I}][0], '{c0[0]['vid']}', {{s: 2.0, e: {2.0 + L}}})"); pg.wait_for_timeout(400)
        cr = pg.evaluate(CLIPS)
        print('  📦 교체 뒤:', cr)
        need(abs(cr[0]['start'] - 2.0) < 0.02 and abs(cr[1]['start'] - c0[1]['start']) < 0.02,
             '⑥ 📦 교체는 앞 카드만 바꾸고 뒤 카드(13.26초~)는 그대로 — 고치기 전엔 조각 단위라 둘 다 바뀌었다')
        # ③ 뒤 카드 X — 진짜 버튼
        pg.click(f'button.delx[onclick*="dropCardAt({I}, 1,"]'); pg.wait_for_timeout(500)
        c1 = pg.evaluate(CLIPS); ids1 = pg.evaluate(f'lists[{I}].slice()')
        print('  X 뒤 카드:', c1, '목록:', ids1)
        need(len(ids1) == 1 and ids1[0].startswith('film_') and len(c1) >= 1 and abs(c1[0]['start'] - 2.0) < 0.02,
             '③ 뒤 카드만 빠지고 앞 카드(교체한 2.0초 장면)는 남는다 — 고치기 전엔 칸이 통째로 비었다')
        # ④ 진짜 저장 → 서버 렌더 계획
        res = pg.evaluate('async () => { try { await applyServer(); return "ok"; } catch (e) { return String(e); } }')
        pg.wait_for_timeout(800)
        beat = [x for x in (Store(str(db)).get_mix_job(J).get('edit_plan') or {}).get('beats', []) if x.get('beat_idx') == I][0]
        mats = [m.get('seg_id') for m in va._beat_material(beat)]
        sp = va.plan_beat_clips_for(beat, DUR.get(beat.get('tts_path') or '', 0.0), SRC.get(J, {}))
        spv = [{'vid': c['video_id'], 'start': round(c['start'], 3), 'src': round(c['src_dur'], 3), 'out': round(c['out_dur'], 3)} for c in sp]
        print('  저장 결과', res, '서버 재료:', mats, '서버 계획:', spv)
        need(mats == ids1, f'④ 서버에 저장된 재료 = 화면 목록 ({mats})')
        same = len(spv) == len(c1) and all(x['vid'] == y['vid'] and abs(x['start'] - y['start']) <= 0.03 and abs(x['src'] - y['src']) <= 0.06 for x, y in zip(spv, c1))
        need(same, '④ 서버 렌더 계획 = 화면 계획')
        # ⑤ 새로 열어 앞 카드 📦 — 쪼갠 조각 하나만 대상
        pg.goto(f'{BASE}/scene_lab.html?job={J}', wait_until='domcontentloaded')
        pg.wait_for_function('typeof _booting!=="undefined" && _booting===false', timeout=30000)
        c2 = pg.evaluate(CLIPS)
        print('  다시 연 뒤 카드:', c2)
        need(len(c2) == len(c1) and all(abs(x['start'] - y['start']) < 0.02 for x, y in zip(c2, c1)), '⑤ 다시 열어도 저장된 그대로')
        need(not errs, f'페이지 오류 {errs[:3]}')
        b.close()
finally:
    server.should_exit = True; time.sleep(1)
print('\n실패', fails or '없음'); sys.exit(1 if fails else 0)
