import json, sys, numpy as np, librosa
M="C:/숏템_칼카피/sseolpulda/mp4/"
SP={
 "oJZDImhYdXw":{"나레":[(0.05,14.35),(18.95,27.4)],"사장":[(14.96,16.65)],"개발팀":[(17.18,18.9)]},
 "7DYbxVNz5q8":{"나레":[(0.05,6.2),(9.23,13.2),(15.56,16.35),(22.19,29.0)],"엔지니어":[(6.26,9.15),(16.43,22.1)],"경영진":[(13.28,15.5)]},
 "6KlP1xkSKnE":{"나레":[(0.0,9.8),(17.94,29.6)],"삼성":[(9.84,12.2),(16.05,17.9)],"애플":[(12.6,15.95)]},
}
out={}
for vid,roles in SP.items():
  y,sr=librosa.load("wav/"+vid+".wav",sr=16000,mono=True)
  f0,vf,_=librosa.pyin(y,fmin=65,fmax=400,sr=sr,frame_length=1024,hop_length=160)
  mf=librosa.feature.mfcc(y=y,sr=sr,n_mfcc=20,hop_length=160)
  cen=librosa.feature.spectral_centroid(y=y,sr=sr,hop_length=160)[0]
  rms=librosa.feature.rms(y=y,hop_length=160)[0]
  t=np.arange(len(f0))*160/sr
  R={}
  for r,spans in roles.items():
    m=np.zeros(len(t),bool)
    for a,b in spans: m|=(t>=a)&(t<b)
    v=m&~np.isnan(f0)
    print(vid,r,int(m.sum()),int(v.sum()),len(f0),len(t))
    if v.sum()==0: continue
    ff=f0[v]
    st=12*np.log2(ff/np.median(ff))
    R[r]={"sec":round(sum(b-a for a,b in spans),2),"f0_med_hz":round(float(np.median(ff)),1),"f0_p10":round(float(np.percentile(ff,10)),1),"f0_p90":round(float(np.percentile(ff,90)),1),
          "semitone_std":round(float(st.std()),2),"centroid_hz":round(float(np.median(cen[v])),0),"rms_db":round(float(20*np.log10(np.mean(rms[m])+1e-9)),1),
          "_mf":mf[1:, v].mean(1)}
  names=list(R)
  base=R["나레"]
  for r in names:
    a=R[r]["_mf"]
    R[r]["mfcc_dist_vs_narr"]=round(float(np.linalg.norm(a-base["_mf"])),2)
    R[r]["f0_semitone_vs_narr"]=round(float(12*np.log2(R[r]["f0_med_hz"]/base["f0_med_hz"])),2)
  # within-narration baseline: split narration halves
  nm=[s for s in roles["나레"]]
  for r in names: R[r].pop("_mf")
  out[vid]=R
  print(vid); [print(" ",r,R[r]) for r in names]
json.dump(out,open(sys.argv[1],"w",encoding="utf-8"),ensure_ascii=False,indent=1)
