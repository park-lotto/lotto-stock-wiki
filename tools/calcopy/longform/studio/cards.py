# 샷 종류별 화면
from .settings import *
from .timing import *
from .footage import *
from .marks import *
BRIGHT = {"bar", "table", "vs", "cycle", "rating", "ladder", "pct"}
def is_bright(s): return s["type"] in BRIGHT or (s["type"] == "quote" and s.get("style") == "paper")
def has_ai_picture(s):
    n = s.get("img", s["s"][0])
    return os.path.exists(E("material", "img", f"s{n:03d}.png")) and not os.path.exists(E("material", "video", f"s{n:03d}.mp4")) and not os.path.exists(E("material", "video", f"s{n:03d}.jpg"))
def shot_src(s):
    if s["type"] == "article":
        m = load_article(s["article"])[1]; return s.get("src") or f'{m.get("media", "")} {m.get("date", "").replace("-", ".")}'
    if "src" in s:
        return s["src"] + (", AI 생성" if (has_ai_picture(s) and s["type"] in ("quote", "bignum", "labels", "ai", "stock")) else "")
    if s["type"] == "ai": return "AI 생성"
    if has_ai_picture(s) and s["type"] in ("stock", "labels", "bignum", "quote"): return "AI 생성"
    return ""

def drift(im, p, k):
    """결 b: 확대 없이 일정 배율로 한 방향으로 흐른다(샷 번호로 방향이 돈다)."""
    z = 1.13; w, h = W / z, H / z; mx, my = W - w, H - h; q = max(0.0, min(1.0, p))
    l, t = [(mx * q, my / 2), (mx * (1 - q), my / 2), (mx / 2, my * q), (mx / 2, my * (1 - q))][k % 4]
    return im.transform((W, H), Image.EXTENT, (l, t, l + w, t + h), Image.BILINEAR)

def backdrop(s, lt, T, dark=0.0):
    im = video_frame(s, lt, T)
    if im is None:
        if s.get("variant"):
            base = base_picture(s.get("img", s["s"][0])); z = 1.16 - 0.06 * max(0.0, min(1.0, lt / max(T, 0.1)))
            w, h = int(W / z), int(H / z); l, tp = int((W - w) * 0.8), int((H - h) * 0.3)
            im = base.crop((l, tp, l + w, tp + h)).resize((W, H), Image.BILINEAR)
        elif CFG.get("photo_motion", "pan") == "pan":
            im = drift(base_picture(s.get("img", s["s"][0])), lt / max(T, 0.1), s["s"][0])
        else:
            im = slow_zoom(base_picture(s.get("img", s["s"][0])), lt / max(T, 0.1), 1.04, 1.16, s.get("k", 0))
    return tone(im, dark).convert("RGBA")

