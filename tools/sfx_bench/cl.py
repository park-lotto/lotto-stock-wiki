import soundfile as sf,numpy as np,json,sys
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
sys.stdout.reconfigure(encoding="utf-8")
SR=44100; L=int(0.25*SR)
ev=json.load(open("events.json"))
cache={}; items=[]
for vid,es in ev.items():
    x=sf.read(f"sep/htdemucs/{vid}/nv.wav")[0]; cache[vid]=x
    for k,e in enumerate(es):
        a=int(e["s"]*SR)-int(0.01*SR); seg=x[max(0,a):max(0,a)+L]
        seg=np.pad(seg,(0,L-len(seg)))
        items.append((vid,k,seg/(np.linalg.norm(seg)+1e-9)))
N=len(items); print("사건",N)
# spectral fingerprint: STFT log-mag, 64 bins x frames
def fp(s):
    W=1024;H=256
    fr=np.stack([s[i:i+W]*np.hanning(W) for i in range(0,len(s)-W,H)])
    m=np.log1p(np.abs(np.fft.rfft(fr,axis=1))[:, :400]*50)
    v=m.flatten(); v=v-v.mean(); return v/(np.linalg.norm(v)+1e-9)
F=np.stack([fp(it[2]) for it in items])
S=F@F.T
D=np.clip(1-S,0,2); np.fill_diagonal(D,0)
Z=linkage(squareform(D,checks=False),"average")
lab=fcluster(Z,0.35,"distance")
np.save("labels.npy",lab); np.save("S.npy",S)
import collections
cnt=collections.Counter(lab)
print("군집",len(cnt))
for c,n in cnt.most_common(25):
    m=[i for i in range(N) if lab[i]==c]
    vids=len(set(items[i][0] for i in m))
    durs=[ev[items[i][0]][items[i][1]]["dur"] for i in m]; cens=[ev[items[i][0]][items[i][1]]["cen"] for i in m]
    sub=S[np.ix_(m,m)]; within=(sub.sum()-len(m))/max(1,len(m)*(len(m)-1))
    print(f"군집{c:3d} {n:3d}건 영상{vids:2d}편 길이중앙{np.median(durs)*1000:5.0f}ms 중심주파수{np.median(cens):6.0f}Hz 내부유사{within:.2f}")
json.dump([[it[0],it[1]] for it in items],open("items.json","w"))
