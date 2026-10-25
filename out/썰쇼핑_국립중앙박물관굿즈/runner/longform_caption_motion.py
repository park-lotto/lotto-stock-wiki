"""Finite caption entrance frames; the last sharp frame is held by overlay.

Horizontal smear is an authored approximation of the measured reference, not
recovery of its original plugin. Operates only on caption RGBA, never footage.
"""
import math
from pathlib import Path
import numpy as np
from PIL import Image


def entrance_frames(image, folder, spec, visible_frames, fps=60):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    box=image.getchannel('A').getbbox()
    if box is None:raise ValueError('Caption has no visible pixels')
    radius=math.ceil(spec['blur_px'])
    x0=max(0,box[0]-radius);x1=min(image.width,box[2]+radius)
    y0,y1=box[1],box[3]
    sharp=image.crop((x0,y0,x1,y1)).convert('RGBA')
    count=min(visible_frames,max(2,math.ceil(spec['duration']*fps)+1))
    # A rerun with fewer frames must not let image2 read an old sequence tail.
    for old in folder.glob('[0-9][0-9][0-9][0-9].png'):old.unlink()
    pixels=np.asarray(sharp,dtype=np.float32)/255
    pixels[:,:,:3]*=pixels[:,:,3:4]
    for n in range(count):
        progress=n/(count-1) if count>1 else 1.
        r=round(radius*(1-progress))
        if r:
            padded=np.pad(pixels,((0,0),(r,r),(0,0)))
            summed=np.concatenate([np.zeros_like(padded[:,:1]),np.cumsum(padded,axis=1)],axis=1)
            out=(summed[:,2*r+1:]-summed[:,:-(2*r+1)])/(2*r+1)
        else:out=pixels.copy()
        alpha=out[:,:,3:4]
        rgb=np.divide(out[:,:,:3],alpha,out=np.zeros_like(out[:,:,:3]),where=alpha>1e-8)
        rgba=np.concatenate([rgb,alpha*progress],axis=2)
        frame=sharp if n==count-1 else Image.fromarray(np.clip(np.rint(rgba*255),0,255).astype('uint8'))
        frame.save(folder/f'{n:04d}.png')
    return {'pattern':folder/'%04d.png','x':x0,'y':y0,'count':count}


def work_entrance_frames(image,folder,spec,visible_frames,fps=60):
    """Squash/rebound appearance observed at Nolan280.25–280.9833.

    Measured yellow-body shape guides the authored whole-chip transform;
    white-year motion and the original plugin are not exactly reconstructed.
    Only the entrance is encoded; overlay holds the exact sharp last PNG.
    """
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    box=image.getchannel('A').getbbox()
    if box is None:raise ValueError('Work chip has no visible pixels')
    x0,x1=box[0],box[2];y0=0;y1=min(image.height,math.ceil(box[3]+(box[3]-box[1])*.5))
    sharp=image.crop((x0,y0,x1,y1)).convert('RGBA');cy=(box[1]+box[3])/2
    delay=round(spec.get('delay',0)*fps);duration=max(1,round(spec['duration']*fps))
    count=min(visible_frames,delay+duration+1)
    for old in folder.glob('[0-9][0-9][0-9][0-9].png'):old.unlink()
    # Source frame offsets from first yellow pixels; measured bounding heights.
    points=[0,1,2,3,4,5,6,7,8,9,10,14,18,21,25,30,44]
    heights=[12,18,32,50,69,88,107,120,131,134,133,111,89,89,98,104,104]
    for n in range(count):
        if n<delay:frame=Image.new('RGBA',sharp.size)
        elif n>=delay+duration:frame=sharp
        else:
            q=(n-delay)/duration*44;scale=float(np.interp(q,points,heights))/104
            frame=sharp.transform(sharp.size,Image.Transform.AFFINE,(1,0,0,0,1/scale,cy-cy/scale),Image.Resampling.BICUBIC)
        frame.save(folder/f'{n:04d}.png')
    return {'pattern':folder/'%04d.png','x':x0,'y':y0,'count':count}
