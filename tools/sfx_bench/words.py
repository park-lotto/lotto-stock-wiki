import json,sys,whisper
sys.stdout.reconfigure(encoding="utf-8")
m=whisper.load_model("small"); p=json.load(open("prep.json",encoding="utf-8"))
for vid in p:
    r=m.transcribe(f"sep/htdemucs/{vid}/vocals.wav",language="ko",word_timestamps=True)
    p[vid]["words"]=[{"s":round(w["start"],2),"e":round(w["end"],2),"w":w["word"].strip()} for s in r["segments"] for w in s["words"]]
    print(vid,len(p[vid]["words"]))
json.dump(p,open("prep.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
