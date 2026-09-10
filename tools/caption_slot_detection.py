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


def extend_reserved_slot_over_source_text(path: Path, slot: dict) -> dict:
    """단색 하단 띠 안의 출처 글자 때문에 끊긴 시작점을 띠의 실제 시작점까지 올린다."""
    if slot.get("mode") != "reserved":
        return slot
    pixels = np.asarray(Image.open(path).convert("RGB"))
    height, width, _ = pixels.shape
    background = np.array([int(slot["background"][i:i + 2], 16) for i in (1, 3, 5)])
    top = int(slot["y"])
    floor = max(round(height * .55), top - round(height * .18))
    misses = 0
    for y in range(top - 1, floor - 1, -1):
        distance = np.max(np.abs(pixels[y].astype(int) - background), axis=1)
        # 출처 글자는 폭 일부만 차지하므로 배경색 픽셀이 과반이면 같은 하단 띠다.
        if float(np.mean(distance <= 26)) >= .56:
            top = y
            misses = 0
        else:
            misses += 1
            if misses >= 2:
                break
    expanded = dict(slot)
    expanded.update({"y": top, "height": height - top, "ratio": round((height - top) / height, 3)})
    return expanded
