# 손 단계 final_tp (98 #176 + #178 끝 페이드): 영상 copy · 소리 = 영상 길이로 자르고 · 말 끝 뒤부터 영상 끝까지 afade(마지막 프레임에서 뚝 끊기지 않게)
#  · alimiter 로 TP ≤ -1.2 · 광고 표식 유지 → finalize.seal(..., 'hottem_render_front+post_meme_thumb+final_tp', 대본)
# PYTHONUTF8=1 py channel/hottemreport/현장썰하이브리드/final_tp.py <in.mp4> <out.mp4> <말 끝 초(완성본 기준)> <대본.json>
import sys, subprocess, json, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import ad_mark, finalize
src, out, speech_end, script = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
vd = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip())
st = speech_end + 0.05
fd = round(vd - st - 0.10, 3)   # 마지막 0.1초는 완전 무음(끝 RMS < -60dB)
assert vd - speech_end >= 0.6, f"끝 여운 {vd - speech_end:.3f} < 0.6"
def meas(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    return I, tp
I0, tp0 = meas(src)
gain = 0.0
for lim in (0.84, 0.80, 0.76, 0.72, 0.68):
    af = f"atrim=0:{vd:.3f},asetpts=N/SR/TB,afade=t=out:st={st:.3f}:d={fd:.3f},volume={gain:.2f}dB,alimiter=limit={lim}:attack=3:release=40:level=false,aresample=48000"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k",
                    "-metadata", f"comment={ad_mark.MARK}", "-movflags", "+faststart", str(out)], check=True, stdin=subprocess.DEVNULL)
    I, tp = meas(out)
    print(f"limit {lim} gain {gain:+.2f} → I {I} TP {tp} (원래 I {I0} TP {tp0}) · 영상 {vd:.3f} · 페이드 {st:.3f}+{fd}")
    if I < -14.6:
        gain = round(gain + (-14.0 - I), 2)
    if tp <= -1.2 and -14.6 <= I <= -13.5:
        break
finalize.seal(out, "hottem_render_front+post_meme_thumb+final_tp", script)
