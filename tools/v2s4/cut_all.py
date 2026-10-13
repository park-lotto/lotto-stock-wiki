import subprocess, glob, os, sys, shutil
sys.path.insert(0, os.path.dirname(__file__))
from scenes import SCENES, ROOT, PUB
only = sys.argv[1:]
for k, (d, recs) in SCENES.items():
    if only and k not in only: continue
    src = os.path.join(ROOT, d); mp3 = glob.glob(os.path.join(src, '*.mp3'))[0]
    out = os.path.join(PUB, k); os.makedirs(out, exist_ok=True)
    shutil.copy(mp3, os.path.join(out, 'voice.mp3'))
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'cut.py'), mp3, out] + [os.path.join(src, x) for x in recs], capture_output=True, text=True)
    print(k, r.stdout.strip(), r.stderr[-300:], flush=True)
