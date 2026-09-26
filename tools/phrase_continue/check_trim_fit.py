# -*- coding: utf-8 -*-
"""꼬다리를 잘라낸 카드는 잘라낸 대로 나오고, [속도 맞추기]를 누르면 그 카드만 정확히 늘어나는지 — 사장님 칸2 그대로.
  ../../.venv/Scripts/python.exe tools/phrase_continue/check_trim_fit.py <dump.sqlite> [--job 7c6c929065ba --beat 1]

2026-09-26 사장님: "꼬다리가 남으면 다른 장면으로 바꾸든지, 0.1초 잘라내고 속도를 조정할까요? 이렇게".
칸2 카드4(원본 10.33~11.41초)는 인형 0.47초 + 리모컨 0.61초. 인형 끝 10.8초에서 잘라 본다.
  ① 자른 카드는 잘라낸 구간만 튼다(리모컨이 되살아나지 않는다) — 고치기 전엔 이어 틀기로 11.41초까지 다시 읽었다
  ② 카드 아래 '⏱ 비어요 [속도 맞추기]' 안내가 뜬다
  ③ 누르면 → 저장(/apply) → 서버 렌더 계획이 그 카드만 playback_speed(정지 없이 끝까지)
  ④ 합본으로 보내는 컷에도 fit 표시 · 되돌리기 누르면 원래대로
POST는 /apply만 통과(격리 DB).
"""
import sys, os, json, time, shutil, sqlite3, threading, pathlib, argparse
ROOT = pathlib.Path(os.environ.get("PC_ROOT") or pathlib.Path(__file__).resolve().parents[2]); sys.path.insert(0, str(ROOT))
ap = argparse.ArgumentParser()
ap.add_argument('dump'); ap.add_argument('--job', default='7c6c929065ba'); ap.add_argument('--beat', type=int, default=1)
ap.add_argument('--card', type=int, default=3); ap.add_argument('--cut_at', type=float, default=10.8)
ap.add_argument('--port', type=int, default=8799); ap.add_argument('--out', default='')
args = ap.parse_args()
work = pathlib.Path(args.out or (pathlib.Path(args.dump).parent / 'trim_fit')).resolve()
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
BASE = f'http://127.0.0.1:{args.port}'; J, I, K = args.job, args.beat, args.card
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
CLIPS = f'''() => planClips(lists[{I}] || [], beatDur({I}), STRETCH[{I}], {I}).map(c => ({{seg: c.seg_id, start: +(+c.start).toFixed(3),
    src: +(+(c.src_dur || c.dur)).toFixed(3), out: +(+c.dur).toFixed(3), fit: !!c.fit}}))'''
def server_plan():
    beat = [x for x in (Store(str(db)).get_mix_job(J).get('edit_plan') or {}).get('beats', []) if x.get('beat_idx') == I][0]
    sp = va.plan_beat_clips_for(beat, DUR.get(beat.get('tts_path') or '', 0.0), SRC.get(J, {}))
    return beat, sp
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 1500, 'height': 1000})
        ctx.route('**/*', lambda r: r.continue_() if (r.request.method in ('GET', 'HEAD') or r.request.url.endswith('/apply')) else r.abort())
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'{BASE}/scene_lab.html?job={J}', wait_until='domcontentloaded')
        pg.wait_for_function('typeof _booting!=="undefined" && _booting===false', timeout=30000)
        c0 = pg.evaluate(CLIPS); print('  처음:', c0)
        seg = pg.evaluate(f'lists[{I}][{K}]'); a = pg.evaluate(f'DATA.segments[lists[{I}][{K}]].start')
        pg.evaluate(f"replaceRoll(lists[{I}][{K}], 's1', {{s: {a}, e: {args.cut_at}}})"); pg.wait_for_timeout(400)
        c1 = pg.evaluate(CLIPS); print('  자른 뒤:', c1)
        need(c1[K]['start'] + c1[K]['src'] <= args.cut_at + 0.02, f'① 자른 카드는 {args.cut_at}초까지만 튼다(꼬다리 안 되살아남) — 고치기 전엔 이어 틀기로 다시 읽었다')
        note = pg.locator('.cutgap', has_text=f'{K + 1}번째 카드').first
        need(note.count() > 0 and '속도 맞추기' in (note.inner_text() if note.count() else ''), '② 카드 아래 "비어요 [속도 맞추기]" 안내가 뜬다')
        if note.count():
            note.locator('button.act').click(); pg.wait_for_timeout(400)
        c2 = pg.evaluate(CLIPS)
        need(c2[K]['fit'], '③ 누르면 화면 컷에 속도 맞춤 표시')
        pv = pg.evaluate(f'pvxCuts().cuts')
        need(any(x.get('fit') for x in pv), '④ 합본으로 보내는 컷에도 fit')
        pg.evaluate('async () => { await applyServer(); }'); pg.wait_for_timeout(800)
        beat, sp = server_plan()
        print('  서버 fit_segs:', beat.get('fit_segs'), '서버 계획:', [(round(c['start'], 2), round(c['src_dur'], 2), round(c['out_dur'], 2), round(c.get('playback_speed', 0), 3)) for c in sp])
        cK = sp[K]
        need(abs(cK['src_dur'] - c1[K]['src']) < 0.03 and abs(cK.get('playback_speed', 0) - cK['src_dur'] / cK['out_dur']) < 0.01,
             '③ 저장 뒤 서버 렌더 계획: 그 카드만 playback_speed = 읽는 길이/화면 길이(정지 없음)')
        play, frz = va._speed_and_freeze(cK['src_dur'], cK['out_dur'], preferred_speed=cK.get('playback_speed'))
        need(frz < 0.01, f'③ 렌더 조각이 정지 없이 끝까지 움직인다(정지 {frz:.3f}초)')
        need(sum(1 for c in sp if c.get('playback_speed')) == 1, '③ 다른 카드는 안 건드림')
        # 되돌리기
        pg.locator('.cutgap', has_text=f'{K + 1}번째 카드').first.locator('button.act').click(); pg.wait_for_timeout(300)
        need(not pg.evaluate(CLIPS)[K]['fit'], '④ 되돌리기 누르면 속도 맞춤 해제')
        need(not errs, f'페이지 오류 {errs[:3]}')
        b.close()
finally:
    server.should_exit = True; time.sleep(1)
print('\n실패', fails or '없음'); sys.exit(1 if fails else 0)
