# -*- coding: utf-8 -*-
"""컷 번호 목록 → 그 구간을 잘라 mp4로 (서버). 모델 비교 페이지가 장면을 영상으로 보여주는 데 쓴다 (2026-09-22).
  python3 tools/seed_analyzer/clip_segs.py --job <job_id> --segs a,b,c --out /tmp/clips
"""
import argparse, os, subprocess, sys
sys.path.insert(0, os.environ.get("LSW_ROOT", "/home/ubuntu/lotto-stock-wiki"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True); ap.add_argument("--segs", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--db", default="/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db")
    ap.add_argument("--work", default="/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs")
    a = ap.parse_args()
    from shopping_shorts.store import Store
    from shopping_shorts.app import _enrich_job_extract
    os.makedirs(a.out, exist_ok=True)
    job = _enrich_job_extract(Store(a.db).get_mix_job(a.job), Store(a.db))
    where = {}
    for vid, ex in (job.get("extract") or {}).items():
        d = os.path.join(a.work, a.job, vid)
        mp4 = next((os.path.join(d, f) for f in (os.listdir(d) if os.path.isdir(d) else []) if f.endswith(".mp4")), None)
        for s in (ex or {}).get("segments") or []:
            where[s.get("seg_id")] = (mp4, float(s.get("start") or 0), float(s.get("end") or 0))
    n = 0
    for sid in [x.strip() for x in a.segs.split(",") if x.strip()]:
        mp4, st, en = where.get(sid, (None, 0, 0))
        if not mp4 or en <= st:
            continue
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(st), "-t", str(max(0.4, en - st)), "-i", mp4,
                        "-vf", "scale=-2:240", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", os.path.join(a.out, sid + ".mp4")])
        n += 1
    print("clips", n)


if __name__ == "__main__":
    main()
