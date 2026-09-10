"""원본 프레임 하단의 단색 자막 전용 영역을 판정한다."""
from pathlib import Path

import numpy as np
from PIL import Image


def detect_bottom_caption_slot(path: Path) -> dict:
    pixels = np.asarray(Image.open(path).convert("RGB"))
    height, width, _ = pixels.shape
    bottom = pixels[-1].astype(float)
    matched = []
    for y in range(height - 1, int(height * .55), -1):
        scan = pixels[y].astype(float)
        if np.mean(np.std(scan, axis=0)) < 7 and np.mean(np.abs(scan - bottom)) < 14:
            matched.append(y)
        else:
            break
    top = min(matched) if matched else height
    band_height = height - top
    ratio = band_height / height
    rgb = np.median(pixels[top:] if band_height else pixels[-1:], axis=(0, 1)).astype(int)
    return {
        "mode": "reserved" if ratio >= .09 else "overlay",
        "y": top if ratio >= .09 else round(height * .68),
        "height": band_height if ratio >= .09 else 28,
        "background": "#{:02X}{:02X}{:02X}".format(*rgb),
        "ratio": round(ratio, 3),
    }
