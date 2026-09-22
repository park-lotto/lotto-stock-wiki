import json,sys,numpy as np,soundfile as sf,subprocess,collections
sys.stdout.reconfigure(encoding="utf-8")
d=sys.argv[1]; P=json.load(open(f"{d}/plan.json",encoding="utf-8")); SR=44100
def load(p):
    r=subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True)
    return np.frombuffer(r.stdout,np.float32).astype(float)
fin=load(f"{d}/final.mp4"); nar=load(f"{d}/narr.wav")
n=min(len(fin),len(nar)); fin,nar=fin[:n],nar[:n]
# 정렬(aac 지연) + 나레이션 배율을 최소제곱으로
best=None
for lag in range(-3000,3001,1):
    a=fin[max(0,lag):n+min(0,lag)]; b=nar[max(0,-lag):n-max(0,lag)]
    if lag%50: continue
    c=float(a@b)/(float(b@b)+1e-9)
    e=float(((a-c*b)**2).sum())
    if best is None or e<best[0]: best=(e,lag,c)
_,lag0,_=best
for lag in range(lag0-60,lag0+61):
    a=fin[max(0,lag):n+min(0,lag)]; b=nar[max(0,-lag):n-max(0,lag)]
    c=float(a@b)/(float(b@b)+1e-9); e=float(((a-c*b)**2).sum())
    if e<best[0]: best=(e,lag,c)
_,lag,c=best
a=fin[max(0,lag):n+min(0,lag)]; b=nar[max(0,-lag):n-max(0,lag)]
res=a-c*b; off=max(0,lag)/SR
print(f"정렬 {lag/SR*1000:.1f}ms · 나레이션 배율 {c:.3f} · 잔여/원본 {20*np.log10(np.std(res)/np.std(a)):.1f}dB")
k=int(0.005*SR); r=20*np.log10(np.sqrt(np.convolve(res**2,np.ones(k)/k,"same"))+1e-9)
floor=np.percentile(r,50); on=r>floor+18
ev=[];i=0
while i<len(on):
    if on[i]:
        j=i
        while j<len(on) and on[j:j+int(0.03*SR)].any(): j+=1
        ev.append((i/SR+off,float(r[i:j].max()))); i=j
    else: i+=1
plan=[(s,t) for s,t,_ in P["events"]]
hit=[(s,t,min(e[0] for e in ev if abs(e[0]-t)<=0.05)-t) for s,t in plan if any(abs(e[0]-t)<=0.05 for e in ev)]
miss=[(s,t) for s,t in plan if not any(abs(e[0]-t)<=0.05 for e in ev)]
extra=[e for e in ev if not any(abs(e[0]-t)<=0.08 for _,t in plan)]
print(f"계획 {len(plan)}발 · 잔여에서 찾음 {len(hit)} · 못찾음 {len(miss)} · 계획밖 {len(extra)}")
dl=np.array([h[2] for h in hit])*1000; print(f"시각 오차 중앙 {np.median(dl):+.0f}ms · 최대 {np.abs(dl).max():.0f}ms")
for m in miss: print("  못찾음",m)
for e in extra: print("  계획밖",round(e[0],2),round(e[1],1))
# 크기: 효과음(잔여) 20ms 최대 vs 나레이션 50ms 중앙(섞인 뒤 배율 반영)
vb=c*b; fr=int(0.05*SR); vr=20*np.log10(np.sqrt((vb[:len(vb)//fr*fr].reshape(-1,fr)**2).mean(1))+1e-9); vm=float(np.median(vr[vr>vr.max()-40]))
EVEN={"opener":-8.8,"dung":-7.0,"pop":-11.9,"ding":-14.7,"whoosh":-20.2,"tick":-22.4,"click2":-20.6}; EV=-17.5
lv=collections.defaultdict(list); kk=int(0.02*SR)
for s,t in plan:
    i0=int((t-off)*SR); seg=res[max(0,i0):i0+int(0.3*SR)]
    if len(seg)>kk: lv[s].append(float(20*np.log10(np.sqrt(np.convolve(seg**2,np.ones(kk)/kk,"valid")).max()+1e-9)))
print("목소리 대비 효과음 크기 (우리 / 이븐쇼핑)")
for s in EVEN:
    if lv[s]: print(f"  {s:7s} {len(lv[s]):2d}발 {np.median(lv[s])-vm:+5.1f} / {EVEN[s]-EV:+5.1f}dB  차이 {np.median(lv[s])-vm-(EVEN[s]-EV):+4.1f}")
