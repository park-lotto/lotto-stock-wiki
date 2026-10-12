import json,subprocess,re,sys,glob,os
import whisper
sys.stdout.reconfigure(encoding="utf-8")
m=whisper.load_model("small")
out={}
for mp4 in sorted(glob.glob("*.mp4")):
    vid=mp4[:-4]
    # cuts
    p=subprocess.run(["ffmpeg","-i",mp4,"-vf","select='gt(scene,0.30)',showinfo","-an","-f","null","-"],capture_output=True,text=True,encoding="utf-8",errors="replace")
    cuts=[float(x) for x in re.findall(r"pts_time:([\d.]+)",p.stderr)]
    dur=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",mp4],capture_output=True,text=True).stdout)
    r=m.transcribe(f"sep/htdemucs/{vid}/vocals.wav",language="ko",word_timestamps=True)
    segs=[{"s":round(s["start"],2),"e":round(s["end"],2),"t":s["text"].strip()} for s in r["segments"]]
    out[vid]={"dur":dur,"cuts":cuts,"segs":segs}
    print(vid,round(dur,1),"cuts",len(cuts),"segs",len(segs))
json.dump(out,open("prep.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