MARKER = [(255, 214, 0), (120, 205, 255), (255, 140, 190)]
def card_quote(s, lt, T, tl):
    st = s.get("style", "dark")
    if st == "dark": img = backdrop(s, lt, T, dark=0.62)
    elif st == "paper":
        img = backdrop(s, lt, T, dark=0.0); ov = Image.new("RGBA", (W, H), C["paper"] + (205,)); img.alpha_composite(ov)
    else: img = backdrop(s, lt, T, dark=0.35)
    f = face("SERIF", 50); d = ImageDraw.Draw(img)
    lines = wrapped_lines(d, s["text"], s.get("hl", []), f, W - 400)
    lh = 86; tot_h = lh * len(lines); maxw = max(sum(width_of(d, p, face("K", 58) if h else f) + (12 if h else 0) for p, h in ln) for ln in lines)
    y = (H - tot_h) // 2 - 20; x0 = (W - maxw) // 2
    if st == "beige":
        d.rectangle([x0 - 60, y - 50, x0 + maxw + 60, y + tot_h + 40], fill=C["beige"] + (245,), outline=C["beige_border"], width=3)
        d.rectangle([x0 - 52, y - 42, x0 + maxw + 52, y + tot_h + 32], outline=C["beige_border"] + (140,), width=1)
    base_c = (255, 255, 255, 255) if st == "dark" else (34, 34, 34, 255)
    hl_c = C["yellow"] + (255,) if st == "dark" else C["wine"] + (255,)
    td = max(1.5, min(7.0, T * 0.8)); total_chars = sum(len(p) for ln in lines for p, _ in ln); shown = int(total_chars * min(1.0, lt / td))
    cnt = 0
    for ln in lines:
        x = x0
        for p, h in ln:
            vis = p[: max(0, min(len(p), shown - cnt))]; cnt += len(p)
            fi = f if not h else face("K", 58)
            if vis:
                if h:
                    hi = s.get("hl", []).index(p) if p in s.get("hl", []) else 0; mc = MARKER[hi % len(MARKER)]
                    vw = width_of(d, vis, fi); d.rectangle([x - 6, y - 4, x + vw + 6, y + 66], fill=mc + (255,))
                    d.text((x, y - 4), vis, font=fi, fill=(17, 17, 17, 255))
                else:
                    d.text((x, y), vis, font=fi, fill=base_c)
            x += width_of(d, p, fi) + (12 if h else 0)
        y += lh
    return img

def number_landing(tl, s):
    return (word_time(tl, s.get("count_line", s["s"][0]), s["count_word"]) + 0.2) if s.get("count_word") else s["t0"] + 1.3
