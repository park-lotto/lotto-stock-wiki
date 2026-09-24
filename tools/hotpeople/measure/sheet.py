import subprocess, json, glob
from PIL import Image, ImageDraw
cj=json.load(open("cuts.json"))
for f,o in cj.items():
    ts=[0]+o["sub_times"]; ends=o["sub_times"]+[o["dur"]]
    mids=[(a+b)/2 for a,b in zip(ts,ends)]
    crops=[]
    # 헤드라인(0.5초)
    raw=subprocess.run(["ffmpeg","-v","error","-ss","0.5","-i",f,"-frames:v","1","-vf","crop=1080:400:0:80","-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True).stdout
    head=Image.frombytes("RGB",(1080,400),raw).resize((540,200))
    for t in mids:
        raw=subprocess.run(["ffmpeg","-v","error","-ss",f"{t:.2f}","-i",f,"-frames:v","1","-vf","crop=1080:200:0:1272","-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True).stdout
        crops.append(Image.frombytes("RGB",(1080,200),raw).resize((540,100)))
    rows=(len(crops)+1)//2
    sheet=Image.new("RGB",(1100,210+rows*104),"white"); sheet.paste(head,(0,0))
    d=ImageDraw.Draw(sheet)
    for i,c in enumerate(crops):
        x=(i%2)*550; y=210+(i//2)*104; sheet.paste(c,(x+10,y)); d.text((x,y),str(i+1),fill=(0,0,255))
    sheet.save(f"sub_{f[:11]}.png"); print(f, len(crops))
