"""조각 영상 1초 간격 OCR → json (조각별 [초, 글, 점수, 상자]). 사용: py sweep.py <영상> <out.json>"""
import sys, json, subprocess, numpy as np, ocr_ko
src, out = sys.argv[1], sys.argv[2]
o = ocr_ko.make()
W, H = 1920, 1080
p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf", "fps=1,scale=1920:1080", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
res, t = [], 0
while True:
    b = p.stdout.read(W * H * 3)
    if len(b) < W * H * 3: break
    img = np.frombuffer(b, np.uint8).reshape(H, W, 3)
    r, _ = o(img)
    for box, txt, sc in (r or []):
        res.append([t + 0.5, txt, round(float(sc), 2), [[int(x), int(y)] for x, y in box]])
    t += 1
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print("done", src, t, len(res))
