# -*- coding: utf-8 -*-
"""검수 — 나온 mp4를 실제로 잰다. 길이 · 컷마다 슬롯이 비지 않았나 · 자막 잉크가 있나 · 자막이 화면 밖으로 안 나갔나.
눈으로 볼 시트(review.png: 컷마다 가운데 프레임)도 만든다 — 숫자 통과 ≠ 결과물 통과(0순위-A1).
"""
import json
import os
import subprocess

import numpy as np
from PIL import Image

from . import spec


def _frame(mp4, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) != spec.CANVAS_W * spec.CANVAS_H * 3:
        return None
    return np.frombuffer(raw, np.uint8).reshape(spec.CANVAS_H, spec.CANVAS_W, 3)


def slot_cuts(mp4):
    """완성 mp4 슬롯의 컷 시각(scene>0.3, 0.2초 이후) — tools/hotpeople/measure/cuts.py 와 같은 자."""
    vf = f"crop={spec.SLOT_W}:{spec.SLOT_H}:{spec.SLOT_X}:{spec.SLOT_Y},select='gt(scene,0.3)',metadata=print:file=-"
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", vf, "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stdout
    return [float(l.split("pts_time:")[1]) for l in r.splitlines() if "pts_time:" in l and float(l.split("pts_time:")[1]) > 0.2]


def inner_cuts(mp4, secs, tol=0.1, cuts=None):
    """★칼카피 1 결과물 검사 — 자막 경계에서 tol 초 넘게 떨어진 컷(= 자막 안에서 화면이 바뀐 것)의 시각 목록."""
    cuts = slot_cuts(mp4) if cuts is None else cuts
    bounds, t = [], 0.0
    for s in secs:
        t += s
        bounds.append(t)
    return [round(c, 2) for c in cuts if min(abs(c - b) for b in bounds) > tol]


def run(mp4, render, wd):
    checks, frames = [], []
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                                    "-of", "json", mp4], capture_output=True, text=True).stdout or "{}")
    dur = float(pr.get("format", {}).get("duration") or 0)
    kinds = [s.get("codec_type") for s in pr.get("streams") or []]
    v = next((s for s in pr.get("streams") or [] if s.get("codec_type") == "video"), {})
    checks.append({"name": "크기 1080x1920", "ok": (v.get("width"), v.get("height")) == (spec.CANVAS_W, spec.CANVAS_H)})
    checks.append({"name": f"길이 {spec.DURATION_MIN:.0f}~{spec.DURATION_MAX:.0f}초", "ok": spec.DURATION_MIN <= dur <= spec.DURATION_MAX, "got": round(dur, 2)})
    checks.append({"name": "소리 트랙", "ok": "audio" in kinds})
    t, blank, noink, overflow = 0.0, [], [], []
    for c in render["cuts"]:
        mid = t + c["sec"] / 2
        t += c["sec"]
        a = _frame(mp4, mid)
        if a is None:
            blank.append(c["i"]); continue
        frames.append(a)
        slot = a[spec.SLOT_Y + 10:spec.SLOT_Y + spec.SLOT_H - 10].astype(int)
        if slot.mean() < 15 or slot.std() < 6:
            blank.append(c["i"])
        band = a[spec.SLOT_Y + spec.SLOT_H:spec.SLOT_Y + spec.SLOT_H + 260]
        if (band.max(axis=2) < 90).mean() < 0.003:
            noink.append(c["i"])
        edge = np.concatenate([band[:, :20], band[:, -20:]], axis=1)
        if (edge.max(axis=2) < 90).mean() > 0.002:
            overflow.append(c["i"])
    checks.append({"name": "슬롯이 빈 컷 0", "ok": not blank, "got": blank})
    checks.append({"name": "자막 없는 컷 0", "ok": not noink, "got": noink})
    checks.append({"name": "자막 화면 밖 0", "ok": not overflow, "got": overflow})
    cuts = slot_cuts(mp4)
    inner = inner_cuts(mp4, [c["sec"] for c in render["cuts"]], cuts=cuts)
    # 자막 하나 = 컷 하나라 컷 수는 자막 수를 못 넘는다 — 넘으면 경계 근처 이중 컷(빈 첫 프레임 등, v3 1차 37컷)
    checks.append({"name": "컷 수 ≤ 자막 수", "ok": len(cuts) + 1 <= len(render["cuts"]), "got": len(cuts) + 1})
    checks.append({"name": f"자막 안 컷 {spec.SUB_INNER_CUTS_MAX} 이하", "ok": len(inner) <= spec.SUB_INNER_CUTS_MAX, "got": inner})
    sheet = None
    if frames:
        th = [Image.fromarray(f).resize((216, 384)) for f in frames]
        cols = 8
        sh = Image.new("RGB", (cols * 220, ((len(th) + cols - 1) // cols) * 388), "white")
        for i, im in enumerate(th):
            sh.paste(im, ((i % cols) * 220, (i // cols) * 388))
        sheet = os.path.join(wd, "out", "review.png")
        sh.save(sheet)
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "duration": round(dur, 2), "sheet": sheet}
