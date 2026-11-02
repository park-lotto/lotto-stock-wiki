import subprocess,numpy as np,cv2,json
out={}
for vid in "ABjQ0YCZoes LHembw8EUU0 tcaIPaGWLrE kC8fkx1Ve3Q 1kfqEB2b1xM Y2YXuAE4J00".split():
    r=subprocess.run(["ffmpeg","-v","error","-ss","0.3","-i",f"C:/숏템_칼카피/evenshopping/src/{vid}.mp4","-frames:v","1","-f","rawvideo","-pix_fmt","bgr24","-"],capture_output=True)
    f=np.frombuffer(r.stdout,np.uint8).reshape(1920,1080,3)
    hsv=cv2.cvtColor(f,cv2.COLOR_BGR2HSV); g=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY)
    # 행 프로파일: 흰 글자(>235, 채도<40), 하늘색(색상 80~100, 채도>120)
    white=(g>230)&(hsv[...,1]<40); cyan=(hsv[...,0]>=80)&(hsv[...,0]<=100)&(hsv[...,1]>120)&(hsv[...,2]>180)
    def rows(m,lo,hi,minpx=30):
        ys=[y for y in range(lo,hi) if m[y].sum()>minpx]; return [min(ys),max(ys)] if ys else None
    wy=rows(white,150,560,40); cy=rows(cyan,150,560,40)
    hx=lambda m,y: '#%02X%02X%02X'%tuple(int(v) for v in np.median(f[y[0]:y[1]+1][m[y[0]:y[1]+1]],0)[::-1]) if y else None
    # 제목 2줄 글자 높이(흰 줄은 띠 밖)
    cap=rows(g<60,560,760,30) # 훅 자막 검은 글자
    # 머리 제목 (t=5) 
    r2=subprocess.run(["ffmpeg","-v","error","-ss","5","-i",f"C:/숏템_칼카피/evenshopping/src/{vid}.mp4","-frames:v","1","-f","rawvideo","-pix_fmt","bgr24","-"],capture_output=True)
    f2=np.frombuffer(r2.stdout,np.uint8).reshape(1920,1080,3); g2=cv2.cvtColor(f2,cv2.COLOR_BGR2GRAY)
    w2=g2[180:400]>200; ys=[y+180 for y in range(220) if w2[y].sum()>30]
    out[vid]={"hook_white_y":wy,"hook_white_hex":hx(white,wy),"hook_cyan_y":cy,"hook_cyan_hex":hx(cyan,cy),"hook_cap_y":cap,
              "head_title_y":[min(ys),max(ys)] if ys else None,"head_bg_hex":'#%02X%02X%02X'%tuple(int(v) for v in np.median(f2[200:220,1000:1070].reshape(-1,3),0)[::-1]),
              "header_bg_hex":'#%02X%02X%02X'%tuple(int(v) for v in np.median(f2[140:165,200:280].reshape(-1,3),0)[::-1]),
              "bottom_bg_hex":'#%02X%02X%02X'%tuple(int(v) for v in np.median(f2[1850:1900,100:1000].reshape(-1,3),0)[::-1]),
              "band_hex":'#%02X%02X%02X'%tuple(int(v) for v in np.median(f2[410:430,20:200].reshape(-1,3),0)[::-1])}
    print(vid,out[vid])
json.dump(out,open("C:/숏템_칼카피/evenshopping/work/hook_measure.json","w"),indent=1)
