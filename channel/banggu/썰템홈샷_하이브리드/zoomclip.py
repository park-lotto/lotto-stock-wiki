# -*- coding: utf-8 -*-
# 썰템홈샷 손 단계(10-27, 98 #170): 정지에 가까운 원본 구간을 같은 크기로 천천히 다가가는 영상으로 굽기(멈춤 검사 대응).
# zoomclip.py <src.mp4> <ss> <dur> <out.mp4> <zoom> <cx> <cy> — 원본 구간을 같은 크기로, cx,cy(0~1) 쪽으로 천천히 다가가는 영상(멈춤 방지)
import sys, subprocess
src, ss, dur, out, z, cx, cy = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], float(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7])
wh = subprocess.run(["ffprobe","-v","error","-select_streams","v","-show_entries","stream=width,height","-of","csv=p=0",src],capture_output=True,text=True).stdout.strip().split(",")
W, H = int(wh[0]), int(wh[1])
# 10-28 (98 #193): 옛 식(scale eval=frame → crop x=(iw-W)*cx)은 crop 이 첫 프레임 크기로만 자리를 정해 x=y=0 에 묶였다
#   → cx,cy 와 상관없이 늘 왼쪽 위로 다가가 물건이 오른쪽 아래로 밀려 나갔다(21 하겐다즈 로고 'Hä' 만 남음). zoompan 은 프레임마다 자리를 다시 잰다.
#   2배로 키운 뒤 zoompan(정수 픽셀 떨림을 줄임) → 원래 크기로.
N = max(1, round(dur * 30))
vf = (f"fps=30,scale={W * 2}:{H * 2}:flags=lanczos,"
      f"zoompan=z='1+{z - 1}*in/{N}':x='(iw-iw/zoom)*{cx}':y='(ih-ih/zoom)*{cy}':d=1:s={W}x{H}:fps=30,setsar=1")
subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{ss}","-t",f"{dur}","-i",src,"-vf",vf,"-an","-c:v","libx264","-crf","16","-pix_fmt","yuv420p",out],check=True,stdin=subprocess.DEVNULL)
print(out)
