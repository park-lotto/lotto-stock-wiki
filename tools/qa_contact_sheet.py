"""캡처 폴더를 묶음 시트로 만든다 — 전 칸을 한눈에 훑기 위한 도구.
실행: py tools/qa_contact_sheet.py <캡처폴더> <접미사(_box.png)> <출력폴더> [열수=2] [시트당=24]"""
import sys,os,glob
from PIL import Image,ImageDraw,ImageFont
src,suffix,out=sys.argv[1],sys.argv[2],sys.argv[3]
cols=int(sys.argv[4]) if len(sys.argv)>4 else 2
per=int(sys.argv[5]) if len(sys.argv)>5 else 24
W=560;LABEL=22
files=sorted(glob.glob(os.path.join(src,'*'+suffix)))
os.makedirs(out,exist_ok=True)
try:font=ImageFont.truetype('malgun.ttf',15)
except Exception:font=ImageFont.load_default()
for s in range(0,len(files),per):
    chunk=files[s:s+per];cells=[]
    for f in chunk:
        im=Image.open(f).convert('RGB');h=int(im.height*W/im.width);im=im.resize((W,h))
        cell=Image.new('RGB',(W,h+LABEL),'white');cell.paste(im,(0,LABEL))
        ImageDraw.Draw(cell).text((4,2),os.path.basename(f).replace(suffix,''),fill='black',font=font);cells.append(cell)
    rows=[cells[i:i+cols] for i in range(0,len(cells),cols)]
    H=sum(max(c.height for c in r) for r in rows)
    sheet=Image.new('RGB',(W*cols,H),'#888');y=0
    for r in rows:
        for i,c in enumerate(r):sheet.paste(c,(i*W,y))
        y+=max(c.height for c in r)
    p=os.path.join(out,f'sheet_{s//per+1:02d}.png');sheet.save(p);print(p,sheet.size)
