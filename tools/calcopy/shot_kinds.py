# -*- coding: utf-8 -*-
"""컷마다 '움직이는 영상인가 멈춘 사진인가'·그림 상자 크기·등장 효과를 잰다.
사용: PYTHONUTF8=1 py shot_kinds.py <bench.json> <mp4 폴더> [창 시작 y(1920 기준, 기본 bench 의 window y)]
방법: 30fps·270×480 회색으로 전부 풀어, bench 가 잰 컷 경계로 샷을 나눈다.
  움직임 = 샷 안(앞뒤 0.2초 제외) 이웃 프레임 차이의 중앙값(그림 상자 안, 0~255).
  상자   = 창 안에서 배경색과 다른 행·열 범위(1080×1920 좌표로 환산).
  등장   = 컷 직후 프레임들이 0.5초 뒤 프레임과 얼마나 다른가 — 첫 프레임부터 같으면 '바로 뜸'.
★움직임 문턱은 분포를 보고 정한다(콘솔에 전 샷 값을 찍는다) — 값이 두 덩어리로 안 갈리면 판정을 믿지 마라."""
import json, os, subprocess, sys
import numpy as np

W, H, FPS = 270, 480, 30
bench = json.load(open(sys.argv[1], encoding="utf-8")); d = sys.argv[2]
rows_out = []
for vid, pv in bench["per_video"].items():
    path = os.path.join(d, vid + ".mp4")
    if not os.path.exists(path) or "cuts" not in pv or pv.get("variant") != bench["main_variant"]:
        continue
    y0 = int(sys.argv[3]) if len(sys.argv) > 3 else bench["layout"]["window"][1]
    r0 = y0 * H // 1920
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={FPS},scale={W}:{H},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.int16)
    n = len(fr); cuts = [0.0] + pv["cuts"]["cuts"] + [n / FPS]
    bg = int(np.median(fr[n // 2][r0:, :3]))
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        fa, fb = int(round(a * FPS)), min(int(round(b * FPS)), n)
        if fb - fa < 8:
            continue
        mid = fr[(fa + fb) // 2][r0:]
        mask = np.abs(mid - bg) > 12
        rr = np.where(mask.mean(1) > 0.05)[0]; cc = np.where(mask.mean(0) > 0.05)[0]
        if len(rr) == 0 or len(cc) == 0:
            continue
        box = (rr[0] + r0, rr[-1] + r0 + 1, cc[0], cc[-1] + 1)
        seg = fr[fa + 6:fb - 6, box[0]:box[1], box[2]:box[3]] if fb - fa > 20 else fr[fa + 2:fb - 2, box[0]:box[1], box[2]:box[3]]
        dif = np.abs(np.diff(seg, axis=0)).mean((1, 2)) if len(seg) > 1 else np.array([0.0])
        ref = fr[min(fa + 15, fb - 1), r0:]
        ent = [float(np.abs(fr[fa + k, r0:] - ref).mean()) for k in range(0, min(8, fb - fa))]
        settle = next((k for k, e in enumerate(ent) if e < max(1.5, ent[-1] * 1.5)), len(ent))
        rows_out.append({"vid": vid, "shot": i, "t0": round(a, 2), "sec": round(b - a, 2), "motion": round(float(np.median(dif)), 2),
                         "motion_p90": round(float(np.percentile(dif, 90)), 2),
                         "box_y": [int(box[0]) * 4, int(box[1]) * 4], "box_x": [int(box[2]) * 4, int(box[3]) * 4], "h": int(box[1] - box[0]) * 4, "w": int(box[3] - box[2]) * 4,
                         "settle_frames": settle, "ent0": round(ent[0], 1)})
for r in rows_out:
    print(f"{r['vid']} #{r['shot']:>2} {r['t0']:>5}s {r['sec']:>4}s 움직임 {r['motion']:>5} (p90 {r['motion_p90']:>5}) 상자 y{r['box_y']} x{r['box_x']} {r['w']}×{r['h']} 등장 {r['settle_frames']}프레임(첫 차이 {r['ent0']})")
json.dump(rows_out, open(os.path.join(os.path.dirname(sys.argv[1]), "shot_kinds.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
m = sorted(r["motion"] for r in rows_out)
print("\n움직임 값 전체(오름차순):", m)
