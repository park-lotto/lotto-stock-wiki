# -*- coding: utf-8 -*-
"""장면 골라 지우기 — **진짜 업체** 1회 시험 (2026-09-26 사장님 "내꺼로 테스트해봐").

clean_base_lab.py와 같은 LAB job 사본으로 돈다. 업체 호출만 진짜(사장님 키 파일), 과금 관문은 그대로.
하는 일: 고른 컷만 청소 → 렌더 → 캡컷 → 그림 비교 자료(고른 컷 전/후, 경계 앞뒤 프레임)를 --out에 남긴다.
실행(트랙 폴더):
  py shopping_shorts/scripts/partial_clean_real_test.py --job <job> --db shopping_shorts/data/lab.db \
     --keyfile <키파일> --pick 1,2,7 --out <폴더> [--tier basic|pro]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHORTS_CLEAN_FINAL", "1")

ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True); ap.add_argument("--db", required=True)
ap.add_argument("--keyfile", required=True); ap.add_argument("--pick", required=True)
ap.add_argument("--out", required=True); ap.add_argument("--tier", default="basic")
ap.add_argument("--skip-clean", action="store_true", help="이미 청소한 정본으로 그림·렌더·캡컷만(재과금 0)")
ap.add_argument("--recover-file", default="", help="업체가 이미 만든 결과 파일(다운로드만 실패했을 때) — 업체 재호출·재과금 0")
a = ap.parse_args()

from shopping_shorts import config as cfg                 # noqa: E402
cfg.DB_PATH = a.db
from shopping_shorts import mix_pipeline as mp            # noqa: E402
from shopping_shorts import clean_base as cb              # noqa: E402
from shopping_shorts.store import Store                   # noqa: E402

keys = [k for k in Path(a.keyfile).read_text(encoding="utf-8").splitlines() if k.strip()]
mp._vmake_keys = lambda s, c=0: keys
store = Store(a.db)
store.set_setting("clean_base_enabled", "1")
work_root = ROOT / "shopping_shorts" / "data" / "mix_jobs"
work = work_root / a.job
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
CALLS = []
_real = mp._vmake_clean


def _counted(src, k, dst, tier=None):
    CALLS.append((Path(src).name, tier, mp._probe_seconds(src)))
    print("[REAL] 업체 호출: %s tier=%s %.2f초" % CALLS[-1], flush=True)
    return _real(src, k, dst, tier=tier)


mp._vmake_clean = _counted
if a.recover_file:
    def _recovered(src, k, dst, tier=None):
        print("[REAL] 업체 재호출 없음 — 이미 만든 결과 사용: %s (보낸 파일 %.2f초)" % (a.recover_file, mp._probe_seconds(src)), flush=True)
        shutil.copyfile(a.recover_file, dst)
        return str(dst)
    mp._vmake_clean = _recovered
_orig_partial = mp._clean_partial


def _keep_raw(mix_raw, *x, **k):
    shutil.copyfile(mix_raw, work / "lab_mix_raw.mp4")
    return _orig_partial(mix_raw, *x, **k)


mp._clean_partial = _keep_raw

if not a.skip_clean:
  for f in list(work.glob("final_clean_*")) + [work / cb.BASE_FILE] + list(work.glob("cb*.mp4")):
    if f.exists():
        f.unlink()
  store.update_mix_job(a.job, subtitle_removal=1, clean_status=None, clean_sources=None, clean_cuts=None,
                       clean_tier=a.tier)
  cuts = mp.clean_pick_cuts(store.get_mix_job(a.job), work)
  idx = [int(x) for x in a.pick.split(",")]
  store.update_mix_job(a.job, clean_cuts=[cuts[i]["key"] for i in idx])
  print("고른 컷:", idx, [cuts[i]["key"] for i in idx], "합 %.2f초" % sum(cuts[i]["dur"] for i in idx))
  print("== 1) 청소(진짜 업체)", flush=True)
  mp.run_clean_sources(a.job, a.db, str(work_root))
job = store.get_mix_job(a.job)
print("   상태:", job.get("clean_status"), job.get("clean_error") or "")
base = cb.load_base(work)
if not base:
    raise SystemExit("정본 없음 — 실패")
clean = Path(base["path"])
raw = work / "lab_mix_raw.mp4"
print("   청소본:", clean.name, "| 프레임 조립본 %d / 청소본 %d" % (mp._probe_fps_frames(raw)[2], mp._probe_fps_frames(clean)[2]))


def _grab(src, t, dst):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % max(0.0, t), "-i", str(src), "-frames:v", "1",
                    "-vf", "scale=360:-2", str(dst)], check=True)


def _pair(t, name):
    """같은 시각의 조립본(왼쪽)·청소본(오른쪽)을 나란히."""
    l, r = out / "_l.png", out / "_r.png"
    _grab(raw, t, l); _grab(clean, t, r)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(l), "-i", str(r), "-filter_complex", "hstack", str(out / name)],
                   check=True)


fps = mp._probe_fps_frames(raw)[1]
for i, c in enumerate(base["cuts"]):
    mid = float(c["fin"]) + float(c["dur"]) / 2
    _pair(mid, "컷%02d_%s_가운데.png" % (i + 1, "지움" if c.get("cleaned") else "안지움"))
# 고른 구간 경계 바로 앞/뒤 프레임(밀림·튐 확인)
sel = [c for c in base["cuts"] if c.get("cleaned")]
for c in sel:
    s0 = float(c["fin"]); s1 = s0 + float(c["dur"])
    _pair(s0 - 1.5 / fps, "경계_%05.2f_직전.png" % s0); _pair(s0 + 1.5 / fps, "경계_%05.2f_직후.png" % s0)
    _pair(s1 - 1.5 / fps, "경계_%05.2f_끝직전.png" % s1); _pair(s1 + 1.5 / fps, "경계_%05.2f_끝직후.png" % s1)

print("== 2) 최종렌더", flush=True)
n0 = len(CALLS)
mp.run_render(a.job, a.db, str(work_root))
job = store.get_mix_job(a.job)
print("   상태:", job.get("status"), job.get("error") or "", "| 렌더 중 업체 호출:", len(CALLS) - n0)
fin = Path(job["video_path"])
shutil.copyfile(fin, out / "final.mp4")
for i, c in enumerate(base["cuts"]):
    _grab(fin, float(c["fin"]) + float(c["dur"]) / 2, out / ("완성본_컷%02d.png" % (i + 1)))

print("== 3) 캡컷", flush=True)
from shopping_shorts import app as A                     # noqa: E402
A._MIX_WORK_DIR = work_root; A.DB_PATH = a.db
r = A.api_mix_capcut(a.job, base=str(work / "capcut_lab"))
print("   응답 status:", getattr(r, "status_code", 200))
dc = sorted((work / "capcut").rglob("draft_content.json"), key=os.path.getmtime)
if dc:
    d = json.loads(dc[-1].read_text(encoding="utf-8"))
    segs = [s for t in d.get("tracks", []) if t.get("type") == "video" for s in t.get("segments", [])]
    print("   캡컷 비디오 조각:", len(segs), "| 정본 컷:", len(base["cuts"]))
print("== 업체 호출 합계:", CALLS)
