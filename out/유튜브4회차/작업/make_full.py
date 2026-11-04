"""4회차 전체 합본: 오프닝 v2(seg/open2.mp4) + 손그림 장면 s01~s12(ink/Sxx/sxx_av.mp4) → seg/yt4_full.mp4
배경음 = 오프닝과 같은 Mixkit 곡을 본편 아래 낮게(-26dB 근처) 깔고, 마지막에 -14 LUFS.
usage: py make_full.py"""
import subprocess
from pathlib import Path
W = Path(__file__).resolve().parent
BGM = W / "music" / "mixkit_130_tech_house_vibes.mp3"
ORDER = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "11B", "12"]   # 11B = 나도 될까(11-04 추가)
parts = [W / "seg" / "open2.mp4"] + [W / "ink" / f"S{k}" / f"s{k.lower()}_av.mp4" for k in ORDER]
for p in parts:
    assert p.exists(), p
def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)
D = [dur(p) for p in parts]
inp, fc = [], ""
for k, p in enumerate(parts):
    inp += ["-i", str(p)]
    fc += f"[{k}:v]fps=30,scale=1920:1080,setsar=1,format=yuv420p,trim=0:{D[k]:.3f},setpts=PTS-STARTPTS[v{k}];"
    fc += f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{D[k]:.3f},asetpts=PTS-STARTPTS[a{k}];"
fc += "".join(f"[v{k}][a{k}]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a0];"
o, T = D[0], sum(D)
n = len(parts)
fc += (f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,aloop=loop=-1:size=2e9,atrim=0:{T - o:.3f},volume=0.05,"
       f"afade=t=in:d=1.5,afade=t=out:st={T - o - 3:.3f}:d=3,adelay={int(o * 1000)}|{int(o * 1000)}[bg];"
       "[a0][bg]amix=inputs=2:normalize=0:duration=first[a]")
out = W / "seg" / "yt4_full.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", *inp, "-i", str(BGM), "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-threads", "4", "-crf", "19", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)], check=True)
print("합본", out, round(dur(out), 2), "초 =", " + ".join(f"{d:.1f}" for d in D))

# 소리 크기: 측정 → 2단계 맞춤(영상 복사) → seg/yt4_full_ln.mp4
import json, re
e = subprocess.run(["ffmpeg", "-v", "info", "-i", str(out), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
m = json.loads(e[e.rindex("{"):e.rindex("}") + 1])
ln = W / "seg" / "yt4_full_ln.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-c:v", "copy", "-af",
                f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']},aresample=48000",
                "-c:a", "aac", "-b:a", "192k", str(ln)], check=True)
print("소리 맞춤", ln)
