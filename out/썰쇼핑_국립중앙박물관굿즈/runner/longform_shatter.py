"""Deterministic picture-textured fragments over a continuing incoming picture.

Authored geometry, not recovered reference-plugin geometry. No audio effects.
The montage owns source clocks and supplies real outgoing handles.
"""
import math
import random
import subprocess
from contextlib import contextmanager
from PIL import Image, ImageDraw
import numpy as np


def fragments(size, seed=17):
    w,h=size; rng=random.Random(seed);cx,cy=w*.5,h*.5
    # Radial cracks plus staggered cross-cracks, not a regular triangle grid.
    angles=[math.atan2(y-cy,x-cx)%(2*math.pi) for x,y in ((0,0),(w,0),(w,h),(0,h))]
    angles+= [(i+rng.uniform(-.25,.25))*2*math.pi/20%(2*math.pi) for i in range(20)]
    angles=sorted(angles);outer=[]
    for a in angles:
        dx,dy=math.cos(a),math.sin(a)
        reach=min(cx/max(abs(dx),1e-12),cy/max(abs(dy),1e-12))
        outer.append((cx+reach*dx,cy+reach*dy))
    rings=[]
    for fraction in (.15,.4,.7,1):
        ring=[]
        for x,y in outer:
            f=fraction+(rng.uniform(-.055,.055) if fraction<1 else 0)
            ring.append((cx+(x-cx)*f,cy+(y-cy)*f))
        rings.append(ring)
    result=[]
    for k,ring in enumerate(rings):
        for i in range(len(angles)):
            j=(i+1)%len(angles)
            polygon=((cx,cy),ring[i],ring[j]) if k==0 else (rings[k-1][i],ring[i],ring[j],rings[k-1][j])
            result.append((polygon,rng.uniform(-3,3),rng.uniform(-3,3),rng.uniform(-1.8,1.8),rng.uniform(.8,1.25)))
    return result


def frame(outgoing, incoming, progress, mesh):
    if outgoing.size!=incoming.size:raise ValueError('Shatter inputs must have equal dimensions')
    if progress<=0:return outgoing.convert('RGB')
    if progress>=1:return incoming.convert('RGB')
    w,h=outgoing.size;q=float(progress);result=incoming.convert('RGBA')
    for triangle,rx,ry,rz,speed in mesh:
        source=np.array(triangle);centre=source.mean(axis=0)
        left=max(0,math.floor(source[:,0].min()));top=max(0,math.floor(source[:,1].min()))
        right=min(w,math.ceil(source[:,0].max()));bottom=min(h,math.ceil(source[:,1].max()))
        if right<=left or bottom<=top:continue
        tile=outgoing.crop((left,top,right,bottom)).convert('RGBA')
        mask=Image.new('L',tile.size);ImageDraw.Draw(mask).polygon([(x-left,y-top) for x,y in triangle],fill=255);tile.putalpha(mask)
        # Project a rotating plane. Use the four crop corners to retain its
        # perspective mapping; the polygon alpha mask travels with it.
        a,b,c=rx*q,ry*q,rz*q
        X=np.array([[1,0,0],[0,math.cos(a),-math.sin(a)],[0,math.sin(a),math.cos(a)]])
        Y=np.array([[math.cos(b),0,math.sin(b)],[0,1,0],[-math.sin(b),0,math.cos(b)]])
        Z=np.array([[math.cos(c),-math.sin(c),0],[math.sin(c),math.cos(c),0],[0,0,1]])
        corners=np.array([[left,top],[right,top],[right,bottom],[left,bottom]],float)
        xyz=np.column_stack((corners-centre,np.zeros(4)))@(Z@Y@X).T
        focal=2*max(w,h);projected=xyz[:,:2]*focal/(focal+xyz[:,2,None])
        drift=np.array([(centre[0]-w*.5)*q*3*speed,(centre[1]-h*.5)*q*2+2.5*h*q*q])
        target=projected+centre+drift
        x0=max(0,math.floor(target[:,0].min()));y0=max(0,math.floor(target[:,1].min()))
        x1=min(w,math.ceil(target[:,0].max()));y1=min(h,math.ceil(target[:,1].max()))
        if x1<=x0 or y1<=y0:continue
        matrix=[];values=[]
        for (x,y),(u,v) in zip(target-[x0,y0],corners-[left,top]):
            matrix.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]]);values.extend([u,v])
        try:coeff=np.linalg.solve(matrix,values)
        except np.linalg.LinAlgError:continue  # A plane exactly edge-on has zero projected area.
        warped=tile.transform((x1-x0,y1-y0),Image.Transform.PERSPECTIVE,coeff,Image.Resampling.BICUBIC)
        result.alpha_composite(warped,(x0,y0))
    return result.convert('RGB')


