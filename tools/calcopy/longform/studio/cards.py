# 샷 종류별 화면
from .settings import *
from .timing import *
from .footage import *
from .marks import *
from .motion import *
from .stage import *
def is_bright(s): return False
def has_ai_picture(s):
    n = s.get("img", s["s"][0])
    return os.path.exists(E("material", "img", f"s{n:03d}.png")) and not os.path.exists(E("material", "video", f"s{n:03d}.mp4")) and not os.path.exists(E("material", "video", f"s{n:03d}.jpg"))
def shot_src(s):
    if s["type"] == "article":
        m = load_article(s["article"])[1]; return s.get("src") or f'{m.get("media", "")} {m.get("date", "").replace("-", ".")}'
    ai = has_ai_picture(s) and s["type"] in ("quote", "bignum", "labels", "ai", "stock")
    if "src" in s: return s["src"] + (", AI 생성" if ai else "")
    return "AI 생성" if ai or s["type"] == "ai" else ""

def card_photo(s, lt, T, tl):
    i = max(j for j, b in enumerate(s["beats"]) if lt >= b[0]); a, name, move, _ = s["beats"][i]; local = lt - a
    img = stage(name, s, picture(s, lt, T, i, move), smooth(local / 0.2), lt).convert("RGBA")
    if s.get("bubble"):
        note_tag(img, s["bubble"][1], 0, 0, lt - (bubble_time(tl, s) - s["t0"]), s.get("note", "leader"))
    if s.get("stamp"):
        alert_tag(img, s["stamp"][1], 0, 0, lt - (word_time(tl, s["stamp"][0], s["stamp"][1]) - s["t0"]))
    if s.get("big"):
        big_note(img, s["big"][1], lt - (line_time(tl, s["big"][0]) - s["t0"]))
    return img

def card_quote(s, lt, T, tl):
    img = soft_back(s); look = s.get("look", "center"); hl = s.get("hl", []); f = face("SERIF", 62); fh = face("HAN", 66)
    d = ImageDraw.Draw(img); rows = wrapped_lines(d, s["text"], hl, f, W - 400); lh = 112
    rw = [sum(d.textlength(p, font=fh if h else f) for p, h in r) for r in rows]; y = (H - lh * len(rows)) // 2 - 10
    if look == "rail":
        d.rectangle([150, y - 20, 160, y - 20 + (lh * len(rows) + 40) * smooth(lt / 0.2)], fill=GOLD)
    else: glow_text(img, "\u201c", 150, y - 30, face("AN", 220), GOLD, 22, smooth(lt / 0.2))
    total = sum(len(p) for r in rows for p, _ in r); shown = int(total * min(1.0, lt / max(1.0, min(4.0, T * 0.5)))); seen = 0
    for r, w in zip(rows, rw):
        x = 210 if look == "rail" else (W - w) / 2
        for p, h in r:
            vis = p[: max(0, min(len(p), shown - seen))]; seen += len(p); fi = fh if h else f
            if vis:
                glow_text(img, vis, x, y + lh / 2, fi, GOLD if h else INK, 12 if h else 0, anchor="l")
                if h: ImageDraw.Draw(img).rectangle([x, y + lh - 16, x + d.textlength(vis, font=fi), y + lh - 10], fill=GOLD)
            x += d.textlength(p, font=fi)
        y += lh
    return img

def number_landing(tl, s):
    return (word_time(tl, s.get("count_line", s["s"][0]), s["count_word"]) + 0.2) if s.get("count_word") else s["t0"] + 1.3
def number_text(s, v, done):
    if s["fmt"] == "joeok":
        iv = int(round(v)); txt = f"{iv // 10000}조 {iv % 10000:,}억 유로" if iv >= 10000 else f"{iv:,}억 유로"
    else: txt = s["fmt"].format(v)
    return s.get("fmt_final", txt) if done else txt
