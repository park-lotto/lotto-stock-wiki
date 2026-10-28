# -*- coding: utf-8 -*-
"""관문 ④ 글자 표본 다시 재기 — render_bench.cut_content_feats(관문과 같은 함수)로 컷마다 프레임 3장 글자 상자 값을 잰다.

쓰는 법(창 여러 개로 나눠 돌린다 — 컷당 수 초):
  py tools/calcopy/gate_fixtures/cut_content_collect.py <specs.json> <시작> <끝> <out.json> [--draw <그림폴더>]
  py tools/calcopy/gate_fixtures/cut_content_collect.py --merge <out.json>... --fixture   # 라벨은 표본 그대로, 값만 새로(id 로 맞춤)

specs.json = [{id, grp, src(원본 경로), ss, dur(초), crop, blur, win:[w,h]}] — 10-25 표본 762컷의 spec 은 세션 scratchpad g4/specs.json + g5/new_specs.json.
--fixture 는 shopping_shorts/tests/fixtures/cut_content_labels.json 의 text.rows 값(frames)만 바꾸고 id·label·set 은 그대로 둔다.
판정 문턱은 여기 두지 않는다 — render_bench 상수·foreign_text 한 곳.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
FX = ROOT / "shopping_shorts/tests/fixtures/cut_content_labels.json"
KEEP_SCORE, KEEP_FILL = 0.85, 0.5          # 표본에 남기는 상자(용량) — 판정 문턱보다 넓게


def draw(sp, r, path):
    import cv2
    import numpy as np
    from tools.calcopy.hybrid import render_bench as RB
    from tools.calcopy.hybrid.common import FPS
    vis = []
    for dt, fr in zip(RB.look_times(max(1, round(sp["dur"] * FPS))), r["text"]):
        a = RB.cut_frame(Path(sp["src"]), sp["ss"] + dt, sp["crop"], tuple(sp["win"]), sp["blur"])
        if a is None:
            continue
        a = a.copy()
        for b in fr:
            if b["score"] < KEEP_SCORE:
                continue
            x0, y0, x1, y1 = b["box"]
            cv2.rectangle(a, (x0, y0), (x1, y1), (0, 0, 255) if RB.foreign_text(b) else (255, 160, 0), 3)
        vis.append(cv2.resize(a, (300, int(300 * a.shape[0] / a.shape[1]))))
    if vis:
        H = max(i.shape[0] for i in vis)
        st = np.hstack([cv2.copyMakeBorder(i, 0, H - i.shape[0], 0, 3, cv2.BORDER_CONSTANT) for i in vis])
        cv2.putText(st, sp["id"], (4, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imencode(".jpg", st)[1].tofile(str(path))


def collect(specs, lo, hi, out, draw_dir=None):
    from tools.calcopy.hybrid import render_bench as RB
    from tools.calcopy.hybrid.common import FPS
    rows = []
    for i, sp in enumerate(specs[lo:hi], lo):
        try:
            r = RB.cut_content_feats(Path(sp["src"]), sp["ss"], max(1, round(sp["dur"] * FPS)), sp["crop"], tuple(sp["win"]), sp["blur"])
        except Exception as e:          # 원본이 없어졌거나 깨짐 — 그 컷만 빠진다(끝에 수를 찍는다)
            print("fail", sp["id"], repr(e), flush=True)
            continue
        if draw_dir:
            draw(sp, r, Path(draw_dir) / (sp["id"].replace("#", "_").replace("/", "_") + ".jpg"))
        rows.append({"id": sp["id"], "grp": sp["grp"], "frames": [[b for b in fr if b["score"] >= KEEP_SCORE and b["fill"] >= KEEP_FILL] for fr in r["text"]]})
        if i % 25 == 0:
            print(i, sp["id"], flush=True)
    Path(out).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print("done", len(rows), "of", len(specs[lo:hi]), flush=True)


def merge_into_fixture(parts):
    new = {}
    for p in parts:
        for r in json.loads(Path(p).read_text(encoding="utf-8")):
            new[r["id"]] = r["frames"]
    F = json.loads(FX.read_text(encoding="utf-8"))
    rows = F["text"]["rows"]
    miss = [r["id"] for r in rows if r["id"] not in new]
    if miss:
        raise SystemExit(f"표본 {len(miss)}컷 값 없음(예: {miss[:3]}) — 그 spec 을 다시 재라")
    for r in rows:
        r["frames"] = [[{k: v for k, v in b.items() if k != "box"} for b in fr] for fr in new[r["id"]]]
    FX.write_text(json.dumps(F, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("fixture rows", len(rows), FX.stat().st_size)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--merge":
        merge_into_fixture([x for x in a[1:] if x != "--fixture"])
    else:
        dd = a[a.index("--draw") + 1] if "--draw" in a else None
        if dd:
            Path(dd).mkdir(parents=True, exist_ok=True)
        collect(json.loads(Path(a[0]).read_text(encoding="utf-8")), int(a[1]), int(a[2]), a[3], dd)
