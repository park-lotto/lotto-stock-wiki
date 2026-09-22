import json,sys,os,shutil,subprocess,numpy as np,soundfile as sf
sys.stdout.reconfigure(encoding="utf-8")
OUT="C:/Users/TheRose/Desktop/이븐쇼핑_효과음_벤치마크"
A=f"{OUT}/1_이븐쇼핑_실측샘플"; B=f"{OUT}/2_추천후보(길이맞춤)"
for d in (A,B): os.makedirs(d,exist_ok=True)
SR=44100
rows=json.load(open("rows.json",encoding="utf-8")); cap=json.load(open("capchg.json")); best=json.load(open("best2.json",encoding="utf-8"))
NAME={"오프너":"0_오프너(영상시작)","뽁":"1_뽁","둥":"2_둥(반전강조)","띠링":"3_띠링(결과감탄)","휙":"4_휙샥(자막넘김)","틱":"5_틱","딸깍2":"6_딸깍딸깍"}
LEN={"오프너":1.0,"뽁":0.18,"둥":0.30,"띠링":0.42,"휙":0.20,"틱":0.10,"딸깍2":0.20}
def fade(x,sr):
    n=min(len(x),int(0.03*sr)); x=x.copy(); x[-n:]*=np.linspace(1,0,n); return x
for typ,nm in NAME.items():
    if typ=="오프너":
        picks=[("ABjQ0YCZoes",0.0),("kC8fkx1Ve3Q",0.0),("Iet-btoTSnU",0.0)]
    else:
        R=sorted([r for r in rows if r["typ"]==typ and any(abs(r["t"]-c)<=0.08 for c in cap[r["vid"]])],key=lambda r:-r["peak"])
        seen=set();picks=[]
        for r in R:
            if r["vid"] in seen: continue
            seen.add(r["vid"]); picks.append((r["vid"],r["t"]))
            if len(picks)==3: break
    for i,(v,t) in enumerate(picks,1):
        x=sf.read(f"sep/htdemucs/{v}/nv.wav")[0]
        s=x[max(0,int((t-0.02)*SR)):int((t+LEN[typ]+0.1)*SR)]
        sf.write(f"{A}/{nm}_실측{i}_{v}_{t:.2f}s.wav",fade(s/ (np.abs(s).max()+1e-9)*0.7,SR),SR)
    for i,(sc,p,d) in enumerate(best[typ]["top"][:3],1):
        src=p.split("/")[-1]; tag=("mixkit"+src.split("-")[0]) if "mixkit" in p else os.path.splitext(src)[0]
        r=subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True)
        y=np.frombuffer(r.stdout,np.float32).astype(float); a=np.abs(y); k=max(0,np.argmax(a>a.max()*0.05)-40)
        y=fade(y[k:k+int(LEN[typ]*SR)],SR); y=y/(np.abs(y).max()+1e-9)*0.7
        fn=f"{B}/{nm}_후보{i}_{tag}_유사{sc:.2f}.wav"; sf.write(fn,y,SR)
    print(nm,"ok")
