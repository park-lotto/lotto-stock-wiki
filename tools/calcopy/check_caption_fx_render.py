"""칼카피 자막 효과(등장 enter·낱말 강조 emphasis)가 **진짜 렌더 영상**을 바꾸나 — 지정 전/후 프레임 실측 (0순위-A1a).

같은 설명서에서 자막 층 enter·emphasis 만 바꿔 compose(최종 합성) 로 mp4 를 만들고,
자막 칸(caption 층 y 둘레) 의 글자 잉크 점 수·밝기 가운데값을 시각별로 잰다.
  - enter=None : 0.03초부터 잉크가 다 있다(1초와 같다)
  - enter=pop/fade/rise : 0.03초 잉크(또는 자리)가 1초와 다르다 → 등장 효과가 렌더에 실렸다
  - emphasis auto(빨강) : 1초 자막 칸에 빨강 점이 생긴다 / 없으면 0
쓰는 법: py tools/calcopy/check_caption_fx_render.py <출력폴더> [frame.json]
"""
import copy
import json
import pathlib
import shutil
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from shopping_shorts import scene_style, video_assemble as va  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402

out = pathlib.Path(sys.argv[1]).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
frame_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "shopping_shorts/calcopy_frame/examples/frame_A_ZdeZRtCeAC4.json"
base = json.loads(frame_path.read_text(encoding="utf-8"))
spec = schema.validate(base)
cap = next(l for l in spec["layers"] if l["kind"] == "text" and l["role"] == "caption")
Y0, Y1 = max(0, int(cap["y"]) - 140), min(1920, int(cap["y"]) + 220)
fails = []


def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok:
        fails.append(msg)


CAPS = ["아니 이거 해외 릴스에서 맨날 보이길래", "두 번째 장면 자막 이거 진짜"]
DURS = [3, 3]
timeline, t = [], 0
for i, (c, d) in enumerate(zip(CAPS, DURS)):
    timeline.append({"beat_idx": i, "t0": t, "dur": d, "narration": c, "caption_lines": [c], "role": "hook" if i == 0 else "body",
                     "primary": {"video_id": "s0", "start": t, "end": t + d}}); t += d
HEAD = {"text": "닿으면 스피커\n소름 돋는 음질 수준"}
src = out / "src.mp4"
va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=blue:s=1080x1920:d={sum(DURS)}", "-r", "30", "-pix_fmt", "yuv420p", str(src)])
TIMES = [3.03, 3.1, 3.2, 4.0]   # 장면 2 시작 직후(장면 1 은 훅이라 영상 맨 앞 프레임 대신 장면 경계로 잰다)


def variant(tag, enter, emphasis):
    f = copy.deepcopy(base)
    for l in f["layers"]:
        if l["kind"] == "text" and l["role"] == "caption":
            l["enter"] = enter
            l["emphasis"] = emphasis
    f.pop("template_off", None)
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(f))
    d = out / tag; d.mkdir()
    final = d / "final.mp4"
    scene_style.compose(str(src), timeline, snap, str(final), d / "cw", HEAD)
    res = {}
    for tt in TIMES:
        png = d / f"t{tt:.2f}.png"
        va._run_ffmpeg(["ffmpeg", "-y", "-ss", f"{tt}", "-i", str(final), "-frames:v", "1", str(png)])
        a = np.asarray(Image.open(png).convert("RGB")).astype(int)[Y0:Y1]
        bg = np.median(a.reshape(-1, 3), axis=0)
        ink = np.abs(a - bg).max(axis=2) > 80
        red = (a[..., 0] > 180) & (a[..., 1] < 90) & (a[..., 2] < 90)
        ys, xs = np.nonzero(ink)
        res[tt] = {"ink": int(ink.sum()), "red": int(red.sum()),
                   "box": [int(xs.min()), int(ys.min()) + Y0, int(xs.max()), int(ys.max()) + Y0] if len(xs) else None}
    print(tag, json.dumps(res, ensure_ascii=False))
    return res


R = {"none": variant("none", None, None),
     "pop": variant("pop", {"kind": "pop", "ms": 300}, None),
     "fade": variant("fade", {"kind": "fade", "ms": 300}, None),
     "rise": variant("rise", {"kind": "rise", "ms": 300}, None),
     "emph": variant("emph", None, {"words": "auto", "rgb": [230, 20, 20], "style": "color"})}
n = R["none"]
need(n[TIMES[0]]["ink"] > 0.9 * n[TIMES[-1]]["ink"], f"enter 없음: 첫 프레임 잉크 {n[TIMES[0]]['ink']} ≈ 1초 {n[TIMES[-1]]['ink']}")
for k in ("pop", "fade", "rise"):
    r = R[k]
    d_ink = abs(r[TIMES[0]]["ink"] - r[TIMES[-1]]["ink"]) / max(1, r[TIMES[-1]]["ink"])
    moved = r[TIMES[0]]["box"] != r[TIMES[-1]]["box"]
    need(d_ink > 0.15 or moved, f"enter {k}: 첫 프레임 잉크 {r[TIMES[0]]['ink']} 상자 {r[TIMES[0]]['box']} vs 끝 {r[TIMES[-1]]['ink']} {r[TIMES[-1]]['box']}")
    need(abs(r[TIMES[-1]]["ink"] - n[TIMES[-1]]["ink"]) / max(1, n[TIMES[-1]]["ink"]) < 0.1, f"enter {k}: 안정 뒤 잉크 {r[TIMES[-1]]['ink']} ≈ 효과 없음 {n[TIMES[-1]]['ink']}")
need(R["emph"][TIMES[-1]]["red"] > 200 and n[TIMES[-1]]["red"] < 50, f"강조 auto 빨강: 빨강 점 {R['emph'][TIMES[-1]]['red']} (효과 없음 {n[TIMES[-1]]['red']})")
(out / "result.json").write_text(json.dumps({"fails": fails, "R": {k: {str(t): v for t, v in r.items()} for k, r in R.items()}}, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
