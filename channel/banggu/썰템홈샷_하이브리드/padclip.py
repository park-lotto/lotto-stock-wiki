# -*- coding: utf-8 -*-
# 썰템홈샷 손 단계(10-28 18 스니커즈, 98 #190): 가로로 긴 그림(옛 광고 포장·신문 광고)을 세로 칸에 통째로 보이게 굽기.
#  make.py render 는 그림 칸을 늘 cover 로 채워(재료 fit:contain 무시) 가로 글자가 잘린다('MARATHON' → 'ARATHO').
#  → 원본 구간을 칸 비율(1080×1428 = 984×1300)로 미리 굽는다: 뒤 = 같은 화면 흐리게 꽉 채움, 앞 = 폭에 맞춰 통째 + 천천히 다가감(멈춤 검사 대응).
# PYTHONUTF8=1 py channel/banggu/썰템홈샷_하이브리드/padclip.py <src.mp4> <ss> <dur> <out.mp4> [zoom=1.08] [crop=w:h:x:y]
import sys, subprocess
src, ss, dur, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
z = float(sys.argv[5]) if len(sys.argv) > 5 else 1.08
pre = f"crop={sys.argv[6]}," if len(sys.argv) > 6 else ""
W, H = 1080, 1428
f = f"(1+{z - 1}*t/{dur})"
vf = (f"fps=30,{pre}split[a][b];"
      f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.15[bg];"
      f"[b]scale=w='trunc({W}*0.96*{f}/2)*2':h=-2:eval=frame:flags=lanczos[fg];"
      f"[bg][fg]overlay=x='(W-w)/2':y='(H-h)/2':eval=frame,setsar=1")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss}", "-t", f"{dur}", "-i", src, "-filter_complex", vf, "-an",
                "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", out], check=True, stdin=subprocess.DEVNULL)
print(out)
