# -*- coding: utf-8 -*-
# 썰템홈샷 손 단계(10-27 08 칠성사이다):
#  ① narr_video compose 가 조각마다 몇 프레임씩 덜 내어(seg0 113→109·seg1 974→971) 영상이 소리보다 짧아
#     봉인 '영상=소리 길이'(허용 1프레임+0.05초)가 실패할 때 — 마지막 프레임을 그 차이만큼 늘린다(tpad clone).
#  ② [여운초] = 끝 말 뒤 여운이 0.6초에 모자라면(체크리스트 ③, 나레 silencedetect −45dB 기준) 영상(마지막 프레임)·소리(무음) 둘 다 그만큼 더 늘린다.
# 영상만 다시 인코딩(engine.encoder.venc) · 광고 표식(comment) 유지 → finalize.seal 다시. 뒤에 tp_limit.py 를 돌리면 그게 다시 봉인한다.
# PYTHONUTF8=1 py channel/banggu/썰템홈샷_하이브리드/tail_pad.py <final.mp4> <대본.json> [여운초]
import sys, subprocess, json, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import encoder, ad_mark, finalize

fin, script = Path(sys.argv[1]), sys.argv[2]
extra = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0


def durs(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(p)],
                                  capture_output=True, text=True).stdout)
    d = {s["codec_type"]: float(s["duration"]) for s in j["streams"] if s.get("duration")}
    return d.get("video"), d.get("audio")


v, a = durs(fin)
print("전 영상", v, "소리", a)
if a and v and (a > v or extra > 0):
    goal = a + extra
    vpad = round(goal - v + 0.02, 3)
    tmp = fin.with_name("final_pad.mp4")
    aargs = ["-af", f"apad=whole_dur={goal:.3f}", "-c:a", "aac", "-b:a", "192k"] if extra > 0 else ["-c:a", "copy"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(fin), "-map", "0:v", "-map", "0:a", "-map_metadata", "0",
                    "-vf", f"tpad=stop_mode=clone:stop_duration={vpad}", *encoder.venc(16), "-pix_fmt", "yuv420p", "-r", "30",
                    *aargs, "-t", f"{goal + 0.01:.3f}", "-metadata", f"comment={ad_mark.MARK}", "-movflags", "+faststart", str(tmp)],
                   check=True, stdin=subprocess.DEVNULL)
    shutil.move(str(tmp), str(fin))
    print("후 영상·소리", *durs(fin), "표식", ad_mark.MARK in ad_mark._probe(fin)[2])
finalize.seal(fin, "narr_video+thumb+tail_pad", script)