def card_number(s, lt, T, tl):
    look = s.get("look", "orbit"); end_t = number_landing(tl, s) - s["t0"]; st_t = max(0.1, end_t - 2.2)
    pr = smooth((lt - st_t) / max(0.3, end_t - st_t)); txt = number_text(s, s["v0"] + (s["v1"] - s["v0"]) * pr, pr >= 1)
    since = lt - end_t; cx, cy = W // 2, H // 2 - 20; bump = max(0.0, 1 - since / 0.2) if since >= 0 else 0.0; ink = GOLD if pr >= 1 else INK; lab_y, sub_y, ax = cy - 190, cy + 186, "c"
    if look == "flood":
        img = soft_back(s); level = int(H * (1 - pr)); d = ImageDraw.Draw(img); d.rectangle([0, level, W, H], fill=GOLD); ink = (14, 14, 16) if pr > 0.55 else INK
        d.rectangle([0, level - 8, W, level], fill=(255, 255, 255))
    else: img = soft_back(s) if look in ("orbit", "slam") else dark(s.get("tint", "base"), lt)
    if look == "orbit":
        orbit(img, cx, cy, 340, lt, GOLD, 0.55); gather(img, cx, cy, (lt - (end_t - 0.5)) / 0.5); ping(img, cx, cy, since / 0.5)
    elif look == "side":
        cx = 150; ax = "l"; d = ImageDraw.Draw(img); d.rectangle([96, cy - 200, 110, cy - 200 + 400 * pr], fill=GOLD); orbit(img, 1580, cy, 220, lt, GOLD); orbit(img, 1580, cy, 140, -lt * 1.5, HOT, 1, 1); dot_globe(img, 1580, cy, 90, lt, a=0.8)
    elif look == "gauge":
        d = ImageDraw.Draw(img); d.rounded_rectangle([260, cy + 130, W - 260, cy + 146], radius=8, fill=(34, 38, 46)); d.rounded_rectangle([260, cy + 130, 260 + (W - 520) * pr, cy + 146], radius=8, fill=GOLD); sub_y = cy + 220
        for i in range(21): xx = 260 + (W - 520) * i / 20; d.line([(xx, cy + 156), (xx, cy + (172 if i % 5 == 0 else 164))], fill=DIM, width=2)
    elif look == "slam":
        ping(img, cx, cy, since / 0.4, HOT, 100, 620); ping(img, cx, cy, (since - 0.08) / 0.4, GOLD, 100, 520)
    elif look == "echo":
        for i in range(5, 0, -1):
            y_ = cy + i * 44 * (1 - pr * 0.4); glow_text(img, txt, cx, y_, big_face(txt, 230, W - 260), GOLD, 0, 0.09 * (6 - i))
    size = int(230 * (1 + 0.1 * bump)) if look != "slam" else int(230 * (1 + 1.2 * (1 - pr)))
    glow_text(img, txt, cx, cy, big_face(txt, size, (W - 260) if look != "side" else 1120), ink, 34 if pr >= 1 and look != "flood" else 8 if look != "flood" else 0, 1, ax)
    if s.get("label"): glow_text(img, s["label"], cx, lab_y, face("B", 44), (14, 14, 16) if look == "flood" and pr > 0.75 else DIM, 0, smooth(lt / 0.2), ax)
    sub_t = (at_time(tl, s["sub_word"]) - s["t0"]) if s.get("sub_word") else end_t + 0.3
    if s.get("sub") and lt > sub_t:
        g = smooth((lt - sub_t) / 0.15); glow_text(img, s["sub"], cx, sub_y + (1 - g) * 16, face("XB", 52), (14, 14, 16) if look == "flood" else INK, 0, g, ax)
    return img

def chart_title(img, title, sub):
    glow_text(img, title, 96, 164, face("HAN", 60), INK, 0, anchor="l")
    if sub: spaced(img, sub, 98, 214, 26, DIM, 2)
    ImageDraw.Draw(img).rectangle([96, 256, 216, 262], fill=GOLD)

def bar_times(s, tl):
    out = []
    for lab, v, disp in s["items"]:
        ft = find_said(tl, s, first_num(disp).rstrip(".,"))
        if ft is None: ft = find_said(tl, s, lab.split()[0])
        out.append(max(0.1, ft - s["t0"] - 0.25) if ft is not None else ((out[-1] + 0.6) if out else 0.15))
    if out: out[0] = min(out[0], 0.5)   # 첫 항목은 말을 기다리지 않는다(빈 화면으로 늘어지지 않게)
    return out

