"""줄별 mp3(서버 gen11 결과)를 대화 샘플 한 편으로 — 무음 자름·loudnorm -16·라이브 1.25배·줄 사이 간격.
사용: py assemble.py <raw폴더> <출력폴더>"""
import json, os, subprocess, sys, glob
RAW, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True); W = os.path.join(RAW, "_w"); os.makedirs(W, exist_ok=True)
TEMPO = 1.25 / 1.2            # API 상한 1.2로 합성 → 라이브 기본 1.25배에 맞춘다(audio_post와 같은 방식: atempo)
GAP_SAME, GAP_TURN = 0.30, 0.22   # 같은 화자 다음 줄 / 화자가 바뀔 때(주고받기는 조금 붙인다)
plan = json.load(open(os.path.join(RAW, "plan.json"), encoding="utf-8"))["plan"]
def dur(f): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f],capture_output=True,text=True).stdout)
res = []
for name, lines in plan.items():
    parts, tl, t, prev = [], [], 0.0, None
    for l in lines:
        src = os.path.join(RAW, l["file"]); c = os.path.join(W, l["file"].replace(".mp3", ".wav"))
        subprocess.run(["ffmpeg","-y","-v","error","-i",src,"-af",
            f"atempo={TEMPO:.4f},silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100",
            "-ac","1",c], check=True)
        if prev is not None:
            g = GAP_SAME if prev == l["who"] else GAP_TURN
            s = os.path.join(W, f"sil_{int(g*1000)}.wav")
            if not os.path.exists(s): subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=44100:cl=mono","-t",str(g),s],check=True)
            parts.append(s); t += g
        d = dur(c); tl.append({"who": l["who"], "text": l["text"], "t": round(t, 2), "dur": round(d, 2)})
        parts.append(c); t += d; prev = l["who"]
    lst = os.path.join(W, f"{name}.txt")
    open(lst, "w", encoding="utf-8").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",lst,"-c:a","libmp3lame","-b:a","160k",os.path.join(OUT, f"{name}.mp3")],check=True)
    res.append({"name": name, "total": round(t, 2), "lines": tl})
json.dump(res, open(os.path.join(OUT, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in res: print(r["name"], r["total"], "초", len(r["lines"]), "줄")
