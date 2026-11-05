import sys, json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw
D = Path("C:/t/fm_samples")
sm = json.load(open("C:/t/fm_jev/samples.json", encoding="utf-8"))
def grab(p, n, h=200):
    pr = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)],capture_output=True,text=True)
    dur = float(pr.stdout.strip() or 1); out = []
    for k in range(n):
        t = dur * (k + .5) / n
        r = subprocess.run(["ffmpeg","-v","error","-ss",f"{t:.2f}","-i",str(p),"-frames:v","1","-vf",f"scale=-2:{h}","-f","image2pipe","-vcodec","png","-"],capture_output=True)
        try:
            import io; out.append((t, Image.open(io.BytesIO(r.stdout)).convert("RGB")))
        except Exception: pass
    return out
for i in map(int, sys.argv[1:]):
    a, b = sm["pos"][i]
    S = grab(D/(a.replace(":","_")+".mp4"), 16); C = grab(D/(b.replace(":","_")+".mp4"), 8)
    W = 8 * 120; sheet = Image.new("RGB", (W, 3 * 215), "white"); d = ImageDraw.Draw(sheet)
    for k, (t, im) in enumerate(S + C):
        im.thumbnail((118, 200)); r, c = (k // 8, k % 8)
        sheet.paste(im, (c * 120, r * 215 + 14)); d.text((c * 120 + 2, r * 215), f"{'S' if k < len(S) else 'O'} {t:.0f}s", fill="red")
    sheet.save(f"C:/t/fm_jev/sheets/pos_{i:02d}.png"); print(i, a, b)
