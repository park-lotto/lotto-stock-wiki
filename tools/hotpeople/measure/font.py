import subprocess, json, glob, os, numpy as np
from PIL import Image, ImageFont, ImageDraw
cj=json.load(open("cuts.json"))
# 대조 표본: (영상, 자막번호, 한 줄 텍스트) — 한 줄짜리만
samples=[("dvJg0By8Luw.mp4",13,"하지만 그는 달랐음."),("dvJg0By8Luw.mp4",14,"방송 대신 유튜브에 올인"),
         ("X4GIghUr_B4.mp4",14,"독학해서 아이들을 가르침"),("CmnmcIvwTPo.mp4",15,"그렇게 5년.")]
def crop_ink(f,idx):
    o=cj[f]; ts=[0]+o["sub_times"]; ends=o["sub_times"]+[o["dur"]]; t=(ts[idx-1]+ends[idx-1])/2
    raw=subprocess.run(["ffmpeg","-v","error","-ss",f"{t:.2f}","-i",f,"-frames:v","1","-vf","crop=1080:200:0:1272","-f","rawvideo","-pix_fmt","gray","-"],capture_output=True).stdout
    a=np.frombuffer(raw,np.uint8).reshape(200,1080)<110
    ys,xs=np.where(a); return a[ys.min():ys.max()+1, xs.min():xs.max()+1]
def render(path,text,h):
    fnt=ImageFont.truetype(path,120); im=Image.new("L",(2400,300),255); ImageDraw.Draw(im).text((20,60),text,font=fnt,fill=0)
    a=np.array(im)<110; ys,xs=np.where(a); return a[ys.min():ys.max()+1, xs.min():xs.max()+1]
def score(ref,cand):
    H,W=ref.shape; c=Image.fromarray((cand*255).astype(np.uint8)).resize((W,H)); c=np.array(c)>127
    ar_ref=W/H; ar_c=cand.shape[1]/cand.shape[0]
    return (ref&c).sum()/max(1,(ref|c).sum()), ar_c/ar_ref
fonts=sorted(glob.glob("C:/Users/CH/Desktop/로또의 주식/.tracks/숏템엔진/shopping_shorts/static/fonts/*.[ot]tf")+glob.glob("C:/Users/CH/Desktop/로또의 주식/.tracks/숏템엔진/shopping_shorts/channel_presets/brainbulb/fonts/*.ttf"))
refs=[(crop_ink(f,i),t) for f,i,t in samples]
res=[]
for p in fonts:
    try:
        ss=[score(r,render(p,t,0)) for r,t in refs]
    except Exception as e: continue
    iou=np.mean([s[0] for s in ss]); ar=np.mean([abs(1-s[1]) for s in ss])
    res.append((iou,ar,os.path.basename(p)))
for r in sorted(res,reverse=True)[:8]: print(f"IoU {r[0]:.3f}  종횡비오차 {r[1]:.3f}  {r[2]}")