def hidden_value(img, s, j, lt, tl):
    return s.get("reveal") and j == s.get("hl", -1) and lt < reveal_time(tl, s) - s["t0"] - 0.3

def pillars(img, s, lt, tl, mark="bar"):
    """세로 비교: 빛기둥이 말하는 순간 차오른다."""
    items = s["items"]; n = len(items); hl = s.get("hl", -1); vals = [it[1] for it in items] + ([s["ref"][0]] if s.get("ref") else [])
    top = max(max(vals), 1) * 1.12; low = min(min(vals), 0) * 1.12; x0, x1, by, ty = 240, W - 240, 820, 330
    if low < 0: by, ty = 600, 330
    scale = (by - ty) / (top if low >= 0 else top - low); slot = (x1 - x0) / n; bw = int(min(150, slot * 0.42)); d = ImageDraw.Draw(img)
    d.line([(x0 - 40, by), (x1 + 40, by)], fill=LINE, width=3); tops = []
    for j, (st, it) in enumerate(zip(bar_times(s, tl), items)):
        lab, v, disp = it; g = smooth((lt - st) / 0.32); cx = x0 + slot * (j + 0.5); col = GOLD if j == hl else (HOT if v < 0 else SOFT); hp = abs(v) * scale * g
        glow_text(img, lab, cx, by + (42 if v >= 0 else -42), face("B", 34), INK if j == hl else DIM)
        if hp < 1: continue
        if g >= 1 and v > 0: tops.append((cx, by - hp - 6))
        if mark == "lollipop":
            head = by - hp if v >= 0 else by + hp; d.line([(cx, by), (cx, head)], fill=col + (255,), width=8); panel(img, [cx - 34, head - 34, cx + 34, head + 34], col, col, radius=34, blur=12); d = ImageDraw.Draw(img)
        elif mark == "blocks":
            cells = max(1, int(hp // 34))
            for c_ in range(cells): d.rectangle([cx - bw / 2, by - 30 - c_ * 34, cx + bw / 2, by - 4 - c_ * 34], fill=col + (int(255 - 110 * c_ / max(cells, 1)),))
        else:
            sp = light_pillar(hp, bw, col); sx = int(cx - sp.width / 2)
            if v >= 0: img.alpha_composite(sp, (sx, int(by - sp.height)))
            else: img.alpha_composite(sp.transpose(Image.FLIP_TOP_BOTTOM), (sx, int(by)))
        ty_ = by - hp - 58 if v >= 0 else by + hp + 44
        if g > 0.5:
            f = big_face(disp, 76 if j == hl else 56, slot - 14); blurred = hidden_value(img, s, j, lt, tl)
            if blurred: panel(img, [cx - 96, ty_ - 42, cx + 96, ty_ + 42], (40, 44, 54), LINE); glow_text(img, "?", cx, ty_, face("AN", 62), GOLD, 10)
            else: glow_text(img, disp, cx, ty_, f, col if j == hl else INK, 18 if j == hl else 0, smooth((g - 0.5) / 0.3))
    if n >= 3 and len(tops) >= 2:   # 다 찬 막대의 머리를 잇는 추세선
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay); dl.line(tops, fill=(255, 255, 255, 235), width=4, joint="curve")
        for x, y in tops: dl.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 255, 255, 255))
        img.alpha_composite(lay)
    return scale, by, x0, x1

