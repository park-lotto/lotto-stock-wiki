# -*- coding: utf-8 -*-
"""[프로브] 수리한 B1(frame_script.extract_script_frames)을 잡의 소스 전부에 돌려 기존 추출과 나란히 본다.
사용: py tools/probes/b1_extract_probe.py <job_id> [video_id]   → out/probes/b1_<job>/result.json
키: SHORTS 풀이 0개인 PC는 예비풀 키로 우회 / Whisper: GROQ 키 없으면 말 트랙 빈칸(시각만 비교)
경로: 저장소 루트로 chdir 후 ASCII 상대경로(한글 절대경로는 로컬 ffmpeg stderr cp949 크래시)."""
import sys, json, os, sqlite3, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = str(Path(__file__).resolve().parents[2])   # 저장소 루트 — 어느 PC/서버든
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from shopping_shorts import keyroute, comment_gen, frame_script
if comment_gen._current_key_and_idx()[0] is None:
    KEY = keyroute.gemini_keys("general")[0]
    comment_gen._current_key_and_idx = lambda: (KEY, 0)
    print("(SHORTS 풀 0개 → 예비풀 키로 우회)")

JOB = sys.argv[1] if len(sys.argv) > 1 else "409f894230c6"
ONLY = sys.argv[2] if len(sys.argv) > 2 else None
ex = json.loads(sqlite3.connect(os.path.join(ROOT, "shopping_shorts", "data", "reference.db")).execute(
    "select extract_json from mix_jobs where job_id=?", (JOB,)).fetchone()[0])
out = os.path.join(ROOT, "out", "probes", "b1_" + JOB)
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
