# -*- coding: utf-8 -*-
# 썰템홈샷 손 단계(10-27 10 하리보·11 호빵, 98 #178): 끝 배경음악이 마지막 프레임에서 뚝 끊기지 않게 소리 끝을 짧게 페이드아웃.
#  tail_pad 가 늘린 여운 구간은 무음(apad)이라 배경음악이 말 끝 바로 뒤에서 뚝 끊긴다 → 마지막 말 끝(나레 silencedetect −45dB)부터 영상 끝까지 afade.
#  영상 copy · 광고 표식(comment) 유지 → finalize.seal. 순서 = render → tail_pad → fade_tail → tp_limit → checks.
# PYTHONUTF8=1 py channel/banggu/썰템홈샷_하이브리드/fade_tail.py <final.mp4> <대본.json> <나레.mp3>
import sys, subprocess, json, re, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import ad_mark, finalize

fin, script, narr = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
dur = float(json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(fin)],
                                      capture_output=True, text=True).stdout)["format"]["duration"])
e = subprocess.run(["ffmpeg", "-i", narr, "-af", "silencedetect=n=-45dB:d=0.1", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", e)]
speech_end = st[-1] if st else dur - 0.8
# 소리 내용 끝 = tail_pad 가 붙인 디지털 무음(apad) 시작 — 페이드는 거기서 0 이 되게(그 뒤가 무음이라 중간에 뚝 끊기지 않게)
e2 = subprocess.run(["ffmpeg", "-i", str(fin), "-vn", "-af", "silencedetect=n=-70dB:d=0.05", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
pads = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", e2) if float(x) > speech_end]
content_end = pads[-1] if pads else dur
fade_st = max(speech_end, content_end - 1.0)
fade_d = round(content_end - fade_st, 3)
print(f"영상 {dur:.3f} · 말 끝 {speech_end:.3f} · 소리 내용 끝 {content_end:.3f} · 페이드 {fade_st:.3f}~{content_end:.3f} ({fade_d}초) · 여운 {dur - speech_end:.3f}초")
if dur - speech_end < 0.6:
    raise SystemExit("끝 여운 0.6초 미만 — tail_pad 를 먼저(여운초 늘려서)")
tmp = fin.with_name("final_fade.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(fin), "-map", "0", "-map_metadata", "0", "-c:v", "copy",
                "-af", f"afade=t=out:st={fade_st:.3f}:d={fade_d:.3f},aresample=48000", "-c:a", "aac", "-b:a", "192k",
                "-metadata", f"comment={ad_mark.MARK}", "-movflags", "+faststart", str(tmp)], check=True, stdin=subprocess.DEVNULL)
shutil.move(str(tmp), str(fin))
finalize.seal(fin, "narr_video+thumb+tail_pad+fade_tail", script)
