# 캡처 15장에서 얼굴을 실제로 찾아 최민식(항상 오른쪽) 중심 x/y 를 faces.json 에 기록한다.
# 규칙(중앙·0.72)으로 때려맞추지 않는다 — 분할컷(11번)에서 얼굴이 양쪽으로 다 잘렸다.
# 검출기 = 볼케이노 framevision 팩의 YuNet (facelib_cv.faces)
import os, sys, json, io
from PIL import Image, ImageDraw

WORK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(WORK, 'framevision'))
import facelib_cv

out, rows = {}, []
for n in range(1, 16):
    p = os.path.join(WORK, 'img_clean', f'{n:02d}.jpg')
    fs = facelib_cv.faces(p) or []
    pil = Image.open(p).convert('RGB'); w, h = pil.size
    if fs:
        f = max(fs, key=lambda b: b['x'] + b['w'] / 2)          # 가장 오른쪽 = 최민식
        cx, cy, how = f['x'] + f['w'] / 2, f['y'] + f['h'] / 2, f'{len(fs)}얼굴→오른쪽'
    else:
        cx, cy, how = 0.5, 0.45, '얼굴없음→중앙'
    out[str(n)] = dict(cx=round(cx, 3), cy=round(cy, 3), faces=len(fs))
    d = ImageDraw.Draw(pil)
    for b in fs:
        d.rectangle([b['x'] * w, b['y'] * h, (b['x'] + b['w']) * w, (b['y'] + b['h']) * h], outline=(0, 255, 0), width=3)
    d.line([(cx * w, 0), (cx * w, h)], fill=(255, 0, 0), width=4)
    d.rectangle([0, 0, 200, 22], fill=(0, 0, 0)); d.text((6, 5), f'{n:02d} {how} cx={cx:.2f}', fill=(255, 255, 0))
    rows.append(pil.resize((450, int(450 * h / w))))
    print(f'{n:02d} {how:14s} cx={cx:.2f} cy={cy:.2f}')

json.dump(out, io.open(os.path.join(WORK, 'faces.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
cw, ch = rows[0].size
sheet = Image.new('RGB', (cw * 5, ch * 3), (20, 20, 20))
for i, r in enumerate(rows): sheet.paste(r, ((i % 5) * cw, (i // 5) * ch))
os.makedirs(os.path.join(WORK, 'v12'), exist_ok=True)
sheet.save(os.path.join(WORK, 'v12', 'faces_sheet.jpg'), quality=88)
print('sheet saved')
