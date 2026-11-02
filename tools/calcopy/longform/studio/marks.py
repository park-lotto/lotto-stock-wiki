# 화면 고정 표시와 태그
from .settings import *
def mark_icon(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); s = size
    d.rectangle([s * .06, s * .06, s * .94, s * .94], fill=C["sub_bar"])
    d.polygon([(s * .38, s * .28), (s * .38, s * .72), (s * .74, s * .5)], fill=(255, 255, 255, 255))
    return im

_ui = {}
def paint_corners(chapter, bright):
    """채널 패와 챕터 태그. logo_side 로 좌우를 바꾼다(캡슐·구분선 없음)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); ac = C["sub_bar"]; right = CFG.get("logo_side", "right") == "right"
    f = face("GM", 34); n = CFG["channel_name"]; nw = width_of(d, n, f); x0 = W - 48 - nw - 44 if right else 48
    d.rectangle([x0, 36, x0 + nw + 44, 96], fill=ac); d.text((x0 + 22, 46), n, font=f, fill=(255, 255, 255, 255))
    if chapter and chapter not in CFG.get("no_capsule", []):
        tag = chapter.split(" : ")[-1]; fc = face("GM", 28); cw = width_of(d, tag, fc); xc = 48 if right else W - 48 - cw - 44
        d.rectangle([xc, 36, xc + cw + 44, 90], fill=(20, 24, 28, 225)); d.rectangle([xc, 84, xc + cw + 44, 90], fill=ac)
        d.text((xc + 22, 47), tag, font=fc, fill=(255, 255, 255, 255))
    return im

def corner_marks(chapter, bright):
    k = (chapter, bright)
    if k not in _ui: _ui[k] = paint_corners(chapter, bright)
    return _ui[k]

NUMTOK = re.compile(r"\d[\d,.]*(?:%|만|천|억|조|원|달러|배|명|개월|개|년|월|분기)*(?: \d천)?(?: ?(?:원|달러|명))?")
def caption_bar(frame, text, p):
    """결 b: 아래 띠 + 흰 글자 + 숫자만 노란색. 글자는 0.12초 동안 살짝 올라온다."""
    d = ImageDraw.Draw(frame, "RGBA"); f = face("GM", 44); w = width_of(d, text, f)
    d.rectangle([0, H - 100, W, H], fill=C["sub_box"]); d.rectangle([0, H - 106, W, H - 100], fill=C["sub_bar"])
    x = (W - w) // 2; y = H - 76 + int((1 - smooth(p / 0.12)) * 16); i = 0
    for m in list(NUMTOK.finditer(text)) + [None]:
        a = text[i: m.start() if m else len(text)]
        if a: d.text((x, y), a, font=f, fill=(255, 255, 255, 255)); x += d.textlength(a, font=f)
        if m: d.text((x, y), m[0], font=f, fill=C["yellow"] + (255,)); x += d.textlength(m[0], font=f); i = m.end()

_src = {}
def source_line(src, bright):
    k = (src, bright)
    if k in _src: return _src[k]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if src:
        d = ImageDraw.Draw(im); f = face("SB", 26); s = src if src == "AI 생성" else f"출처 : {src}"
        w = width_of(d, s, f); col = (51, 51, 51, 255) if bright else (229, 229, 229, 255)
        x_, y_ = 48, H - 148   # 자막 띠 위 왼쪽
        d.text((x_, y_), s, font=f, fill=col, stroke_width=0 if bright else 2, stroke_fill=(0, 0, 0, 200))
    _src[k] = im; return im

def note_tag(img, text, cx, cy, p):
    if p <= 0: return
    f = face("GM", 40); d = ImageDraw.Draw(img); w = width_of(d, text, f); x = 64 - (1 - smooth(p / 0.2)) * (w + 140); y = H - 262
    d.rectangle([x, y, x + w + 58, y + 78], fill=(255, 255, 255, 245)); d.rectangle([x, y, x + 12, y + 78], fill=C["sub_bar"])
    d.text((x + 34, y + 19), text, font=f, fill=(17, 24, 28, 255))

def alert_tag(img, text, cx, cy, p):
    if p <= 0: return
    f = face("GM", 54); d = ImageDraw.Draw(img); w = width_of(d, text, f); x = W - 64 - w - 56 + (1 - smooth(p / 0.16)) * (w + 120); y = 128
    d.rectangle([x, y, x + w + 56, y + 92], fill=C["wine"] + (245,)); d.text((x + 28, y + 19), text, font=f, fill=(255, 255, 255, 255))

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
    dl.rounded_rectangle([x - 50, H // 2 - 84, x + w + 50, H // 2 + 56], radius=20, fill=(0, 0, 0, int(a * 0.66)))
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

