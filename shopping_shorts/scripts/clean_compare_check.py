# -*- coding: utf-8 -*-
"""자막제거 전/후 비교 화면 결과물 검사 (2026-09-27, 0순위-C 결과물 검사).

비교 화면이 컷마다 내는 BEFORE(원본 src 지점)·AFTER(청소본 지점) 두 그림이 **같은 장면**인지 프레임으로 잰다.
판정은 화면과 같은 함수(mix_pipeline.clean_compare_clips)가 준 좌표로 한다 — 계산을 따로 하지 않는다.
컷마다 "AFTER 좌표 프레임 ↔ 원본 프레임" 거리와, 청소본 ±1초 안에서 가장 닮은 자리와의 차이를 찍는다.
판정(2026-09-27): 가운데 띠(위10%·아래30% 제외) 회색 5x5 → z-score 정규화 → 칸별 |차| 평균 >= SCENE_T(0.55)면 다른 장면(tools/editor_vs_final_video.py 방식). 옛 16x16 절대 거리는 원본에만 있는 자막 글자·손 움직임을 차이로 세어 8c63b0691924에서 8/26컷 오탐.
실행(서버·트랙 공통): py shopping_shorts/scripts/clean_compare_check.py --job <job_id> [--db <db>] [--work-root <dir>]
"""
import argparse
import io
import contextlib
import subprocess
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))    # 트랙/서버 repo 안에서 실행
except IndexError:
    pass                                                             # /tmp 등 밖에서 실행 — PYTHONPATH로
ap = argparse.ArgumentParser()
ap.add_argument("--job", required=True)
ap.add_argument("--db", default="")
ap.add_argument("--work-root", default="")
ap.add_argument("--scene-t", type=float, default=0.55, help="가운데 띠 정규화 거리가 이 값 이상이면 '다른 장면'(무관 장면 ~1.13)")
a = ap.parse_args()
if a.db:
    from shopping_shorts import config as cfg
    cfg.DB_PATH = a.db
import os, importlib.util
if os.getenv("PATCH_DIR"):          # 배포 전 대조: 고친 모듈을 먼저 얹는다(tools/editor_vs_final_video.py와 같은 방식)
    import shopping_shorts
    # ★app은 얹지 않는다 — app.py는 자기 폴더의 landing.html 등을 읽어 /tmp에선 죽는다(2026-09-27 실측).
    #   모듈 5개는 tools/editor_vs_final_video.py와 같은 목록 — 짝이 맞는 한 벌을 통째로 얹어야 한다.
    for _n in ("frame_match", "screen_clips", "video_assemble", "clean_base", "mix_pipeline"):
        _f = Path(os.getenv("PATCH_DIR")) / ("%s.py" % _n)
        if _f.exists():
            _spec = importlib.util.spec_from_file_location("shopping_shorts.%s" % _n, str(_f))
            _m = importlib.util.module_from_spec(_spec); sys.modules["shopping_shorts.%s" % _n] = _m
            setattr(shopping_shorts, _n, _m)
            with contextlib.redirect_stderr(io.StringIO()):
                _spec.loader.exec_module(_m)
with contextlib.redirect_stderr(io.StringIO()):
    from shopping_shorts import app as A, mix_pipeline as mp
    from shopping_shorts.store import Store
if a.db:
    A.DB_PATH = a.db
if a.work_root:
    A._MIX_WORK_DIR = Path(a.work_root)
st = Store(A.DB_PATH); job = st.get_mix_job(a.job); work = A._MIX_WORK_DIR / a.job
r = mp.clean_compare_clips(job, work)
clips, clean = r.get("clips") or [], r.get("clean_path")
if not clips or not clean:
    raise SystemExit("비교 컷 없음: plan_used=%s stale=%s" % (r.get("plan_used"), r.get("stale")))
srcs = mp._resolve_sources(job, work)


def one(path, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % max(0.0, t), "-i", str(path), "-frames:v", "1",
                          "-vf", "crop=iw:ih*0.6:0:ih*0.1,scale=5:5,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return list(raw[:25])


def strip(path, t0, t1):
    n = int((t1 - t0) * 30) + 1
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % max(0.0, t0), "-i", str(path), "-frames:v", str(n),
                          "-vf", "fps=30,crop=iw:ih*0.6:0:ih*0.1,scale=5:5,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return [list(raw[i:i + 25]) for i in range(0, len(raw) - 24, 25)]


def _z(v):
    n = len(v) or 1
    m = sum(v) / n
    sd = (sum((p - m) ** 2 for p in v) / n) ** 0.5
    return [(p - m) / sd for p in v] if sd > 0 else list(v)


def dist(x, y):
    zx, zy = _z(x), _z(y)
    n = min(len(zx), len(zy))
    return sum(abs(p - q) for p, q in zip(zx, zy)) / n if n else 0.0


bad = 0; nalign = 0
print("컷 | 소스 | BEFORE↔AFTER 거리 | 청소본 최적자리 차이 | 판정   (plan_used=%s, stale=%s)" % (r.get("plan_used"), r.get("stale")))
for c in clips:
    if c.get("cleaned") is False:
        continue
    if hasattr(mp, "compare_frame_times"):      # 화면과 같은 프레임 번호(주인 함수) — 없으면 옛 소수점 초
        mid_s, mid_f = mp.compare_frame_times(c, 0.5)
    else:
        mid_s = c["src"] + c["dur"] * 0.5; mid_f = c["fin"] + c["dur"] * 0.5
    sf = one(srcs[c["video_id"]], mid_s); af = one(clean, mid_f)
    d0 = dist(sf, af)
    # ★탐색 격자를 청소본 프레임 격자(n/30)에 맞춘다 — 안 맞추면 ±1프레임이 측정 잡음으로 찍힌다(2026-09-27)
    t0 = max(0.0, round((mid_f - 1.0) * 30) / 30.0 + 0.0005); fr = strip(clean, t0, mid_f + 1.0)
    best = min(((dist(sf, f), t0 + k / 30.0) for k, f in enumerate(fr)), default=(d0, mid_f))
    # 지도 자리가 곧 최적 자리인가(거리 차 0.05 이내) — 좌표가 맞으면 True. 이게 '밀림 0'의 판정이다.
    aligned = (d0 - best[0]) <= 0.05
    nalign += (not aligned)
    # 다른 장면 판정: 지도 자리의 가운데 띠 정규화 거리가 SCENE_T 이상(최적자리는 참고로만 찍는다)
    wrong = d0 >= a.scene_t
    bad += wrong
    print("%2d | %s@%5.2f | %5.2f | %+.2f초(거리 %.2f) | %s" % (c["ci"], c["video_id"], mid_s, d0, best[1] - mid_f, best[0], "★다른 장면" if wrong else "OK"))
n_all = len([c for c in clips if c.get("cleaned") is not False])
print("== 다른 장면으로 보이는 컷: %d / %d | 지도 자리가 최적 자리가 아닌 컷(밀림): %d / %d" % (bad, n_all, nalign, n_all))
