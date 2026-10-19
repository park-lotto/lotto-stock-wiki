import subprocess, json, numpy as np, statistics as st
cj=json.load(open("cuts.json"))
L=[];W=[];Y=[];hl=0;tot=0;first_hl=0;last_hl=0
for f,o in cj.items():
    ts=[0]+o["sub_times"]; e=o["sub_times"]+[o["dur"]]
    for k,(a,b) in enumerate(zip(ts,e)):
        raw=subprocess.run(["ffmpeg","-v","error","-ss",f"{(a+b)/2:.2f}","-i",f,"-frames:v","1","-vf","crop=1080:260:0:1272","-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True).stdout
        im=np.frombuffer(raw,np.uint8).reshape(260,1080,3).astype(int)
        ink=(im.max(axis=2)<90)                      # 검정 글자
        mark=((im[:,:,0]>230)&(im[:,:,1]>205)&(im[:,:,1]<240)&(im[:,:,2]<185)).mean()>0.01
        rows=ink.mean(axis=1)>0.003; bands=[];s=None
        for y in range(261):
            on=y<260 and rows[y]
            if on and s is None: s=y
            if not on and s is not None:
                if y-s>20: bands.append((s,y))
                s=None
        if not bands: continue
        tot+=1; hl+=mark; first_hl+= mark and k==0; last_hl+= mark and k==len(ts)-1
        L.append(len(bands)); Y.append(bands[0][0]+1272)
        for s0,e0 in bands:
            xs=np.where(ink[s0:e0].any(axis=0))[0]; W.append(xs.max()-xs.min())
print("자막",tot,"개 | 1줄",L.count(1),"2줄",L.count(2),"3줄+",sum(1 for x in L if x>2))
print("줄 폭 px: 중앙",int(st.median(W)),"최대",max(W),"90%",int(np.percentile(W,90)))
print("첫 줄 시작 y: 중앙",int(st.median(Y)),"범위",min(Y),max(Y))
print("형광펜 자막",hl,"/",tot,"| 첫 자막이 형광펜",first_hl,"/",len(cj),"| 마지막이 형광펜",last_hl,"/",len(cj))
