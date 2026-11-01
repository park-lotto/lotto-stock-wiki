import time,torch,cv2,numpy as np,json
from simple_lama_inpainting.models.model import download_model,LAMA_MODEL_URL
d=torch.device('cuda');net=torch.jit.load(download_model(LAMA_MODEL_URL),map_location=d).eval()
ker=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(15,15))
def read(p):
    c=cv2.VideoCapture(p);F=[]
    while True:
        o,f=c.read()
        if not o:break
        F.append(f)
    return F
def mask(f,bands):
    h,w=f.shape[:2];m=np.zeros((h,w),'uint8')
    for y0,y1 in bands:
        a,b=int(y0*h),int(y1*h);R=f[a:b]
        g=cv2.cvtColor(R,cv2.COLOR_BGR2GRAY)
        t=((cv2.morphologyEx(g,cv2.MORPH_TOPHAT,ker)>40)*255).astype('uint8')
        n,l,s,_=cv2.connectedComponentsWithStats(t)
        for k in range(1,n):
            if s[k,4]<10:t[l==k]=0
        if y0 in BIG: t=cv2.dilate(t,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(BIG[y0],BIG[y0])))
        m[a:b]=t
    for x0,x1,y0,y1 in EMO:                                          # 클로드 지정 이모지 자리만
        a,b,c,e=int(y0*h),int(y1*h),int(x0*w),int(x1*w)
        hs=cv2.cvtColor(f[a:b,c:e],cv2.COLOR_BGR2HSV)
        m[a:b,c:e]=np.maximum(m[a:b,c:e],((hs[...,1]>110)&(hs[...,2]>100))*255)
    return m
def run(im,mk):
    pd=lambda a:cv2.copyMakeBorder(a,0,(8-a.shape[0]%8)%8,0,(8-a.shape[1]%8)%8,cv2.BORDER_REFLECT)
    i=torch.from_numpy(pd(im[:,:,::-1].copy())/255.).permute(2,0,1)[None].float().to(d)
    k=torch.from_numpy((pd(mk)>0)*1.)[None,None].float().to(d)
    with torch.no_grad():o=net(i,k)[0].permute(1,2,0).cpu().numpy()
    o=(o.clip(0,1)*255).astype('uint8')[:im.shape[0],:im.shape[1],::-1];a=im.copy();a[mk>0]=o[mk>0];return a
def clean(F,bands):
    M=[mask(f,bands) for f in F];O=[];h,w=F[0].shape[:2]
    for i,f in enumerate(F):
        u=cv2.dilate(np.maximum.reduce(M[max(0,i-2):i+3]),np.ones((9,9),'uint8'));r=f.copy()
        for y0,y1 in bands:
            a,b=max(0,int(y0*h)-48),min(h,int(y1*h)+48)
            if u[a:b].any(): r[a:b]=run(r[a:b],u[a:b])
        O.append(r)
    return O
def flick(F,bands):
    h=F[0].shape[0];s=[]
    for y0,y1 in bands:
        a,b=int(y0*h),int(y1*h);G=[cv2.cvtColor(f[a:b],cv2.COLOR_BGR2GRAY).astype('float32') for f in F]
        s.append(np.mean([np.abs(cv2.absdiff(G[i],G[i-1])-cv2.absdiff(G[i-1],G[i-2])).mean() for i in range(2,len(G))]))
    return round(float(np.mean(s)),2)
BIG={};EMO=[]
def go(name,src,bs,big,emo):
    global BIG,EMO
    BIG,EMO=big,emo;F=read(src);L=clean(F,bs);return F,L
rows=[]
for i,bs,big,emo in [(6,[(.17,.31),(.68,.77)],{.17:17},[]),(1,[(.13,.21),(.68,.82)],{},[(.90,1,.14,.20)])]:
    F,L=go(i,f'cmp10/c10/{i}_o.mp4',bs,big,emo);V=read(f'cmp10/c10/{i}_v.mp4');m=min(len(F),len(V))//2
    t=lambda x:cv2.resize(x,(270,480));rows+= [t(F[m]),t(V[m]),t(L[m])]
F,L=go('c','clip.mp4',[(.44,.55)],{},[(.70,.80,.47,.53)])
for k in (45,135):rows.append(cv2.resize(L[k],(270,480)))
cv2.imwrite('fix.jpg',np.hstack(rows))