def rails(img, s, lt, tl):
    """가로 비교: 레일 위로 빛 막대가 달린다."""
    items = s["items"]; hl = s.get("hl", -1); vals = [it[1] for it in items] + ([s["ref"][0]] if s.get("ref") else []); top = max(vals) * 1.12
    x0, x1 = 560, W - 260; n = len(items); slot = min(132, 530 / n); y0 = 300 + (530 - slot * n) / 2; bh = int(slot * 0.5); d = ImageDraw.Draw(img)
    for j, (st, it) in enumerate(zip(bar_times(s, tl), items)):
        lab, v, disp = it; g = smooth((lt - st) / 0.32); cy = y0 + slot * (j + 0.5); wp = (x1 - x0) * v / top * g; col = GOLD if j == hl else SOFT
        glow_text(img, lab, x0 - 32, cy, face("B", 36), INK if j == hl else DIM, anchor="r")
        d.rounded_rectangle([x0, cy - 3, x1, cy + 3], radius=3, fill=(34, 38, 46))
        if wp > 2:
            if j == hl: panel(img, [x0, cy - bh / 2, x0 + wp, cy + bh / 2], col, col, blur=14, radius=6)
            else: d.rounded_rectangle([x0, cy - bh / 2, x0 + wp, cy + bh / 2], radius=6, fill=col)
            d = ImageDraw.Draw(img); d.ellipse([x0 + wp - 12, cy - 12, x0 + wp + 12, cy + 12], fill=(255, 255, 255))
        if g > 0.5:
            if hidden_value(img, s, j, lt, tl): glow_text(img, "?", x0 + wp + 46, cy, face("AN", 56), GOLD, 10)
            else: glow_text(img, disp, x0 + wp + 28, cy, big_face(disp, 56, 380), col if j == hl else INK, 14 if j == hl else 0, anchor="l")
    return (x1 - x0) / top, x0, y0, slot * n

def rings(img, s, lt, tl):
    """겹친 고리: 값만큼 호가 돈다."""
    items = s["items"]; hl = s.get("hl", -1); top = max(it[1] for it in items) * 1.05; cx, cy = 640, 570; lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for j, (st, it) in enumerate(zip(bar_times(s, tl), items)):
        lab, v, disp = it; g = smooth((lt - st) / 0.4); r = 270 - j * 66; col = GOLD if j == hl else SOFT
        ImageDraw.Draw(img).ellipse([cx - r, cy - r, cx + r, cy + r], outline=(34, 38, 46), width=38)
        if g > 0: d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 330 * v / top * g, fill=col + (255,), width=38)
        y = 420 + j * 130; glow_text(img, lab, 1090, y, face("B", 36), INK if j == hl else DIM, 0, 1, "l")
        if g > 0.5:
            if hidden_value(img, s, j, lt, tl): glow_text(img, "?", 1090, y + 56, face("AN", 56), GOLD, 10, 1, "l")
            else: glow_text(img, disp, 1090, y + 56, big_face(disp, 64, 640), col if j == hl else INK, 14 if j == hl else 0, 1, "l")
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(10))); img.alpha_composite(lay)

def bubbles(img, s, lt, tl):
    """값의 넓이만큼 커지는 원."""
    items = s["items"]; hl = s.get("hl", -1); top = max(it[1] for it in items); n = len(items); slot = (W - 300) / n
    for j, (st, it) in enumerate(zip(bar_times(s, tl), items)):
        lab, v, disp = it; g = smooth((lt - st) / 0.3); cx = 150 + slot * (j + 0.5); cy = 560; r = 240 * math.sqrt(max(v, 0) / top) * g; col = GOLD if j == hl else SOFT
        glow_text(img, lab, cx, 850, face("B", 34), INK if j == hl else DIM)
        if r > 2: panel(img, [cx - r, cy - r, cx + r, cy + r], col, col, radius=int(r), blur=16)
        if g > 0.6:
            if hidden_value(img, s, j, lt, tl): glow_text(img, "?", cx, cy, face("AN", 80), (14, 14, 16))
            else: glow_text(img, disp, cx, cy if r > 110 else cy - r - 46, big_face(disp, 62, max(r * 1.8, 260)), (14, 14, 16) if r > 110 else INK)

