# -*- coding: utf-8 -*-
# 썰템홈샷 손 단계(10-27, 98 #170): 정지에 가까운 원본 구간을 같은 크기로 천천히 다가가는 영상으로 굽기(멈춤 검사 대응).
# zoomclip.py <src.mp4> <ss> <dur> <out.mp4> <zoom> <cx> <cy> — 원본 구간을 같은 크기로, cx,cy(0~1) 쪽으로 천천히 다가가는 영상(멈춤 방지)
import sys, subprocess
src, ss, dur, out, z, cx, cy = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], float(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7])
wh = subprocess.run(["ffprobe","-v","error","-select_streams","v","-show_entries","stream=width,height","-of","csv=p=0",src],capture_output=True,text=True).stdout.strip().split(",")
W, H = int(wh[0]), int(wh[1])
f = f"(1+{z-1}*t/{dur})"
vf = (f"fps=30,scale=w='trunc({W}*{f}/2)*2':h='trunc({H}*{f}/2)*2':eval=frame:flags=lanczos,crop={W}:{H}:x='(iw-{W})*{cx}':y='(ih-{H})*{cy}',setsar=1")
subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{ss}","-t",f"{dur}","-i",src,"-vf",vf,"-an","-c:v","libx264","-crf","16","-pix_fmt","yuv420p",out],check=True,stdin=subprocess.DEVNULL)
print(out)
