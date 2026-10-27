# py endrms.py <mp4> [초=2.5] — 마지막 N초를 0.1초 단위 RMS(dBFS)로
import subprocess,sys,numpy as np,json
p=sys.argv[1]; N=float(sys.argv[2]) if len(sys.argv)>2 else 2.5
d=float(json.loads(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",p],capture_output=True,text=True).stdout)["format"]["duration"])
raw=subprocess.run(["ffmpeg","-v","error","-ss",f"{d-N:.3f}","-i",p,"-vn","-ac","1","-ar","48000","-f","f32le","-"],capture_output=True).stdout
a=np.frombuffer(raw,dtype=np.float32); n=4800
out=[]
for i in range(0,len(a),n):
    x=a[i:i+n]
    if len(x)<n//2: break
    r=float(np.sqrt(np.mean(x*x))+1e-12); out.append((round(d-N+i/48000,1),round(20*np.log10(r),1)))
print("길이",round(d,3)); print(" ".join(f"{t}:{v}" for t,v in out))