def card_bars(s, lt, T, tl):
    img = dark(s.get("tint", "base"), lt); chart_title(img, s["title"], s.get("sub")); d = ImageDraw.Draw(img); look = s.get("look", "rail" if s.get("orient") == "h" else "bar")
    for a, later, _ in s.get("swaps", []):
        if lt >= a: look = later
    if look == "rings": rings(img, s, lt, tl)
    elif look == "bubble": bubbles(img, s, lt, tl)
    elif look == "rail":
        sc, x0, y0, hh = rails(img, s, lt, tl)
        if s.get("ref"):
            rv, rl = s["ref"]; rx = x0 + rv * sc
            for yy in range(int(y0 - 20), int(y0 + hh + 20), 26): d.line([(rx, yy), (rx, yy + 14)], fill=HOT + (210,), width=3)
            glow_text(img, rl, rx, y0 - 44, face("B", 30), HOT)
    else:
        sc, by, x0, x1 = pillars(img, s, lt, tl, look)
        if s.get("ref") and (not s.get("ref_at") or lt >= line_time(tl, s["ref_at"]) - s["t0"]):
            rv, rl = s["ref"]; ry = by - rv * sc
            for xx in range(int(x0 - 40), int(x1 + 40), 28): d.line([(xx, ry), (xx + 16, ry)], fill=HOT + (210,), width=3)
            glow_text(img, rl, x1 + 50, ry - 26, face("B", 30), HOT, anchor="r")
    if s.get("badge"):
        bt = (word_time(tl, s["badge"][0], s["badge"][2]) if len(s["badge"]) > 2 else line_time(tl, s["badge"][0])) - s["t0"]
        if lt > bt: alert_tag(img, s["badge"][1], 0, 0, lt - bt)
    if s.get("stamp"):
        alert_tag(img, s["stamp"][1], 0, 0, lt - (word_time(tl, s["stamp"][0], s["stamp"][1]) - s["t0"]))
    return img

def card_table(s, lt, T, tl):
    img = dark(s.get("tint", "base"), lt); chart_title(img, s["title"], None); d = ImageDraw.Draw(img); cols, rows = s["cols"], s["rows"]; fr = face("SB", 36)
    widths = [max(width_of(d, str(r[c]), fr) for r in rows + [cols]) + 90 for c in range(len(cols))]; sc = min(1.0, (W - 240) / sum(widths)); widths = [w * sc for w in widths]
    tot = sum(widths); x0 = (W - tot) / 2; y = 300; rh = 84; rev = (reveal_time(tl, s) - s["t0"]) if s.get("reveal") else 0
    xx = x0
    for c, w in zip(cols, widths): spaced(img, c, xx + 24, y + 26, 28, GOLD, 3); xx += w
    d.line([(x0, y + rh - 8), (x0 + tot, y + rh - 8)], fill=GOLD + (255,), width=3); y += rh
    for ri, r in enumerate(rows):
        hl = ri in s.get("hl_rows", []); at = max(0.2, at_time(tl, s["row_at"][ri]) - s["t0"] - 0.2) if s.get("row_at") and ri < len(s["row_at"]) else 0.2 + ri * 0.18
        q = smooth((lt - at) / 0.3)
        if q > 0:
            ox = (1 - q) * 80; panel(img, [x0 + ox, y, x0 + tot + ox, y + rh - 10], (30, 28, 18) if hl else (18, 20, 26), GOLD if hl else None, a=int(255 * q), blur=12 if hl else 0)
            xx = x0 + ox; hide = s.get("reveal") and lt < rev and (hl or (not s.get("hl_rows") and ri == len(rows) - 1))
            for c, w in enumerate(widths):
                glow_text(img, "●●●" if hide and c else str(r[c]), xx + 24, y + (rh - 10) / 2, face("XB" if hl or c == 0 else "SB", 36), GOLD if hl else INK, 0, q, "l"); xx += w
        y += rh
    return img

def label_time(tl, it, j):
    return word_time(tl, it[0], it[2]) if len(it) > 2 else line_time(tl, it[0]) + j * 0.35
def label_shown(tl, s, j):
    """화면에 나오는 순간. 첫 항목은 샷 시작 뒤 0.3초를 넘기지 않는다."""
    at = label_time(tl, s["items"][j], j) - s["t0"]
    return min(at, 0.3) if j == 0 else at
