import numpy as np, subprocess, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,FPS=1920,1080,30
imgs=[Image.open(f"search_{i}.png").convert("RGB") for i in range(1,5)]
SB=240; HD=56; SCROLL=500; D=3.1
def eo(x): x=min(max(x,0),1); return 1-(1-x)**3
FONT=lambda s: ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf",s)
# (phrase,x,y) picks from cands_i.json (real on-screen text) + appear time
PICKS=[
 [("자동 제작 프로그램",1251,525,.9),("조회수 104만회",708,573,1.25),("자동화",1272,645,1.6),("100%",1245,941,2.0)],
 [("수익 창출",760,549,.9),("수익 창출",1049,549,1.1),("수익화",1303,549,1.3),("수익화",1215,1080,2.0)],
 [("쇼츠 부업",725,549,.9),("부업",455,549,1.1),("80만원",1327,549,1.3),("부업",1231,965,2.0)],
 [("클로드",1011,427,.6),("자동화",1164,427,.8),("100% 자동화",1576,1156,1.7)],
]
CAPS=["쇼츠 자동화 프로그램","쇼츠 수익화 강의","AI 쇼츠 부업","클로드로 자동화"]
boxes=[]
for i,pk in enumerate(PICKS):
    c=json.load(open(f"cands_{i+1}.json",encoding="utf8")); L=[]
    for ph,x,y,t in pk:
        m=[r for r in c if r[0]==ph and r[2]==x and r[3]==y]; assert m,(i,ph,x,y)
        off=SCROLL*eo((t+0.35-0.5)/2.1); sy=m[0][3]-off; assert 70<sy<830,(i,ph,sy)
        L.append((ph,m[0][2],m[0][3],m[0][4],m[0][5],t))
    boxes.append(L)
def caption(img,text,t0,t,size,y0,y1):
    p=eo((t-t0)/0.4)
    if p<=0: return img
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    dy=int((1-p)*60)
    d.rectangle((0,y0+dy,W,y1+dy),fill=(0,0,0,int(185*p)))
    f=FONT(size); b=d.textbbox((0,0),text,font=f)
    d.text(((W-(b[2]-b[0]))/2-b[0],(y0+y1)/2+dy-(b[3]-b[1])/2-b[1]),text,font=f,fill=(255,255,255,int(255*p)))
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
def scene(i,t,cap=True):
    im=imgs[i]; off=int(round(SCROLL*eo((t-0.5)/2.1)))
    reg=im.crop((SB,HD+off,W,HD+off+H-HD)).convert("RGBA")
    ov=Image.new("RGBA",reg.size,(0,0,0,0)); d=ImageDraw.Draw(ov)
    for ph,x,y,w,h,ton in boxes[i]:
        p=eo((t-ton)/0.35)
        if p<=0: continue
        pad=9; X=x-SB-pad; Y=y-HD-off-pad
        ww=int((w+2*pad)*p)
        d.rectangle((X,Y,X+ww,Y+h+2*pad),fill=(255,226,0,int(125*p)),outline=(255,140,0,int(255*p)),width=4)
    reg=Image.alpha_composite(reg,ov).convert("RGB")
    base=im.crop((0,0,W,H)).copy(); base.paste(reg,(SB,HD)); base.paste(im.crop((0,0,W,HD)),(0,0))
    z=1.3-0.3*eo(t/0.9)
    if z>1.001:
        cw,ch=W/z,H/z; x0=min(max(900-cw/2,0),W-cw)
        base=base.resize((W,H),Image.LANCZOS,box=(x0,0,x0+cw,ch))
    if cap: base=caption(base,CAPS[i],0.25,t,104,850,1030)
    return base
def stack(t):
    p=eo((t-0.0)/1.0)
    bg=Image.new("RGB",(W,H),(236,236,238))
    for i in range(4):
        card=scene(i,D-0.01,cap=False); k=i-1.5
        s=1-0.45*p; ang=k*3.5*p; cw,ch=int(W*s),int(H*s)
        c=card.resize((cw,ch),Image.LANCZOS).convert("RGBA")
        sh=Image.new("RGBA",(cw+24,ch+24),(0,0,0,0)); sh.paste((0,0,0,int(70*p)),(12,16,cw+12,ch+16))
        sh=sh.filter(ImageFilter.GaussianBlur(10)); sh.alpha_composite(c,(12,12))
        sh=sh.rotate(-ang,expand=True,resample=Image.BICUBIC)
        cx=960+k*150*p; cy=490+k*45*p
        bg.paste(sh,(int(cx-sh.width/2),int(cy-sh.height/2)),sh)
    return caption(bg,"다 해 보셨죠?",0.9,t,140,860,1050)
T4=4*D
def frame(f):
    t=f/FPS
    if t<T4:
        i=int(t//D); lt=t-i*D; a=scene(i,lt)
        if lt>D-0.3 and i<3: a=Image.blend(a,scene(i+1,lt-D),(lt-(D-0.3))/0.3)
        return a
    st=t-T4
    if st<0.3: return Image.blend(scene(3,D-0.01),stack(0),st/0.3)
    return stack(st)
TOTAL=14.8
if __name__=="__main__":
    pr=subprocess.Popen(["ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r","30","-i","-","-c:v","libx264","-pix_fmt","yuv420p","-crf","16","-an","out_v2.mp4"],stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
    for f in range(int(TOTAL*FPS)): pr.stdin.write(np.asarray(frame(f)).tobytes())
    pr.stdin.close(); pr.wait()
