import sys, subprocess, pathlib, math
from PIL import Image
sc=sys.argv[1]; d=pathlib.Path(__file__).parent/sc; tmp=d/'_fr'; tmp.mkdir(exist_ok=True)
for f in tmp.glob('*.jpg'): f.unlink()
subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(d/'out.mp4'),'-vf','fps=1,scale=480:-1','-q:v','4',str(tmp/'f%02d.jpg')])
fr=sorted(tmp.glob('f*.jpg')); ims=[Image.open(f) for f in fr]; w,h=ims[0].size; cols=3; rows=math.ceil(len(ims)/cols)
sh=Image.new('RGB',(cols*w,rows*h),'white')
for i,im in enumerate(ims): sh.paste(im,((i%cols)*w,(i//cols)*h))
sh.save(d/'sheet.jpg',quality=82); print(sh.size, len(ims))
