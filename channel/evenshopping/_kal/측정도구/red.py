import sys,subprocess,numpy as np,cv2
vid,t0,t1=sys.argv[1],float(sys.argv[2]),float(sys.argv[3])
W,H=270,305
p=subprocess.Popen(["ffmpeg","-v","error","-ss",str(t0),"-to",str(t1),"-i",f"C:/숏템_칼카피/evenshopping/src/{vid}.mp4","-vf",f"fps=30,crop=1080:1220:0:590,scale={W}:{H}","-f","rawvideo","-pix_fmt","bgr24","-"],stdout=subprocess.PIPE)
i=0;prev=None
while True:
    b=p.stdout.read(W*H*3)
    if len(b)<W*H*3: break
    f=np.frombuffer(b,np.uint8).reshape(H,W,3); hsv=cv2.cvtColor(f,cv2.COLOR_BGR2HSV)
    red=((hsv[...,0]<8)|(hsv[...,0]>172))&(hsv[...,1]>150)&(hsv[...,2]>120)
    ys,xs=np.where(red)
    lightblue=((hsv[...,0]>85)&(hsv[...,0]<110)&(hsv[...,1]<90)&(hsv[...,2]>200)).mean()
    white=((f.min(2))>225).mean()
    print(round(t0+i/30,3),int(red.sum()),(int(xs.min()*4),int(ys.min()*4+590),int(xs.max()*4),int(ys.max()*4+590)) if len(xs)>20 else None,round(float(lightblue),2),round(float(white),2))
    i+=1
