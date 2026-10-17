import subprocess, sys, io
from PIL import Image
vid,out,y0,y1=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]); ts=[float(x) for x in sys.argv[5:]]
rows=[]
for t in ts:
    b=subprocess.run(["ffmpeg","-v","error","-ss",str(t),"-i",f"C:/숏템_칼카피/sseolpulda/mp4/{vid}.mp4","-frames:v","1","-f","image2pipe","-vcodec","png","-"],capture_output=True).stdout
    rows.append(Image.open(io.BytesIO(b)).convert("RGB").crop((0,y0,1080,y1)).resize((540,(y1-y0)//2)))
S=Image.new("RGB",(1080,rows[0].height*((len(rows)+1)//2)),"white")
for i,r in enumerate(rows): S.paste(r,((i%2)*540,(i//2)*r.height))
S.save(out,quality=90)
