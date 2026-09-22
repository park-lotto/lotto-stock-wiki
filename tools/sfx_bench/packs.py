import json,sys,os,subprocess,itertools,random,shutil,numpy as np,soundfile as sf
sys.stdout.reconfigure(encoding="utf-8")
SR=44100
sel=json.load(open("sel.json",encoding="utf-8"))
def P(typ,idx): return sel[typ][idx]["p"]
# 눈 검수로 남긴 후보(0부터): 칸 -> [(이름, 경로, 원본키)]
KEEP={"오프너":[0,1,2],"뽁":[0,1,2,3,5],"둥":[0,5,3,4],"띠링":[0,2,3,4],"휙":[0,1,3,5],"틱":[0,1,2],"딸깍2":[0,2,3]}
def key(p):  # 같은 원본 판정(음높이 변형은 원본과 같은 키)
    b=os.path.basename(p).split("_음높이")[0].replace("뽁소리2","뽁소리 (2)").replace(".wav","").replace(".mp3","")
    return b
def load(p):
    x=subprocess.run(["ffmpeg","-v","error","-i",p,"-t","3","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True).stdout
    x=np.frombuffer(x,np.float32).astype(float); a=np.abs(x); i=max(0,np.argmax(a>a.max()*0.05)-60); return x[i:]
LEN={"뽁":0.2,"둥":0.32,"띠링":0.45,"휙":0.22,"틱":0.10,"딸깍2":0.2,"오프너":1.1}
LVL={"오프너":-8.8,"둥":-7.0,"뽁":-11.9,"띠링":-14.7,"휙":-20.2,"틱":-22.4,"딸깍2":-20.6}   # 이븐쇼핑 20ms 최대세기(dB)
def shape(typ,x):
    y=np.pad(x,(0,max(0,int(LEN[typ]*SR)-len(x))))[:int(LEN[typ]*SR)].copy()
    n=int(min(0.25,LEN[typ]/3)*SR); y[-n:]*=np.linspace(1,0,n)**2
    fr=int(0.02*SR); pk=np.sqrt(np.convolve(y**2,np.ones(fr)/fr,"valid")).max()
    y=y*(10**(LVL[typ]/20)/pk)
    if np.abs(y).max()>0.98: y*=0.98/np.abs(y).max()
    return y
cands={t:[(f"{t}{chr(65+j)}",P(t,i),key(P(t,i))) for j,i in enumerate(v)] for t,v in KEEP.items()}
# 딸깍딸깍 = 틱 후보 두 번(0.1초 간격) 조립 3개 추가
os.makedirs("dd",exist_ok=True)
for j,i in enumerate([0,1]):
    x=load(P("틱",i))[:int(0.045*SR)]; y=np.zeros(int(0.2*SR)); y[:len(x)]+=x; o=int(0.1*SR); y[o:o+len(x)]+=x*0.9
    fn=os.path.abspath(f"dd/딸깍두번_{key(P('틱',i))}.wav").replace("\\","/"); sf.write(fn,y,SR)
    cands["딸깍2"].append((f"딸깍2{chr(68+j)}",fn,key(P("틱",i))))
SLOTS=["오프너","뽁","둥","띠링","휙","틱","딸깍2"]
for t in SLOTS: print(t,[c[0] for c in cands[t]])
# 팩 뽑기: 서로 다른 칸 수 최소값을 키우고, 후보 사용횟수를 고르게
random.seed(3)
def valid(pk):
    ks=[cands[t][i][2] for t,i in zip(SLOTS,pk)]; return len(ks)==len(set(ks))
allc=[pk for pk in itertools.product(*[range(len(cands[t])) for t in SLOTS]) if valid(pk)]
print("가능한 조합",len(allc))
N=int(sys.argv[1]) if len(sys.argv)>1 else 20
packs=[random.choice(allc)]
use={(t,i):0 for t in SLOTS for i in range(len(cands[t]))}
for t,i in zip(SLOTS,packs[0]): use[(t,i)]+=1
while len(packs)<N:
    best=None
    for pk in random.sample(allc,6000):
        dmin=min(sum(a!=b for a,b in zip(pk,q)) for q in packs)
        bal=-sum(use[(t,i)] for t,i in zip(SLOTS,pk))
        s=(dmin,bal)
        if best is None or s>best[0]: best=(s,pk)
    packs.append(best[1])
    for t,i in zip(SLOTS,best[1]): use[(t,i)]+=1
D=[sum(a!=b for a,b in zip(p,q)) for p,q in itertools.combinations(packs,2)]
print(f"팩 {N}개 · 두 팩 사이 다른 칸: 최소 {min(D)} · 중앙 {int(np.median(D))} · 최대 {max(D)} (7칸 중)")
print("후보별 사용횟수:",{f"{cands[t][i][0]}":use[(t,i)] for t in SLOTS for i in range(len(cands[t]))})
OUT="C:/Users/TheRose/Desktop/이븐쇼핑_효과음_벤치마크/3_효과음팩"
if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
cache={}
man=[]
DEMO=[("오프너",0.06),("휙",1.60),("틱",1.70),("뽁",2.40),("띠링",3.20),("휙",4.00),("둥",4.80),("딸깍2",5.60),("틱",5.69),("뽁",6.30),("띠링",7.10),("휙",7.90)]
for n,pk in enumerate(packs,1):
    d=f"{OUT}/팩{n:02d}"; os.makedirs(d); row={"팩":f"팩{n:02d}"}
    snd={}
    for t,i in zip(SLOTS,pk):
        name,p,_=cands[t][i]
        if p not in cache: cache[p]=load(p)
        y=shape(t,cache[p]); snd[t]=y
        sf.write(f"{d}/{SLOTS.index(t)}_{t.replace('2','딸깍')}_{name}.wav",y,SR)
        row[t]=f"{name} ({os.path.basename(p)})"
    mix=np.zeros(int(8.6*SR))
    for t,s in DEMO:
        y=snd[t]; i=int(s*SR); mix[i:i+len(y)]+=y[:len(mix)-i]
    sf.write(f"{d}/미리듣기_이븐쇼핑순서.wav",mix/max(1,np.abs(mix).max()/0.95),SR)
    man.append(row)
json.dump({"slots":SLOTS,"packs":man,"min_diff":min(D),"median_diff":int(np.median(D))},open(f"{OUT}/팩구성표.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("저장:",OUT)