def chips_chain(img, s, lt, tl):
    """말하는 순간 블록이 이어 붙는다."""
    items = s["items"]; n = len(items); d = ImageDraw.Draw(img); step = min(176, 640 / max(n, 1)); f = fit_face("HAN", int(min(76, step * 0.48)), max((it[1] for it in items), key=len), 560 if n > 2 else 760)
    ws = [d.textlength(it[1], font=f) + 110 for it in items]; gap = 70; row = sum(ws) + gap * (n - 1) <= W - 180; pts = []
    if row:
        x = (W - sum(ws) - gap * (n - 1)) / 2
        for j, w in enumerate(ws): pts.append((x + w / 2, H / 2 - 20 + (-1) ** j * 34)); x += w + gap
    else: pts = [(W / 2 + (-1) ** j * 120, H / 2 - 30 + (j - (n - 1) / 2) * step) for j in range(n)]
    for j in range(1, n):
        g = smooth((lt - label_shown(tl, s, j)) / 0.12); a, b = pts[j - 1], pts[j]
        if g > 0: d.line([a, (a[0] + (b[0] - a[0]) * g, a[1] + (b[1] - a[1]) * g)], fill=GOLD + (255,), width=3)
    for j, (it, (cx, cy), w) in enumerate(zip(items, pts, ws)):
        p = lt - label_shown(tl, s, j)
        if p <= 0: continue
        sc = 1 + 0.16 * (1 - smooth(p / 0.12)); col = INK if it[1].strip().lower() == "vs" else (GOLD, HOT)[j % 2]; hw, hh = w * sc / 2, min(72, step * 0.4) * sc
        panel(img, [cx - hw, cy - hh, cx + hw, cy + hh], (14, 14, 16), col, blur=12, width=3, radius=6); glow_text(img, it[1], cx, cy, f, INK)

def chips_list(img, s, lt, tl):
    """왼쪽 정렬 목록에 체크가 찍힌다."""
    items = s["items"]; n = len(items); step = min(150, 620 / max(n, 1)); y0 = H / 2 - 40 - (n - 1) / 2 * step; f = fit_face("HAN", int(min(70, step * 0.5)), max((it[1] for it in items), key=len), 1200)
    for j, it in enumerate(items):
        p = lt - label_shown(tl, s, j); y = y0 + j * step; d = ImageDraw.Draw(img)
        d.rectangle([300, y - 30, 360, y + 30], outline=LINE, width=3)
        if p <= 0: continue
        g = smooth(p / 0.12); d.line([(312, y), (326, y + 16)], fill=GOLD + (255,), width=7)
        if g > 0.5: d.line([(326, y + 16), (326 + 26 * (g - 0.5) * 2, y + 16 - 36 * (g - 0.5) * 2)], fill=GOLD + (255,), width=7)
        glow_text(img, it[1], 400 + (1 - g) * 60, y, f, INK, 0, g, "l")

def chips_flow(img, s, lt, tl):
    """화살표로 이어지는 원 노드."""
    items = s["items"]; n = len(items); slot = (W - 240) / n; y = H / 2 - 30; f = fit_face("HAN", 60, max((it[1] for it in items), key=len), min(slot * 0.42, 150) * 1.75); d = ImageDraw.Draw(img)
    for j, it in enumerate(items):
        p = lt - label_shown(tl, s, j); cx = 120 + slot * (j + 0.5); r = min(slot * 0.42, 150)
        if p <= 0: d.ellipse([cx - r, y - r, cx + r, y + r], outline=LINE, width=3); continue
        g = smooth(p / 0.12); col = (GOLD, HOT)[j % 2]; ping(img, cx, y, p / 0.35, col, r * 0.67, r * 1.1); panel(img, [cx - r, y - r, cx + r, y + r], (14, 14, 16), col, width=4, radius=int(r), blur=12, a=int(255 * g)); glow_text(img, it[1], cx, y, f, INK, 0, g); d = ImageDraw.Draw(img)
        if j: px = cx - slot + r + 8; d.line([(px, y), (px + (slot - 2 * r - 16) * g, y)], fill=col + (255,), width=5)

def card_chips(s, lt, T, tl):
    img = soft_back(s); {"list": chips_list, "flow": chips_flow}.get(s.get("look"), chips_chain)(img, s, lt, tl); return img

def split_label(t):
    a = t.split(": "); return (a[0], a[1]) if len(a) == 2 else ("", t)

