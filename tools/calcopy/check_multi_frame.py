"""틀 여러 장 설명서(frames + 시간축)를 라이브 렌더 경로(compose_still → render_layer_one)로 시각별 한 장씩 그려 원본 같은 시각과 대조.

    PYTHONUTF8=1 py tools/calcopy/check_multi_frame.py <frame.json> <뜯기.json> <출력폴더> --at 0.5 10.0 11.5

시각마다: 그 시각을 시작으로 하는 장면 하나를 만든다(자막 = 뜯기 captions 의 그 시각 글, 여러 줄이면 줄바꿈으로) →
compose_still(영상 칸 재료 = 원본 같은 시각 프레임을 우리 창 자리로 오린 것) → 원본과 나란히(compare_<t>.png) +
영상 창 밖 글자 줄(잉크 행 묶음) 위치표 · 자막 줄 y. 결과 check.json.
"""
import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from shopping_shorts import scene_style  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402
from shopping_shorts.channelkit.bench import probe  # noqa: E402


def caption_at(J, t):
    it = next((i for i in (J.get("captions") or {}).get("items") or [] if i["t0"] <= t < i["t1"]), None)
    return "\n".join(it["text"]) if it and it.get("text") else ""


def rect_at(spec, t, cap_text):
    """설명서의 그 시각 영상 창 — 렌더러 specRect 와 같은 규칙(컷 → 컷 y 또는 자막 아래 붙임)."""
    layers = schema.layers_at(spec, t)
    v = next((l for l in layers if l["kind"] == "video"), None)
    if not v:
        return None
    W = spec["canvas"][0]
    c = next((c for c in v.get("cuts") or [] if c["t"][0] <= t + 1e-6 < c["t"][1]), None)
    w, h = (c["w"], c["h"]) if c else (v["w"], v["h"])
    x = (c["x"] if c["x"] is not None else (W - w) / 2) if c else v["x"]
    y = v["y"]
    if c and c.get("y") is not None:
        y = c["y"]
    elif v.get("anchor"):
        cap = next((l for l in layers if l["kind"] == "text" and l["role"] == "caption"), None)
        n = min(cap["lines"], len(cap_text.split("\n"))) if (cap and cap_text.strip()) else 0
        y = cap["y"] + n * cap["line_h"] + v["anchor"]["gap"] if cap else y
    return [int(x), int(y), int(w), int(h)]


def ink_rows(img, rect, dark_or_diff):
    """영상 창 밖 행 중 바탕(행의 최빈 색)과 80 넘게 다른 점이 있는 행 묶음."""
    a = np.asarray(img.convert("RGB")).astype(int)
    H, W = a.shape[:2]
    keep = np.ones(H, bool)
    if rect:
        keep[max(0, rect[1]):min(H, rect[1] + rect[3])] = False
    rows = []
    for y in range(H):
        if not keep[y]:
            rows.append(False); continue
        row = a[y]
        med = np.median(row, axis=0)
        rows.append(bool((np.abs(row - med).max(axis=1) > dark_or_diff).sum() > 3))
    runs, s = [], None
    for y, on in enumerate(rows + [False]):
        if on and s is None:
            s = y
        if not on and s is not None:
            if y - s >= 4:
                runs.append([s, y - 1])
            s = None
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame"); ap.add_argument("tteutgi"); ap.add_argument("out")
    ap.add_argument("--at", nargs="+", type=float, required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve(); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    frame = json.loads(pathlib.Path(a.frame).read_text(encoding="utf-8"))
    J = json.loads(pathlib.Path(a.tteutgi).read_text(encoding="utf-8"))
    spec = schema.validate(frame)
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
    W, H = spec["canvas"]
    title = next((l for l in schema.all_layers(spec) if l["kind"] == "text" and l["role"] == "title"), None)
    head = {"text": (title or {}).get("text") or ""}
    res = {}
    for t in a.at:
        cap = caption_at(J, t)
        tl = [{"beat_idx": 0, "t0": 0, "dur": t, "narration": "", "caption_lines": [], "role": "hook",
               "primary": {"video_id": "s0", "start": 0, "end": t}},
              {"beat_idx": 1, "t0": t, "dur": 1.0, "narration": cap.replace("\n", " "), "caption_lines": [cap] if cap else [],
               "role": "body", "primary": {"video_id": "s0", "start": t, "end": t + 1}}]
        ctx = scene_style.context_for(tl, head, snap)
        idx = next(i for i, s in enumerate(ctx["scenes"]) if abs(s["start"] - t) < 1e-6)
        orig = Image.fromarray(probe.grab(J["source"], t, f"scale={W}:{H}", W, H))
        r = rect_at(spec, t, cap)
        mat = out / f"mat_{t}.png"
        (orig.crop((r[0], r[1], r[0] + r[2], r[1] + r[3])) if r else orig).save(mat)
        ours = out / f"ours_{t}.png"
        scene_style.compose_still(str(mat), tl, snap, out / f"work_{t}", idx, ours, head)
        mine = Image.open(ours).convert("RGB")
        ro, ru = ink_rows(orig, r, 80), ink_rows(mine, r, 80)
        sheet = Image.new("RGB", (W * 2 + 30, H + 70), (40, 40, 40))
        sheet.paste(orig, (0, 70)); sheet.paste(mine, (W + 30, 70))
        d = ImageDraw.Draw(sheet)
        d.text((20, 20), f"orig t={t}", fill="white"); d.text((W + 50, 20), f"ours t={t} rect={r}", fill="white")
        sheet.save(out / f"compare_{t}.png")
        res[str(t)] = {"caption": cap, "rect": r, "orig_rows": ro, "ours_rows": ru}
        print(t, "rect", r, "\n  원본 글자 줄", ro, "\n  우리 글자 줄", ru)
    (out / "check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