def card_number(s, lt, T, tl):
    img = backdrop(s, lt, T, dark=0.5); d = ImageDraw.Draw(img)
    end_t = number_landing(tl, s) - s["t0"]
    st_t = max(0.15, end_t - 3.0)
    pr = smooth((lt - st_t) / max(0.3, end_t - st_t)); v = s["v0"] + (s["v1"] - s["v0"]) * pr
    if s["fmt"] == "joeok":
        iv = int(round(v)); txt = (f"{iv // 10000}조 {iv % 10000:,}억 유로" if iv >= 10000 else f"{iv:,}억 유로")
    else:
        txt = s["fmt"].format(v)
    if pr >= 1 and s.get("fmt_final"): txt = s["fmt_final"]
    bump = max(0.0, 1 - (lt - end_t) / 0.28) if lt >= end_t else 0.0
    f = face("GM", int(150 * (1 + 0.16 * bump))); w = width_of(d, txt, f); tb = d.textbbox((0, 0), txt, font=f)
    nx = lambda w_: 132
    d.rectangle([92, H // 2 - 190, 104, H // 2 + 130], fill=C["sub_bar"])
    cy_ = H // 2 - 35; sh = int(10 * bump * math.sin(lt * 90))
    d.text((nx(w) + sh, cy_ - (tb[1] + tb[3]) / 2), txt, font=f, fill=(255, 255, 255, 255) if bump < 0.5 else C["yellow"] + (255,), stroke_width=6, stroke_fill=(0, 0, 0, 255))
    fl = face("B", 46); w2 = width_of(d, s["label"], fl); d.text((nx(w2), H // 2 - 190), s["label"], font=fl, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    sub_t = (at_time(tl, s["sub_word"]) - s["t0"]) if s.get("sub_word") else end_t + 0.5
    if s.get("sub") and lt > sub_t:
        fs = face("XB", 54); w3 = width_of(d, s["sub"], fs); d.text((nx(w3), H // 2 + 70), s["sub"], font=fs, fill=C["yellow"] + (255,), stroke_width=4, stroke_fill=(0, 0, 0, 255))
    return img

def chart_title(d, title, sub):
    f = face("XB", 60); w = width_of(d, title, f); d.text(((W - w) // 2, 150), title, font=f, fill=(34, 34, 34, 255))
    if sub: fs = face("M", 30); w2 = width_of(d, sub, fs); d.text(((W - w2) // 2, 228), sub, font=fs, fill=(102, 102, 102, 255))

def card_bars(s, lt, T, tl):
    img = page().convert("RGBA"); d = ImageDraw.Draw(img); chart_title(d, s["title"], s.get("sub"))
    items = s["items"]; n = len(items); hl = s.get("hl", -1); orient = s.get("orient", "v")
    vals = [v for _, v, _ in items] + ([s["ref"][0]] if s.get("ref") else [])
    vmin = min(0, min(vals)) * 1.12; vmax = max(0, max(vals)) * 1.12
    if vmax <= 0: vmax = abs(vmin) * 1.6
    rev_t = (reveal_time(tl, s) - s["t0"] - 0.3) if s.get("reveal") else 0
    g = smooth((lt - 0.15) / 0.7)
    # 막대마다: 그 숫자를 말하는 순간 차오름(못 찾으면 0.4초 간격)
    starts = []
    for j, (lab, v, disp) in enumerate(items):
        ft = find_said(tl, s, first_num(disp).rstrip(".,"))
        if ft is None: ft = find_said(tl, s, lab.split()[0])
        if ft is not None: starts.append(max(0.1, ft - s["t0"] - 0.25))
        else: starts.append((starts[-1] + 0.6) if starts else 0.15)
    G = [smooth((lt - st) / 0.55) for st in starts]
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    if orient == "v":
        x_area0, x_area1, y_base, y_top = 360, W - 360, 800, 330
        if vmin < 0: y_base, y_top = 560, 300
        slot = (x_area1 - x_area0) / n; bw = min(220, slot * 0.55)
        for j, (lab, v, disp) in enumerate(items):
            g = G[j]; cx = x_area0 + slot * (j + 0.5); hpx = (y_base - y_top) * (abs(v) / (vmax - vmin)) * g
            col = C["blue"] if j == hl else C["gray"]
            if v >= 0: dl.rectangle([cx - bw / 2, y_base - hpx, cx + bw / 2, y_base], fill=col + (255,))
            else: dl.rectangle([cx - bw / 2, y_base, cx + bw / 2, y_base + hpx], fill=C["red"] + (255,))
            fl = face("B", 34); w = width_of(dl, lab, fl); dl.text((cx - w / 2, (y_base + 14) if v >= 0 else (y_base - 52)), lab, font=fl, fill=(68, 68, 68, 255))
            if g > 0.6:
                fv = face("K", 54 if j == hl else 44); w = width_of(dl, disp, fv); ty = (y_base - hpx - 70) if v > 0 else ((y_base - 120) if v == 0 else (y_base + hpx + 12))
                vl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dv = ImageDraw.Draw(vl)
                dv.text((cx - w / 2, ty), disp, font=fv, fill=((C["blue"] if j == hl else (108, 117, 125)) if v >= 0 else C["red"]) + (255,))
                if s.get("reveal") and j == hl and lt < rev_t: vl = vl.filter(ImageFilter.GaussianBlur(14))
                lay.alpha_composite(vl)
        dl.line([(x_area0 - 20, y_base), (x_area1 + 20, y_base)], fill=(150, 150, 150, 255), width=2)
        if s.get("ref") and (not s.get("ref_at") or lt >= line_time(tl, s["ref_at"]) - s["t0"]):
            rv, rl = s["ref"]; ry = y_base - (y_base - y_top) * (rv / (vmax - vmin))
            for xx in range(int(x_area0 - 20), int(x_area1 + 20), 28): d.line([(xx, ry), (xx + 16, ry)], fill=C["red"] + (150,), width=3)
            dl.text((x_area1 + 30, ry - 20), rl, font=face("B", 30), fill=C["red"] + (255,))
    else:
        x0, x1, y0 = 560, W - 300, 340; slot = min(150, 520 / n); bh = slot * 0.62
        for j, (lab, v, disp) in enumerate(items):
            g = G[j]; cy = y0 + slot * (j + 0.5) + (520 - slot * n) / 2; wpx = (x1 - x0) * (v / vmax) * g
            col = C["blue"] if j == hl else C["gray"]
            dl.rectangle([x0, cy - bh / 2, x0 + wpx, cy + bh / 2], fill=col + (255,))
            fl = face("B", 36); w = width_of(dl, lab, fl); dl.text((x0 - 30 - w, cy - 22), lab, font=fl, fill=(68, 68, 68, 255))
            if g > 0.6:
                fv = face("K", 48); vl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dv = ImageDraw.Draw(vl)
                dv.text((x0 + wpx + 20, cy - 30), disp, font=fv, fill=(C["blue"] if j == hl else (108, 117, 125)) + (255,))
                if s.get("reveal") and j == hl and lt < rev_t: vl = vl.filter(ImageFilter.GaussianBlur(14))
                lay.alpha_composite(vl)
        if s.get("ref"):
            rv, rl = s["ref"]; rx = x0 + (x1 - x0) * (rv / vmax)
            for yy in range(y0 - 20, y0 + 560, 26): d.line([(rx, yy), (rx, yy + 14)], fill=C["red"] + (150,), width=3)
            dl.text((rx - 60, y0 - 70), rl, font=face("B", 32), fill=C["red"] + (255,))
    img.alpha_composite(lay)
    if s.get("badge"):
        bt = (word_time(tl, s["badge"][0], s["badge"][2]) if len(s["badge"]) > 2 else line_time(tl, s["badge"][0])) - s["t0"]
        if lt > bt:
            d = ImageDraw.Draw(img); fb = face("K", 56); t = s["badge"][1]; w = width_of(d, t, fb)
            bx = W - 150 - (w + 60); q = smooth((lt - bt) / 0.18); sc_ = 1.0 + 0.25 * (1 - q)
            bl = Image.new("RGBA", (w + 60, 90), (0, 0, 0, 0)); dbl = ImageDraw.Draw(bl)
            dbl.rounded_rectangle([0, 0, w + 59, 89], radius=45, fill=C["red"] + (255,)); dbl.text((30, 8), t, font=fb, fill=(255, 255, 255, 255))
            bl = bl.resize((int(bl.width * sc_), int(bl.height * sc_)), Image.BICUBIC)
            img.alpha_composite(bl, (int(bx + (w + 60) / 2 - bl.width / 2), int(295 - bl.height / 2)))
    if s.get("stamp"):
        stt = word_time(tl, s["stamp"][0], s["stamp"][1]) - s["t0"]; alert_tag(img, s["stamp"][1], W - 520, 760, lt - stt)
    return img

def card_table(s, lt, T, tl):
    img = page().convert("RGBA"); d = ImageDraw.Draw(img); chart_title(d, s["title"], None)
    cols, rows = s["cols"], s["rows"]; nc = len(cols)
    fh, fr = face("B", 36), face("SB", 36)
    widths = [max(width_of(d, str(r[c]), fr) for r in rows + [cols]) + 80 for c in range(nc)]
    tot = sum(widths); sc = min(1.0, (W - 240) / tot); widths = [w * sc for w in widths]; tot = sum(widths)
    x0 = (W - tot) / 2; y = 290; rh = 88
    rev_t = (reveal_time(tl, s) - s["t0"]) if s.get("reveal") else 0
    d.rounded_rectangle([x0, y, x0 + tot, y + rh], radius=16, fill=C["table_head"] + (255,))
    xx = x0
    for c in range(nc): w = width_of(d, cols[c], fh); d.text((xx + (widths[c] - w) / 2, y + 22), cols[c], font=fh, fill=(255, 255, 255, 255)); xx += widths[c]
    y += rh
    for ri, r in enumerate(rows):
        hl = ri in s.get("hl_rows", [])
        bg = C["table_hl"] if hl else (C["table_alt"] if ri % 2 else (255, 255, 255))
        rl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(rl)
        dr.rectangle([x0, y, x0 + tot, y + rh], fill=bg + (255,)); dr.line([(x0, y + rh), (x0 + tot, y + rh)], fill=(224, 224, 224, 255), width=2)
        xx = x0
        for c in range(nc):
            t = str(r[c]); fnt = face("XB" if (hl or c == 0) else "SB", 36); w = width_of(dr, t, fnt)
            dr.text((xx + (widths[c] - w) / 2, y + 22), t, font=fnt, fill=((30, 58, 138, 255) if c == 0 else (34, 34, 34, 255)))
            xx += widths[c]
        if s.get("row_at") and ri < len(s["row_at"]): appear = smooth((lt - max(0.2, at_time(tl, s["row_at"][ri]) - s["t0"] - 0.2)) / 0.3)
        else: appear = smooth((lt - 0.2 - ri * 0.18) / 0.3)
        if appear > 0:
            if s.get("reveal") and lt < rev_t and (ri in s.get("hl_rows", []) or (not s.get("hl_rows") and ri == len(rows) - 1)): rl = rl.filter(ImageFilter.GaussianBlur(10))
            a = rl.getchannel("A").point(lambda v: int(v * appear)); rl.putalpha(a); img.alpha_composite(rl)
        y += rh
    return img

def label_time(tl, it, j):
    return word_time(tl, it[0], it[2]) if len(it) > 2 else line_time(tl, it[0]) + j * 0.35
LABELC = [((255, 214, 0), (17, 17, 17)), ((30, 108, 235), (255, 255, 255)), ((255, 30, 138), (255, 255, 255))]
def card_chips(s, lt, T, tl):
    img = backdrop(s, lt, T, dark=0.45); d = ImageDraw.Draw(img)
    items = s["items"]; f = face("K", 80); n = len(items)
    ws = [width_of(d, it[1], f) + 100 for it in items]; gap = 40
    row = sum(ws) + gap * (n - 1) <= W - 200
    if row:
        x = (W - (sum(ws) + gap * (n - 1))) / 2; ys = [H // 2 - 50] * n; xs = []
        for w in ws: xs.append(x); x += w + gap
    else:
        xs = [(W - w) / 2 for w in ws]; ys = [H // 2 - 60 - (n - 1) * 80 + j * 160 for j in range(n)]
    for j, it in enumerate(items):
        t = it[1]; at = label_time(tl, it, j) - s["t0"]
        p = lt - at
        if p <= 0: continue
        sc = (0.55 + 0.6 * smooth(p / 0.12)) if p < 0.12 else (1.15 - 0.15 * smooth((p - 0.12) / 0.12))
        fw = face("K", max(20, int(80 * sc))); w = width_of(d, t, fw)
        cx = xs[j] + ws[j] / 2; cy = ys[j] + 45
        plain = t.strip().lower() == "vs"
        bgc, ink = ((255, 255, 255), (17, 17, 17)) if plain else LABELC[j % len(LABELC)]
        bgc, ink = [(TYPO_BG["lime"], (12, 24, 28)), (TYPO_BG["pink"], (12, 24, 28)), (C["yellow"], (12, 24, 28))][j % 3]
        d.rectangle([cx - w / 2 - 44, cy - 58 * sc, cx + w / 2 + 44, cy + 58 * sc], fill=tuple(bgc) + (250,))
        tb = d.textbbox((0, 0), t, font=fw); d.text((cx - w / 2 - tb[0], cy - (tb[1] + tb[3]) / 2), t, font=fw, fill=ink + (255,))
    return img

def card_versus(s, lt, T, tl):
    img = page().convert("RGBA"); d = ImageDraw.Draw(img)
    if s.get("title"): chart_title(d, s["title"], None)
    ats = [at_time(tl, a) - s["t0"] for a in s["at"]] if s.get("at") else [0.15, 0.5, 1.4]
    for j, (t, col) in enumerate([(s["left"], C["blue"]), (s["right"], C["red"])]):
        p = smooth((lt - ats[j]) / 0.35)
        if p <= 0: continue
        cx = W / 2 + (-1 if j == 0 else 1) * 420; f = face("K", 66); w = width_of(d, t, f)
        d.rounded_rectangle([cx - 330, 340, cx + 330, 640], radius=30, fill=col + (int(255 * p),))
        d.text((cx - w / 2, 450), t, font=f, fill=(255, 255, 255, int(255 * p)))
    if lt > ats[1]:
        f = face("HAN", 120); w = width_of(d, "VS", f); d.text(((W - w) / 2, 410), "VS", font=f, fill=(34, 34, 34, 255))
    if s.get("sub") and lt > ats[2]:
        f = face("B", 42); w = width_of(d, s["sub"], f); d.text(((W - w) / 2, 720), s["sub"], font=f, fill=(68, 68, 68, 255))
    return img

def card_loop(s, lt, T, tl):
    img = page().convert("RGBA"); d = ImageDraw.Draw(img)
    if s.get("title"): chart_title(d, s["title"], None)
    cx, cy, R = W / 2, H / 2 + 20, 270; n = len(s["items"])
    pts = [(cx + R * math.cos(-math.pi / 2 + j * 2 * math.pi / n), cy + R * math.sin(-math.pi / 2 + j * 2 * math.pi / n)) for j in range(n)]
    active = int((lt / 0.9)) % n if lt > 0.3 else -1
    for j in range(n):
        a, b = pts[j], pts[(j + 1) % n]; mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        p = smooth((lt - 0.2 - j * 0.3) / 0.3)
        if p > 0:
            ex = a[0] + (b[0] - a[0]) * (0.25 + 0.5 * p); ey = a[1] + (b[1] - a[1]) * (0.25 + 0.5 * p)
            d.line([(a[0] + (b[0] - a[0]) * 0.25, a[1] + (b[1] - a[1]) * 0.25), (ex, ey)], fill=(120, 120, 120, 255), width=10)
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            d.polygon([(ex + 26 * math.cos(ang), ey + 26 * math.sin(ang)), (ex + 22 * math.cos(ang + 2.4), ey + 22 * math.sin(ang + 2.4)), (ex + 22 * math.cos(ang - 2.4), ey + 22 * math.sin(ang - 2.4))], fill=(120, 120, 120, 255))
    for j, t in enumerate(s["items"]):
        x, y = pts[j]; col = C["red"] if j == active else C["navy"]
        d.ellipse([x - 120, y - 70, x + 120, y + 70], fill=col + (255,)); f = face("K", 54); w = width_of(d, t, f); d.text((x - w / 2, y - 36), t, font=f, fill=(255, 255, 255, 255))
    return img

def card_grade(s, lt, T, tl):
    img = page().convert("RGBA"); d = ImageDraw.Draw(img); chart_title(d, "피치 · 프랑스 국가신용등급", None)
    ats = [at_time(tl, a) - s["t0"] for a in s["at"]] if s.get("at") else [0.15, 0.8, 1.4]
    p = smooth((lt - ats[0]) / 0.4)
    d.ellipse([W / 2 - 520, 330, W / 2 - 160, 690], fill=C["navy"] + (int(255 * p),))
    f = face("K", 150); w = width_of(d, s["grade"], f); d.text((W / 2 - 340 - w / 2, 420), s["grade"], font=f, fill=(255, 255, 255, int(255 * p)))
    fl = face("B", 40); d.text((W / 2 - 400, 720), "등급 유지", font=fl, fill=(68, 68, 68, 255))
    if lt > ats[1]:
        d.text((W / 2 + 40, 380), "등급 전망", font=face("B", 44), fill=(68, 68, 68, 255))
        d.text((W / 2 + 40, 460), s["before"], font=face("K", 80), fill=C["gray"] + (255,))
        d.text((W / 2 + 290, 460), "→", font=face("K", 80), fill=(90, 90, 90, 255))
        if lt > ats[2]: d.text((W / 2 + 400, 460), s["after"], font=face("K", 80), fill=C["red"] + (255,))
    return img

def card_steps(s, lt, T, tl):
    img = page().convert("RGBA"); d = ImageDraw.Draw(img); chart_title(d, "신용등급 사다리 (피치 기준)", None)
    rows = s["rows"]; y = 280; rh = 76; x0 = W / 2 - 420
    for j, r in enumerate(rows):
        p = smooth((lt - 0.1 - j * 0.08) / 0.25)
        if p <= 0: continue
        hl = r == s["hl"]; junk = r.startswith("BB") and not r.startswith("BBB")
        col = C["blue"] if hl else ((200, 60, 60) if junk else (120, 130, 145))
        d.rounded_rectangle([x0, y, x0 + 220, y + rh - 12], radius=12, fill=col + (int(255 * p),))
        f = face("K", 44); w = width_of(d, r, f); d.text((x0 + 110 - w / 2, y + 8), r, font=f, fill=(255, 255, 255, int(255 * p)))
        if r in s["marks"]: d.text((x0 + 260, y + 10), s["marks"][r], font=face("XB" if hl else "B", 40), fill=(col if (hl or junk) else (68, 68, 68)) + (int(255 * p),))
        y += rh
    nt = (at_time(tl, s["note_at"]) - s["t0"]) if s.get("note_at") else 1.2
    if lt > nt:
        y1 = 280 + rh * rows.index("A+") + rh / 2 - 6; y2 = 280 + rh * rows.index("BB+") + rh / 2 - 6; bx = x0 - 40
        d.line([(bx, y1), (bx - 30, y1), (bx - 30, y2), (bx, y2)], fill=C["red"] + (255,), width=5)
        f = face("XB", 40); t = "여섯 칸 차이"; w = width_of(d, t, f)
        d.rounded_rectangle([bx - 60 - w - 40, (y1 + y2) / 2 - 36, bx - 50, (y1 + y2) / 2 + 36], radius=18, fill=C["red"] + (255,))
        d.text((bx - 70 - w, (y1 + y2) / 2 - 26), t, font=f, fill=(255, 255, 255, 255))
    return img

def card_share(s, lt, T, tl):
    img = page().convert("RGBA"); d = ImageDraw.Draw(img)
    if s.get("title_top"): chart_title(d, s["title_top"], None)
    c_end = (at_time(tl, s["count_at"]) - s["t0"] + 0.2) if s.get("count_at") else 1.2
    c_st = max(0.15, c_end - 3.0); p = smooth((lt - c_st) / max(0.3, c_end - c_st)); v = s["value"] * p; cx, cy, r = W / 2 - 330, H / 2 + 40, 230
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(217, 221, 226, 255))
    d.pieslice([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * v / 100, fill=C["red"] + (255,))
    d.ellipse([cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62], fill=C["paper"] + (255,))
    t = f"{v:.0f}%"; f = face("K", 96); w = width_of(d, t, f); d.text((cx - w / 2, cy - 62), t, font=f, fill=C["red"] + (255,))
    fw = face("XB", 50); d.text((W / 2 + 10, H / 2 - 150), s["who"], font=fw, fill=C["navy"] + (255,))
    y = H / 2 - 60
    for ln in s["title"].split("\n"): d.text((W / 2 + 10, y), ln, font=face("B", 46), fill=(34, 34, 34, 255)); y += 66
    return img

def card_photo(s, lt, T, tl):
    img = backdrop(s, lt, T, dark=0.05)
    if s.get("bubble"):
        bt = bubble_time(tl, s) - s["t0"]; note_tag(img, s["bubble"][1], W / 2 + 40, H / 2 - 120, lt - bt)
    if s.get("stamp"):
        stt = word_time(tl, s["stamp"][0], s["stamp"][1]) - s["t0"]; alert_tag(img, s["stamp"][1], W / 2 + 330, H / 2 + 40, lt - stt)
    if s.get("big"):
        bt = line_time(tl, s["big"][0]) - s["t0"]; big_note(img, s["big"][1], lt - bt)
    return img


