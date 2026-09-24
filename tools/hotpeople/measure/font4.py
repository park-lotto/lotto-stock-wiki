import numpy as np, os
from PIL import Image, ImageFont, ImageDraw
exec(open("font.py",encoding="utf-8").read().split("fonts=sorted")[0])
F="C:/Users/CH/Desktop/로또의 주식/.tracks/숏템엔진/shopping_shorts/static/fonts/"
B="C:/Users/CH/Desktop/로또의 주식/.tracks/숏템엔진/shopping_shorts/channel_presets/brainbulb/fonts/"
cands=["/c/Users/CH/AppData/Local/Temp/claude/C--Users-CH-Desktop-------/da57e58d-9b11-4b31-9942-aec0f5ae4858/scratchpad/hot/s10/fonts_dl/BMHANNAPro.ttf".replace("/c/","C:/"),F+"BMJUA.ttf",F+"BMDOHYEON.ttf",F+"TmonMonsori.ttf",F+"Jalnan2.ttf",F+"GmarketSansBold.otf",F+"Cafe24Ohsquare.ttf",F+"BlackHanSans.ttf",B+"SBAggroB.ttf",F+"KCCGanpan.otf",F+"Binggrae-Bold.otf",B+"S-CoreDream-7ExtraBold.ttf",F+"GothicA1-Black.ttf"]
r,t=crop_ink("dvJg0By8Luw.mp4",14),"방송 대신 유튜브에 올인"
h=70; rows=[Image.fromarray(((~r)*255).astype(np.uint8)).resize((int(r.shape[1]*h/r.shape[0]),h))]
names=["원본"]
for p in cands:
    fnt=ImageFont.truetype(p,120); im=Image.new("L",(2800,320),255); ImageDraw.Draw(im).text((20,70),t,font=fnt,fill=0)
    a=np.array(im)<110; ys,xs=np.where(a); a=a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    rows.append(Image.fromarray(((~a)*255).astype(np.uint8)).resize((int(a.shape[1]*h/a.shape[0]),h))); names.append(os.path.basename(p))
W=max(x.width for x in rows)+260; out=Image.new("L",(W,len(rows)*(h+14)),255); d=ImageDraw.Draw(out)
lab=ImageFont.truetype(F+"NanumGothic-Bold.ttf",22)
for i,(im,n) in enumerate(zip(rows,names)): out.paste(im,(250,i*(h+14))); d.text((5,i*(h+14)+22),n[:22],font=lab,fill=0)
out.save("font_grid.png")
