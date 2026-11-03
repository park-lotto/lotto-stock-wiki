# -*- coding: utf-8 -*-
# 썰템홈샷 손 단계(10-27 06·07, 98 #168): 렌더·썸네일 뒤 완성본의 소리만 리미터로 True Peak ≤ -1.2dBTP · 영상 copy·광고 표식 유지 → finalize.seal 다시.
# PYTHONUTF8=1 py channel/banggu/썰템홈샷_하이브리드/tp_limit.py <final.mp4> <대본.json> [gain dB]
import sys, subprocess, json, re, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
fin, script = Path(sys.argv[1]), sys.argv[2]
def meas(p):
    e = subprocess.run(["ffmpeg","-nostats","-i",str(p),"-vn","-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True,encoding="utf-8",errors="replace").stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    return I, TP
I0, T0 = meas(fin); print("전", I0, T0)
tmp = fin.with_name("final_tp.mp4")
gain = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
for lim in (0.80, 0.75, 0.70):
    af = f"volume={gain}dB,alimiter=limit={lim}:level=false:attack=1:release=60,aresample=48000"
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(fin),"-map","0","-map_metadata","0","-c:v","copy","-af",af,"-c:a","aac","-b:a","192k","-movflags","+faststart",str(tmp)],check=True,stdin=subprocess.DEVNULL)
    I, T = meas(tmp); print("limit", lim, "→", I, T)
    if T <= -1.2: break
shutil.move(str(tmp), str(fin))
from tools.calcopy.engine import finalize
finalize.seal(fin, "narr_video+thumb+tp_limit", script)
print("후", meas(fin))
