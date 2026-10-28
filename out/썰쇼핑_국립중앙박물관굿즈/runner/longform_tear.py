"""Seeded jagged paper coverage with shaded reverse-side flaps."""
from pathlib import Path
import numpy as np
from longform_photo import encode_frames

def layers_at(progress,size=(480,270),seed=23):
 w,h=size
 keep=np.full((h,w),255,np.uint8);fold=np.zeros((h,w),np.uint8)
 if progress<=0:return keep,fold
 if progress>=1:return np.zeros_like(keep),fold
 yy,xx=np.mgrid[0:h,0:w].astype(np.float32);xx/=w;yy/=h
 rng=np.random.default_rng(seed)
 # Independently torn sheets arrive from opposing corners. No frame history.
 for n,(start,end) in enumerate(((0,.95),(.20,.98),(.43,1))):
  q=np.clip((progress-start)/(end-start),0,1)
  noise=np.interp(np.arange(h),np.linspace(0,h-1,90),rng.uniform(-.018,.018,90))[:,None]
  grain=rng.integers(-5,6,(h,w))
  if q<=0:continue
  if n==0:d=xx+.58*yy+noise;along=yy
  elif n==1:d=(1-xx)+.65*yy+noise;along=yy
  else:
   # Bottom-up movement needs roughness across columns, not across its travel direction.
   noise=np.interp(np.arange(w),np.linspace(0,w-1,90),rng.uniform(-.018,.018,90))[None,:]
   d=(1-yy)+.35*xx+noise;along=xx
  front=q*1.8-.06
  removed=d<front
  keep[removed]=0;fold[removed]=0
  # Tapered wedge: the reverse face narrows to a folded corner, with shadow.
  width=.26*np.sin(np.pi*q)*np.clip(1-abs(along-.48)*1.9,0,1)
  distance=front-d
  flap=removed & (distance<width)
  shade=np.clip(228-85*np.clip(distance/(width+.0001),0,1)+grain,0,255)
  fold[flap]=shade[flap].astype(np.uint8)
 return keep,fold

def render_layers(folder,frames,spec):
 root=Path(folder);root.mkdir(parents=True,exist_ok=True)
 first=spec['at']*max(1,frames-1);span=spec['duration']*max(1,frames-1)
 outputs=[]
 for channel,name in enumerate(('tear-mask','tear-fold')):
  def pixels():
   for i in range(frames):
    gray=layers_at((i-first)/span,seed=spec.get('seed',23))[channel]
    yield np.repeat(gray[:,:,None],3,axis=2).tobytes()
  path=root/(name+'.mp4');encode_frames(pixels(),path,size=(480,270));outputs.append(path)
 return outputs
