# 렌더 전 샷 확인표. 재료 없는 칸·잘못된 참조가 있으면 실패로 끝난다. 표는 build/shot_sheet_N.jpg
import glob, importlib.util, json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(os.environ.get("LONGFORM_WORK") or os.getcwd())
BUILD = os.path.join(WORK, "build"); os.makedirs(BUILD, exist_ok=True)
spec = importlib.util.spec_from_file_location("shots", os.path.join(WORK, "shots.py")); sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
LINES = {x["i"]: x["text"] for x in json.load(open(os.path.join(WORK, "narr", "lines.json"), encoding="utf-8")) if x["type"] == "line"}
NO_ASSET = ("bar", "typo", "vs", "table", "pct", "cycle", "rating", "ladder")
TW, TH, COLS, PER = 384, 216, 5, 40
font = ImageFont.truetype(os.path.join(HERE, "fonts", "Pretendard-Bold.otf"), 18)


def png(n): return os.path.join(WORK, "assets", "img", f"s{n:03d}.png")
def mp4(n): return os.path.join(WORK, "assets", "stock", f"s{n:03d}.mp4")


def thumb(s):
    n = s["s"][0]
    if "img" in s: return Image.open(png(s["img"])).convert("RGB") if os.path.exists(png(s["img"])) else None
    src = mp4(s.get("clip", n))
    if os.path.exists(src):
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "2", "-i", src, "-frames:v", "1", "-vf", f"scale={TW}:{TH}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True).stdout
        return Image.frombytes("RGB", (TW, TH), raw) if len(raw) == TW * TH * 3 else None
    return Image.open(png(n)).convert("RGB") if os.path.exists(png(n)) else None


bad, cards = [], []
for s in sh.S:
    if s["type"] in NO_ASSET:
        continue
    im = thumb(s)
    if im is None:
        bad.append(s["s"][0])
        im = Image.new("RGB", (TW, TH), (200, 40, 40))
    im = im.resize((TW, TH)); d = ImageDraw.Draw(im)
    d.rectangle([0, TH - 28, TW, TH], fill=(0, 0, 0))
    d.text((6, TH - 25), f"{s['s'][0]} {LINES.get(s['s'][0], '')[:24]}", font=font, fill=(255, 255, 255))
    cards.append(im)
for f in glob.glob(os.path.join(BUILD, "shot_sheet_*.jpg")): os.remove(f)
for k in range(0, len(cards), PER):
    b = cards[k:k + PER]; rows = (len(b) + COLS - 1) // COLS
    sheet = Image.new("RGB", (TW * COLS, TH * rows))
    for i, im in enumerate(b): sheet.paste(im, (i % COLS * TW, i // COLS * TH))
    sheet.save(os.path.join(BUILD, f"shot_sheet_{k // PER}.jpg"), quality=82)
print(f"재료 칸 {len(cards)}개, 빈 칸 {len(bad)}개", bad)
sys.exit(1 if bad else 0)
