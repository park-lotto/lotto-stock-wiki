# -*- coding: utf-8 -*-
"""트롯파파 1차 제작기 — 울지마트롯 뼈대(같은 위치·같은 흐름) + 우리 유료급 글꼴·자막 (2026-10-23, 관제 097).

    PYTHONUTF8=1 py channel/uljimatrot/_tools/make_trotpapa.py channel/uljimatrot/트롯파파_1차/A_후드티.json [--no-tts]

자리(1080x1920, 벤치 실측 스타일분석.md §1~3): 제목 띠 y150~300 / 2줄 300~430 · 창 y440~1300 · 자막 기준선 y≈1240
  · CTA 2줄 y≈1010~1150 · 트롯파파 칩 = 출처 줄 자리 y≈1500 · 커서 아이콘 x≈880 y≈1180 · 훅 ≈ 나레 길이(누끼+검정+줌)
디자인 기준: awesome-design-md spotify — 근흑 #121212 바탕, 알약 칩(#1F1F1F·테 #4D4D4D), 그림자 rgba(0,0,0,.5) 0 8 24.
움직임: 자막 등장 0.12초 ease-out(투명 0→1 + 12px 위로), 커서 0.7초 주기 ±6px, 훅 줌 1.00→1.07, 원형 전환 0.3초.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
FONTS = ROOT / "shopping_shorts/static/fonts"
COPY = "--style=copy" in sys.argv               # 원본 판(벤치 99% — 글꼴 근사 G마켓 산스, 10-23 대조 1위)
SUBS = "--no-subs" not in sys.argv               # 자막·CTA·공개 글자를 이 도구가 그린다(끄면 = 자막팩 판 바탕)
F_BOLD = str(FONTS / ("GmarketSansBold.otf" if COPY else "Pretendard-ExtraBold.otf"))
F_BRAND = str(FONTS / "GmarketSansBold.otf")
BGM = ROOT / "shopping_shorts/assets/bgm_lib/honwaka_puppu.mp3"
WORK = Path("C:/숏템_칼카피/uljimatrot/make")
VOICE = "tc_6059dad0b83880769a50502f"        # 박창수
W, H, FPS = 1080, 1920, 30
BG = (0, 0, 0) if COPY else (18, 18, 18)       # 원본 순검정 / 우리 spotify #121212
WIN_Y, WIN_H = 440, 860
SUB_Y = 1240                                  # 자막 줄 가운데
CPS = 6.7                                     # 벤치 나레 6.1~7.5자/초 중앙
YELLOW = (255, 212, 59)
# 원본 판 좌표 — 눈대중 금지. 벤치 줄판독(channel/uljimatrot/줄판독/<id>.json, 픽셀 실측)에서 load_spec 이 채운다.
SPEC = {"title_band": [150, 292], "title_y": [[178, 265], [325, 409]], "cap": [1201, 1279], "cta_y": [918, 996],
        "src_y": [1510, 1557], "src_hex": "#FDFAD6", "icon": [840, 1332, 947, 1439], "icon_period": 1.0, "icon_amp": 4,
        "outline": 7, "outline_hex": "#19191F", "circle_period": None, "hook_exit": ["circleopen", 0.3], "hook_zoom": 0.07,
        "hook_arrow": True}


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def load_spec(path):
    """줄판독 한 편 → SPEC·WIN_Y·WIN_H·SUB_Y. 빈 칸은 기본값 그대로(빈칸 목록을 찍는다)."""
    global WIN_Y, WIN_H, SUB_Y
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    L = d.get("layout") or {}
    miss = []
    win = L.get("window")
    if win:
        WIN_Y, WIN_H = win[1], (win[3] - win[1]) // 2 * 2      # 인코더는 짝수 높이만
    else:
        miss.append("window")
    if L.get("caption_band"):
        SPEC["cap"] = L["caption_band"]
    else:
        miss.append("caption_band")
    SUB_Y = sum(SPEC["cap"]) // 2
    tl = d.get("title_lines") or []
    ty = L.get("title_y") or []
    if tl and tl[0].get("band_y"):
        SPEC["title_band"] = tl[0]["band_y"]
    elif ty and isinstance(ty[0], list):
        SPEC["title_band"] = ty[0]
    ys = [t.get("y") for t in tl if t.get("y")]
    if len(ys) == 2:
        SPEC["title_y"] = ys
    elif ty and isinstance(ty[0], list):          # 띠 칸·2줄 칸만 잰 편 → 칸 안 글자(위 17%·아래 23% 여백, Jlgd 실측 비율)
        SPEC["title_y"] = [[a + (b - a) * .17, b - (b - a) * .23] for a, b in ty]
        miss.append("title 글자 y(칸에서 비율로)")
    for k, key in (("cta_y", "cta_caption_y"), ("src_y", "source_y"), ("src_hex", "source_hex")):
        if L.get(key):
            SPEC[k] = L[key]
        else:
            miss.append(key)
    ic = L.get("icon") or {}
    if ic.get("bbox"):
        SPEC["icon"] = ic["bbox"]
    else:
        miss.append("icon")
    lines = d.get("lines") or []
    ol = [l["outline"] for l in lines if isinstance(l.get("outline"), dict) and l["outline"].get("px")]
    if ol:
        ol.sort(key=lambda o: o["px"])
        SPEC["outline"] = ol[len(ol) // 2]["px"]
        SPEC["outline_hex"] = ol[len(ol) // 2].get("hex") or SPEC["outline_hex"]
    hk = d.get("hook") or {}
    SPEC["circle_period"] = 0.77 if "0.77" in str(hk.get("circle_anim", "")) else None
    ex = str(hk.get("exit", ""))
    SPEC["hook_exit"] = ["zoomin", 0.17] if "줌" in ex else ["circleopen", 0.1]
    SPEC["hook_zoom"] = 0.07 if "zoom" in str(hk.get("motion", "")) else 0.0
    SPEC["hook_arrow"] = bool(hk.get("arrow"))
    print("좌표:", {"window": [WIN_Y, WIN_Y + WIN_H], "sub_y": SUB_Y, **SPEC}, "빈칸:", miss)


def fit_text(parts, box_h, stroke, glyph=False):
    """잉크(외곽 포함) 높이가 벤치 실측 box_h 가 되게 글자 크기를 고른다 → 잉크만 잘라 돌려준다."""
    size = int(box_h * 1.1)
    for _ in range(8):
        im = text_img(parts, size, stroke=stroke, color_ol=hexrgb(SPEC["outline_hex"]))
        ref = text_img(parts, size, stroke=0, shadow=False) if glyph else im      # glyph=True: 외곽 뺀 글자 높이로 맞춤(compare 의 '글자 높이' 자)
        bb = ref.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()
        h = bb[3] - bb[1]
        if abs(h - box_h) <= 1:
            break
        size = max(10, round(size * box_h / h))
    if glyph:
        return im
    return im.crop((0, bb[1], im.width, bb[3]))


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit(f"실패: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r.stdout


def dur(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).strip())


def font(path, size):
    return ImageFont.truetype(path, size)


# ── 글자 그림 ───────────────────────────────────────────────
def text_img(parts, size, stroke=9, shadow=not COPY, fpath=F_BOLD, color_ol=(11, 11, 11)):
    """parts = [(글, 색)] 한 줄 → RGBA. 흰 글자 + 검정 외곽 + 아래 그림자(spotify 0 8 24 .5)."""
    f = font(fpath, size)
    widths = [f.getlength(t) for t, _ in parts]
    tw = int(sum(widths)) + stroke * 2 + 40
    th = int(size * 1.35) + stroke * 2 + 40
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(sh)
        x = 20 + stroke
        for (t, _), w in zip(parts, widths):
            d.text((x, 20 + stroke + 8), t, font=f, fill=(0, 0, 0, 128), stroke_width=stroke, stroke_fill=(0, 0, 0, 128))
            x += w
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(im)
    x = 20 + stroke
    for (t, c), w in zip(parts, widths):
        d.text((x, 20 + stroke), t, font=f, fill=c + (255,), stroke_width=stroke, stroke_fill=tuple(color_ol) + (255,))
        x += w
    return im


def split_key(text, key):
    if key and key in text:
        a, b = text.split(key, 1)
        return [(a, (255, 255, 255)), (key, YELLOW), (b, (255, 255, 255))]
    return [(text, (255, 255, 255))]


def chunks(text, maxc=10):
    """띄어쓰기 단위로 maxc 자 안쪽 조각(벤치 조각 중앙 8자·p90 11)."""
    out, cur = [], ""
    for w in text.split():
        if cur and len((cur + " " + w).replace(" ", "")) > maxc:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def frame_png(path: Path, im: Image.Image):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


def static_overlay(cfg, out: Path):
    """제목 2줄(벤치 자리) — 띠는 빨강 그라데이션, 글자는 Pretendard ExtraBold + 그림자."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if COPY:                                      # 원본: 띠 #FF1700 y150~292 · 글자 흰 + 검정 테 + 오른쪽 아래 진한 그림자
        b0, b1 = SPEC["title_band"]
        ImageDraw.Draw(im).rectangle([0, b0, W, b1], fill=(255, 23, 0, 255))
        for line, (y0, y1) in zip(cfg["title"], SPEC["title_y"]):
            t = hard_shadow(fit_text([(line, (255, 255, 255))], 88, 7, glyph=True))      # compare 실측: 원본 띠 글자 높이 88·획 13~14
            if t.width > W - 30:
                t = t.resize((W - 30, int(t.height * (W - 30) / t.width)))
            gb = text_img([(line, (255, 255, 255))], 10, stroke=0, shadow=False)
            im.alpha_composite(t, ((W - t.width) // 2, int((y0 + y1) / 2 - t.height / 2)))
        return frame_png(out, im)
    band = Image.new("RGBA", (W, 150))
    bd = ImageDraw.Draw(band)
    for x in range(W):
        t = x / W
        bd.line([(x, 0), (x, 150)], fill=(int(255 - 28 * t), int(45 - 27 * t), int(32 - 21 * t), 255))
    im.alpha_composite(band, (0, 150))
    for i, (line, y) in enumerate(zip(cfg["title"], (150, 300))):
        t = text_img([(line, (255, 255, 255))], 92, stroke=0)
        if t.width > W - 40:
            t = t.resize((W - 40, int(t.height * (W - 40) / t.width)))
        im.alpha_composite(t, ((W - t.width) // 2, y + (150 if i == 0 else 130) // 2 - t.height // 2))
    return frame_png(out, im)


def hard_shadow(t, dx=5, dy=5):
    """원본 제목 그림자: 글자 모양 그대로 오른쪽 아래로 민 진한 그림자."""
    a = t.getchannel("A")
    sh = Image.new("RGBA", (t.width + dx, t.height + dy), (0, 0, 0, 0))
    sh.paste(Image.new("RGBA", t.size, (0, 0, 0, 200)), (dx, dy), a)
    sh.alpha_composite(t, (0, 0))
    return sh


def chunky_arrow(length=170, angle=225, thick=34, head=96):
    """원본 화살표(훅·오른쪽 아래 아이콘): 빨강 #FF1A31 위→아래 진해짐 · 흰 테 9px · 큰 삼각 머리 · 옅은 그림자. angle=가리키는 방향(도, 0=오른쪽, 시계)."""
    s = 4
    L, T, Hh = length * s, thick * s, head * s
    hl = int(Hh * 0.8)
    w, h = L + 80 * s, Hh + 80 * s
    cy = h // 2
    shape = [(40 * s, cy - T // 2), (40 * s + L - hl, cy - T // 2), (40 * s + L - hl, cy - Hh // 2), (40 * s + L, cy),
             (40 * s + L - hl, cy + Hh // 2), (40 * s + L - hl, cy + T // 2), (40 * s, cy + T // 2)]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon(shape, fill=(255, 255, 255, 255))
    d.line(shape + [shape[0]], fill=(255, 255, 255, 255), width=18 * s, joint="curve")
    fill = Image.new("RGBA", (w, h))
    fd = ImageDraw.Draw(fill)
    for y in range(h):
        k = y / h
        fd.line([(0, y), (w, y)], fill=(255, int(40 - 22 * k), int(60 - 30 * k), 255))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(shape, fill=255)
    im.paste(fill, (0, 0), m)
    big = Image.new("RGBA", (w + 40 * s, h + 40 * s), (0, 0, 0, 0))
    sh = Image.new("RGBA", big.size, (0, 0, 0, 0))
    sh.paste(Image.new("RGBA", im.size, (0, 0, 0, 110)), (24 * s, 28 * s), im.getchannel("A"))
    big = Image.alpha_composite(big, sh.filter(ImageFilter.GaussianBlur(8 * s)))
    big.alpha_composite(im, (10 * s, 10 * s))
    big = big.rotate(-angle, expand=True, resample=Image.BICUBIC)
    big = big.resize((big.width // s, big.height // s), Image.LANCZOS)
    return big.crop(big.getbbox())


def brand_chip(cfg, out: Path):
    if COPY:                                      # 원본 출처 줄 자리·꼴(노랑 #FAF277 글자, 바탕 없음) — 우리 브랜드를 앞에
        txt = f"트롯파파   출처 : {cfg['source_label'].replace('원본 ', '')}"
        y0, y1 = SPEC["src_y"]
        f = font(F_BOLD, 60)
        bb = f.getbbox(txt)
        f = font(F_BOLD, int(60 * (y1 - y0) / (bb[3] - bb[1])))
        im = Image.new("RGBA", (int(f.getlength(txt)) + 20, int((y1 - y0) * 2)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), txt, font=f, fill=hexrgb(SPEC["src_hex"]) + (255,))
        return frame_png(out, im.crop(im.getbbox()))
    """트롯파파 칩 — 출처 줄 자리. 알약(#1F1F1F, 테 #4D4D4D) + 빨강 점 + 브랜드 · 원본 표기."""
    f1, f2 = font(F_BRAND, 50), font(F_BOLD, 36)
    label2 = cfg["source_label"]
    w = int(28 + 22 + 16 + f1.getlength("트롯파파") + 26 + f2.getlength(label2) + 32)
    h = 92
    im = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([30, 38, 30 + w, 38 + h], radius=h // 2, fill=(0, 0, 0, 128))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(12)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([30, 30, 30 + w, 30 + h], radius=h // 2, fill=(31, 31, 31, 255), outline=(77, 77, 77, 255), width=2)
    cx = 30 + 28 + 11
    d.ellipse([cx - 11, 30 + h // 2 - 11, cx + 11, 30 + h // 2 + 11], fill=(255, 32, 26, 255))
    x = cx + 11 + 16
    d.text((x, 30 + h // 2), "트롯파파", font=f1, fill=(255, 255, 255, 255), anchor="lm")
    x += f1.getlength("트롯파파") + 26
    d.text((x, 30 + h // 2 + 2), label2, font=f2, fill=(179, 179, 179, 255), anchor="lm")
    return frame_png(out, im)


def cursor_icon(out: Path):
    if COPY:                                      # 원본 오른쪽 아래 아이콘 = 빨강·흰 짧은 화살표 ↙ (x840~973 y1256~1440)
        x0, y0, x1, y1 = SPEC["icon"]
        return frame_png(out, chunky_arrow(120, 135, 30, 80).resize((x1 - x0, y1 - y0), Image.LANCZOS))
    return cursor_icon_ours(out)


def cursor_icon_ours(out: Path):
    """오른쪽 아래 빨강·흰 커서(벤치 4/10편) — 우리 판은 테두리 두께·그림자를 더한다."""
    s = 4
    im = Image.new("RGBA", (130 * s, 150 * s), (0, 0, 0, 0))
    pts = [(20, 10), (20, 118), (48, 92), (68, 136), (88, 127), (68, 84), (106, 84)]
    pts = [(x * s, y * s) for x, y in pts]
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon([(x, y + 8 * s) for x, y in pts], fill=(0, 0, 0, 140))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(6 * s)))
    d = ImageDraw.Draw(im)
    d.polygon(pts, fill=(255, 255, 255, 255))
    inner = [(x * s, y * s) for x, y in [(30, 32), (30, 96), (50, 77), (70, 120), (77, 117), (58, 76), (86, 76)]]
    d.polygon(inner, fill=(255, 32, 26, 255))
    im = im.resize((130, 150), Image.LANCZOS)
    return frame_png(out, im)


# ── TTS ────────────────────────────────────────────────────
def tts(text, allow=True) -> Path:
    from tools.calcopy.engine import name_dict as ND
    spoken = ND.apply_all(text, VOICE)
    p = WORK / "tts" / (hashlib.sha1(f"{VOICE}|{spoken}".encode()).hexdigest()[:16] + ".mp3")
    if not p.exists():
        if not allow:
            raise SystemExit(f"TTS 캐시 없음: {text}")
        from shopping_shorts.channelkit import providers
        p.parent.mkdir(parents=True, exist_ok=True)
        providers.typecast_synth(VOICE)(spoken, str(p))
    return p


def tight(src: Path, out: Path, tempo: float) -> float:
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
         f"atempo={tempo:.3f},aformat=sample_rates=44100:channel_layouts=mono", out])
    return dur(out)


# ── 장면 ───────────────────────────────────────────────────
def cut(src, t, xfrac, d, out: Path):
    """원본 → 창(1080x860). 아래 18%(원본 박힌 자막 띠)를 빼고 가운데를 창 비율로 자른다."""
    ch = "ih*0.80"
    cw = f"{ch}*{W}/{WIN_H}"
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-t", f"{d:.3f}", "-an",
         "-vf", f"crop={cw}:{ch}:(iw-{cw})*{xfrac}:ih*0.02,scale={W}:{WIN_H},fps={FPS},setsar=1",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out])
    return out


def grab(src, t, out: Path):
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", out])
    return out


def cutout(img: Path, out: Path, box=None, model="bria-rmbg"):
    """누끼. 원본 박힌 자막 띠(아래 18%)는 먼저 잘라 낸다. box=[x0,y0,x1,y1](비율)면 그 안만.
    → (누끼 그림, 원본 잘린 그림 기준 bbox 왼위 좌표)"""
    from rembg import new_session, remove
    src = Image.open(img).convert("RGB")
    bx = box or [0, 0, 1, 0.82]
    crop = src.crop((int(bx[0] * src.width), int(bx[1] * src.height), int(bx[2] * src.width), int(bx[3] * src.height)))
    if not out.exists():
        import io
        b = io.BytesIO()
        crop.save(b, "PNG")
        out.write_bytes(remove(b.getvalue(), session=new_session(model)))
    im = Image.open(out).convert("RGBA")
    bb = im.getbbox()
    return im.crop(bb), bb, crop.size


def hook_frames(cfg, d, wd: Path):
    """훅: 근흑 바탕 + 누끼 인물(원본 장면) 천천히 줌 + (제품 누끼에 빨간 원을 그리는 효과 | 빨간 화살표)."""
    src = cfg["src"]
    hb = cfg["hook"].get("box", [0, 0, 1, 0.82])
    people, bb, csz = cutout(grab(src, cfg["hook"]["frame"], wd / "hook_src.png"), wd / "hook_cut.png", hb, "u2net_human_seg")
    sc = min(1180 / people.width, 1500 / people.height) if COPY else min(1040 / people.width, 1020 / people.height)
    people = people.resize((int(people.width * sc), int(people.height * sc)), Image.LANCZOS)
    circ = None
    if cfg["hook"].get("circle"):                       # 원본 비율 좌표 → 누끼 그림 좌표
        c = cfg["hook"]["circle"]
        fw, fh = csz[0] / (hb[2] - hb[0]), csz[1] / (hb[3] - hb[1])     # 원본 한 장 크기
        circ = [((c[0] - hb[0]) * fw - bb[0]) * sc, ((c[1] - hb[1]) * fh - bb[1]) * sc,
                ((c[2] - hb[0]) * fw - bb[0]) * sc, ((c[3] - hb[1]) * fh - bb[1]) * sc]
    n = int(round(d * FPS))
    fd = wd / "hook"
    fd.mkdir(exist_ok=True)
    for i in range(n):
        t = i / FPS
        z = 1.0 + (SPEC["hook_zoom"] if COPY else 0.07) * (t / max(d, 0.1))
        fr = Image.new("RGBA", (W, H), BG + (255,))
        pi = people.resize((int(people.width * z), int(people.height * z)), Image.BILINEAR)
        ox, oy = (W - pi.width) // 2, (H if COPY else 1500) - pi.height     # 원본 훅 = 화면 아래 끝까지 크게
        fr.alpha_composite(pi, (ox, oy))
        if circ is not None:
            per = SPEC["circle_period"] if COPY else None
            k = ((t % per) / per) if per else min(1.0, max(0.0, (t - 0.4) / 0.6))    # 원본: 0.77초마다 지우고 다시 그림
            k = 1 - (1 - k) ** 3                                  # ease-out
            if k > 0:
                box = [ox + v * z for v in (circ[0], circ[1])] + [ox + circ[2] * z, oy + circ[3] * z]
                box[1] = oy + circ[1] * z
                pad = 40
                ImageDraw.Draw(fr).arc([box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad], start=-90, end=-90 + 360 * k,
                                       fill=(244, 41, 24, 255), width=11 if COPY else 16)
        elif cfg["hook"].get("arrow") and (SPEC["hook_arrow"] or not COPY):
            ax, ay = cfg["hook"].get("arrow_copy", cfg["hook"]["arrow"]) if COPY else cfg["hook"]["arrow"]
            bob = 14 * math.sin(2 * math.pi * t / 0.8)
            fr.alpha_composite(arrow_img(), (ax + int(bob), ay + int(bob)))
        fr.convert("RGB").save(fd / f"{i:04d}.png")
    out = wd / "hook.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-framerate", FPS, "-i", fd / "%04d.png", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-pix_fmt", "yuv420p", out])
    return out


_ARROW = None


def arrow_img():
    if COPY:
        return chunky_arrow(190, 135, 38, 104)
    return arrow_img_ours()


def arrow_img_ours():
    """빨간 곡선 화살표 #FF1A31 흰 테(벤치 3편) — 위 오른쪽에서 출발해 아래 왼쪽 끝을 가리킨다(끝 = 그림 왼쪽 아래)."""
    global _ARROW
    if _ARROW is None:
        s = 3
        im = Image.new("RGBA", (340 * s, 340 * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        p0, p1, p2 = (300, 30), (250, 230), (70, 290)            # 2차 곡선
        pts = [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
                (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]) for u in [i / 40 for i in range(41)]]
        ex, ey = pts[-1]
        dx, dy = ex - pts[-4][0], ey - pts[-4][1]
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        tip = (ex + ux * 30, ey + uy * 30)
        head = [tip, (ex - uy * 34, ey + ux * 34), (ex + uy * 34, ey - ux * 34)]
        for col, wdt, grow in (((255, 255, 255, 255), 34, 9), ((255, 26, 49, 255), 20, 0)):
            d.line([(x * s, y * s) for x, y in pts], fill=col, width=wdt * s, joint="curve")
            hh = [(x + (x - ex) * grow / 34, y + (y - ey) * grow / 34) for x, y in head]
            d.polygon([(x * s, y * s) for x, y in hh], fill=col)
        _ARROW = im.resize((340, 340), Image.LANCZOS)
    return _ARROW


def reveal_frame(cfg, wd: Path) -> Path:
    """공개 카드 바탕: 제품 편 = 흰 바탕 + 제품 누끼 / 그 밖 = 원본 정지 장면."""
    src = cfg["src"]
    r = cfg["reveal"]
    canvas = Image.new("RGB", (W, WIN_H), (255, 255, 255))
    if r.get("box"):
        p, _, _ = cutout(grab(src, r["frame"], wd / "prod_src.png"), wd / "prod_cut.png", r["box"])
        sc = min(820 / p.width, 800 / p.height)
        p = p.resize((int(p.width * sc), int(p.height * sc)), Image.LANCZOS)
        canvas.paste(p, ((W - p.width) // 2, (WIN_H - p.height) // 2), p)
    else:
        g = Image.open(grab(src, r["frame"], wd / "reveal_src.png")).convert("RGB")
        ch = int(g.height * 0.80)
        cw = int(ch * W / WIN_H)
        g = g.crop(((g.width - cw) // 2, int(g.height * 0.02), (g.width - cw) // 2 + cw, int(g.height * 0.02) + ch))
        canvas = g.resize((W, WIN_H), Image.LANCZOS)
    out = wd / "reveal.png"
    canvas.save(out)
    return out


# ── 조립 ───────────────────────────────────────────────────
def make(cfg_path: Path, allow_tts=True):
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if COPY:
        load_spec(ROOT / cfg["bench"])
    wd = WORK / (cfg["slug"] + ("_copy" if COPY else ""))
    wd.mkdir(parents=True, exist_ok=True)
    segs = [("hook", cfg["hook"]["tts"])] + [(f"l{i}", l["tts"]) for i, l in enumerate(cfg["lines"])] + [("cta", cfg["cta"]["tts"])]
    raw = {k: tts(t, allow_tts) for k, t in segs}
    chars = sum(len(t.replace(" ", "")) for _, t in segs)
    rawd = sum(tight(raw[k], wd / f"n0_{k}.wav", 1.0) for k, _ in segs)     # 앞뒤 무음 뺀 실제 말 길이
    tempo = max(0.85, min(1.35, rawd / (chars / CPS)))   # 벤치 말속도(6.7자/초)에 맞춤
    tl, t, auds = [], 0.0, []
    for k, txt in segs:
        a = wd / f"n_{k}.wav"
        d = tight(raw[k], a, tempo)
        tl.append({"k": k, "text": txt, "t0": t, "t1": t + d})
        auds.append((a, t))
        t += d + 0.12
    hook_end = tl[0]["t1"] + 0.15
    reveal_t0 = tl[-1]["t1"] + 0.25
    total = reveal_t0 + 1.4

    # 창 영상: 줄마다 장면을 나눠 이어 붙임(훅 뒤부터 공개 전까지)
    parts = []
    spans = [(x["t0"] if i else hook_end, tl[i + 1]["t0"] if i + 1 < len(tl) else reveal_t0) for i, x in enumerate(tl)][1:]
    clip_lists = [l["clips"] for l in cfg["lines"]] + [[cfg["cta"]["clip"]]]
    for j, ((a, b), clips) in enumerate(zip(spans, clip_lists)):
        if j == 0:
            a = hook_end
        each = (b - a) / len(clips)
        for m, (st, xf) in enumerate(clips):
            parts.append(cut(cfg["src"], st, xf, each, wd / f"c{j}_{m}.mp4"))
    rv = reveal_frame(cfg, wd)
    parts.append(wd / "reveal.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", rv, "-t", f"{total - reveal_t0:.3f}", "-vf", f"fps={FPS},format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", parts[-1]])
    lst = wd / "parts.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    win = wd / "window.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", FPS, win])

    hook = hook_frames(cfg, hook_end + 0.3, wd)
    # 겹쳐 올릴 그림들
    ov = [(static_overlay(cfg, wd / "title.png"), 0, 0, 0, total, False)]
    chip = brand_chip(cfg, wd / "chip.png")
    ci = Image.open(chip)
    cx = 80 if COPY else (W - ci.width) // 2
    ov.append((chip, cx, SPEC["src_y"][0] if COPY else 1500 - ci.height // 2, hook_end, total, False))
    anim = not COPY                                   # 원본 = 바로 뜸(instant 130/144)
    subs = []
    for x, line in zip(tl[1:-1], cfg["lines"]):
        cs = chunks(x["text"])
        n = sum(len(c.replace(" ", "")) for c in cs)
        tt = x["t0"]
        for c in cs:
            d = (x["t1"] - x["t0"]) * len(c.replace(" ", "")) / n
            subs.append((c, tt, tt + d, line.get("key")))
            tt += d
    cta = tl[-1]
    for i, (c, a, b, key) in enumerate(subs if SUBS else []):
        if COPY:
            im = fit_text([(c, (255, 255, 255))], SPEC["cap"][1] - SPEC["cap"][0], SPEC["outline"])
        else:
            im = text_img(split_key(c, key if key and key in c else None), 84)
        p = frame_png(wd / f"sub{i:02d}.png", im)
        ov.append((p, (W - im.width) // 2, SPEC["cap"][0] if COPY else SUB_Y - im.height // 2, a, b, anim))
    for i, line in enumerate(cfg["cta"]["screen"] if SUBS else []):
        ch = SPEC["cta_y"][1] - SPEC["cta_y"][0]
        im = fit_text([(line, (255, 255, 255))], ch, SPEC["outline"]) if COPY else text_img([(line, (255, 255, 255))], 80)
        p = frame_png(wd / f"cta{i}.png", im)
        yy = SPEC["cta_y"][0] + i * int(ch * 1.25) if COPY else 1040 + i * 115 - im.height // 2
        ov.append((p, (W - im.width) // 2, yy, cta["t0"], reveal_t0, anim))
    for i, line in enumerate(cfg["reveal"]["lines"] if SUBS else []):
        im = text_img([(line, (255, 255, 255))], 92) if COPY else text_img(split_key(line, None) if i == 0 else [(line, YELLOW)], 92)
        p = frame_png(wd / f"rev{i}.png", im)
        ov.append((p, (W - im.width) // 2, 1080 + i * 120 - im.height // 2, reveal_t0, total, anim))
    cur = cursor_icon(wd / "cursor.png")

    # ffmpeg 그래프
    ins = ["-f", "lavfi", "-i", f"color=c=0x{BG[0]:02x}{BG[1]:02x}{BG[2]:02x}:s={W}x{H}:r={FPS}:d={total:.3f}", "-i", win, "-i", hook]
    g = [f"[0][1]overlay=0:{WIN_Y}:eof_action=pass[body]",
         f"[2]fps={FPS},format=yuv420p[hk]",
         f"[hk][body]xfade=transition={SPEC['hook_exit'][0] if COPY else 'circleopen'}:duration={SPEC['hook_exit'][1] if COPY else 0.3}:offset={hook_end:.3f}[base0]"]
    last = "base0"
    idx = 3
    for p, x, y, a, b, anim in ov:
        ins += ["-loop", "1", "-t", f"{total:.3f}", "-i", p]
        if anim:
            g.append(f"[{idx}]format=rgba,fade=in:st={a:.3f}:d=0.12:alpha=1[o{idx}]")
            ye = f"{y}+12*max(0\\,1-(t-{a:.3f})/0.12)"
        else:
            g.append(f"[{idx}]format=rgba[o{idx}]")
            ye = str(y)
        g.append(f"[{last}][o{idx}]overlay=x={x}:y='{ye}':enable='between(t,{a:.3f},{b:.3f})'[v{idx}]")
        last = f"v{idx}"
        idx += 1
    ins += ["-loop", "1", "-t", f"{total:.3f}", "-i", cur]
    g.append(f"[{last}][{idx}]overlay=x={SPEC['icon'][0] if COPY else 900}:y='{SPEC['icon'][1] if COPY else 1330}+{SPEC['icon_amp'] if COPY else 6}*sin(2*PI*t/{SPEC['icon_period'] if COPY else 0.7})':enable='between(t,{hook_end:.3f},{total:.3f})'[vout]")
    idx += 1
    # 소리: 나레 자리 맞춰 + BGM -24dB 깔기(나레 있을 때 더 낮춤)
    adel = []
    for j, (a, st) in enumerate(auds):
        ins += ["-i", a]
        adel.append(f"[{idx}]adelay={int(st * 1000)}|{int(st * 1000)},aformat=channel_layouts=stereo[a{j}]")
        idx += 1
    ins += ["-stream_loop", "-1", "-i", BGM]
    bg = idx
    g += adel
    g.append("".join(f"[a{j}]" for j in range(len(auds))) + f"amix=inputs={len(auds)}:normalize=0:duration=longest[narr]")
    g.append(f"[{bg}]atrim=0:{total:.3f},volume=0.10,aformat=channel_layouts=stereo[bgm]")
    g.append("[narr]asplit[n1][n2];[bgm][n2]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[duck]")
    g.append(f"[n1][duck]amix=inputs=2:normalize=0:duration=first,apad,atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    out = wd / f"트롯파파_{cfg['slug']}{'_원본판' if COPY else ''}{'' if SUBS else '_바탕'}.mp4"
    gfile = wd / "graph.txt"
    gfile.write_text(";\n".join(g), encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex_script", gfile, "-map", "[vout]", "-map", "[aout]",
         "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100", out])
    (wd / "timeline.json").write_text(json.dumps({"tempo": tempo, "total": total, "hook_end": hook_end, "reveal_t0": reveal_t0,
                                                  "segments": tl, "subs": subs}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완성 {out}  길이 {total:.2f}초  tempo {tempo:.2f}  자막 {len(subs)}줄")
    return out


if __name__ == "__main__":
    make(Path(sys.argv[1]), allow_tts="--no-tts" not in sys.argv)