def card_versus(s, lt, T, tl):
    img = dark(s.get("tint", "base"), lt); ats = [at_time(tl, a) - s["t0"] for a in s["at"]] if s.get("at") else [0.15, 0.5, 1.4]; ats[0] = min(ats[0], 0.3); look = s.get("look", "panels"); d = ImageDraw.Draw(img); ps = [smooth((lt - a) / 0.18) for a in ats[:2]]
    for a, later, _ in s.get("swaps", []):
        if lt >= a: look = later
    sides = [(*split_label(s["left"]), GOLD), (*split_label(s["right"]), HOT)]
    if look == "diagonal":
        for j, (tag, txt, col) in enumerate(sides):
            if ps[j] <= 0: continue
            tint = tuple(int(c * 0.3) for c in col); off = (1 - ps[j]) * 700 * (-1 if j == 0 else 1)
            pts = [(off, 0), (W * 0.58 + off, 0), (W * 0.42 + off, H), (off, H)] if j == 0 else [(W * 0.58 + off, 0), (W + off, 0), (W + off, H), (W * 0.42 + off, H)]
            d.polygon(pts, fill=tint + (255,)); cx = W * 0.25 + off if j == 0 else W * 0.75 + off; spaced(img, tag, cx - 120, 390, 30, col, 6); glow_text(img, txt, cx, 500, fit_face("HAN", 84, txt, 720), INK); d = ImageDraw.Draw(img)
        if lt > ats[1]: d.line([(W * 0.58, 0), (W * 0.42, H)], fill=(255, 255, 255, 255), width=6)
    elif look == "stacked":
        for j, (tag, txt, col) in enumerate(sides):
            if ps[j] <= 0: continue
            y0 = 200 + j * 300; wd = (W - 300) * ps[j]; x0 = 150 if j == 0 else W - 150 - wd; panel(img, [x0, y0, x0 + wd, y0 + 260], tuple(int(c * 0.22) for c in col), col, width=3, radius=6, blur=12)
            if ps[j] > 0.7: spaced(img, tag, 200, y0 + 28, 28, col, 6); glow_text(img, txt, W / 2, y0 + 140, fit_face("HAN", 84, txt, 1300), INK)
    else:
        for j, (tag, txt, col) in enumerate(sides):
            if ps[j] <= 0: continue
            sign = -1 if j == 0 else 1; cx = W / 2 + sign * (440 + (1 - ps[j]) * 260); panel(img, [cx - 350, 340, cx + 350, 660], tuple(int(c * 0.2) for c in col), col, a=int(255 * ps[j]), width=3, blur=16, radius=8)
            if tag: spaced(img, tag, cx - 300, 382, 30, col, 6, int(255 * ps[j]))
            glow_text(img, txt, cx, 512, fit_face("HAN", 72, txt, 620), INK, 0, ps[j])
        if lt > ats[1]:
            ping(img, W / 2, 500, (lt - ats[1]) / 0.4, INK, 80, 300); ImageDraw.Draw(img).ellipse([W / 2 - 84, 416, W / 2 + 84, 584], fill=NIGHT + (255,), outline=INK + (255,), width=4); glow_text(img, "VS", W / 2, 500, face("AN", 92), INK, 10)
    if s.get("title") and look != "diagonal": glow_text(img, s["title"], W / 2, 150, face("HAN", 60), INK)
    if s.get("sub") and lt > ats[2]: glow_text(img, s["sub"], W / 2, 800 if look != "diagonal" else 700, face("B", 44), INK if look == "diagonal" else DIM, 0, smooth((lt - ats[2]) / 0.2))
    return img

def card_loop(s, lt, T, tl):
    img = dark(s.get("tint", "base"), lt)
    if s.get("title"): chart_title(img, s["title"], None)
    cx, cy, R = W / 2, H / 2 + 40, 290; n = len(s["items"]); orbit(img, cx, cy, R, lt, GOLD, 1.0, 2)
    now = int(lt / 0.9) % n if lt > 0.3 else -1
    for j, t in enumerate(s["items"]):
        a = -math.pi / 2 + j * 6.283 / n; x, y = cx + R * math.cos(a), cy + R * math.sin(a); q = smooth((lt - 0.1 - j * 0.2) / 0.3)
        if q <= 0: continue
        on = j == now; panel(img, [x - 130, y - 60, x + 130, y + 60], (40, 34, 16) if on else (18, 20, 26), GOLD if on else LINE, a=int(255 * q), blur=12 if on else 0)
        glow_text(img, t, x, y, fit_face("HAN", 50, t, 230), INK, 0, q)
    return img

