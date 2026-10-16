# -*- coding: utf-8 -*-
"""바나나맛우유 2편 — 한 자막 페이지 안에서 컷을 두 번 바꾸는 '이음 재료' 만들기 (조율자 10-16: 컷 중앙 ≤2.2초·컷 ≥14).
narr_video 는 컷을 자막 페이지 시작에서만 바꾼다(도구 담당 소관 — 손대지 않음). 그래서 한 페이지에 들어갈 재료를
미리 두 토막 이어 붙인 영상 한 개로 만들어 재료.json 의 그 컷 src 로 준다(ss 0, src_crop 없음, 칸 크기 그대로).
토막마다 자기 src_crop 으로 자르고 그 컷 칸(box w×h) 비율로 cover → 이어 붙임(30fps, tv 범위 — narr_video 와 같은 색 범위).
    PYTHONUTF8=1 py channel/banggu/칼카피_banana/build_combos.py
"""
import json, subprocess
from pathlib import Path
HQ = Path("C:/숏템_칼카피/banggu/칼카피_banana/make/hq")
MEME = "C:/숏템_칼카피/packs/meme/meme_pack/gdb_xcqjp88f5st8k9jg.mp4"
W = "v_WxIoAPn7MLw.mp4"; WC = [60, 60, 1700, 840]; Y = "v_NHSounPyqCQ.mp4"
# 컷 번호: (칸 [w,h], [(소스, 시작초, 길이초, crop|None), …])  — 길이 합 = 그 페이지 길이(narr_tight 기준) + 끝 여유 0.3
COMBOS = {
    1: ([1080, 760], [("v_yX8wLi__dRc.mp4", 12.0, 1.67, [220, 140, 1420, 650]), (W, 114.4, 1.35 + 0.3, WC)]),
    2: ([924, 873], [(MEME, 0.0, 1.6, None), (W, 120.3, 1.75 + 0.3, WC)]),
    5: ([1080, 933], [(W, 72.5, 1.6, WC), (W, 86.0, 1.25 + 0.3, WC)]),
    7: ([1080, 885], [(W, 77.0, 1.9, WC), (W, 84.5, 1.43 + 0.3, WC)]),
    8: ([1080, 699], [(Y, 0.3, 1.6, [60, 20, 1160, 520]), (Y, 15.0, 1.5 + 0.3, [60, 20, 1160, 520])]),
    9: ([1080, 700], [(Y, 7.6, 1.32, [200, 90, 800, 470]), (W, 109.0, 1.3 + 0.3, [200, 60, 1500, 800])]),
    10: ([1080, 933], [(W, 110.3, 1.6, [200, 60, 1500, 800]), (W, 104.0, 1.34 + 0.3, [460, 40, 1000, 860])]),
}


def part(src, ss, dur, crop, w, h, out):
    s = src if Path(src).is_absolute() else str(HQ / src)
    pre = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}," if crop else ""
    vf = f"{pre}scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30,scale=out_range=tv,format=yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-i", s, "-t", f"{dur:.3f}", "-vf", vf, "-an",
                    "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-color_range", "tv", str(out)], check=True, stdin=subprocess.DEVNULL)


for k, (box, parts) in COMBOS.items():
    w, h = box
    files = []
    for j, (src, ss, dur, crop) in enumerate(parts):
        f = HQ / f"_p{k}_{j}.mp4"
        part(src, ss, dur, crop, w, h, f)
        files.append(f)
    lst = HQ / f"_p{k}.txt"
    lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
    out = HQ / f"combo_{k}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True, stdin=subprocess.DEVNULL)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    print(k, out.name, d, [round(p[2], 2) for p in parts])
