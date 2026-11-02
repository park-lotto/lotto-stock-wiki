# 사진·영상을 얹는 무대 11종. 무대마다 곁들이는 움직임이 다르다.
from .settings import *
from .footage import *
from .motion import *
FOCI = [(0.5, 0.45), (0.3, 0.4), (0.7, 0.4), (0.5, 0.6)]

def camera(im, p, move, focus):
    """다가가기·물러나기·올리기·내리기. 옆으로 흐르지 않는다."""
    z = {"in": 1.04 + 0.12 * p, "out": 1.16 - 0.12 * p, "rise": 1.12, "sink": 1.12}[move]; w, h = W / z, H / z; l, t = (W - w) * focus[0], (H - h) * focus[1]
    if move == "rise": t = (H - h) * (1 - p)
    if move == "sink": t = (H - h) * p
    return im.transform((W, H), Image.EXTENT, (l, t, l + w, t + h), Image.BILINEAR)

def picture(s, lt, T, beat, move):
    """실사는 그대로 흘리고, 그림은 박자마다 초점을 바꿔 움직인다."""
    n = s["s"][0]; v = video_frame(s, lt, T); a, b = s["beats"][beat][0], s["beats"][beat + 1][0] if beat + 1 < len(s["beats"]) else T
    if v is None: v = camera(base_picture(s.get("img", n)), max(0.0, min(1.0, (lt - a) / max(b - a, 0.1))), move, FOCI[(n + beat) % 4])
    return tone(v, 0.0).convert("RGBA")

_back = {}
def soft_back(s):
    n = s.get("img", s["s"][0])
    if os.path.exists(E("material", "video", f"s{s.get('clip', s['s'][0]):03d}.mp4")): return dark("navy")
    if n not in _back:
        if len(_back) > 6: _back.clear()
        _back[n] = tone(base_picture(n).filter(ImageFilter.GaussianBlur(26)), 0.68).convert("RGBA")
    return _back[n].copy()

def sized(pic, w, h, focus=(0.5, 0.5)):
    r = max(w / W, h / H); cw, ch = w / r, h / r; l, t = (W - cw) * focus[0], (H - ch) * focus[1]
    return pic.resize((w, h), Image.BILINEAR, box=(l, t, l + cw, t + ch))

def s_window(s, pic, q, t, side=0):
    img = soft_back(s); bw, bh = 1464, 824; x, y = (W - bw) // 2 + side, 104 + int((1 - q) * 30)
    img.alpha_composite(sized(pic, bw, bh), (x, y)); corner_ticks(ImageDraw.Draw(img), (x - 14, y - 14, x + bw + 14, y + bh + 14), GOLD + (255,)); return img

def s_offset(s, pic, q, t):
    """사진을 왼쪽으로 밀고 오른쪽에 도는 고리와 눈금."""
    img = dark(s["tint"], t); bw, bh = 1340, 800; x = 54 - int((1 - q) * 80); img.alpha_composite(sized(pic, bw, bh), (x, 110)); d = ImageDraw.Draw(img)
    d.rectangle([x + bw, 110, x + bw + 8, 910], fill=GOLD); orbit(img, 1640, 340, 150, t, GOLD); orbit(img, 1640, 340, 92, -t * 1.6, HOT, 1.0, 1)
    for i in range(14):
        wd = 60 + 150 * (0.5 + 0.5 * math.sin(t * 2.2 + i * 0.7)); d.rectangle([1500, 590 + i * 22, 1500 + wd, 598 + i * 22], fill=GOLD + (120,))
    return img

_masks = {}
def poly_mask(key, pts):
    if key not in _masks:
        _masks[key] = Image.new("L", (W, H), 0); ImageDraw.Draw(_masks[key]).polygon(pts, fill=255)
    return _masks[key]

def s_slant(s, pic, q, t, mirror=False):
    img = dark(s["tint"], t); dot_globe(img, W * (0.83 if mirror else 0.17), H * 0.47, 210, t + s["s"][0], a=q)
    pts = [(0, 0), (W * 0.70, 0), (W * 0.60, H), (0, H)] if mirror else [(W * 0.40, 0), (W, 0), (W, H), (W * 0.30, H)]
    img.paste(pic, (0, 0), poly_mask(mirror, pts)); ex = (W * 0.70 if mirror else W * 0.40) + (1 - q) * (-200 if mirror else 200)
    ImageDraw.Draw(img).line([(ex, 0), (ex - W * 0.10, H)], fill=GOLD + (255,), width=7); return img

