"""유튜브 4회차 썸네일 — 2560x1440(고화질). 가운데 = 주황 픽셀 캐릭터."""
import sys, os
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

S = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\CH\Desktop\로또의 주식"
FONTDIR = REPO + r"\.claude\worktrees\agent-aef0f9be0298b206b\shopping_shorts\static\fonts"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S, "thumb_4.png")
K = 2                      # 1280x720 기준 좌표를 K배로
W, H = 1280 * K, 720 * K

bg = Image.new("RGB", (W, H), (8, 8, 10))
cw = 230 * K
xs = [-20, 190, 400, 650, 860, 1070]
ys = [70, 10, 60, 40, 0, 50]
for k in range(6):
    im = Image.open(os.path.join(S, f"c{k+1}.png")).convert("RGB")
    im = im.resize((cw, int(im.height * cw / im.width)), Image.LANCZOS)
    im = ImageEnhance.Brightness(im).enhance(0.58)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), 14 * K, fill=255)
    bg.paste(im, (xs[k] * K, ys[k] * K), mask)

grad = Image.new("L", (1, H))
for y in range(H):
    grad.putpixel((0, y), int(max(0, min(255, (y / K - 330) * 255 / 230))))
bg = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), bg, grad.resize((W, H)))
bg = bg.convert("RGBA")

# ── 가운데 캐릭터(픽셀) ──
GRID = [   # 클로드 코드 시작 화면 문자 그림(4분할 블록)을 칸으로 옮김 — 한 칸 = 가로1:세로2
    "   ############  ",
    "   ##E######E##  ",
    " ################",
    "   ############  ",
    "    # #    # #   ",
]
ORANGE = (217, 119, 87)
PX = 21 * K
PY = 2 * PX
P = PX
gw, gh = len(GRID[0]) * PX, len(GRID) * PY
cx, cy = W // 2, 230 * K
ox, oy = cx - gw // 2, cy - gh // 2

glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse((cx - gw * 0.75, cy - gh * 0.75, cx + gw * 0.75, cy + gh * 0.75), fill=(255, 120, 50, 200))
glow = glow.filter(ImageFilter.GaussianBlur(55 * K))
bg = Image.alpha_composite(bg, glow)
bg = Image.alpha_composite(bg, glow)

def draw_char(img, x0, y0, body, eye, shade=True):
    d = ImageDraw.Draw(img)
    for r, row in enumerate(GRID):
        for c, ch in enumerate(row):
            if ch == " ":
                continue
            x, y = x0 + c * PX, y0 + r * PY
            d.rectangle((x, y, x + PX - 1, y + PY - 1), fill=eye if ch == "E" else body)

# 그림자 → 검은 외곽(배경과 분리) → 본체
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw_char(shadow, ox + 10 * K, oy + 14 * K, (0, 0, 0, 170), (0, 0, 0, 170))
bg = Image.alpha_composite(bg, shadow.filter(ImageFilter.GaussianBlur(8 * K)))
outline = Image.new("RGBA", (W, H), (0, 0, 0, 0))
for dx in (-1, 0, 1):
    for dy in (-1, 0, 1):
        draw_char(outline, ox + dx * 6 * K, oy + dy * 6 * K, (0, 0, 0, 255), (0, 0, 0, 255))
bg = Image.alpha_composite(bg, outline)
draw_char(bg, ox, oy, ORANGE + (255,), (20, 20, 20, 255))

# ── 글씨 ──
d = ImageDraw.Draw(bg)
heavy = os.environ.get("THUMB_FONT") or os.path.join(S, "fonts", "Pretendard-Black.otf")
import json
C = json.loads(os.environ.get("THUMB_COPY") or json.dumps({
    "tag": "자막·성우·편집, 손 안 댄다!",
    "l1": [["클로드가 난리났다!!", "W"]],
    "l2": [["쇼츠 ", "M"], ["손편집", "Y"], [" 하시는 분들만 클릭", "M"]]}))
COL = {"W": (255, 255, 255), "M": (35, 240, 200), "Y": (255, 214, 0), "R": (255, 45, 45)}
f = ImageFont.truetype(heavy, C.get("tag_size", 40) * K)
tag = C["tag"]
tw = d.textlength(tag, font=f)
tx, ty = (C["tag_xy"][0] * K, C["tag_xy"][1] * K) if C.get("tag_xy") else (W - tw - 70 * K, 92 * K)
ts = C.get("tag_size", 40)
d.rounded_rectangle((tx - 18 * K, ty - 12 * K, tx + tw + 18 * K, ty + int(ts * 1.38) * K), 8 * K, fill=(0, 0, 0))
d.text((tx, ty), tag, font=f, fill=COL[C.get("tag_col", "W")])

def line(parts, base, size, stroke, maxw=W - 120 * K):
    # 칸마다 [글자, 색, 배율(선택)] — 배율로 한 단어만 크게
    while True:
        fos = [ImageFont.truetype(heavy, int(size * (p[2] if len(p) > 2 else 1))) for p in parts]
        tot = sum(d.textlength(p[0], font=fo) for p, fo in zip(parts, fos))
        if tot <= maxw: break
        size -= 4
    x = 60 * K
    for p, fo in zip(parts, fos):
        sc = p[2] if len(p) > 2 else 1
        d.text((x, base), p[0], font=fo, fill=COL[p[1]], stroke_width=int(stroke * max(1, sc)), stroke_fill=(0, 0, 0), anchor="ls")
        x += d.textlength(p[0], font=fo)
    return x
x = line(C["l1"], 555 * K, 140 * K, 10 * K)
x = line(C["l2"], 685 * K, 104 * K, 9 * K)
print("line2 end", int(x), "/", W)
bg.convert("RGB").save(OUT)
print(OUT, bg.size)
