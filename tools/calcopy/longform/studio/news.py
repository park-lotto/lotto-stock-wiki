# 기사 화면
from .settings import *
from .timing import *
from .footage import *
ART_W, ART_H, ART_Y = 1440, 780, 128   # 기사 카드 자리 — 출처 표시(marks.source_mark)도 이 자리를 쓴다
ART_BOX = ((W - ART_W) // 2, ART_Y, (W + ART_W) // 2, ART_Y + ART_H)
_art = {}
def load_article(name):
    if name not in _art:
        im = Image.open(E("material", "news", name + ".png")).convert("RGB")
        meta = json.load(open(E("material", "news", name + ".json"), encoding="utf-8"))
        _art[name] = (im, meta)
    return _art[name]
_artbg = {}
def article_bg(s):
    k = s["s"][0]
    if k not in _artbg:
        base = base_picture(s.get("img", s["s"][0]))
        _artbg[k] = tone(base.filter(ImageFilter.GaussianBlur(18)), 0.55).convert("RGBA")
    return _artbg[k]
def circle_times(s, tl):
    ats = s.get("circle_at") or []
    n = len(load_article(s["article"])[1]["boxes"]); T = s["t1"] - s["t0"]; out = []
    for j in range(n):
        out.append((at_time(tl, ats[j]) - s["t0"]) if j < len(ats) and ats[j] else T * (0.32 + 0.3 * j))
    return out
def pen_circle(dl, box, g, seed):
    x0, y0, x1, y1 = box; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; rx, ry = (x1 - x0) / 2 + 34, (y1 - y0) / 2 + 26
    rnd = random.Random(seed); ph = rnd.uniform(0, 6.28); n = max(2, int(80 * g)); pts = []
    for i in range(n + 1):
        a = -2.4 + (2 * math.pi + 0.5) * (i / 80); wob = 1 + 0.035 * math.sin(a * 3 + ph) + 0.05 * (i / 80)
        pts.append((cx + rx * wob * math.cos(a), cy + ry * wob * math.sin(a) - 4 * (i / 80)))
    dl.line(pts, fill=(235, 30, 30, 255), width=8, joint="curve")
def card_news(s, lt, T, tl):
    img = article_bg(s).copy(); art, meta = load_article(s["article"])
    boxes = meta["boxes"]; cts = circle_times(s, tl)
    allb = [b for bs in boxes for b in bs]
    def union(bs): return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
    U = union(allb); fx = (U[0] + U[2]) / 2; fy = (U[1] + U[3]) / 2
    # 보여 줄 창: 처음엔 기사 위쪽(제목)부터, 첫 동그라미 전에 구절로 내려오며 살짝 확대
    DW, DH = ART_W, ART_H; aw, ah = art.size
    # 처음엔 기사 폭 전체 → 첫 동그라미 때 첫 구절이 화면 폭 60%쯤 되게 확대
    B0 = union(boxes[0]); pw = max(200, B0[2] - B0[0])
    z0 = DW / aw; z1 = min(max(z0, 0.6 * DW / pw), z0 * 1.45, 1.0)
    mv = smooth((lt - 0.2) / max(0.6, cts[0] - 0.2)); z = z0 + (z1 - z0) * mv
    fx = (B0[0] + B0[2]) / 2; fy = (B0[1] + B0[3]) / 2
    cw, ch = DW / z, DH / z
    top_y = 0 if not meta.get("headline_box") else max(0, meta["headline_box"][1] - 40)
    cy0 = min(max(top_y + ch / 2, ch / 2), max(ch / 2, ah - ch / 2)); cy1 = min(max(fy, ch / 2), max(ch / 2, ah - ch / 2))
    cyy = cy0 + (cy1 - cy0) * mv
    cxt = min(max(fx, cw / 2), aw - cw / 2) if cw < aw else aw / 2; cxx = aw / 2 + (cxt - aw / 2) * mv
    l, t = cxx - cw / 2, cyy - ch / 2
    view = art.transform((DW, DH), Image.EXTENT, (l, t, l + cw, t + ch), Image.BICUBIC, fillcolor=(255, 255, 255)).convert("RGBA")
    # 형광 + 동그라미 (화면 좌표)
    hl = Image.new("RGBA", (DW, DH), (0, 0, 0, 0)); dh = ImageDraw.Draw(hl)
    ov = Image.new("RGBA", (DW, DH), (0, 0, 0, 0)); do = ImageDraw.Draw(ov)
    for j, bs in enumerate(boxes):
        g = smooth((lt - cts[j]) / 0.45)
        if g <= 0: continue
        sb = [[(b[0] - l) * z, (b[1] - t) * z, (b[2] - l) * z, (b[3] - t) * z] for b in bs]
        for b in sb: dh.rectangle([b[0] - 4, b[1] + 2, b[0] - 4 + (b[2] - b[0] + 8) * min(1, g * 1.4), b[3] + 2], fill=(255, 230, 0, 110))
        if len(sb) == 1 or (union(sb)[3] - union(sb)[1]) < 90: pen_circle(do, union(sb), g, j * 7 + s["s"][0])
        else:  # 여러 줄 구절: 줄마다 빨간 밑줄
            for i_, b in enumerate(sb):
                gi = max(0.0, min(1.0, g * len(sb) - i_))
                if gi > 0: do.line([(b[0], b[3] + 6), (b[0] + (b[2] - b[0]) * gi, b[3] + 6 - 3 * gi)], fill=(235, 30, 30, 255), width=8)
    view.alpha_composite(hl); view.alpha_composite(ov)
    # 카드(그림자) 등장: 아래에서 올라오며
    q = smooth(lt / 0.35); x0 = (W - DW) // 2; y0 = ART_Y + int((1 - q) * 120)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle([x0 + 10, y0 + 16, x0 + DW + 10, y0 + DH + 16], fill=(0, 0, 0, int(150 * q)))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    if q < 1: view.putalpha(view.getchannel("A").point(lambda v: int(v * q)))
    img.alpha_composite(view, (x0, y0))
    return img

