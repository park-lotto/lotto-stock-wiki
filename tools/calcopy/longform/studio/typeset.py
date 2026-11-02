# 문장 카드
from .settings import *
from .timing import *
from .marks import *
from .motion import *
TYPO_BG = {"black": (12, 24, 28), "ivory": (240, 244, 243), "lime": (72, 226, 196), "pink": (255, 112, 80), "blue": (18, 160, 142)}
TYPO_INK = {"black": (245, 245, 240), "ivory": (17, 17, 17), "lime": (17, 17, 17), "pink": (17, 17, 17), "blue": (255, 255, 255)}
if CFG.get("typo_colors"):   # 결 손잡이 — 편 config 로 타이포 카드 색을 바꾼다
    TYPO_BG.update({k: tuple(v) for k, v in CFG["typo_colors"].items()})
    ACCENTS[:] = [TYPO_BG["lime"], TYPO_BG["pink"], tuple(C["yellow"]), TYPO_BG["blue"]]
def type_items(s, tl):
    """items: (문장, 단어, 글자, 바탕, 위치 L/C/R, 크기 S0/S1/S2, 등장 stamp/whip, [박스색])"""
    out = []
    for j, it in enumerate(s["items"]):
        t = max(s["t0"], at_time(tl, (it[0], it[1])) - 0.05) if j else s["t0"]
        out.append(dict(t=t, text=it[2], bg=it[3], pos=it[4], size=it[5], enter=it[6], box=(it[7] if len(it) > 7 else None), mode=s.get("modes", ["rise"] * (j + 1))[j]))
    return out
def type_current(s, lt, tl):
    cs = type_items(s, tl); T = s["t0"] + lt; cur = cs[0]
    for c in cs:
        if c["t"] <= T: cur = c
    return cur, T - cur["t"]
def type_reveal(c, p):
    """결 b: 글자가 차례로 아래에서 올라오고, 강조는 색 글자 + 밑줄이 그어진다."""
    bg = TYPO_BG[c["bg"]]; mode = c.get("mode", "rise")
    img = night().convert("RGBA") if c["bg"] == "black" else Image.new("RGBA", (W, H), bg + (255,)); ink = TYPO_INK[c["bg"]]; d = ImageDraw.Draw(img)
    rows = [read_marks(r) for r in c["text"].split("/")]; size = {"S0": 300, "S1": 190, "S2": 130}[c["size"]]
    while True:
        f = face("GM", size); rw = [sum(width_of(d, t, f) for t, _ in r) for r in rows]
        if max(rw) <= W * 0.84 or size < 60: break
        size = int(size * 0.92)
    lh = int(size * 1.3); y = (H - lh * len(rows)) / 2; n = 0
    for r, w in zip(rows, rw):
        x = {"L": W * 0.08, "C": (W - w) / 2, "R": W * 0.92 - w}[c["pos"]]
        for t, k in r:
            col = (TYPO_BG[c["box"]] if c.get("box") else C["sub_bar"][:3]) if k == "box" else ink
            if k == "box" and c["bg"] != "black": col = (12, 14, 18)
            base = x; tb = d.textbbox((0, 0), "가", font=f)
            for i, ch in enumerate(t):
                g, dx, dy = letter_move(mode, p, n, i, len(t), size); n += 1; cx = base + d.textlength(t[:i], font=f)
                if g > 0: d.text((cx + dx, y + (lh - tb[3] - tb[1]) / 2 + dy), ch, font=f, fill=tuple(col) + (int(255 * g),))
            ww = width_of(d, t, f)
            if k:
                g = smooth((p - n * 0.016 - 0.03) / 0.14); yy = y + lh * (0.93 if k == "box" else 0.52)
                if g > 0: d.rectangle([base, yy, base + ww * g, yy + max(8, size // 14)], fill=tuple(col if k == "box" else C["wine"]) + (255,))
            x += ww
        y += lh
    if mode == "slam" and p < 0.14:
        z = 1 + 0.9 * (1 - smooth(p / 0.14)); w, h = W / z, H / z; l, t = (W - w) / 2, (H - h) / 2; img = img.transform((W, H), Image.EXTENT, (l, t, l + w, t + h), Image.BILINEAR)
    return img

def letter_move(mode, p, n, i, count, size):
    """글자 하나의 (투명도, 가로, 세로). rise·drop·spread·type·wipe·slam."""
    if mode == "slam": return 1.0, 0, 0
    if mode == "type": return (1.0 if p >= n * 0.03 else 0.0), 0, 0
    if mode == "wipe": return (1.0 if p >= n * 0.012 else 0.0), 0, 0
    g = smooth((p - n * 0.016) / 0.14)
    if mode == "drop": return g, 0, -(1 - g) * size * 0.6
    if mode == "spread": g = smooth(p / 0.18); return g, (i - count / 2) * (1 - g) * size * 0.5, 0
    return g, 0, (1 - g) * size * 0.55

def card_type(s, lt, T, tl):
    c, p = type_current(s, lt, tl)
    return type_reveal(c, p)

def type_is_light(s, lt, tl):
    c, _ = type_current(s, lt, tl); return c["bg"] != "black"

