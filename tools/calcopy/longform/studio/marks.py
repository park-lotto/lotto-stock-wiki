# 화면 고정 표시와 태그
from .settings import *
from .motion import *
def mark_icon(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); s = size
    d.ellipse([s * .04, s * .04, s * .96, s * .96], outline=GOLD + (255,), width=max(3, s // 16))
    d.polygon([(s * .4, s * .3), (s * .4, s * .7), (s * .72, s * .5)], fill=GOLD + (255,))
    return im

_ui = {}
def paint_corners(chapter, bright):
    """위쪽 얇은 표시줄: 빛 점과 채널명, 반대편에 챕터."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); left = CFG.get("logo_side", "right") == "right"
    ink = (20, 22, 26) if bright else INK; n = CFG["channel_name"]; f = face("GM", 28); w = d.textlength(n, font=f)
    x = 54 if left else W - 54 - w - 28
    d.ellipse([x, 44, x + 16, 60], fill=GOLD + (255,)); d.text((x + 28, 37), n, font=f, fill=ink + (255,), stroke_width=2, stroke_fill=(0, 0, 0, 0 if bright else 150))
    if chapter and chapter not in CFG.get("no_capsule", []):
        spaced(im, chapter.split(" : ")[-1], W - 54 if left else 54, 40, 24, ink, 3, right=left)
    return im

def corner_marks(chapter, bright):
    k = (chapter, bright)
    if k not in _ui: _ui[k] = paint_corners(chapter, bright)
    return _ui[k]

_shade = None
def low_shade():
    global _shade
    if _shade is None:
        ramp = Image.new("L", (1, H)); ramp.putdata([int(min(1, max(0, (y - H * 0.70) / (H * 0.30))) ** 1.4 * 215) for y in range(H)])
        _shade = Image.new("RGBA", (W, H), (0, 0, 0, 255)); _shade.putalpha(ramp.resize((W, H)))
    return _shade

NUMTOK = re.compile(r"\d[\d,.]*(?:%|만|천|억|조|원|달러|배|명|개월|개|년|월|분기)*(?: \d천)?(?: ?(?:원|달러|명))?")
def caption_bar(frame, text, p):
    """띠 없이 아래 그늘 위에 뜬 글자. 숫자는 강조색으로 빛난다."""
    frame.alpha_composite(low_shade()); f = face("GM", 50); d = ImageDraw.Draw(frame); w = d.textlength(text, font=f)
    x = (W - w) / 2; y = H - 104 + int((1 - smooth(p / 0.12)) * 14); i = 0
    for m in list(NUMTOK.finditer(text)) + [None]:
        a = text[i: m.start() if m else len(text)]
        if a: d.text((x, y), a, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 230)); x += d.textlength(a, font=f)
        if m: d.text((x, y), m[0], font=f, fill=GOLD + (255,), stroke_width=3, stroke_fill=(0, 0, 0, 230)); x += d.textlength(m[0], font=f); i = m.end()

_src = {}
def source_line(src, bright):
    """출처는 오른쪽 위 표시줄 아래 작은 표지로."""
    k = (src, bright)
    if k in _src: return _src[k]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if src: spaced(im, src if src == "AI 생성" else f"출처 {src}", W - 54, 78, 22, (20, 22, 26) if bright else INK, 2, 215, right=True)
    _src[k] = im; return im

def note_tag(img, text, cx, cy, p):
    """키워드: 빛 점에서 선이 뻗어 표가 열린다."""
    if p <= 0: return
    f = face("HAN", 46); g = smooth(p / 0.22); d = ImageDraw.Draw(img); w = d.textlength(text, font=f); x, y = 96, H - 300
    d.ellipse([x - 12, y + 30, x + 12, y + 54], fill=GOLD + (255,)); d.line([(x, y + 42), (x + 60, y + 42)], fill=GOLD + (255,), width=3)
    bw = (w + 56) * g; panel(img, [x + 60, y, x + 60 + bw, y + 84], (12, 13, 16), GOLD, radius=4, blur=10)
    if g > 0.75: glow_text(img, text, x + 88, y + 42, f, INK, 0, smooth((g - 0.75) / 0.25), "l")

def alert_tag(img, text, cx, cy, p):
    """경고: 빨간 고리가 번지며 찍힌다."""
    if p <= 0: return
    f = fit_face("HAN", 58, text, 700); d = ImageDraw.Draw(img); w = d.textlength(text, font=f); x = W - 96 - w - 60; y = 130; sc = 1 + 0.2 * (1 - smooth(p / 0.14))
    ping(img, x + w / 2 + 30, y + 50, p / 0.5, HOT, 60, 220); bw, bh = (w + 60) * sc, 100 * sc
    panel(img, [x + (w + 60 - bw) / 2, y + (100 - bh) / 2, x + (w + 60 + bw) / 2, y + (100 + bh) / 2], HOT, HOT, blur=14, radius=4)
    glow_text(img, text, x + w / 2 + 30, y + 50, f, (255, 255, 255))

MARK = re.compile(r"\[\[(.+?)\]\]|~~(.+?)~~")
def read_marks(text):
    """[[강조박스]] · ~~취소선~~ → [(조각, 종류)]  종류: '' / 'box' / 'strike'"""
    out, i = [], 0
    for m in MARK.finditer(text):
        if m.start() > i: out.append((text[i:m.start()], ""))
        out.append((m[1], "box") if m[1] is not None else (m[2], "strike")); i = m.end()
    if i < len(text): out.append((text[i:], ""))
    return out
ACCENTS = [(200, 255, 0), (255, 30, 138), (255, 214, 0), (30, 108, 235)]
def big_note(img, text, p):
    if p <= 0: return
    a = int(255 * smooth(p / 0.2)); sc = 1.0 + 0.18 * (1 - smooth(p / 0.22)); f = face("K", int(80 * sc)); d = ImageDraw.Draw(img)
    segs = read_marks(text); ws = [width_of(d, t, f) for t, _ in segs]; w = sum(ws)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    y = H // 2 - 60; x = (W - w) // 2
    dl.rectangle([x - 50, H // 2 - 84, x + w + 50, H // 2 + 56], fill=(8, 9, 12, int(a * 0.82)))
    dl.rectangle([x - 50, H // 2 - 84, x - 42, H // 2 + 56], fill=GOLD + (a,))
    nb = 0
    for (t, k), ww in zip(segs, ws):
        if k == "box":
            g = smooth((p - 0.25) / 0.2); c = ACCENTS[nb % len(ACCENTS)]; nb += 1
            if g > 0: dl.rectangle([x - 10, H // 2 - 74, x - 10 + (ww + 20) * g, H // 2 + 46], fill=c + (a,))
            dl.text((x, y), t, font=f, fill=((17, 17, 17, a) if g > 0.5 else (255, 225, 53, a)))
        elif k == "strike":
            dl.text((x, y), t, font=f, fill=(210, 210, 210, a), stroke_width=4, stroke_fill=(0, 0, 0, a))
            g = smooth((p - 0.15) / 0.2)
            if g > 0: dl.line([(x - 6, H // 2 - 8), (x - 6 + (ww + 12) * g, H // 2 - 8)], fill=(255, 40, 40, a), width=10)
        else:
            dl.text((x, y), t, font=f, fill=(255, 225, 53, a), stroke_width=5, stroke_fill=(0, 0, 0, a))
        x += ww
    img.alpha_composite(lay)

def wrapped_lines(d, text, hl, f, maxw):
    """줄바꿈(\n) 기준 + 강조 구간 표시: [(줄, [(조각, 강조여부)])]"""
    out = []
    for ln in text.split("\n"):
        parts, rest = [], ln
        while rest:
            pos = [(rest.find(h), h) for h in hl if h and rest.find(h) >= 0]
            if not pos: parts.append((rest, False)); break
            i, h = min(pos)
            if i > 0: parts.append((rest[:i], False))
            parts.append((h, True)); rest = rest[i + len(h):]
        out.append(parts)
    return out

