"""배경음 목록 중복 검사(관제 146). Shazam(곡 길이 20%·60% 두 지점) 이름 중복 + 스펙트럼 유사도 상위 쌍.
사용: py -3.12 tools/bgm_lib/dedupe.py shopping_shorts/assets/bgm_lib <임시폴더>   (shazamio 는 3.12에만 설치됨 — 3.14 빌드 실패)"""
import asyncio, subprocess, sys, os, glob, itertools
import numpy as np
from shazamio import Shazam
D=sys.argv[1]; T=sys.argv[2]
files=sorted(glob.glob(os.path.join(D,"*.mp3")))
def pcm(f,ss,t):
    raw=subprocess.run(["ffmpeg","-nostdin","-v","error","-ss",str(ss),"-t",str(t),"-i",f,"-ac","1","-ar","4000","-f","f32le","-"],capture_output=True,check=True).stdout
    return np.frombuffer(raw,dtype=np.float32)
def chroma(f):  # 곡 전체 스펙트럼 지문(키·속도 같으면 비슷)
    w=pcm(f,0,60); n=1024; fr=[np.abs(np.fft.rfft(w[i:i+n]*np.hanning(n))) for i in range(0,len(w)-n,n)]
    s=np.log1p(np.mean(fr,axis=0)); return (s-s.mean())/s.std()
async def main():
    names={}
    for f in files:
        ids=[]
        d=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]).decode())
        for ss in (round(d*0.2,1), round(d*0.6,1)):
            out=os.path.join(T,"_d.mp3"); subprocess.run(["ffmpeg","-nostdin","-y","-loglevel","error","-ss",str(ss),"-t",str(min(10,d*0.35)),"-i",f,out],check=True)
            r=await Shazam().recognize(out); tr=r.get("track") or {}; ids.append((tr.get("title") or "").lower())
        names[os.path.basename(f)]=ids; print(os.path.basename(f), ids, flush=True)
    print("--- 이름 중복")
    seen={}
    for k,v in names.items():
        for t in set(v)-{""}:
            seen.setdefault(t,set()).add(k)
    dup=[(t,s) for t,s in seen.items() if len(s)>1]
    print(dup or "없음")
    print("--- 스펙트럼 유사도 상위 5쌍")
    ch={os.path.basename(f):chroma(f) for f in files}
    pairs=sorted(((float(np.dot(ch[a],ch[b])/len(ch[a])),a,b) for a,b in itertools.combinations(ch,2)),reverse=True)[:5]
    for p in pairs: print(round(p[0],3),p[1],p[2])
asyncio.run(main())
