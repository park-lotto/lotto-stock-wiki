# -*- coding: utf-8 -*-
"""[서버에서 돌린다] 실제 고객 작업의 **사본**으로 진짜 렌더(run_render)·캡컷 내보내기(api_mix_capcut)를 돌려
자막박스 색·투명도(boxClear)가 완성 영상과 캡컷 레이어까지 가는지 잰다 (2026-09-24 데이워커님 건, 0순위-A1a).
  cd /home/ubuntu/lotto-stock-wiki && python3 /tmp/live_caption_box_render.py <job_id> [/tmp/cbox]
★고객 DB·작업 폴더는 건드리지 않는다 — DB는 sqlite backup으로, 작업 폴더는 cp -r(하드링크 금지: ffmpeg -y가 같은 inode를 덮는다)로 복사한다.
모든 장면의 자막박스를 #ff2266으로 두고 투명도 0% / 60%로 두 번 렌더 → 0%에서 분홍이던 자리의 R이 60%에서 떨어지는지.
"""
import sys, os, json, sqlite3, shutil, subprocess, statistics, time, pathlib
ROOT = pathlib.Path('/home/ubuntu/lotto-stock-wiki'); sys.path.insert(0, str(ROOT))
job_id = sys.argv[1]; base = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else '/tmp/cbox') / job_id
shutil.rmtree(base, ignore_errors=True); base.mkdir(parents=True)
from PIL import Image
from shopping_shorts.store import Store
from shopping_shorts import mix_pipeline, scene_style
LIVE_DB = ROOT / 'shopping_shorts/data/reference.db'; LIVE_WORK = ROOT / 'shopping_shorts/data/mix_jobs'
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg, flush=True)
    if not ok: fails.append(msg)
PINK = lambda c: c[0] > 215 and c[1] < 80 and 60 < c[2] < 150
def variant(clear):
    d = base / f'c{clear}'; d.mkdir()
    db = d / 'ref.db'; src = sqlite3.connect(str(LIVE_DB)); dst = sqlite3.connect(str(db)); src.backup(dst); src.close(); dst.close()
    work_root = d / 'work'; work_root.mkdir()
    subprocess.run(['cp', '-r', str(LIVE_WORK / job_id), str(work_root / job_id)], check=True)
    st = Store(str(db)); job = st.get_mix_job(job_id)
    deco = job.get('deco') or {}
    deco = json.loads(deco) if isinstance(deco, str) else deco
    snap = dict(deco['scene_style']); pid, mode = snap['presetId'], snap.get('mode', 'story')
    n = 40   # 장면 수보다 넉넉히 — 편집기의 '모든 장면'과 같게 모든 칸에 같은 값
    lay = dict(snap.get('captionLayouts') or {})
    for i in range(n):
        k = f'{pid}:{mode}:{i}:caption'; cur = dict(lay.get(k) or {})
        cur.setdefault('placement', 'free' if k in (snap.get('captionDrags') or {}) or pid == 'plain' else 'title')
        cur.update({'background': '#ff2266', 'bgUser': True, 'boxClear': clear}); cur.pop('look', None); lay[k] = cur
    snap['captionLayouts'] = lay
    snap = scene_style.validate_snapshot(snap)          # 서버 저장과 같은 검증을 거친다
    deco = {**deco, 'scene_style': snap}
    st.update_mix_job(job_id, deco=deco, status='ready_for_review', video_path=None)
    t = time.time(); mix_pipeline.run_render(job_id, str(db), str(work_root), skip_clean=True)
    j2 = Store(str(db)).get_mix_job(job_id)
    print(f'  [{clear}%] run_render {round(time.time() - t)}초 status={j2.get("status")} video={j2.get("video_path")} err={j2.get("error")}', flush=True)
    # 캡컷: app의 DB·작업 경로를 사본으로 돌려 놓고 진짜 함수를 부른다
    from shopping_shorts import app
    app.DB_PATH = str(db); app._MIX_WORK_DIR = work_root
    r = app.api_mix_capcut(job_id, base='C:/Users/x/CapCut Drafts')
    cc = r if isinstance(r, dict) else json.loads(r.body)
    pngs = sorted((work_root / job_id / 'capcut_scene_style').glob('*.png'))
    draft = next((v for k, v in (cc.get('texts') or {}).items() if k.endswith('draft_content.json')), '')
    return {'video': j2.get('video_path'), 'status': j2.get('status'), 'capcut_ok': cc.get('ok'), 'pngs': pngs,
            'draft_refs': sum(1 for p in pngs if p.name in draft), 'mode': mode, 'pid': pid}
def frame(video, t, out):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', str(video), '-frames:v', '1', str(out)], check=True)
    return Image.open(out).convert('RGB')
def png_pink_alpha(p):
    im = Image.open(p).convert('RGBA'); w, h = im.size
    al = [a for y in range(0, h, 4) for x in range(0, w, 8) for (r, g, b, a) in [im.getpixel((x, y))] if a > 20 and PINK((r, g, b))]
    return (int(statistics.median(al)) if al else 0), len(al)
R = {c: variant(c) for c in (0, 60)}
a, b = R[0], R[60]
print('작업', job_id, a['pid'], a['mode'])
need(a['status'] == 'done' and b['status'] == 'done' and a['video'] and b['video'], f'① 두 렌더 모두 완료 ({a["status"]}/{b["status"]})')
if a['video'] and b['video']:
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a['video']], capture_output=True, text=True).stdout or 0)
    rows = []
    for t in [round(dur * k / 10, 2) for k in (2, 4, 6, 8)]:
        fa = frame(a['video'], t, base / f'a_{t}.png'); fb = frame(b['video'], t, base / f'b_{t}.png'); W, H = fa.size
        spots = [(x, y) for y in range(0, H, 4) for x in range(0, W, 8) if PINK(fa.getpixel((x, y)))]
        ra = statistics.median(fa.getpixel(q)[0] for q in spots) if spots else 0
        rb = statistics.median(fb.getpixel(q)[0] for q in spots) if spots else 0
        rows.append((t, len(spots), ra, rb)); print(f'    {t}초: 0%에서 분홍 {len(spots)}곳 R {ra} → 60% R {rb}', flush=True)
    good = [r for r in rows if r[1] > 150]
    need(len(good) >= 3 and all(r[2] > 200 and r[3] < 170 for r in good), f'② 완성 영상: 자막박스가 0%엔 진한 분홍, 60%엔 옅어짐 {rows}')
need(a['capcut_ok'] and b['capcut_ok'] and a['pngs'] and a['draft_refs'] == len(a['pngs']), f'③ 캡컷 내보내기 성공·장면 레이어 {len(a["pngs"])}장 전부 draft에 연결({a["draft_refs"]})')
pa = [png_pink_alpha(p) for p in a['pngs']]; pb = [png_pink_alpha(p) for p in b['pngs']]
hit = [(x, y) for x, y in zip(pa, pb) if x[1] > 150]
print('    캡컷 레이어 (알파 중앙값, 점 수) 0%→60%:', list(zip(pa, pb))[:6], flush=True)
need(len(hit) >= 2 and all(x[0] > 240 and 90 <= y[0] <= 115 for x, y in hit), f'③ 캡컷 장면 레이어: 박스 알파 255 → 약 102 ({len(hit)}장)')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건', flush=True); sys.exit(1 if fails else 0)
