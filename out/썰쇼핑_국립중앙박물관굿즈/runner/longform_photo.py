"""Subpixel scale animation with fixed anchor, no integer crop/zoompan.

The original is resampled once to a 2x working canvas. Every frame samples
that same canvas with a floating-point inverse affine transform. Never chains
frame-to-frame transforms. Runs with the same Pillow/FFmpeg code on both OSes.
"""
from pathlib import Path
import subprocess
import shutil
import os
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps, ImageFilter, ImageEnhance

def prepare(path, size=(3840,2160), fit="auto"):
    im=Image.open(path).convert('RGB')
    if fit=="contain" or fit=="auto" and im.width/im.height<1.3:
        canvas=ImageOps.fit(im,size,Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(90))
        canvas=ImageEnhance.Brightness(canvas).enhance(.68)
        im=ImageOps.contain(im,size,Image.Resampling.LANCZOS)
        canvas.paste(im,((size[0]-im.width)//2,(size[1]-im.height)//2))
        return canvas
    return ImageOps.fit(im,size,Image.Resampling.LANCZOS,centering=(.5,.35))

def coefficients(frame,frames,width=1920,height=1080,mode='in',max_scale=None,min_scale=1):
    # Preserve the approved short-shot motion, but bound travel for long shots.
    # Exponentiating by an unbounded narration duration caused extreme zooms.
    duration=max(0,(frames-1)/60)
    progress=frame/max(1,frames-1)
    seconds=progress*min(duration,8)
    scale=1.0241**seconds if mode=='in' else .926**((progress-1)*min(duration,5))
    if max_scale is not None:scale=min_scale+(max_scale-min_scale)*(progress if mode=='in' else 1-progress)
    if mode=='still':scale=1
    a=2/scale
    return (a,0,width-width/scale,0,a,height-height/scale)

def frame_bytes(base,frames,mode='in',workers=1,size=(1920,1080),max_scale=None,min_scale=1):
    """Bounded, ordered sampling of a read-only canvas; no temporal resampling."""
    def sample(i):
        return base.transform(size,Image.Transform.AFFINE,
            coefficients(i,frames,width=size[0],height=size[1],mode=mode,max_scale=max_scale,min_scale=min_scale),
            Image.Resampling.BICUBIC).tobytes()
    workers=max(1,min(4,int(workers)))
    if workers==1:
        for i in range(frames):yield sample(i)
        return
    # Pillow releases the GIL for affine sampling. Keep at most four full-size
    # results in flight, and emit in frame order regardless of completion order.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending=deque();next_frame=0
        try:
            while next_frame<min(workers,frames):
                pending.append(pool.submit(sample,next_frame));next_frame+=1
            while pending:
                result=pending.popleft().result()
                if next_frame<frames:
                    pending.append(pool.submit(sample,next_frame));next_frame+=1
                yield result
        finally:
            for future in pending:future.cancel()

def render(source,dest,frames,mode='in',workers=None,fit='auto',max_scale=None,min_scale=1):
    base=prepare(source,fit=fit)
    if workers is None:workers=min(4,max(1,(os.cpu_count() or 1)-2))
    encode_frames(Frames(lambda:frame_bytes(base,frames,mode,workers,max_scale=max_scale,min_scale=min_scale)),dest)

def paired_frames(first,second,frames,visible_frames,entrances,size=(1920,1080)):
    """Two independent, seek-stable vertical entrances; each photo stays visible."""
    w,h=size;half=w//2;panels=[]
    for path in (first,second):
        with Image.open(path) as original:
            image=ImageOps.contain(original.convert('RGB'),(half*2,h*2),Image.Resampling.LANCZOS)
        panel=Image.new('RGB',(half*2,h*2),'black')
        panel.paste(image,((half*2-image.width)//2,(h*2-image.height)//2));panels.append(panel)
    for index in range(frames):
        canvas=Image.new('RGB',size,'black');t=index/max(1,visible_frames-1)
        for side,(panel,entry) in enumerate(zip(panels,entrances)):
            progress=max(0,min(1,(t-entry['at'])/entry['duration']))
            # Linear travel is explicit authoring, not an inferred reference easing.
            offset=h*(1-progress)*(1 if entry['from']=='bottom' else -1)
            view=panel.transform((half,h),Image.Transform.AFFINE,
                (2,0,0,0,2,-2*offset),Image.Resampling.BICUBIC,fillcolor='black')
            canvas.paste(view,(side*half,0))
        yield canvas.tobytes()

def encoder_slot(crf,size=(1920,1080)):
    """Encoder argv (a list — splat it) for every longform encode at `-preset fast -crf N -threads 4` (60 fps).

    CPU = exactly the old libx264 arguments; GPU = this PC's pick at the same size (runner/video_encoder.py).
    One place for all longform pieces, so the pieces the assembly joins with `-c copy` share one encoder."""
    import video_encoder
    return video_encoder.x264('fast',crf,size[0],size[1],60,program='ffmpeg',extra=('-threads',4),color=False)

class EncoderFailed(RuntimeError):
    """A GPU encoder failed while making a piece the assembly joins with `-c copy` (scene.mp4 · endcard.mp4).

    Joined pieces are not retried one by one: render_joined (longform_engine) renders every joined piece again
    on CPU, so the stage receipts keep naming the encoder that really made their file."""

def joined_encode(args):
    """(argv, gpu name or None, encoder name) for a joined piece — this PC's pick, no per-piece CPU retry."""
    import video_encoder
    argv,gpu=video_encoder.expand(args)
    return argv,gpu,gpu or video_encoder.cpu_name(args)

def joined_failed(gpu,reason):
    import video_encoder
    video_encoder.failed(gpu,reason)
    return EncoderFailed(f'{gpu}: {reason}'[-600:])

def planned_encoder():
    """Encoder name joined pieces use on this PC now (CPU once a GPU failed in this process)."""
    import video_encoder
    return video_encoder.chosen_name(encoder_slot(19))

class Frames:
    """Replayable frame source: each iteration calls `make()` again. encode_frames needs this to retry
    on CPU after a GPU encoder failed part-way (a plain generator cannot be replayed)."""
    def __init__(self,make):self.make=make
    def __iter__(self):return iter(self.make())

def encode_frames(pixels_iter,dest,size=(1920,1080),crf=16,joined=False):
    """Encode ordered RGB frames from photos or independently animated layers. Returns the encoder name used.

    `pixels_iter` a Frames (replayable) → this PC's encoder, CPU once if the GPU fails part-way.
    A one-shot iterator cannot be replayed → CPU only (the old arguments).
    joined=True (a piece joined with `-c copy`): this PC's pick only — a GPU failure raises EncoderFailed."""
    import video_encoder
    head=[shutil.which('ffmpeg'),'-y','-v','error','-f','rawvideo','-pixel_format','rgb24',
          '-video_size',f'{size[0]}x{size[1]}','-framerate','60','-i','pipe:0','-an']
    args=head+[*encoder_slot(crf,size),'-pix_fmt','yuv420p',str(dest)]
    if joined:
        argv,gpu,name=joined_encode(args)
        try:_encode_once(argv,pixels_iter,dest)
        except RuntimeError as error:
            if gpu is None:raise
            raise joined_failed(gpu,str(error)+' · '+_log_tail(dest)) from error
        return name
    tries=video_encoder.attempts(args) if isinstance(pixels_iter,Frames) else [(None,video_encoder.expand(args,'cpu')[0])]
    for gpu,argv in tries:
        try:
            _encode_once(argv,pixels_iter,dest)
            return gpu or video_encoder.cpu_name(args)
        except RuntimeError as error:
            if gpu is None:raise
            video_encoder.failed(gpu,str(error)+' · '+_log_tail(dest))

def _log_tail(dest):
    try:return Path(str(dest)+'.log').read_text(encoding='utf-8',errors='replace')[-400:]
    except OSError:return ''

def _encode_once(argv,pixels_iter,dest):
    with Path(str(dest)+'.log').open('wb') as log:
        p=subprocess.Popen(argv,stdin=subprocess.PIPE,stderr=log)
        try:
            for pixels in pixels_iter:
                _feed(p,pixels,dest)
            _feed(p,None,dest)
            code=p.wait()
            if code:raise RuntimeError(f'photo encoder failed: {code}; see {dest}.log')
        except BaseException:
            p.kill();p.wait();raise

def _feed(p,pixels,dest):
    """Write one frame (None = close). The encoder exiting early (e.g. a GPU session that failed to open)
    shows up here as a closed pipe — BrokenPipeError on macOS, OSError(EINVAL) on Windows."""
    try:
        if pixels is None:p.stdin.close()
        else:p.stdin.write(pixels)
    except OSError as error:
        p.wait();raise RuntimeError(f'photo encoder closed its input: {p.returncode}; see {dest}.log') from error

if __name__=='__main__':
    import sys
    render(Path(sys.argv[1]),Path(sys.argv[2]),int(sys.argv[3]))