@contextmanager
def decoded(path, start, count, size):
    # Decode by frame index, not rounded seconds; both clocks are already60fps.
    args=['ffmpeg','-v','error','-i',str(path),'-vf',f'trim=start_frame={start}:end_frame={start+count},setpts=PTS-STARTPTS','-an','-f','rawvideo','-pix_fmt','rgb24','-']
    with open(str(path)+'.shatter-decode.log','wb') as log:
        p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=log)
        def read():
            needed=size[0]*size[1]*3;data=bytearray()
            while len(data)<needed:
                part=p.stdout.read(needed-len(data))
                if not part:raise RuntimeError('Shatter source ended before declared handle')
                data.extend(part)
            return Image.frombytes('RGB',size,bytes(data))
        try:
            yield read
            if p.stdout.read(1):raise RuntimeError('Shatter decoder returned extra frames')
            if p.wait():raise RuntimeError('Shatter source decoding failed')
        finally:
            if p.poll() is None:p.kill();p.wait()
            p.stdout.close()


def render(outgoing,incoming,dest,start,count,seed=17,size=(1920,1080)):
    from longform_photo import encode_frames
    mesh=fragments(size,seed)
    with decoded(outgoing,start,count,size) as a,decoded(incoming,0,count,size) as b:
        encode_frames((frame(a(),b(),i/max(1,count-1),mesh).tobytes() for i in range(count)),dest,size=size)
    return dest


def handoff(folder,outgoing,incoming,spec):
    """Replace incoming prefix with shards; do not change either scene's clock."""
    from pathlib import Path
    from film_editor import command
    from longform_state import ProductionError,save
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    count=spec['frames'];start=outgoing['visible_frames'];total=incoming['frames']
    if outgoing['frames']<start+count or count>=incoming['visible_frames']:
        raise ProductionError('scene_handoff_handles','장면 전환용 실제 화면 구간이 부족합니다.',action='edit_plan')
    shard=render(outgoing['path'],incoming['path'],folder/'shards.mp4',start,count,spec.get('seed',17))
    dest=folder/'handoff.mkv'
    command(folder,['ffmpeg','-y','-v','error','-filter_complex_threads','1','-i',shard,'-i',incoming['path'],
        '-filter_complex',f'[0:v]settb=1/60,setpts=PTS-STARTPTS[a];[1:v]trim=start_frame={count}:end_frame={total},settb=1/60,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[v]',
        '-map','[v]','-an','-frames:v',total,'-r','60','-c:v','ffv1','-pix_fmt','yuv420p',dest],'scene-handoff',timeout=1800)
    # Matroska does not require nb_frames. Decode-count instead of trusting duration.
    import json
    raw=command(folder,['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames','-of','json',dest],'handoff-count')
    actual=int(json.loads(raw)['streams'][0]['nb_read_frames'])
    if actual!=total:raise ProductionError('scene_handoff_frames','장면 전환으로 프레임 수가 바뀌었습니다.')
    result=dict(incoming,path=str(dest),start=0,normalized=True,
                handoff_source_visual=outgoing['visual'],handoff_frames=count)
    proof=folder/'handoff.json';save(proof,{'outgoing':outgoing,'incoming':incoming,'transition':spec,'frames':actual,'audio_retimed':False})
    return result,[dest,proof]
