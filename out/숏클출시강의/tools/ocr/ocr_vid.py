"""영상 fps 간격 OCR → json [t, 글, 점수, [x0,y0,x1,y1]] (원본 픽셀). 사용: py ocr_vid.py <영상> <fps> <out.json> [t0 t1]"""
import sys, json, subprocess, numpy as np, ocr_ko
src, fps, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
t0 = float(sys.argv[4]) if len(sys.argv) > 4 else 0; t1 = float(sys.argv[5]) if len(sys.argv) > 5 else 1e9
w, h = map(int, subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height","-of","csv=p=0",src],capture_output=True,text=True).stdout.strip().split(",")[:2])
sc = 2 if max(w, h) < 1100 else 1
o = ocr_ko.make()
p = subprocess.Popen(["ffmpeg","-v","error","-ss",str(t0),"-t",str(t1-t0) if t1<1e8 else "99999","-i",src,"-vf",f"fps={fps},scale={w*sc}:{h*sc}","-f","rawvideo","-pix_fmt","bgr24","-"],stdout=subprocess.PIPE)
res, k = [], 0
while True:
    b = p.stdout.read(w*h*sc*sc*3)
    if len(b) < w*h*sc*sc*3: break
    r, _ = o(np.frombuffer(b, np.uint8).reshape(h*sc, w*sc, 3))
    t = round(t0 + k / fps, 3)
    for box, txt, s in (r or []):
        xs=[q[0]/sc for q in box]; ys=[q[1]/sc for q in box]
        res.append([t, txt, round(float(s),2), [int(min(xs)),int(min(ys)),int(max(xs)),int(max(ys))]])
    k += 1
json.dump(res, open(out,"w",encoding="utf-8"), ensure_ascii=False); print("done", src, k, len(res))
