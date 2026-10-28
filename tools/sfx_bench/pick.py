import json,sys,subprocess,numpy as np
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.rcParams["font.family"]="Malgun Gothic"
pool=json.load(open("pool.json",encoding="utf-8"))
MARGIN={"뽁":0.16,"둥":0.28,"띠링":0.16,"휙":0.16,"틱":0.16,"딸깍2":0.17,"오프너":0.16}
LEN={"뽁":0.2,"둥":0.35,"띠링":0.45,"휙":0.25,"틱":0.12,"딸깍2":0.2,"오프너":1.0}
sel={}
for typ,d in pool.items():
    c=[x for x in d["cands"] if x["score"]>=d["ceil"]-MARGIN[typ]][:6]
    sel[typ]=c; print(typ,len(c),[f'{x["p"].split("/")[-1][:22]}({x["score"]:.2f})' for x in c])
json.dump(sel,open("sel.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
SR=44100
fig,axs=plt.subplots(7,6,figsize=(24,20))
for r,(typ,c) in enumerate(sel.items()):
    for k in range(6):
        ax=axs[r,k]; ax.axis("off")
        if k>=len(c): continue
        x=subprocess.run(["ffmpeg","-v","error","-i",c[k]["p"],"-t","3","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True).stdout
        x=np.frombuffer(x,np.float32).astype(float); a=np.abs(x); i=max(0,np.argmax(a>a.max()*0.05)-100); x=x[i:i+int(LEN[typ]*SR)]
        ax.axis("on"); ax.specgram(x,NFFT=512,Fs=SR,noverlap=448,cmap="magma",vmin=-110); ax.set_ylim(0,16000)
        ax.set_title(f'{typ}{k+1} {c[k]["p"].split("/")[-1][:20]} {c[k]["score"]:.2f}',fontsize=8)
plt.tight_layout(); plt.savefig("sel.png",dpi=42)
