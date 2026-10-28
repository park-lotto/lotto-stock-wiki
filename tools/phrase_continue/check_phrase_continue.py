# -*- coding: utf-8 -*-
"""미리보기(3단계 화면 planClips)와 렌더(plan_beat_clips_for)가 **같은 컷**을 짜는지 — 라이브 작업 그대로 대조한다.
  ../../.venv/Scripts/python.exe tools/phrase_continue/check_phrase_continue.py <dump.sqlite> [--limit N] [--job ID]

왜 있나(2026-09-26 사장님 "구절이 나눠져도 쭉 이어지게"):
  같은 규칙이 화면(JS)과 렌더(파이썬)에 두 벌로 적혀 있다. 09-24 '릴 뒤 이어 쓰기'는 렌더에만 들어가
  미리보기는 멈추고 완성본은 딴 장면이 나왔다. 한쪽만 고치면 이 도구가 잡는다.

입력: tools/phrase_continue/dump_jobs.py 가 라이브 서버에서 읽기 전용으로 떠 온 sqlite(작업 행 + 영상·음성 길이).
하는 일: 트랙 코드로 앱을 격리 DB에 띄우고 **진짜 scene_lab.html**을 브라우저로 연다(POST는 전부 막는다 — 음성 자동생성 등
  유료 호출 차단). 칸마다 page의 planClips 결과와 서버 plan_beat_clips_for 결과를 컷 단위로 비교한다.
세는 것(사장님이 볼 것):
  - 불일치 칸: 미리보기 컷과 렌더 컷이 다르다(시작·읽는 길이 0.03초 넘게, 또는 컷 수)
  - 멈춤 컷: 화면 길이 대비 원본을 절반도 못 읽는 컷(2배 넘게 느림)
  - 되감김: 같은 영상이 이어지는데 다음 컷 시작이 앞 컷 끝보다 0.05초 넘게 앞(뒤로 튐)
"""
import sys, json, time, shutil, sqlite3, threading, pathlib, argparse
import os
ROOT = pathlib.Path(os.environ.get("PC_ROOT") or pathlib.Path(__file__).resolve().parents[2]); sys.path.insert(0, str(ROOT))  # PC_ROOT=다른 체크아웃(기준선 대조용)

ap = argparse.ArgumentParser()
ap.add_argument('dump'); ap.add_argument('--limit', type=int, default=0); ap.add_argument('--job', default='')
ap.add_argument('--port', type=int, default=8791); ap.add_argument('--out', default='')
args = ap.parse_args()

work = pathlib.Path(args.out or (pathlib.Path(args.dump).parent / 'pc_check')).resolve()
shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
db = work / 'qa.db'; shutil.copyfile(args.dump, db)
con = sqlite3.connect(db)
DUR = {}
SRC = {}
for jid, kind, key, sec in con.execute('select job_id, kind, key, sec from durations'):
    if kind == 'src':
        SRC.setdefault(jid, {})[key] = sec; DUR[f'/fake/{jid}/{key}.mp4'] = sec
    else:
        DUR[key] = sec
jobs = [r[0] for r in con.execute('select job_id from mix_jobs order by updated_at desc')]
if args.job: jobs = [args.job]
if args.limit: jobs = jobs[:args.limit]
con.close()

from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts import app as module
import uvicorn
from playwright.sync_api import sync_playwright

module.DB_PATH = str(db); module._AUTH_ON = False
module._MIX_WORK_DIR = work / 'mixwork'; module._THUMB_DIR = work / 'thumbs'
_orig_probe = va._probe_duration
va._probe_duration = lambda p: DUR.get(str(p).replace('\\', '/'), 0.0) or DUR.get(str(p), 0.0)
module._resolve_sources = lambda job, w: {v: pathlib.Path(f'/fake/{job["job_id"]}/{v}.mp4') for v in SRC.get(job['job_id'], {})}

server = uvicorn.Server(uvicorn.Config(module.app, host='127.0.0.1', port=args.port, log_level='error'))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started: break
    time.sleep(.2)
BASE = f'http://127.0.0.1:{args.port}'

def server_plan(beat, jid):
    tts = DUR.get(beat.get('tts_path') or '', 0.0)
    if not tts: return None
    return va.plan_beat_clips_for(beat, tts, SRC.get(jid, {}))

