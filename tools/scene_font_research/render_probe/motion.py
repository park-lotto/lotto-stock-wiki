import json, pathlib, subprocess, sys
from PIL import Image, ImageChops, ImageStat
S = pathlib.Path(sys.argv[1]); work = S / 'work_base'
req = json.load(open(work / 'scene-style-request.json', encoding='utf-8')); scenes = req['context']['scenes']
layers = json.load(open(work / 'scene-style-layers.json', encoding='utf-8'))
def frame(video, t, crop=None):
    p = S / '_f.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', str(video), '-frames:v', '1', '-vf', 'scale=270:480', str(p)], check=True)
    im = Image.open(p).convert('L')
    return im.crop(crop) if crop else im
def motion(video, times, crop=None):
    fr = [frame(video, t, crop) for t in times]; d = []
    for a, b in zip(fr, fr[1:]): d.append(ImageStat.Stat(ImageChops.difference(a, b)).mean[0])
    return round(sum(d) / max(1, len(d)), 2)
print('part  구간(초)      청소본움직임  최종조각움직임  anim  camera  media_top%  media_h%')
for i in [0, 1, 2, 3, 4, 6, 7, 9, 10]:
    if i >= len(scenes): break
    sc, lay = scenes[i], layers[i]; part = work / f'scene-style-{i:04d}.mp4'
    if not part.exists(): continue
    dur = sc['end'] - sc['start']; n = max(3, int(dur / 0.25)); rel = [k * dur / n for k in range(n)]
    top, h = lay['media']['top'], lay['media']['height']; crop = (0, int(480 * top / 100), 270, int(480 * (top + h) / 100))
    mc = motion(S / 'clean.mp4', [sc['start'] + r for r in rel]); mp = motion(part, rel, crop)
    cam = any(abs(f.get('zoom', 1) - 1) > 1e-5 for f in (lay.get('camera') or []))
    print(f'{i:4d}  {sc["start"]:5.2f}-{sc["end"]:5.2f}   {mc:8.2f}   {mp:8.2f}      {"Y" if lay.get("animation") else "-"}     {"Y" if cam else "-"}     {top:5.1f}    {h:5.1f}')
