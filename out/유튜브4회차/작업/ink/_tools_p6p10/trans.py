"""ART_GATE_1 자가검사 ③⑥: 0.1초 간격 프레임.
 - 잉크 0.5% 미만 프레임 수(전 구간), 전환 시각 ±0.3초 프레임을 한 장(<장면>/trans_sheet.jpg)으로
 - 마지막 픽셀 변화 시각(연속 프레임 평균차 > 0.15 기준)
usage: py trans.py P7 6.4 11.7 14.6
"""
import sys, subprocess, pathlib, tempfile, json
import numpy as np
from PIL import Image
HQ = pathlib.Path(__file__).resolve().parent.parent
sc = sys.argv[1]; cuts = [float(x) for x in sys.argv[2:]]
d = HQ / sc; tmp = pathlib.Path(tempfile.mkdtemp())
subprocess.run(['ffmpeg', '-v', 'error', '-i', str(d / 'out.mp4'), '-vf', 'fps=10,scale=480:-1', str(tmp / 'f%04d.png')], check=True)
fr = sorted(tmp.glob('f*.png')); paper = np.array([251, 248, 241], dtype=np.int16)
arr = [np.asarray(Image.open(f).convert('RGB'), dtype=np.int16) for f in fr]
ink = [float((np.abs(a - paper).max(axis=2) > 30).mean()) for a in arr]
low = [round(i / 10, 1) for i, v in enumerate(ink) if v < 0.005]
diff = [float(np.abs(arr[i] - arr[i - 1]).mean()) for i in range(1, len(arr))]
last = max([i / 10 for i, v in enumerate(diff, start=1) if v > 0.15] or [0])
rows = []
for c in cuts:
    idx = [int(round((c + k / 10) * 10)) for k in range(-3, 4)]
    rows.append([Image.fromarray(arr[min(max(i, 0), len(arr) - 1)].astype('uint8')).resize((160, 90)) for i in idx])
if rows:
    sh = Image.new('RGB', (160 * 7, 90 * len(rows)), 'white')
    for r, row in enumerate(rows):
        for c, im in enumerate(row): sh.paste(im, (c * 160, r * 90))
    sh.save(d / 'trans_sheet.jpg', quality=85)
print(json.dumps({'scene': sc, 'ink_lt0.5_frames_0.1s': len(low), 'low_at': low[:10], 'last_change_s': last, 'trans_min_ink': [round(min(ink[max(0, int(c * 10) - 3):int(c * 10) + 4]) * 100, 2) for c in cuts]}, ensure_ascii=False))
