import sys, json, pathlib, subprocess, re, shutil, time
ROOT = pathlib.Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
S = pathlib.Path(sys.argv[1]); tag = sys.argv[2]; overrides = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
from shopping_shorts import scene_style
d = json.load(open(S / 'job956.json', encoding='utf-8'))
snap = dict(d['snapshot']); snap.update(overrides)
work = S / f'work_{tag}'; shutil.rmtree(work, ignore_errors=True); work.mkdir()
t = time.time()
scene_style.compose(str(S / 'clean.mp4'), d['timeline'], snap, str(S / f'out_{tag}.mp4'), str(work), d['headcopy'])
print('compose 초:', round(time.time() - t, 1))
def freezes(p):
    r = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(p), '-vf', 'freezedetect=n=0.02:d=0.3', '-an', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return re.findall(r'freeze_start: ([0-9.]+)|freeze_duration: ([0-9.]+)', r.stderr)
print('전체 freeze:', [x for x in freezes(S / f'out_{tag}.mp4')])
layers = json.load(open(work / 'scene-style-layers.json', encoding='utf-8'))
for i, p in enumerate(sorted(work.glob('*.mp4'), key=lambda x: int(re.findall(r'\d+', x.stem)[-1]) if re.findall(r'\d+', x.stem) else 0)):
    fz = freezes(p); lay = layers[i] if i < len(layers) else {}
    cam = lay.get('camera') or []; zoomed = any(abs(f.get('zoom', 1) - 1) > 1e-5 for f in cam)
    print(f'  part {p.name}: freeze {fz or "-"} | animation {bool(lay.get("animation"))} | camera {zoomed} ({len(cam)}f)')