def rewinds_and_freezes(clips, key_start, key_src, key_out):
    # 되감김 = 바로 앞 컷과 같은 영상이고, 다음 컷이 앞 컷 **안쪽**에서 다시 시작(앞 컷 시작 이후·끝 이전) — 같은 장면이 뒤로 튐.
    #   다른 장면으로 넘어가며 영상의 앞쪽을 쓰는 것(12.67초 → 8.83초)은 되감김이 아니다.
    rw = fr = 0
    for a, b in zip(clips, clips[1:]):
        if a['video_id'] == b['video_id'] and a[key_start] - 1e-3 <= b[key_start] < a[key_start] + a[key_src] - 0.05:
            rw += 1
    for c in clips:
        if c[key_out] > 0.2 and c[key_src] < c[key_out] * 0.5: fr += 1
    return rw, fr

S = dict(jobs=0, beats=0, phrase_beats=0, skipped_list_mismatch=0, mismatch_phrase=0, mismatch_other=0,
         pv_freeze=0, rd_freeze=0, pv_rewind=0, rd_rewind=0, errors=0)
EX = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 900})
        # ★유료 호출 차단 — 화면은 음성 자동생성(autoMakeTts) 등 POST를 보낸다. GET만 통과.
        ctx.route('**/*', lambda r: r.continue_() if r.request.method in ('GET', 'HEAD') else r.abort())
        pg = ctx.new_page()
        for jid in jobs:
            job = Store(str(db)).get_mix_job(jid)
            plan = (job or {}).get('edit_plan') or {}
            beats = plan.get('beats') or []
            if not beats: continue
            try:
                pg.goto(f'{BASE}/scene_lab.html?job={jid}', wait_until='domcontentloaded')
                pg.wait_for_function('typeof DATA==="object" && DATA && DATA.beats && typeof _booting!=="undefined" && _booting===false', timeout=30000)
                pv = pg.evaluate('''() => DATA.beats.map((b, i) => ({
                    ids: (lists[i] || []).slice(),
                    clips: planClips(lists[i] || [], beatDur(i), STRETCH[i], i).map(c => ({video_id: c.video_id, seg_id: c.seg_id,
                        start: +c.start, src: +(c.src_dur || c.dur), out: +c.dur}))}))''')
            except Exception as e:
                S['errors'] += 1
                print('page-error', jid, str(e)[:200])
                continue
            S['jobs'] += 1
            for i, bt in enumerate(beats):
                S['beats'] += 1
                sp = server_plan(bt, jid)
                if sp is None: continue
                mat = [m.get('seg_id') for m in va._beat_material(bt)]
                if [x for x in pv[i]['ids']] != [x for x in mat if x]:
                    S['skipped_list_mismatch'] += 1; continue
                phrase = bool(bt.get('phrase_sync'))
                if phrase: S['phrase_beats'] += 1
                a = pv[i]['clips']
                s = [{'video_id': c['video_id'], 'start': float(c['start']), 'src': float(c['src_dur']), 'out': float(c['out_dur'])} for c in sp]
                same = len(a) == len(s) and all(x['video_id'] == y['video_id'] and abs(x['start'] - y['start']) <= 0.03
                                                 and abs(x['src'] - y['src']) <= 0.03 for x, y in zip(a, s))
                tail_only = (not same and len(a) == len(s) and len(a) > 0
                             and all(x['video_id'] == y['video_id'] and abs(x['start'] - y['start']) <= 0.03 for x, y in zip(a, s))
                             and all(abs(x['src'] - y['src']) <= 0.03 for x, y in zip(a[:-1], s[:-1]))
                             and abs(a[-1]['src'] - s[-1]['src']) <= 0.06)
                if tail_only:
                    S['tail_only_' + ('phrase' if phrase else 'other')] = S.get('tail_only_' + ('phrase' if phrase else 'other'), 0) + 1
                elif not same:
                    S['mismatch_phrase' if phrase else 'mismatch_other'] += 1
                    if len(EX) < 8:
                        EX.append((jid, i, 'phrase' if phrase else 'other',
                                   [(c['video_id'], round(c['start'], 2), round(c['src'], 2), round(c['out'], 2)) for c in a],
                                   [(c['video_id'], round(c['start'], 2), round(c['src'], 2), round(c['out'], 2)) for c in s]))
                rw, fr = rewinds_and_freezes(a, 'start', 'src', 'out'); S['pv_rewind'] += rw; S['pv_freeze'] += fr
                rw, fr = rewinds_and_freezes(s, 'start', 'src', 'out'); S['rd_rewind'] += rw; S['rd_freeze'] += fr
        b.close()
finally:
    server.should_exit = True; time.sleep(1)
print(json.dumps(S, ensure_ascii=False))
for e in EX: print('예:', json.dumps(e, ensure_ascii=False)[:600])
