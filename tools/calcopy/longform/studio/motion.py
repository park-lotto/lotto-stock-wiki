# 화면 문법의 주인: 어두운 바탕·빛 번짐·입자·궤도·빛기둥. 카드와 전환은 여기 함수를 부른다.
from .settings import *
INK = (244, 245, 247); DIM = (150, 158, 170); LINE = (58, 64, 76)
GOLD = tuple(C["sub_bar"][:3]); HOT = tuple(C["red"][:3]); SOFT = tuple(C["gray"][:3]); NIGHT = tuple(C.get("night", (9, 11, 16)))

_night = None
def night():
    """은은한 중앙 빛과 점 격자가 있는 바탕."""
    global _night
    if _night is None:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((x - W / 2) / (W * 0.6)) ** 2 + ((y - H / 2) / (H * 0.6)) ** 2)
        arr = np.array(NIGHT, np.float32) + (np.clip(1 - r, 0, 1) ** 2)[..., None] * np.array(GOLD, np.float32) * 0.07
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB"); d = ImageDraw.Draw(im)
        for gx in range(60, W, 60):
            for gy in range(60, H, 60): d.point((gx, gy), fill=(46, 50, 60))
        _night = im
    return _night.copy()

_noise = []
def film_grain(frame, t):
    """필름 입자. 초당 12번 바뀐다."""
    global _noise
    if not _noise:
        rng = np.random.default_rng(11)
        _noise = [np.asarray(Image.fromarray(rng.integers(0, 256, (H // 3, W // 3), dtype=np.uint8)).resize((W, H), Image.BILINEAR), np.int16)[..., None] // 64 - 2 for _ in range(6)]
    a = np.asarray(frame.convert("RGB"), np.int16) + _noise[int(t * 12) % 6]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")

_spr = {}
def glow_sprite(text, f, col, blur):
    k = (text, id(f), col, blur)
    if k in _spr: return _spr[k]
    if len(_spr) > 600: _spr.clear()
    x0, y0, x1, y1 = ImageDraw.Draw(Image.new("L", (4, 4))).textbbox((0, 0), text, font=f)
    pad = max(8, blur * 3); im = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - x0, pad - y0), text, font=f, fill=col + (255,))
    if blur:
        halo = im.filter(ImageFilter.GaussianBlur(blur)); halo.alpha_composite(im); im = halo
    _spr[k] = (im, pad, x1 - x0, y1 - y0); return _spr[k]

def glow_text(img, text, x, y, f, col=INK, blur=0, a=1.0, anchor="c"):
    """(x, y) = 글자 덩어리의 가운데(c) 또는 왼쪽 가운데(l) 또는 오른쪽 가운데(r)."""
    if a <= 0 or not text: return
    im, pad, w, h = glow_sprite(text, f, tuple(col), blur)
    if a < 1: im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    lx = {"c": x - w / 2, "l": x, "r": x - w}[anchor] - pad
    img.alpha_composite(im, (max(0, int(lx)), max(0, int(y - h / 2 - pad))))

def hangul(ch): return "가" <= ch <= "힣"
def spaced(img, text, x, y, size=20, col=DIM, gap=4, a=255, right=False):
    """자간 넓은 작은 표지. 글자는 한글 고딕, 나머지는 고정폭."""
    d = ImageDraw.Draw(img); fk, fm = face("SB", size), face("MONO", size - 2)
    adv = [d.textlength(c, font=fk if hangul(c) else fm) + gap for c in text]
    if right: x -= sum(adv)
    for c, w in zip(text, adv):
        d.text((x, y), c, font=fk if hangul(c) else fm, fill=tuple(col) + (a,)); x += w

def fit_face(name, size, text, maxw, low=48):
    d = ImageDraw.Draw(Image.new("L", (4, 4)))
    while size > low and d.textlength(text, font=face(name, size)) > maxw: size = int(size * 0.94)
    return face(name, size)

def big_face(text, size, maxw):
    """숫자만이면 좁고 높은 글꼴, 한글이 섞이면 굵은 한글 글꼴."""
    return fit_face("HAN", int(size * 0.8), text, maxw) if any(hangul(c) for c in text) else fit_face("AN", size, text, maxw)

def panel(img, box, fill=(16, 18, 24), edge=None, a=255, width=2, radius=10, blur=0):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    if blur and edge:
        d.rounded_rectangle(box, radius=radius, outline=tuple(edge) + (int(a * 0.8),), width=width + 6); lay = lay.filter(ImageFilter.GaussianBlur(blur)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle(box, radius=radius, fill=tuple(fill) + (int(a * 0.94),), outline=(tuple(edge) + (a,)) if edge else None, width=width)
    img.alpha_composite(lay)

def corner_ticks(d, box, col, n=34, width=4):
    x0, y0, x1, y1 = box
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(cx + sx * n, cy), (cx, cy), (cx, cy + sy * n)], fill=col, width=width)

_gath = np.random.default_rng(9)
GATHER = np.stack([_gath.uniform(0, 6.283, 420), _gath.uniform(220, 880, 420), _gath.uniform(0, 70, 420)], 1)
def gather(img, cx, cy, p, col=GOLD):
    """흩어진 입자가 한 점으로 모인다(p 0→1)."""
    if p <= 0 or p >= 1: return
    d = ImageDraw.Draw(img); q = 1 - (1 - p) ** 3
    for i, (a, r, o) in enumerate(GATHER):
        rr = (1 - q) * r + o; x = cx + math.cos(a) * rr * 1.5; y = cy + math.sin(a) * rr; s = 3 if i % 3 else 2
        d.rectangle([x, y, x + s, y + s], fill=tuple(col if i % 3 else INK) + (170,))

def ping(img, cx, cy, p, col=GOLD, r0=90, r1=420):
    """숫자가 닿는 순간 번지는 고리."""
    if p <= 0 or p >= 1: return
    d = ImageDraw.Draw(img); r = r0 + (r1 - r0) * smooth(p); a = int(190 * (1 - p))
    d.ellipse([cx - r * 1.5, cy - r, cx + r * 1.5, cy + r], outline=tuple(col) + (a,), width=4)

_pil = {}
def light_pillar(hpx, bw, col):
    """아래에서 차오르는 빛 막대. 위쪽이 밝고 끝에 빛나는 뚜껑이 있다."""
    k = (bw, col)
    if k not in _pil:
        wd, full = bw + 120, 640; c = wd // 2; halo = Image.new("RGBA", (wd, full), (0, 0, 0, 0))
        ImageDraw.Draw(halo).rectangle([c - bw // 2, 0, c + bw // 2, full], fill=tuple(col) + (120,)); halo = halo.filter(ImageFilter.GaussianBlur(28))
        arr = np.zeros((full, bw, 4), np.uint8); arr[..., :3] = col; arr[..., 3] = np.linspace(255, 150, full)[:, None].astype(np.uint8)
        halo.alpha_composite(Image.fromarray(arr, "RGBA"), (c - bw // 2, 0)); _pil[k] = halo
    im = _pil[k]; h = max(1, min(im.height, int(hpx))); out = im.crop((0, 0, im.width, h)); c = im.width // 2
    ImageDraw.Draw(out).rectangle([c - bw // 2, 0, c + bw // 2, 5], fill=(255, 255, 255, 255))
    return out

_rays = np.random.default_rng(13)
RAYS = np.stack([_rays.uniform(0, 6.283, 260), _rays.uniform(0.05, 1.0, 260), _rays.uniform(0.6, 1.6, 260)], 1)
def speed_lines(img, t, col=INK, cx=None, cy=None):
    """중심에서 뻗는 속도선."""
    d = ImageDraw.Draw(img); cx = W / 2 if cx is None else cx; cy = H / 2 if cy is None else cy; mx = W * 0.72
    for a, st, v in RAYS:
        r = (st + t * v) % 1.0; r0 = r * r * mx; r1 = min(mx, r0 + 40 + r * 230)
        d.line([(cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a) * r1, cy + math.sin(a) * r1)], fill=tuple(col) + (int(40 + 150 * r),), width=2)

def ring_line(img, cx, cy, R, col=LINE, a=1.0, width=2):
    ImageDraw.Draw(img).ellipse([cx - R, cy - R, cx + R, cy + R], outline=tuple(col) + (int(255 * a),), width=width)

def light_sweep(frame, p):
    """컷이 바뀔 때 얇은 빛살이 지난다."""
    if p <= 0 or p >= 1: return
    x = -500 + (W + 1000) * p; lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for off, wd, a in ((0, 90, 70), (120, 16, 210), (170, 5, 255)):
        d.polygon([(x + off + 180, 0), (x + off + 180 + wd, 0), (x + off + wd, H), (x + off, H)], fill=GOLD + (a,))
    frame.alpha_composite(lay)

def night_wipe(frame, p):
    """어두운 판이 대각선으로 지나며 빛나는 모서리를 남긴다."""
    x = -W * 0.6 + W * 2.2 * p; lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.polygon([(x, 0), (x + W * 0.9, 0), (x + W * 0.5, H), (x - W * 0.4, H)], fill=NIGHT + (255,))
    d.line([(x, 0), (x - W * 0.4, H)], fill=GOLD + (255,), width=8); d.line([(x + W * 0.9, 0), (x + W * 0.5, H)], fill=GOLD + (255,), width=8)
    frame.alpha_composite(lay)


TINT = {"base": NIGHT, "navy": (8, 13, 30), "wine": (22, 9, 14), "teal": (6, 19, 22)}
_tinted = {}
def dark(tint="base", t=0.0):
    """색조가 다른 어두운 바탕."""
    if tint not in _tinted:
        add = np.array(TINT[tint], np.int16) - np.array(NIGHT, np.int16)
        _tinted[tint] = Image.fromarray(np.clip(np.asarray(night(), np.int16) + add, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return _tinted[tint].copy()

CUT_SEC = 0.16
def cut_in(frame, kind, p):
    """새 화면이 들어오는 순간(0.16초)."""
    if kind == "none" or p >= 1 or p < 0: return frame
    q = smooth(p)
    if kind == "flash": frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(235 * (1 - p)))))
    elif kind == "sweep": light_sweep(frame, p)
    elif kind == "punch":
        z = 1.14 - 0.14 * q; w, h = W / z, H / z; l, t = (W - w) / 2, (H - h) / 2; return frame.transform((W, H), Image.EXTENT, (l, t, l + w, t + h), Image.BILINEAR)
    elif kind == "whip":
        sm = frame.resize((W // 18, H), Image.BILINEAR).resize((W, H), Image.BILINEAR); out = Image.blend(sm, frame, q); dx = int((1 - q) * 220)
        base = Image.new("RGBA", (W, H), NIGHT + (255,)); base.alpha_composite(out, (dx, 0)); return base
    else:
        d = ImageDraw.Draw(frame)
        if kind == "slices":
            for i in range(7):
                y0, y1 = i * H // 7, (i + 1) * H // 7; w = int(W * (1 - q)); d.rectangle([0, y0, w, y1] if i % 2 else [W - w, y0, W, y1], fill=NIGHT)
        elif kind == "shutter":
            for i in range(9): x0 = i * W // 9; d.rectangle([x0, 0, x0 + int(W / 9 * (1 - q)), H], fill=NIGHT)
        elif kind == "iris":
            r = q * 1200; lay = Image.new("RGBA", (W, H), NIGHT + (255,)); ImageDraw.Draw(lay).ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=(0, 0, 0, 0)); frame.alpha_composite(lay)
    return frame

def chapter_wipe(frame, kind, p):
    if kind == "diagonal": night_wipe(frame, p); return
    d = ImageDraw.Draw(frame); c = 1 - abs(2 * p - 1)
    if kind == "blinds":
        for i in range(8):
            y = i * H // 8; d.rectangle([0, y, W, y + int(H / 8 * c)], fill=NIGHT); d.rectangle([0, y + int(H / 8 * c), W, y + int(H / 8 * c) + 3], fill=GOLD)
    else:
        w = int(W / 2 * c); d.rectangle([0, 0, w, H], fill=NIGHT); d.rectangle([W - w, 0, W, H], fill=NIGHT); d.rectangle([w - 6, 0, w, H], fill=GOLD); d.rectangle([W - w, 0, W - w + 6, H], fill=GOLD)

def living(frame, p, punch=0.0):
    """정지한 카드도 살짝 다가가고, 강조 순간에는 툭 들어간다."""
    z = 1 + 0.045 * p + 0.07 * punch; w, h = W / z, H / z; l, t = (W - w) / 2, (H - h) / 2
    return frame.transform((W, H), Image.EXTENT, (l, t, l + w, t + h), Image.BILINEAR)
