import numpy as np, subprocess, math
from PIL import Image
W,H,FPS=1920,1080,30
imgs=[Image.open(f"search_{i}.png").convert("RGB") for i in range(1,5)]
SB=240; HD=56; SCROLL=1100
def eo(x): x=min(max(x,0),1); return 1-(1-x)**3
def scene(i,t):
    im=imgs[i]; off=SCROLL*eo((t-0.6)/2.2)
    base=im.crop((0,0,W,H)).copy()
    reg=im.crop((SB,HD+int(round(off)),W,HD+int(round(off))+H-HD))
    base.paste(reg,(SB,HD))
    base.paste(im.crop((0,0,W,HD)),(0,0))   # header fixed
    z=1.3-0.3*eo(t/0.9)
    if z>1.001:
        cx,cy=900,28
        cw,ch=W/z,H/z
        x0=min(max(cx-cw/2,0),W-cw); y0=0
        base=base.resize((W,H),Image.LANCZOS,box=(x0,y0,x0+cw,y0+ch))
    return base
def final(i): return scene(i,2.99)
def stack(t):
    p=eo(t)
    bg=Image.new("RGB",(W,H),(236,236,238))
    for i in range(4):
        card=final(i); k=i-1.5
        s=1-0.45*p; ang=k*3.5*p
        cw,ch=int(W*s),int(H*s)
        c=card.resize((cw,ch),Image.LANCZOS).convert("RGBA")
        # border/shadow
        sh=Image.new("RGBA",(cw+24,ch+24),(0,0,0,0)); 
        sh.paste((0,0,0,int(70*p)),(12,16,cw+12,ch+16))
        from PIL import ImageFilter
        sh=sh.filter(ImageFilter.GaussianBlur(10))
        sh.alpha_composite(c,(12,12))
        sh=sh.rotate(-ang,expand=True,resample=Image.BICUBIC)
        cx=960+k*150*p; cy=540+k*45*p
        bg.paste(sh,(int(cx-sh.width/2),int(cy-sh.height/2)),sh)
    return bg
def frame(f):
    t=f/FPS
    if t<12.0:
        i=int(t//3); lt=t-i*3
        a=scene(i,lt)
        if lt>2.7 and i<3:
            b=scene(i+1,lt-3); m=(lt-2.7)/0.3
            a=Image.blend(a,b,m)
        if i==3 and lt>=2.7: pass
        return a
    st=t-12.0
    a=stack(st) if st>0.3 else None
    if st<=0.3:
        # fade from last scene (frozen end) to stack start
        return Image.blend(final(3),stack(0),st/0.3) if st>0 else final(3)
    return a
N=13*FPS
pr=subprocess.Popen(["ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-c:v","libx264","-pix_fmt","yuv420p","-crf","16","-an","out.mp4"],stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
for f in range(N): pr.stdin.write(np.asarray(frame(f)).tobytes())
pr.stdin.close(); pr.wait()
