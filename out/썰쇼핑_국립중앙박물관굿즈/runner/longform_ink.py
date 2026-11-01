"""Deterministic multi-origin ink coverage, composed below captions and brand."""
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageFilter
from longform_photo import encode_frames


def arrival_field(size=(480,270),seed=17):
    """Fixed spatial field, not a stateful fluid simulation or a uniform fade."""
    w,h=size
    rng=np.random.default_rng(seed)
    yy,xx=np.mgrid[0:h,0:w].astype(np.float32)
    xx/=w;yy/=h
    noise=np.zeros((h,w),np.float32)
    for resolution,amplitude in ((10,.11),(28,.065),(70,.024)):
        values=rng.integers(0,256,(resolution,resolution),dtype=np.uint8)
        layer=Image.fromarray(values).resize(size,Image.Resampling.BICUBIC)
        noise+=(np.asarray(layer,dtype=np.float32)/255-.5)*amplitude
    origins=((.10,.36,0),(.36,.16,.08),(.32,.82,.02),(.77,.66,.12),(.94,.20,.19))
    fields=[]
    for x,y,delay in origins:
        distance=np.sqrt(((xx-x)*1.45)**2+(yy-y)**2)
        fields.append(distance+noise+delay)
    field=np.minimum.reduce(fields)
    return (field-field.min())/(field.max()-field.min())


def mask_at(field,progress):
    if progress<=0:return np.full(field.shape,255,np.uint8)
    if progress>=1:return np.zeros(field.shape,np.uint8)
    # A narrow grey fringe surrounds a dark advancing core.
    value=np.clip((field-progress)/.055+.5,0,1)
    value=value*value*(3-2*value)
    return np.round(value*255).astype(np.uint8)


def render_mask(folder,frames,spec):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    field=arrival_field(seed=spec.get('seed',17))
    first=spec['at']*max(1,frames-1)
    span=spec['duration']*max(1,frames-1)
    # Use the authored end position for the inclusive terminal frame. Dividing
    # (i-first)/span can produce 0.9999999999999998 at an exact endpoint,
    # leaving the field's brightest pixel half exposed indefinitely.
    end_frame=math.ceil(min(1.,spec['at']+spec['duration'])*max(1,frames-1))
    def pixels():
        for i in range(frames):
            gray=mask_at(field,1. if i>=end_frame else (i-first)/span)
            yield np.repeat(gray[:,:,None],3,axis=2).tobytes()
    path=folder/'ink-mask.mp4'
    encode_frames(pixels(),path,size=(field.shape[1],field.shape[0]))
    return path
