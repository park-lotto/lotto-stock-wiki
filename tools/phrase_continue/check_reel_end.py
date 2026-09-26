# -*- coding: utf-8 -*-
"""담은 장면이 **원본 영상의 맨 끝**일 때 구절 이어 틀기가 영상 밖(검정)을 읽지 않는지 — 사장님 화면 그대로 재현.
  ../../.venv/Scripts/python.exe tools/phrase_continue/check_reel_end.py <dump.sqlite> [--job 7c6c929065ba --beat 9]

2026-09-26 사장님 캡처(작업 c0c8fa382d07 = job 7c6c929065ba 칸10): 장면을 빼 영상5 8.07~9.45초(영상 전체 9.45초) 하나만 남기자
구절 4개 중 2~4번째 카드가 검정. 이어 틀기가 9.45초 너머를 읽으려 했다.
확인: 화면 planClips·카드 썸네일 구간·서버 렌더 계획이 전부 원본 길이 안이다. POST 차단(격리 DB).
"""
import sys, os, json, time, shutil, sqlite3, threading, pathlib, argparse, re
ROOT = pathlib.Path(os.environ.get("PC_ROOT") or pathlib.Path(__file__).resolve().parents[2]); sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser()
ap.add_argument('dump'); ap.add_argument('--job', default='7c6c929065ba'); ap.add_argument('--beat', type=int, default=9)
ap.add_argument('--vid', default='s4'); ap.add_argument('--a', type=float, default=8.067); ap.add_argument('--b', type=float, default=9.45)
ap.add_argument('--port', type=int, default=8797); ap.add_argument('--out', default='')
args = ap.parse_args()
work = pathlib.Path(args.out or (pathlib.Path(args.dump).parent / 'reel_end')).resolve()
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
REEL = SRC[J][args.vid]
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 1500, 'height': 1000})
        ctx.route('**/*', lambda r: r.continue_() if r.request.method in ('GET', 'HEAD') else r.abort())
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'{BASE}/scene_lab.html?job={J}', wait_until='domcontentloaded')
        pg.wait_for_function('typeof _booting!=="undefined" && _booting===false', timeout=30000)
        # 사장님 화면 상태: 이 칸에 영상 끝 장면 하나만
        sid = pg.evaluate(f"(() => {{ const id = _makeFilmSeg('{args.vid}', {args.a}, {args.b}); lists[{I}] = [id]; render(); return id; }})()")
        pg.wait_for_timeout(400)
        cl = pg.evaluate(f'''() => planClips(lists[{I}], beatDur({I}), STRETCH[{I}], {I}).map(c => ({{start: +c.start, src: +(c.src_dur || c.dur), out: +c.dur}}))''')
        imgs = pg.evaluate(f'''() => [...document.querySelectorAll('button.delx[onclick*="dropCardAt({I}, "]')].map(x => x.closest('.tbcut').querySelector('img').getAttribute('src'))''')
        print('  원본 길이', REEL, '화면 컷:', cl)
        print('  카드 썸네일:', imgs)
        need(len(cl) >= 2 and all(c['start'] <= REEL - 0.05 and c['start'] + c['src'] <= REEL + 0.02 for c in cl),
             '① 화면 컷이 전부 원본 영상 안(검정 없음) — 고치기 전엔 9.45초 너머를 읽었다')
        bad = []
        for u in imgs:
            m = re.search(r'film_[^/]+?_([0-9.]+)_([0-9.]+)$', u or '')
            if m and float(m.group(1)) > REEL - 0.05: bad.append(u)
        need(len(imgs) >= 2 and not bad, f'② 카드 썸네일이 원본 안의 구간을 요청한다 {bad}')
        # 서버 렌더 계획(같은 상태를 서버 입장에서)
        job = Store(str(db)).get_mix_job(J); bt = dict((job['edit_plan']['beats'])[I])
        bt['scene_override'] = [{'video_id': args.vid, 'seg_id': sid, 'start': args.a, 'end': args.b}]
        sp = va.plan_beat_clips_for(bt, DUR.get(bt.get('tts_path') or '', 0.0), SRC.get(J, {}))
        print('  서버 계획:', [(round(c['start'], 2), round(c['src_dur'], 2), round(c['out_dur'], 2)) for c in sp])
        need(sp and all(c['start'] <= REEL - 0.05 for c in sp), '③ 서버 렌더 계획도 원본 안')
        need(not errs, f'페이지 오류 {errs[:3]}')
        b.close()
finally:
    server.should_exit = True; time.sleep(1)
print('\n실패', fails or '없음'); sys.exit(1 if fails else 0)
