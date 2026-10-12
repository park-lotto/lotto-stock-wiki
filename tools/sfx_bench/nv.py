import soundfile as sf, numpy as np, glob, os, sys
sys.stdout.reconfigure(encoding="utf-8")
for d in sorted(glob.glob("sep/htdemucs/*")):
    vid=os.path.basename(d)
    x=sum(sf.read(f"{d}/{s}.wav")[0].mean(1) for s in ["drums","bass","other"])
    v=sf.read(f"{d}/vocals.wav")[0].mean(1)
    sf.write(f"{d}/nv.wav",x,44100)
    fr=int(0.05*44100)
    rms=lambda a: 20*np.log10(np.sqrt((a[:len(a)//fr*fr].reshape(-1,fr)**2).mean(1))+1e-9)
    rn,rv=rms(x),rms(v)
    print(f"{vid} 비음성 중앙 {np.median(rn):6.1f}dB  10%분위 {np.percentile(rn,10):6.1f}  음성 중앙 {np.median(rv):6.1f}dB  비음성 -45dB미만 {np.mean(rn<-45)*100:4.0f}%")
