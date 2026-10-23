import re,requests,collections,concurrent.futures as cf, cv2, numpy as np
t=open('trip.html',encoding='utf-8').read()
ids=list(dict.fromkeys(re.findall(r'images/([0-9a-zA-Z]{15,}?)_[A-Z]_\d+_\d+',t)))
H={'User-Agent':'Mozilla/5.0','Referer':'https://kr.trip.com/'}
def get(i):
    for suf in ['_R_1280_853_R5_D.jpg','_Z_1280_853_R50_Q90.jpg','_W_1280_853_R5_Q70.jpg']:
        r=requests.get('https://ak-d.tripcdn.com/images/'+i+suf,headers=H,timeout=20)
        if r.status_code==200 and len(r.content)>5000:
            open('trip/%s.jpg'%i,'wb').write(r.content); return i,len(r.content)
    return i,0
with cf.ThreadPoolExecutor(8) as ex: res=list(ex.map(get,ids))
ok=[i for i,n in res if n]; print('받음',len(ok),'/',len(ids))
tiles=[]
for k,i in enumerate(ok):
    im=cv2.imdecode(np.fromfile('trip/%s.jpg'%i,np.uint8),1); h,w=im.shape[:2]
    im=cv2.resize(im,(240,160)); cv2.putText(im,str(k),(4,22),0,0.7,(0,255,255),2); cv2.putText(im,'%dx%d'%(w,h),(4,154),0,0.45,(0,255,255),1); tiles.append(im)
open('trip_ids.txt','w').write('\n'.join(ok))
while len(tiles)%10: tiles.append(np.zeros_like(tiles[0]))
g=np.vstack([np.hstack(tiles[j:j+10]) for j in range(0,len(tiles),10)])
cv2.imencode('.jpg',g)[1].tofile('trip_sheet.jpg'); print(g.shape)
