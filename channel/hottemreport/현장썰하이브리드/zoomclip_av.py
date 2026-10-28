# -*- coding: utf-8 -*-
# 숏템리폿 손 단계(10-28, 98 #188 — 정지에 가까운 원음 구간 멈춤 대응): 원본 구간을 같은 크기로 cx,cy(0~1) 쪽으로 천천히 다가가는 영상 + 원음 그대로.
#  banggu zoomclip.py 와 같은 확대식(소리 없는 판) — 원음 블록(O)은 소리가 그 파일에서 나와야 해서 소리를 살린 판이다.
# PYTHONUTF8=1 py channel/hottemreport/현장썰하이브리드/zoomclip_av.py <src.mp4> <ss> <dur> <out.mp4> <zoom> <cx> <cy>
import sys, subprocess
src, ss, dur, out, z, cx, cy = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], float(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7])
wh = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip().split(",")
W, H = int(wh[0]), int(wh[1])
f = f"(1+{z - 1}*t/{dur})"
vf = f"fps=30,scale=w='trunc({W}*{f}/2)*2':h='trunc({H}*{f}/2)*2':eval=frame:flags=lanczos,crop={W}:{H}:x='(iw-{W})*{cx}':y='(ih-{H})*{cy}',setsar=1"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss}", "-t", f"{dur}", "-i", src, "-vf", vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", out], check=True, stdin=subprocess.DEVNULL)
print(out)
