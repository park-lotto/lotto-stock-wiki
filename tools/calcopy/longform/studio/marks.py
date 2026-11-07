# 화면 고정 표시와 태그
from .settings import *
from .motion import *
def mark_icon(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); s = size
    d.ellipse([s * .04, s * .04, s * .96, s * .96], outline=GOLD + (255,), width=max(3, s // 16))
    d.polygon([(s * .4, s * .3), (s * .4, s * .7), (s * .72, s * .5)], fill=GOLD + (255,))
    return im

def logo_badge(im):
    """원형 배지 로고(판 칸 logo_box = x, y, 지름). 영상 내내 같은 자리."""
    x, y, dia = CFG["logo_box"]; ring = tuple(CFG["logo_ring"]); s = 4; big = Image.new("RGBA", (dia * s, dia * s), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
    d.ellipse([0, 0, dia * s - 1, dia * s - 1], fill=(14, 22, 34, 255)); d.ellipse([0, 0, dia * s - 1, dia * s - 1], outline=ring + (255,), width=6 * s)
    d.ellipse([9 * s, 9 * s, (dia - 9) * s, (dia - 9) * s], outline=GOLD + (255,), width=2 * s)
    n = CFG.get("logo_text") or CFG["channel_name"]; f = fit_face("HAN", 36 * s, n, (dia - 26) * s, 10 * s)
    d.text((dia * s / 2, dia * s / 2), n, font=f, fill=(255, 255, 255, 255), anchor="mm", stroke_width=s, stroke_fill=(0, 0, 0, 200))
    im.alpha_composite(big.resize((dia, dia), Image.LANCZOS), (x, y))

_ui = {}
def paint_corners(chapter, bright):
    """위쪽 고정 표시: 로고(빛 점+채널명 또는 원형 배지), 반대편에 챕터."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); left = CFG.get("logo_side", "right") == "right"
    ink = (20, 22, 26) if bright else INK
    if CFG["logo_style"] == "badge": logo_badge(im)
    else:
        n = CFG["channel_name"]; f = face("GM", 28); w = d.textlength(n, font=f); x = 54 if left else W - 54 - w - 28
        d.ellipse([x, 44, x + 16, 60], fill=GOLD + (255,)); d.text((x + 28, 37), n, font=f, fill=ink + (255,), stroke_width=2, stroke_fill=(0, 0, 0, 0 if bright else 150))
    if CFG["chapter_label"] and chapter and chapter not in CFG.get("no_capsule", []):
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
    """자막. 기본 = 띠 없이 아래 그늘 위에 뜬 글자, 숫자는 강조색. 판이 caption_box 를 주면 반투명 상자 + 왼쪽 막대."""
    if CFG["caption_shade"]: frame.alpha_composite(low_shade())
    f = face(CFG["caption_font"], CFG["caption_size"]); d = ImageDraw.Draw(frame); w = d.textlength(text, font=f)
    x = (W - w) / 2; y = H - 104 + (int((1 - smooth(p / 0.12)) * 14) if CFG["caption_rise"] else 0); i = 0
    bx = CFG["caption_box"]
    if bx:
        bw = w + 2 * bx["pad"] + bx["bar_w"]; x0 = (W - bw) / 2; lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.rounded_rectangle([x0, bx["y0"], x0 + bw, bx["y1"]], radius=bx["radius"], fill=tuple(bx["rgba"]))
        dl.rectangle([x0, bx["y0"], x0 + bx["bar_w"] - 1, bx["y1"]], fill=tuple(bx["bar_rgb"]) + (255,)); frame.alpha_composite(lay)
        x = x0 + bx["bar_w"] + bx["pad"]; tb = d.textbbox((0, 0), text, font=f); y = (bx["y0"] + bx["y1"]) / 2 - (tb[1] + tb[3]) / 2
    toks = list(NUMTOK.finditer(text)) if CFG["caption_num_accent"] else []
    for m in toks + [None]:
        a = text[i: m.start() if m else len(text)]
        if a: d.text((x, y), a, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 230)); x += d.textlength(a, font=f)
        if m: d.text((x, y), m[0], font=f, fill=GOLD + (255,), stroke_width=3, stroke_fill=(0, 0, 0, 230)); x += d.textlength(m[0], font=f); i = m.end()

def source_mark(frame, s, src, box=None):
    """출처 표시의 주인. 판이 under_card 이고 카드 자리(box)가 있으면 카드 아래 오른쪽 작은 글자, 아니면 위 표시줄 아래."""
    if CFG["source_style"] == "under_card" and box and src:
        t = CFG["source_format"].format(src=src); f = face("B", 26); d = ImageDraw.Draw(frame)
        d.text((box[2], box[3] + 8), t, font=f, fill=(225, 228, 232, 255), anchor="ra", stroke_width=2, stroke_fill=(0, 0, 0, 160)); return
    frame.alpha_composite(source_line(src, False))

_src = {}
def source_line(src, bright):
    """출처는 오른쪽 위 표시줄 아래 작은 표지로."""
    k = (src, bright)
    if k in _src: return _src[k]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if src: spaced(im, src if src == "AI 생성" else f"출처 {src}", W - 54, 78, 22, (20, 22, 26) if bright else INK, 2, 215, right=True)
    _src[k] = im; return im

def note_tag(img, text, cx, cy, p, look="leader"):
    """키워드 표 4종."""
    if p <= 0: return
    f = face("HAN", 46); g = smooth(p / 0.14); d = ImageDraw.Draw(img); w = d.textlength(text, font=f)
    if look == "leader":
        x, y = 96, H - 300; d.ellipse([x - 12, y + 30, x + 12, y + 54], fill=GOLD + (255,)); d.line([(x, y + 42), (x + 60, y + 42)], fill=GOLD + (255,), width=3)
        panel(img, [x + 60, y, x + 60 + (w + 56) * g, y + 84], (12, 13, 16), GOLD, radius=4, blur=10)
        if g > 0.7: glow_text(img, text, x + 88, y + 42, f, INK, 0, (g - 0.7) / 0.3, "l")
    elif look == "slash":
        x, y = 90 - (1 - g) * 500, 150; d.polygon([(x, y), (x + w + 90, y), (x + w + 60, y + 88), (x - 30, y + 88)], fill=GOLD + (255,)); glow_text(img, text, x + 34, y + 44, f, (14, 14, 16), 0, 1, "l")
    elif look == "ribbon":
        y = H - 268; bw = (w + 120) * g; d.rectangle([W / 2 - bw / 2, y, W / 2 + bw / 2, y + 84], fill=(245, 245, 240, 255)); d.rectangle([W / 2 - bw / 2, y + 80, W / 2 + bw / 2, y + 84], fill=HOT + (255,))
        if g > 0.7: glow_text(img, text, W / 2, y + 42, f, (14, 14, 16), 0, (g - 0.7) / 0.3)
    else:
        x, y = W - 96 - w - 70 + (1 - g) * 500, H - 300; d.rectangle([x, y, x + w + 70, y + 84], fill=(14, 14, 16, 235)); d.rectangle([x + w + 62, y, x + w + 70, y + 84], fill=GOLD + (255,)); glow_text(img, text, x + 28, y + 42, f, INK, 0, 1, "l")

def alert_tag(img, text, cx, cy, p):
    """경고: 빨간 고리가 번지며 찍힌다."""
    if p <= 0: return
    f = fit_face("HAN", 58, text, 700); d = ImageDraw.Draw(img); w = d.textlength(text, font=f); x = W - 96 - w - 60; y = 130; sc = 1 + 0.2 * (1 - smooth(p / 0.1))
    ping(img, x + w / 2 + 30, y + 50, p / 0.4, HOT, 60, 220); bw, bh = (w + 60) * sc, 100 * sc
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

