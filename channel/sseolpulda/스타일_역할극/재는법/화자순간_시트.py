import subprocess, sys, io
from PIL import Image, ImageDraw, ImageFont
vid, out = sys.argv[1], sys.argv[2]; ts=[float(x) for x in sys.argv[3:]]
F=ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf",34)
ims=[]
for t in ts:
    b=subprocess.run(["ffmpeg","-v","error","-ss",str(t),"-i",f"C:/숏템_칼카피/sseolpulda/mp4/{vid}.mp4","-frames:v","1","-f","image2pipe","-vcodec","png","-"],capture_output=True).stdout
    im=Image.open(io.BytesIO(b)).convert("RGB").resize((432,768)); d=ImageDraw.Draw(im); d.rectangle((0,0,110,44),fill="red"); d.text((6,2),f"{t}s",font=F,fill="white"); ims.append(im)
S=Image.new("RGB",(432*len(ims),768),"white")
for i,im in enumerate(ims): S.paste(im,(432*i,0))
S.save(out,quality=88)