def s_strips(s, pic, q, t):
    """사진 세 쪽이 위아래에서 맞물린다."""
    img = dark(s["tint"], t); gap = 12; bw = (W - gap * 2) // 3
    for i in range(3):
        qi = smooth(q * 1.6 - i * 0.3); dy = int((1 - qi) * (-H if i % 2 else H)); x = i * (bw + gap); img.alpha_composite(pic.crop((x, 0, x + bw, H)), (x, dy))
    return img

def s_iris(s, pic, q, t):
    """둥근 창 안의 사진과 도는 궤도."""
    img = dark(s["tint"], t); cx, cy, r = 1190, 470, int(400 * (0.82 + 0.18 * q))
    if "iris" not in _masks:
        big = Image.new("L", (1600, 1600), 0); ImageDraw.Draw(big).ellipse([0, 0, 1599, 1599], fill=255); _masks["iris"] = big
    mask = _masks["iris"].resize((r * 2, r * 2), Image.BILINEAR); part = pic.crop((W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r)); img.paste(part, (cx - r, cy - r), mask)
    orbit(img, cx, cy, r + 26, t, GOLD); orbit(img, cx, cy, r + 58, -t * 0.7, HOT, 0.6, 1); dot_globe(img, 330, 470, 150, t, a=q); return img

def s_tilt(s, pic, q, t):
    """살짝 기운 사진 카드."""
    img = soft_back(s); ang = (-3.2 if s["s"][0] % 2 else 3.2) * (1 + (1 - q) * 1.4); bw, bh = 1330, 748; card = sized(pic, bw, bh); pad = 60
    lay = Image.new("RGBA", (bw + pad * 2, bh + pad * 2), (0, 0, 0, 0)); ImageDraw.Draw(lay).rectangle([pad - 10, pad - 10, pad + bw + 9, pad + bh + 9], fill=(245, 245, 240, 255)); lay.alpha_composite(card, (pad, pad))
    lay = lay.rotate(ang, Image.BILINEAR, expand=True); img.alpha_composite(lay, ((W - lay.width) // 2, (H - lay.height) // 2 - 30 + int((1 - q) * 60))); return img

def s_cinema(s, pic, q, t):
    """검은 띠가 닫히는 영화 비율과 옆 눈금."""
    img = pic.copy(); d = ImageDraw.Draw(img); bh = int(128 * q); d.rectangle([0, 0, W, bh], fill=(0, 0, 0)); d.rectangle([0, H - bh, W, H], fill=(0, 0, 0))
    for i in range(30):
        yy = 170 + i * 25; d.rectangle([W - 42, yy, W - (30 if i % 5 else 18), yy + 2], fill=GOLD + (200,))
    yy = 170 + (t * 90) % 725; d.polygon([(W - 58, yy - 8), (W - 58, yy + 8), (W - 46, yy)], fill=GOLD); return img

def s_duo(s, pic, q, t):
    """큰 사진 옆에 확대한 두 조각."""
    img = dark(s["tint"], t); m = 12; mw, sw = 1250, W - 1250 - m; sh = (H - m) // 2; img.alpha_composite(sized(pic, mw, H), (0, 0))
    for i, f in enumerate(((0.25, 0.3), (0.75, 0.7))):
        cw, ch = W * 0.42, H * 0.42 * (sh / sw) * (W / H) * 0.5625 * 1.78; l, tp = (W - cw) * f[0], (H - ch) * f[1]; part = pic.resize((sw, sh), Image.BILINEAR, box=(l, tp, l + cw, tp + ch))
        img.alpha_composite(part, (mw + m + int((1 - smooth(q * 1.5 - i * 0.4)) * 700), i * (sh + m)))
    return img

def stage(name, s, pic, q, t):
    if name in ("push", "pull"): return pic
    if name == "window": return s_window(s, pic, q, t)
    if name == "offset": return s_offset(s, pic, q, t)
    if name == "slant": return s_slant(s, pic, q, t)
    if name == "slant_r": return s_slant(s, pic, q, t, True)
    return {"strips": s_strips, "iris": s_iris, "tilt": s_tilt, "cinema": s_cinema, "duo": s_duo}[name](s, pic, q, t)
