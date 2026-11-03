"""ART_GATE 판정용 수치+시트 도구.
py _qtools/gate2_check.py <scene_dir> [...]
  → <scene_dir>/_gate2/sheet.jpg (1초 간격, 4열, 폭 1000)  + 수치 한 줄 JSON
수치: 1초 프레임 잉크% / 3x3 칸 비움(잉크<0.3%) / 0.1초 프레임 최소 잉크·시각 / 마지막 픽셀 변화 시각 /
      첫 0.3·0.6·1.2초 잉크 / y>880 가운데 띠 잉크 / 1초 프레임끼리 거의 같은 쌍(정지·반복 의심)
"""
import sys, subprocess, pathlib, math, json
import numpy as np
from PIL import Image

def frames(mp4, fps, w, out):
    out.mkdir(exist_ok=True)
    for f in out.glob('*.png'): f.unlink()
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(mp4),'-vf',f'fps={fps},scale={w}:-1',str(out/'f%04d.png')],check=True)
    return sorted(out.glob('f*.png'))

def ink(a):  # a: HxWx3 uint8 ; ink = 흰 종이(밝기>235, 채도 낮음)가 아닌 픽셀
    g=a.astype(np.int16); mx=g.max(2); mn=g.min(2)
    return ((mx<225)|((mx-mn)>40))

def main(d):
    d=pathlib.Path(d); mp4=d/'out.mp4'; g=d/'_gate2'; g.mkdir(exist_ok=True)
    dur=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(mp4)]).decode().strip())
    # 1초 프레임(0.5,1.5,…)
    f1=frames(mp4,1,480,g/'_f1'); ims=[np.array(Image.open(f).convert('RGB')) for f in f1]
    H,W,_=ims[0].shape
    ink1=[]; empty=[]; band=[]
    for a in ims:
        m=ink(a); ink1.append(round(100*m.mean(),1))
        cells=[]
        for r in range(3):
            for c in range(3):
                cells.append(m[r*H//3:(r+1)*H//3, c*W//3:(c+1)*W//3].mean()*100)
        empty.append(sum(1 for v in cells if v<0.3))
        yb=int(H*880/1080); band.append(round(100*m[yb:, W*400//1920:W*1520//1920].mean(),1))
    # 거의 같은 프레임 쌍 (비인접 포함) → 정지/반복
    sim=[]
    for i in range(len(ims)):
        for j in range(i+1,len(ims)):
            dif=np.abs(ims[i].astype(np.int16)-ims[j].astype(np.int16)).max(2)
            if (dif>40).mean()<0.002: sim.append((i,j))
    # 시트
    pil=[Image.open(f) for f in f1]; cols=4; w,h=pil[0].size; w2=250; h2=int(h*w2/w)
    rows=math.ceil(len(pil)/cols); sh=Image.new('RGB',(cols*w2,rows*h2),'white')
    from PIL import ImageDraw
    for i,im in enumerate(pil):
        im=im.resize((w2,h2)); dr=ImageDraw.Draw(im); dr.rectangle((0,0,34,14),fill='red'); dr.text((2,1),f'{i}.5s',fill='white')
        sh.paste(im,((i%cols)*w2,(i//cols)*h2))
    sh.save(g/'sheet.jpg',quality=85)
    # 0.1초 프레임: 최소 잉크, 마지막 변화, 첫 그리기
    f10=frames(mp4,10,240,g/'_f10'); arr=[np.array(Image.open(f).convert('RGB')) for f in f10]
    inks=[ink(a).mean()*100 for a in arr]
    mi=int(np.argmin(inks)); last=0
    for i in range(1,len(arr)):
        dif=np.abs(arr[i].astype(np.int16)-arr[i-1].astype(np.int16)).max(2)
        if (dif>40).mean()>0.0005: last=i
    low=[(round(i/10,1),round(v,2)) for i,v in enumerate(inks) if v<1.0]
    def at(t):
        i=min(len(inks)-1,int(t*10)); return round(inks[i],2)
    res=dict(scene=d.name,dur=dur,ink1=ink1,empty9=empty,band_y880=band,same_pairs=sim,
             min_ink=(round(mi/10,1),round(inks[mi],2)),low_frames=low[:12],last_change=round(last/10,1),end_margin=round(dur-last/10,1),
             first=dict(t03=at(0.3),t06=at(0.6),t12=at(1.2)))
    (g/'metrics.json').write_text(json.dumps(res,ensure_ascii=False))
    print(json.dumps(res,ensure_ascii=False))
    for f in list((g/'_f10').glob('*.png')): f.unlink()

if __name__=='__main__':
    for a in sys.argv[1:]: main(a)
