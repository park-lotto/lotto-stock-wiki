import subprocess, numpy as np, glob
W,H=1080,1920
for f in sorted(glob.glob("*.mp4")):
    dur=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]).decode())
    raw=subprocess.run(["ffmpeg","-v","error","-i",f,"-vf","fps=2,crop=1080:390:0:80,scale=270:98","-f","rawvideo","-pix_fmt","gray","-"],capture_output=True).stdout
    n=len(raw)//(270*98); a=np.frombuffer(raw[:n*270*98],np.uint8).reshape(n,98,270)
    ink=(a<120).mean(axis=(1,2))       # 헤드라인 영역의 어두운(글자) 비율
    on=ink>0.02
    s="".join("#" if x else "." for x in on)
    print(f"{f[:11]} dur={dur:5.1f} on={on.mean():.0%} {s}")
