# 컷마다 앞2·컷·뒤2 프레임(60fps 기준 -2,-1,0,+1,+3) 한 줄씩 → 한 장
import sys,json,subprocess,os,numpy as np,cv2
mp4,mj,out=sys.argv[1:4]
d=json.load(open(mj,encoding='utf-8')); fps=d['fps']
rows=[]
for c in d['cuts']:
    f=c['f']; ims=[]
    for off in (-2,-1,0,1,3):
        t=max(0,(f+off)/fps)
        r=subprocess.run(["ffmpeg","-v","error","-ss",f"{t:.4f}","-i",mp4,"-frames:v","1","-vf","crop=1080:1220:0:590,scale=120:136","-f","rawvideo","-pix_fmt","bgr24","-"],capture_output=True)
        a=np.frombuffer(r.stdout,np.uint8)
        ims.append(a.reshape(136,120,3) if a.size==136*120*3 else np.zeros((136,120,3),np.uint8))
    row=np.hstack(ims); lab=np.zeros((136,150,3),np.uint8)+255
    cv2.putText(lab,f"{c['t']:.2f}",(4,40),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,0,0),2); cv2.putText(lab,c['tr'][:10],(4,80),cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,0,200),1)
    rows.append(np.hstack([lab,row]))
half=(len(rows)+1)//2
L=rows[:half]; R=rows[half:]+[np.zeros_like(rows[0])+255]*(half-len(rows[half:]))
img=np.hstack([np.vstack(L),np.zeros((136*half,10,3),np.uint8),np.vstack(R)])
ok,buf=cv2.imencode('.jpg',img); buf.tofile(out); print(out,len(rows))
