# -*- coding: utf-8 -*-
"""수리한 트랙 코드(.tracks/B1프레임태깅)의 extract_script_frames를 로컬 4편에 실제로 돌린다.
키: 예비풀 우회 / Whisper: 로컬 GROQ 없음 → None / 경로: ASCII 상대경로."""
import sys, json, os, sqlite3, time, shutil
sys.stdout.reconfigure(encoding="utf-8")
TRACK = r"C:\Users\CH\Desktop\로또의 주식\.tracks\B1프레임태깅"
MAIN = r"C:\Users\CH\Desktop\로또의 주식"
sys.path.insert(0, TRACK)
os.chdir(MAIN)                                   # 영상·DB는 main 폴더에만 있다
from shopping_shorts import keyroute, comment_gen, frame_script
assert frame_script.__file__.startswith(TRACK), frame_script.__file__
KEY = keyroute.gemini_keys("general")[0]
comment_gen._current_key_and_idx = lambda: (KEY, 0)

JOB = "409f894230c6"
ONLY = sys.argv[1] if len(sys.argv) > 1 else None
ex = json.loads(sqlite3.connect(os.path.join(MAIN, "shopping_shorts", "data", "reference.db")).execute(
    "select extract_json from mix_jobs where job_id=?", (JOB,)).fetchone()[0])
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "b1_track_" + JOB)
os.makedirs(out, exist_ok=True)
res = {}
for vid in ex:
    if ONLY and vid != ONLY:
        continue
    vpath = os.path.join("shopping_shorts", "data", "mix_jobs", JOB, vid, vid + ".mp4")
    t0 = time.time()
    r = frame_script.extract_script_frames(vpath, vid, caption="", _no_classic=True,
                                           transcribe_words=lambda mp3: None)
    segs = r.get("segments") or []
    print(f"\n[{vid}] 세그 {len(segs)}개 / {time.time()-t0:.0f}s  (기존 {len(ex[vid]['segments'])}개)")
    for s in segs:
        print(f"  {float(s['start']):6.2f}-{float(s['end']):6.2f} 결:{s.get('shot_role','')!s:4} key:{'Y' if s.get('is_key') else '-'} | {(s.get('scene_desc') or '')[:70]}")
    res[vid] = r
    time.sleep(4)
json.dump(res, open(os.path.join(out, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nsaved", out)