def card_grade(s, lt, T, tl):
    img = dark(s.get("tint", "base"), lt); chart_title(img, s.get("title", "신용등급"), None); ats = [at_time(tl, a) - s["t0"] for a in s["at"]] if s.get("at") else [0.15, 0.8, 1.4]
    cx, cy = W / 2 - 340, H / 2 + 50; p = smooth((lt - ats[0]) / 0.4); orbit(img, cx, cy, 190, lt, GOLD, p)
    glow_text(img, s["grade"], cx, cy, face("AN", 170), GOLD, 22, p); glow_text(img, "등급 유지", cx, cy + 250, face("B", 40), DIM, 0, p)
    if lt > ats[1]:
        spaced(img, "등급 전망", W / 2 + 50, 400, 34, DIM, 4); glow_text(img, s["before"], W / 2 + 130, 520, face("HAN", 86), SOFT)
        g = smooth((lt - ats[1]) / 0.3); ImageDraw.Draw(img).line([(W / 2 + 270, 520), (W / 2 + 270 + 110 * g, 520)], fill=INK + (255,), width=6)
        if lt > ats[2]: glow_text(img, s["after"], W / 2 + 520, 520, face("HAN", 96), HOT, 18)
    return img

def card_steps(s, lt, T, tl):
    img = dark(s.get("tint", "base"), lt); chart_title(img, s.get("title", "등급 사다리"), None); rows = s["rows"]; rh = min(76, 560 // len(rows)); y = 290; x0 = W / 2 - 420; ys = {}
    for j, r in enumerate(rows):
        p = smooth((lt - 0.1 - j * 0.08) / 0.25); ys[r] = y + rh / 2
        if p > 0:
            hl = r == s["hl"]; col = GOLD if hl else SOFT
            panel(img, [x0, y, x0 + 220, y + rh - 12], tuple(int(c * 0.25) for c in col), col, a=int(255 * p), blur=12 if hl else 0, radius=6)
            glow_text(img, r, x0 + 110, y + (rh - 12) / 2, face("AN", 46), INK, 0, p)
            if r in s.get("marks", {}): glow_text(img, s["marks"][r], x0 + 256, y + (rh - 12) / 2, face("XB" if hl else "B", 38), col, 0, p, "l")
        y += rh
    span = s.get("span")
    if span and lt > (at_time(tl, s["note_at"]) - s["t0"] if s.get("note_at") else 1.2):
        y1, y2 = ys[span[0]], ys[span[1]]; bx = x0 - 40
        ImageDraw.Draw(img).line([(bx, y1), (bx - 30, y1), (bx - 30, y2), (bx, y2)], fill=HOT + (255,), width=5)
        glow_text(img, span[2], bx - 56, (y1 + y2) / 2, face("XB", 40), HOT, 10, 1, "r")
    return img

def card_share(s, lt, T, tl):
    img = dark(s.get("tint", "base"), lt)
    if s.get("title_top"): chart_title(img, s["title_top"], None)
    end = (at_time(tl, s["count_at"]) - s["t0"] + 0.2) if s.get("count_at") else 1.2; st = max(0.15, end - 3.0); p = smooth((lt - st) / max(0.3, end - st)); v = s["value"] * p
    cx, cy, r = W / 2 - 340, H / 2 + 50, 250; lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 3.6 * v, fill=GOLD + (255,), width=44); img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(20))); img.alpha_composite(lay)
    ImageDraw.Draw(img).ellipse([cx - r, cy - r, cx + r, cy + r], outline=LINE, width=2)
    glow_text(img, f"{v:.0f}%", cx, cy, face("AN", 150), GOLD, 22); glow_text(img, s["who"], W / 2 + 40, H / 2 - 100, face("XB", 52), GOLD, 0, 1, "l"); y = H / 2 - 10
    for ln in s["title"].split("\n"): glow_text(img, ln, W / 2 + 40, y, face("B", 46), INK, 0, 1, "l"); y += 68
    return img

from .news import load_article
