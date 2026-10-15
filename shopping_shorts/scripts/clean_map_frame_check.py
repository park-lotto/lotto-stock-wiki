# -*- coding: utf-8 -*-
"""컷 지도(final_clip_pairs / 정본)의 컷 시작 프레임이 청소본 파일의 **실제** 컷 시작 프레임과 같은가 (2026-09-27).

컷마다 원본에서 그 컷의 첫 프레임을 뜨고, 청소본의 지도 자리 ±6프레임 안에서 가장 닮은 프레임 번호를 찾는다(가운데 띠·정규화).
차이 0 = 지도가 파일과 같은 프레임 배치. 첫 컷(0프레임)은 탐색 창이 잘려 잡음이 날 수 있어 뺀다.
서버: cd /home/ubuntu/lotto-stock-wiki && [PATCH_DIR=...] python3 shopping_shorts/scripts/clean_map_frame_check.py --job <job> [--use-fcp]
  --use-fcp: 저장된 정본 컷 대신 지금 코드의 final_clip_pairs(스냅샷 편성)로 지도를 다시 계산해 비교(배포 전 검사용).
"""
import argparse, io, contextlib, json, os, subprocess, sys, importlib.util
from pathlib import Path
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
except IndexError:
    pass
if os.getenv("PATCH_DIR"):
    import shopping_shorts
    for _n in ("frame_match", "screen_clips", "video_assemble", "clean_base", "mix_pipeline"):
        _f = Path(os.getenv("PATCH_DIR")) / ("%s.py" % _n)
        if _f.exists():
            _spec = importlib.util.spec_from_file_location("shopping_shorts.%s" % _n, str(_f))
            _m = importlib.util.module_from_spec(_spec); sys.modules["shopping_shorts.%s" % _n] = _m
            setattr(shopping_shorts, _n, _m)
            with contextlib.redirect_stderr(io.StringIO()):
                _spec.loader.exec_module(_m)
ap = argparse.ArgumentParser(); ap.add_argument("--job", required=True); ap.add_argument("--use-fcp", action="store_true")
a = ap.parse_args()
with contextlib.redirect_stderr(io.StringIO()):
    from shopping_shorts import app as A, mix_pipeline as mp, clean_base as cb
    from shopping_shorts.store import Store
st = Store(A.DB_PATH); job = st.get_mix_job(a.job); work = A._MIX_WORK_DIR / a.job
b = cb.load_base(work); clean = b["path"]; srcs = mp._resolve_sources(job, work)
if a.use_fcp:
    sp = next(work.glob("final_clean_%s.plan.json" % b["sig"]), None)
    plan = json.loads(sp.read_text(encoding="utf-8")) if sp else job["edit_plan"]
    tts = {x["beat_idx"]: x["tts_path"] for x in plan["beats"] if x.get("tts_path")}
    cuts = mp.final_clip_pairs(plan, tts, mp._src_durs_for(job, work))
else:
    cuts = b["cuts"]


def gray(path, t, n=1):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.4f" % max(0.0, t), "-i", str(path), "-frames:v", str(n),
                          "-vf", "crop=iw:ih*0.6:0:ih*0.1,scale=6:6,format=gray", "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    return [list(raw[i:i + 36]) for i in range(0, len(raw) - 35, 36)]


def z(v):
    m = sum(v) / len(v); sd = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 or 1
    return [(x - m) / sd for x in v]


def d(x, y):
    x, y = z(x), z(y); return sum(abs(p - q) for p, q in zip(x, y)) / len(x)


hist = {}
print("컷 | 비트 | 지도 시작프레임 | 파일 실제 | 차이   (지도=%s)" % ("final_clip_pairs" if a.use_fcp else "정본 cuts"))
for i, c in enumerate(cuts):
    if c.get("cleaned") is False or i == 0:
        continue
    fmap = float(c["fin"]) * 30
    sf = gray(srcs[c["video_id"]], float(c["src"]) + 0.0005)
    if not sf:
        continue
    f0 = max(0, int(round(fmap)) - 6); fr = gray(clean, f0 / 30.0 + 0.0005, 13)
    best = min((d(sf[0], f), f0 + k) for k, f in enumerate(fr))
    diff = best[1] - fmap; hist[round(diff)] = hist.get(round(diff), 0) + 1
    print("%2d | %s | %7.2f | %4d | %+.2f" % (i, c.get("beat_idx"), fmap, best[1], diff))
print("== 차이 분포(프레임):", dict(sorted(hist.items())), "| 격자 위(정수) 지도:", all(abs(float(c["fin"]) * 30 - round(float(c["fin"]) * 30)) < 1e-6 for c in cuts))
