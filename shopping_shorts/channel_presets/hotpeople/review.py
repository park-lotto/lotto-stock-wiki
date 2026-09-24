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
