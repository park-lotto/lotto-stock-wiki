import json,subprocess,re,wave,numpy as np
L=[re.sub(r"^/c/","C:/",l.strip()) for l in open("list.txt",encoding="utf8") if l.strip()]
sp=json.load(open("spots.json"))
for v,D in (("w",18),("t",12)):
    out=np.zeros((D*48000,2),np.float32)
    for k,(c,a,d,S) in enumerate(sp[v]):
        o=subprocess.run(["ffmpeg","-nostats","-hide_banner","-ss",str(a),"-t",str(d),"-i",L[c],"-vn","-af","ebur128","-f","null","-"],capture_output=True,text=True).stderr
        li=float(o.rsplit("I:",1)[1].split("LUFS")[0]); g=-15-li
        subprocess.run(["ffmpeg","-v","error","-y","-ss",str(a),"-t",str(d),"-i",L[c],"-vn","-ar","48000","-ac","2","-af",f"volume={g}dB,afade=t=in:d=0.15,afade=t=out:st={d-0.15}:d=0.15","-f","s16le",f"aud/c{v}{k}.raw"],check=True)
        x=np.frombuffer(open(f"aud/c{v}{k}.raw","rb").read(),np.int16).reshape(-1,2).astype(np.float32)/32768
        i0=int(S*48000); out[i0:i0+len(x)]+=x
    print(v,"peak",20*np.log10(np.abs(out).max()))
    out=np.clip(out,-0.89,0.89)
    w=wave.open(f"aud/mix_{v}.wav","wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes((out*32767).astype(np.int16).tobytes()); w.close()
