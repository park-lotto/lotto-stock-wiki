"""gen_mixed 결과 폴더 → 한 편. 조각마다 앞뒤 무음 자르고 loudnorm -16(엔진 간 크기 맞춤),
조각 안 긴 공백은 0.22초로 줄이고, 조각 사이 0.3초, 마지막에 1.25배(라이브 기본). 사용: py assemble_mixed.py <조각폴더> <출력.mp3>"""
import json, os, subprocess, sys
src, dst = sys.argv[1], sys.argv[2]
meta = json.load(open(os.path.join(src, "segs.json"), encoding="utf-8"))
w = os.path.join(src, "_w"); os.makedirs(w, exist_ok=True)
sil = os.path.join(w, "gap.wav")
subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=44100:cl=mono","-t","0.3",sil],check=True)
parts = []
for m in meta:
    o = os.path.join(w, m["file"].replace(".mp3", ".wav"))
    subprocess.run(["ffmpeg","-y","-v","error","-i",os.path.join(src,m["file"]),"-af",
        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
        "silenceremove=stop_periods=-1:stop_duration=0.3:stop_threshold=-40dB:stop_silence=0.22,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100",
        "-ac","1",o],check=True)
    if parts: parts.append(sil)
    parts.append(o)
lst = os.path.join(w, "list.txt")
open(lst,"w",encoding="utf-8").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",lst,"-af","atempo=1.25","-b:a","160k",dst],check=True)
print(dst)
