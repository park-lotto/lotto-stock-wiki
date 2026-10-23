import requests,re,cv2,numpy as np,urllib.parse as up,hashlib,json,concurrent.futures as cf
B='https://www.skybay.co.kr'; H={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130','Referer':B+'/'}
t=open('official.html',encoding='utf-8').read()
pages=sorted(set(re.findall(r'href="(/[^"#]*)"',t)))
pages=[p for p in pages if not re.search(r'\.(css|js|ico|png|jpg)',p)]
imgs={}
def grab(p):
    try: return p,requests.get(B+p,headers=H,timeout=20).text
    except Exception: return p,''
with cf.ThreadPoolExecutor(6) as ex:
    for p,h in ex.map(grab,pages):
        title=(re.search(r'<title>(.*?)</title>',h) or [None,''])[1]
        for u in re.findall(r'(?:https?:)?//cdn\.imweb\.me/[^"\'\s\)<>]+?\.(?:jpg|jpeg|png|webp)',h):
            u=('https:'+u) if u.startswith('//') else u
            imgs.setdefault(u,p)
print('페이지',len(pages),'그림주소',len(imgs))
def dl(item):
    u,p=item
    try:
        c=requests.get(u,headers=H,timeout=25).content; im=cv2.imdecode(np.frombuffer(c,np.uint8),1)
        if im is None or min(im.shape[:2])<600: return None
        hsh=hashlib.md5(cv2.resize(im,(16,16)).tobytes()).hexdigest()[:10]
        return (hsh,u,p,im.shape[1],im.shape[0],c)
    except Exception: return None
seen={}; 
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(dl,imgs.items()):
        if r and r[0] not in seen: seen[r[0]]=r
out=sorted(seen.values(),key=lambda r:r[2])
meta={}
for k,(h,u,p,w,hh,c) in enumerate(out):
    open('official/a%03d.jpg'%k,'wb').write(c); meta['a%03d'%k]={'src':u,'page':B+p,'size':[w,hh]}
json.dump(meta,open('official/sources.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('큰 사진(중복 제거)',len(out))
tiles=[]
for k,(h,u,p,w,hh,c) in enumerate(out):
    im=cv2.imdecode(np.frombuffer(c,np.uint8),1); im=cv2.resize(im,(200,int(200*hh/w)) if w>=hh else (int(200*w/hh),200))
    tile=np.zeros((200,200,3),np.uint8); tile[:im.shape[0],:im.shape[1]]=im[:200,:200]
    cv2.putText(tile,'%d %dx%d'%(k,w,hh),(3,16),0,0.42,(0,255,255),1); tiles.append(tile)
while len(tiles)%12: tiles.append(np.zeros((200,200,3),np.uint8))
g=np.vstack([np.hstack(tiles[j:j+12]) for j in range(0,len(tiles),12)])
cv2.imencode('.jpg',g)[1].tofile('official_sheet.jpg'); print(g.shape)
