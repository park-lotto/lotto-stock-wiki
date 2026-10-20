# -*- coding: utf-8 -*-
"""여행 숏폼 장면 공방 — 장면 한 장을 '사람이 한 땀 한 땀' 만든 것처럼 (관제 239, 2026-10-20 사장님).

사장님: "공장에서 찍어낸 자동화가 아니라 정말 공들여 사람이 만들었구나 — 디테일이 핵심" /
        "댓글 설명엔 관련 이미지 — 하나가 아니라 고객 사진 여러 장으로 신뢰" / "폴라로이드·액자·손글씨" /
        "우리는 직접 가 본 게 아니라 소개하는 사람"
→ 장면 = 실제 투숙객 사진 여러 장(후기에서, 출처 표기) + 그 손님이 쓴 말(글자 그대로) + 예능 자막 한마디.

판단 주인(이 파일 한 곳):
  scene_photos   — 장면 키워드가 든 후기의 사진을 모아 오푸스가 직접 보고 '그게 실제로 보이는' 사진을 고른다
  review_snippet — 그 후기에서 키워드가 든 말 한 토막(글자 그대로, 손글씨 메모용)
  STYLES         — 장면 틀(폴라로이드·액자 갤러리·손글씨 메모장·스크랩북·후기 말풍선) → 1080×1920 PNG 한 장
렌더·캡컷은 이 PNG 를 사진 컷처럼 쓴다(같은 파일 → 길마다 같은 그림).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from pathlib import Path

W, H = 1080, 1920
_FONT_DIR = Path(__file__).resolve().parent / "static" / "fonts"
HAND_FONTS = {   # 손글씨 — 프로젝트에 이미 있는 OFL 글꼴
    "pen": "NanumPenScript.ttf", "gaegu": "Gaegu-Bold.ttf", "gamja": "GamjaFlower.ttf",
    "melody": "HiMelody.ttf", "dokdo": "EastSeaDokdo.ttf", "poor": "PoorStory.ttf",
}
SOURCE_NOTE = "실제 투숙객 사진 · 출처: %s"


def font(name, size):
    from PIL import ImageFont
    if name in HAND_FONTS:
        return ImageFont.truetype(str(_FONT_DIR / HAND_FONTS[name]), size)
    from shopping_shorts.video_assemble import _resolve_font
    return ImageFont.truetype(_resolve_font(), size)


# ── 사진 고르기 ────────────────────────────────────────────────────────────────
_PICK_PROMPT = (
    "숙소 영상의 한 장면에 쓸 **실제 투숙객 사진**을 고른다. 장면 주제: %s (핵심어: %s).\n"
    "사진 photo_1~%d 를 다 열어 보고 고른다:\n"
    "- 주제가 **실제로 또렷하게 보이는** 사진만(짬뽕이면 짬뽕 그릇이 보여야 한다). 주제와 상관없는 사진·흐린 사진 제외.\n"
    "- 사람 얼굴이 알아볼 수 있게 크게 나온 사진·아이 사진은 제외(초상권). 손·뒷모습은 괜찮다.\n"
    "- 여러 장을 이어 붙인 콜라주·다른 음식(케이크 등)이 더 크게 나온 사진은 제외 — 주제가 화면의 주인공이어야 한다.\n"
    "- 고른 것끼리 각도·구도가 겹치지 않게(같은 장면 두 장 금지). 가장 좋은 것부터 최대 %d장.\n"
    "JSON: {\"pick\": [{\"n\": 사진번호, \"why\": \"한 줄\"}]}")


def _key(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]


_SCREEN_SCHEMA = {"type": "object", "properties": {"photos": {"type": "array", "items": {
    "type": "object", "properties": {"n": {"type": "integer"}, "shows": {"type": "boolean"}, "face": {"type": "boolean"}},
    "required": ["n", "shows", "face"]}}}, "required": ["photos"]}


def _screen(got, topic, work):
    """1차 거르기 — 12장 격자로 '주제가 보이나'만(무료 제미나이, 끊기면 하이쿠). 통과한 것만 오푸스에게 간다."""
    from shopping_shorts import travel_build as tb
    keep = []
    for gi in range(0, len(got), 12):
        chunk = got[gi:gi + 12]
        grid = tb.make_grid([g["path"] for g in chunk], Path(work) / ("screen_%02d.jpg" % (gi // 12)))
        prompt = ("격자 사진 1~%d(왼쪽 위부터 번호). 각 사진에 '%s'이(가) 또렷하게 보이면 shows=true. "
                  "사람 얼굴이 알아볼 수 있게 크게 나오면 face=true." % (len(chunk), topic))
        ans = None
        try:
            from shopping_shorts.edit_plan import _vault_call_image
            ans = _vault_call_image(prompt, _SCREEN_SCHEMA, grid)
        except Exception:
            ans = None
        if not ans:
            try:
                ans = tb.claude_call([grid], prompt + '\nJSON: {"photos": [{"n": 1, "shows": true, "face": false}]}', model="haiku")
            except Exception:
                ans = {}
        for x in (ans or {}).get("photos") or []:
            k = int(x.get("n", 0)) - 1
            if 0 <= k < len(chunk) and x.get("shows") and not x.get("face"):
                keep.append(chunk[k])
    return keep


def scene_photos(reviews, keys, topic, work, want=5, pool=120, call=None):
    """keys(핵심어 목록) 중 하나가 든 사진 후기 → 사진 전부 받기 → 1차 거르기(제미나이 격자) → 오푸스가 보고 고른 것.
    ★후기 첫 사진·앞 3장만 보면 대부분 객실이다(실측 2026-10-20 짬뽕: 14장 중 2장, 27장 중 1장) — 후기 사진을 다 보고 거른다.
    고른 것은 한 후기에서 한 장만(여러 손님의 사진이 되도록 = 신뢰). 반환 [{path, url, review, why}]."""
    from concurrent.futures import ThreadPoolExecutor
    from shopping_shorts import travel_build as tb
    call = call or tb.claude_call
    work = Path(work)
    cands = [r for r in reviews if r.get("images") and any(k in r.get("content", "") for k in keys)]
    # 앞 핵심어(가장 좁은 말)가 든 후기 먼저, 그 안에서 베스트·공감 순 — 넓은 말(룸서비스)이 앞자리를 다 차지하면
    # 받은 120장에 짬뽕이 0장이 된다(실측 2026-10-20 keys=[짬뽕,해물짬뽕,룸서비스] → 0장, [짬뽕]만 → 5장)
    first = lambda r: min(i for i, k in enumerate(keys) if k in r.get("content", ""))
    cands.sort(key=lambda r: (first(r), -(r.get("best") or 0), -(r.get("likes") or 0)))
    jobs = [(url, r) for r in cands for url in r["images"]][:pool]

    def fetch(job):
        url, r = job
        p = work / "rv_photos" / (_key(url) + ".jpg")
        try:
            if not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                tb.download(url, p)
            return {"path": str(p), "url": url, "review": r}
        except Exception:
            return None
    with ThreadPoolExecutor(8) as ex:
        got = [g for g in ex.map(fetch, jobs) if g]
    got = _screen(got, topic, work)[:30]
    if not got:
        return []
    ans = call([g["path"] for g in got], _PICK_PROMPT % (topic, ", ".join(keys), len(got), want * 2))
    out, seen_rv = [], set()
    for x in ans.get("pick") or []:
        k = int(x.get("n", 0)) - 1
        if 0 <= k < len(got) and id(got[k]["review"]) not in seen_rv:
            seen_rv.add(id(got[k]["review"]))
            out.append(dict(got[k], why=x.get("why", "")))
    return out[:want]


_QUOTE_PROMPT = (
    "숙소 후기 몇 개다. 각 후기에서 '%s'에 대한 **뜻이 통하는 한 구절**을 글자 하나 바꾸지 말고 그대로 잘라 온다"
    "(6~16자, 맞춤법·띄어쓰기 원문 그대로). 사진 옆에 손글씨로 붙일 말이다 — 감탄·평가가 담긴 구절이 좋다"
    "(예: '인생 짬뽕', '짬뽕 진짜 맛있어요'). 가격 숫자만 있는 구절은 피한다.\n\n%s\n\nJSON: {\"quotes\": [{\"n\": 번호, \"q\": \"\"}]}")


def photo_quotes(reviews, keys, topic):
    """사진마다 붙일 손님 말 — 오푸스가 뜻이 통하는 구절을 고르고, 원문에 글자 그대로 있는지 검사(없으면 기계 자르기로)."""
    from shopping_shorts import travel_build as tb
    def around(t):
        """핵심어 주변만 — 앞 500자만 주면 핵심어가 뒤에 나오는 후기는 답이 안 온다(4개 중 1개만 답한 실측 2026-10-20)."""
        t = re.sub(r"\s+", " ", t or "")
        i = min([t.find(k) for k in keys if k in t] or [0])
        return t[max(0, i - 150): i + 250]
    body = "\n".join("%d) %s" % (i + 1, around(r.get("content", ""))) for i, r in enumerate(reviews))
    body += "\n\n후기마다 반드시 하나씩(번호 %d개 전부)." % len(reviews)
    try:
        got = tb.claude_call([], _QUOTE_PROMPT % (topic, body), model="opus")
    except Exception:
        got = {}
    by = {int(x.get("n", 0)) - 1: (x.get("q") or "").strip() for x in got.get("quotes") or []}
    out = []
    for i, r in enumerate(reviews):
        q = by.get(i, "")
        # 띄어쓰기만 다른 것은 같은 말로 본다(4개 중 3개가 공백 차이로 떨어진 실측 2026-10-20) — 글자는 원문 그대로여야 한다
        ok = q and re.sub(r"\s+", "", q) in re.sub(r"\s+", "", r.get("content", ""))
        out.append(q if ok else review_snippet(r.get("content", ""), keys, 16))
    return out


def review_snippet(text, keys, max_len=18):
    """후기에서 핵심어가 든 말 한 토막 — **글자 그대로**(실제 말투). 문장부호·줄바꿈에서 자른다."""
    t = re.sub(r"\s+", " ", text or "")
    for k in keys:
        i = t.find(k)
        if i < 0:
            continue
        parts = re.split(r"(?<=[.!?~ㅎㅋ])\s+|[\n·•]", t)
        for s in parts:
            if k in s:
                s = s.strip(" -\"'")
                if len(s) <= max_len:
                    return s
                j = s.find(k)
                a = max(0, min(j - max_len // 3, len(s) - max_len))
                cut = s[a:a + max_len]
                if " " in cut[3:]:            # 단어 중간에서 끊지 않게 앞뒤를 띄어쓰기에 맞춘다
                    cut = cut[cut.find(" ") + 1:] if a > 0 else cut
                    cut = cut[:cut.rfind(" ")] if a + max_len < len(s) else cut
                return ("…" if a > 0 else "") + cut.strip() + ("…" if a + max_len < len(s) else "")
    return ""


# ── 그리기 도구 ─────────────────────────────────────────────────────────────────
def _cover(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s) + 1, int(img.height * s) + 1))
    return img.crop(((img.width - w) // 2, (img.height - h) // 2, (img.width - w) // 2 + w, (img.height - h) // 2 + h))


def _open(p):
    from PIL import Image, ImageOps
    return ImageOps.exif_transpose(Image.open(p)).convert("RGB")


def _shadow(layer, box_img, xy, blur=14, offset=(10, 16), alpha=120):
    from PIL import Image, ImageFilter
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    m = box_img.split()[-1].point(lambda v: alpha if v > 0 else 0)
    sh.paste((0, 0, 0, alpha), (xy[0] + offset[0], xy[1] + offset[1]), m)
    layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))


def _tape(draw, cx, cy, w=150, h=46, ang=0, color=(250, 236, 170, 200)):
    a = math.radians(ang)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)))
    draw.polygon(pts, fill=color)


def _paper_bg(kind="paper", seed=0, bg_photo=None):
    """배경 — 종이(크림·크래프트·모눈) 또는 숙소 사진 흐림. 결이 살짝 있는 종이로(평평한 단색이면 공장 티가 난다)."""
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(seed)
    if kind == "photo" and bg_photo:
        bg = _cover(_open(bg_photo), W, H).filter(ImageFilter.GaussianBlur(22))
        return Image.blend(bg, Image.new("RGB", (W, H), (18, 18, 22)), 0.35).convert("RGBA")
    base = {"paper": (247, 241, 228), "kraft": (214, 186, 146), "grid": (250, 249, 244), "cork": (196, 154, 108)}[kind]
    img = Image.new("RGB", (W, H), base)
    px = img.load()
    for _ in range(26000):        # 종이 결(점 잡음)
        x, y = rnd.randrange(W), rnd.randrange(H)
        dv = rnd.randint(-10, 10)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + dv)), max(0, min(255, g + dv)), max(0, min(255, b + dv)))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    d = ImageDraw.Draw(img)
    if kind == "grid":
        for x in range(0, W, 54):
            d.line([(x, 0), (x, H)], fill=(214, 226, 240), width=2)
        for y in range(0, H, 54):
            d.line([(0, y), (W, y)], fill=(214, 226, 240), width=2)
    return img.convert("RGBA")


def _polaroid(photo_path, w, caption="", hand="pen", tilt=0):
    """폴라로이드 한 장 — 흰 테두리(아래 넓게) + 손글씨 한 줄."""
    from PIL import Image, ImageDraw
    pw = w - 2 * int(w * 0.06)
    ph = int(pw * 1.0)
    side = int(w * 0.06)
    card = Image.new("RGBA", (w, side + ph + int(w * 0.26)), (252, 251, 247, 255))
    card.paste(_cover(_open(photo_path), pw, ph), (side, side))
    if caption:
        d = ImageDraw.Draw(card)
        f = font(hand, int(w * 0.11))
        while d.textlength(caption, font=f) > w - 2 * side and f.size > 24:
            f = font(hand, f.size - 2)
        d.text(((w - d.textlength(caption, font=f)) / 2, side + ph + int(w * 0.05)), caption, font=f, fill=(40, 40, 60, 255))
    return card.rotate(tilt, resample=Image.BICUBIC, expand=True)


def _frame(photo_path, w, h, style="wood"):
    """액자 — 나무/금색 테 + 흰 매트."""
    from PIL import Image, ImageDraw
    t = int(w * 0.07)
    mat = int(w * 0.06)
    fr = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(fr)
    col = {"wood": [(120, 80, 48), (150, 104, 66)], "gold": [(176, 138, 58), (220, 186, 104)], "black": [(30, 30, 30), (60, 60, 60)]}[style]
    d.rectangle((0, 0, w, h), fill=col[0] + (255,))
    d.rectangle((t // 3, t // 3, w - t // 3, h - t // 3), fill=col[1] + (255,))
    d.rectangle((t, t, w - t, h - t), fill=(250, 248, 242, 255))
    fr.paste(_cover(_open(photo_path), w - 2 * (t + mat), h - 2 * (t + mat)), (t + mat, t + mat))
    return fr


def _source_tag(layer, text, y=None):
    from PIL import ImageDraw
    d = ImageDraw.Draw(layer)
    f = font("", 30)
    tw = d.textlength(text, font=f)
    y = y if y is not None else H - 96
    d.rounded_rectangle(((W - tw) / 2 - 20, y, (W + tw) / 2 + 20, y + 50), 25, fill=(0, 0, 0, 150))
    d.text(((W - tw) / 2, y + 8), text, font=f, fill=(255, 255, 255, 235))


def _title(layer, text, hand="gaegu", y=150, color=(30, 30, 40), size=92, mark=(255, 226, 90)):
    """손글씨 제목 + 형광펜 밑줄."""
    from PIL import ImageDraw
    d = ImageDraw.Draw(layer)
    f = font(hand, size)
    tw = d.textlength(text, font=f)
    x = (W - tw) / 2
    d.rounded_rectangle((x - 16, y + size * 0.55, x + tw + 16, y + size * 1.05), 14, fill=mark + (200,))
    d.text((x, y), text, font=f, fill=color + (255,))


# ── 장면 틀 ─────────────────────────────────────────────────────────────────────
def style_polaroid(photos, title, snippets, source, seed=0, bg="cork", reserve_bottom=False):
    """코르크판(또는 크래프트지) 위 폴라로이드 3~5장 흩뿌리기 + 마스킹테이프 + 손님 말 손글씨.
    reserve_bottom = 예능 자막 자리(아래 1/4)를 비운다 — 4장을 위쪽에 모은다(자막이 사진을 덮은 실측 2026-10-20)."""
    from PIL import ImageDraw
    rnd = random.Random(seed)
    layer = _paper_bg(bg, seed)
    _title(layer, title, y=120)
    if reserve_bottom:
        slots = [(70, 330, -6), (570, 300, 6), (110, 860, 4), (590, 820, -5)][:len(photos)]
    else:
        slots = [(90, 380, -7), (560, 330, 6), (300, 860, 3), (70, 1250, -4), (600, 1200, 8)][:len(photos)]
    hands = ["pen", "gaegu", "gamja", "melody", "poor"]
    for i, (ph, (x, y, ang)) in enumerate(zip(photos, slots)):
        card = _polaroid(ph["path"], 430, snippets[i] if i < len(snippets) else "", hands[i % len(hands)], ang + rnd.uniform(-2, 2))
        _shadow(layer, card, (x, y))
        layer.alpha_composite(card, (x, y))
        d = ImageDraw.Draw(layer)
        _tape(d, x + card.width / 2 + rnd.randint(-30, 30), y + 18, ang=ang + rnd.uniform(-8, 8),
              color=rnd.choice([(250, 236, 170, 210), (255, 196, 210, 200), (190, 226, 250, 200)]))
    _source_tag(layer, SOURCE_NOTE % source)
    return layer


def style_gallery(photos, title, snippets, source, seed=0, **_):
    """전시회 벽 — 액자 3~4점 + 작품 설명 카드(손님 말)."""
    from PIL import ImageDraw
    layer = _paper_bg("paper", seed)
    d = ImageDraw.Draw(layer)
    d.rectangle((0, 1700, W, H), fill=(176, 148, 116, 255))          # 바닥
    _title(layer, title, hand="melody", y=110, mark=(200, 230, 255))
    boxes = [(80, 330, 560, 520, "wood"), (600, 360, 400, 400, "gold"), (130, 920, 420, 420, "black"), (590, 840, 420, 560, "wood")][:len(photos)]
    for i, (ph, (x, y, w, h, st)) in enumerate(zip(photos, boxes)):
        fr = _frame(ph["path"], w, h, st)
        _shadow(layer, fr, (x, y), offset=(8, 18))
        layer.alpha_composite(fr, (x, y))
        if i < len(snippets) and snippets[i]:
            f = font("pen", 44)
            tw = d.textlength(snippets[i], font=f)
            cx, cy = x + w / 2 - tw / 2 - 18, y + h + 22
            d.rectangle((cx, cy, cx + tw + 36, cy + 62), fill=(255, 255, 255, 240), outline=(200, 200, 200, 255))
            d.text((cx + 18, cy + 8), snippets[i], font=f, fill=(50, 50, 60, 255))
    _source_tag(layer, SOURCE_NOTE % source)   # 맨 아래 — 1760 은 말 자막 띠와 겹쳤다(2026-10-20 콘티)
    return layer


def style_memo(photos, title, tips, source, seed=0, **_):
    """모눈 노트에 손글씨 꿀팁 + 형광펜 + 클립으로 꽂은 사진 두 장."""
    from PIL import ImageDraw
    rnd = random.Random(seed)
    layer = _paper_bg("grid", seed)
    d = ImageDraw.Draw(layer)
    d.line([(120, 0), (120, H)], fill=(240, 140, 140, 255), width=4)             # 노트 여백선
    _title(layer, title, hand="pen", y=110, size=110)
    y = 330
    for i, t in enumerate(tips[:5]):
        f = font(rnd.choice(["pen", "gaegu"]), 84)
        d.text((160, y), "✔", font=font("", 52), fill=(230, 80, 80, 255))
        lines = []
        cur = ""
        for w_ in t.split(" "):
            if d.textlength(cur + " " + w_, font=f) > W - 260 and cur:
                lines.append(cur)
                cur = w_
            else:
                cur = (cur + " " + w_).strip()
        lines.append(cur)
        for ln in lines[:2]:
            if i == 0:
                d.rounded_rectangle((220, y + 30, 230 + d.textlength(ln, font=f), y + 70), 10, fill=(255, 232, 100, 180))
            d.text((230, y), ln, font=f, fill=(35, 40, 70, 255))
            y += 98
        y += 40
    for k, ph in enumerate(photos[:2]):
        card = _polaroid(ph["path"], 380, "", tilt=(-6 if k == 0 else 7))
        x0, y0 = (130, 1330) if k == 0 else (560, 1290)
        _shadow(layer, card, (x0, y0))
        layer.alpha_composite(card, (x0, y0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((x0 + card.width / 2 - 18, y0 - 30, x0 + card.width / 2 + 18, y0 + 50), 10, fill=(170, 170, 180, 255))  # 클립
    _source_tag(layer, SOURCE_NOTE % source)
    return layer


def style_scrapbook(photos, title, snippets, source, seed=0, stickers=("⭐", "💛", "🌊"), **_):
    """크래프트지 스크랩북 — 사진을 찢은 종이처럼 겹쳐 붙이고 스티커·날짜 도장."""
    from PIL import Image, ImageDraw, ImageFont
    rnd = random.Random(seed)
    layer = _paper_bg("kraft", seed)
    _title(layer, title, hand="dokdo", y=120, size=120, color=(60, 30, 10), mark=(255, 255, 255))
    spots = [(70, 360, 560, 440, -3), (470, 620, 540, 420, 4), (90, 1010, 520, 430, 2), (500, 1240, 500, 400, -5)][:len(photos)]
    for i, (ph, (x, y, w, h, ang)) in enumerate(zip(photos, spots)):
        im = _cover(_open(ph["path"]), w, h).convert("RGBA")
        bd = Image.new("RGBA", (w + 24, h + 24), (255, 255, 255, 255))
        bd.alpha_composite(im, (12, 12))
        bd = bd.rotate(ang, resample=Image.BICUBIC, expand=True)
        _shadow(layer, bd, (x, y), offset=(6, 10), blur=8)
        layer.alpha_composite(bd, (x, y))
        if i < len(snippets) and snippets[i]:
            d = ImageDraw.Draw(layer)
            f = font("gamja", 50)
            tw = d.textlength(snippets[i], font=f)
            tx, ty = min(W - tw - 60, x + 30), y + bd.height - 30
            d.rounded_rectangle((tx - 14, ty - 6, tx + tw + 14, ty + 60), 12, fill=(255, 250, 235, 235))
            d.text((tx, ty), snippets[i], font=f, fill=(90, 50, 20, 255))
    d = ImageDraw.Draw(layer)
    try:
        ef = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", 109)
        for s, (sx, sy) in zip(stickers, [(880, 300), (60, 860), (900, 1600)]):
            d.text((sx, sy), s, font=ef, embedded_color=True)
    except Exception:
        pass
    _source_tag(layer, SOURCE_NOTE % source)
    return layer


def style_review_stack(photos, title, reviews_text, source, seed=0, reserve_bottom=False, **_):
    """사진 한 장 크게 + 실제 후기 말풍선이 차곡차곡(여러 손님이 같은 말을 한다는 느낌).
    reserve_bottom = 자막 자리를 비운다 — 사진을 줄이고 말풍선 3개를 위로(자막과 겹친 실측 2026-10-20)."""
    from PIL import ImageDraw
    layer = _paper_bg("photo", seed, bg_photo=photos[0]["path"] if photos else None)
    pw, py0 = (W - 360, 230) if reserve_bottom else (W - 200, 230)
    if photos:
        bd = _polaroid(photos[0]["path"], pw, "", tilt=-2)
        _shadow(layer, bd, ((W - bd.width) // 2, py0))
        layer.alpha_composite(bd, ((W - bd.width) // 2, py0))
    _title(layer, title, hand="gaegu", y=90, color=(255, 255, 255), mark=(255, 92, 53))
    d = ImageDraw.Draw(layer)
    y = 960 if reserve_bottom else 1180
    f = font("", 40)
    for i, t in enumerate(reviews_text[:3 if reserve_bottom else 4]):
        x = 90 if i % 2 == 0 else 200
        tw = min(d.textlength(t, font=f), W - x - 120)
        d.rounded_rectangle((x, y, x + tw + 56, y + 76), 38, fill=(255, 255, 255, 240))
        d.text((x + 28, y + 14), t, font=f, fill=(30, 30, 36, 255))
        y += 104
    _source_tag(layer, SOURCE_NOTE % source)
    return layer


STYLES = {"폴라로이드": style_polaroid, "전시회 액자": style_gallery, "손글씨 메모": style_memo,
          "스크랩북": style_scrapbook, "후기 말풍선": style_review_stack}


def make_scene(style, photos, title, texts, out_path, source="여기어때", seed=0, variety=None):
    """장면 한 장 = 틀(style) + (선택) 예능 자막(travel_build.variety_caption_png). 1080×1920 PNG."""
    from PIL import Image
    src = source if not (variety and variety.get("count")) else "%s · 후기 %s명이 같은 말" % (source, variety["count"])
    layer = STYLES[style](photos[:4] if variety else photos, title, texts, src, seed=seed, reserve_bottom=bool(variety))
    if variety:      # 자막은 아래 비워 둔 자리에(맨 아래 띠는 말 자막 자리 — 0.83→0.80, 2026-10-20 콘티), 도장은 출처 표기에 합쳤으니 끈다(겹침 실측 2026-10-20)
        from shopping_shorts import travel_build as tb
        ov = tb.variety_caption_png(variety, str(Path(out_path).with_suffix(".cap.png")), palette=seed, y_ratio=0.80, stamp=False)
        layer.alpha_composite(Image.open(ov))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    layer.convert("RGB").save(out_path, quality=92)
    return str(out_path)


# ── 말 자막(우리 자막팩) ─────────────────────────────────────────────────────────
def caption_pack(key="tension"):
    """자막팩 정의는 static/caption-motions.js 의 CAPTION_PACKS(/*PACKS*/ 표식 사이 JSON) 한 곳 — 장면꾸미기와 같은 것을 읽는다."""
    src = (Path(__file__).parent / "static" / "caption-motions.js").read_text(encoding="utf-8")
    m = re.search(r"/\*PACKS\*/(\{.*?\n\})\s*;?\s*/\*PACKS\*/", src, re.S) or re.search(r"/\*PACKS\*/(\{.*?\n \}\n\})", src, re.S)
    return json.loads(m.group(1))[key]


def _hex(c, a=255):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def narration_caption_png(text, out_path, emph="", pack="tension", y_ratio=0.70, scale=0.85):
    """말 자막 한 장(투명 1080×1920) — 자막팩 글꼴·크기·외곽선 그대로, 강조 단어 뒤에 팩 색 상자(예능 텐션 = 노란 상자).
    미리보기용 정지 그림이다. 영상의 자막은 장면꾸미기 자막팩 엔진이 같은 팩으로 그린다."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    p = caption_pack(pack)
    W, H = 1080, 1920
    size = int(p.get("size", 112) * scale)
    f = ImageFont.truetype(str(next(_FONT_DIR.glob(p["font"] + ".*"))), size)
    col = _hex(p["text"]["color"])
    stroke = max(4, int(size * 0.07))
    box = _hex((p.get("wordFx") or {}).get("color", "#FFE600"))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    words, lines, cur = text.split(), [], ""
    for w in words:                                   # 폭에 맞춰 어절 단위로 줄바꿈(최대 2줄)
        t = (cur + " " + w).strip()
        if cur and d.textlength(t, font=f) > W - 140:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    lh = int(size * 1.25)
    y0 = int(H * y_ratio) - lh * len(lines) // 2
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for i, ln in enumerate(lines):
        x = (W - d.textlength(ln, font=f)) / 2
        y = y0 + i * lh
        if emph and emph in ln:                       # 강조 단어 상자 — 글자보다 먼저(뒤에) 깐다
            ex = x + d.textlength(ln[:ln.find(emph)], font=f)
            ew = d.textlength(emph, font=f)
            d.rounded_rectangle((ex - 14, y - 6, ex + ew + 14, y + size + 16), 14, fill=box)
        sd.text((x, y + size * 0.05), ln, font=f, fill=(0, 0, 0, 180), stroke_width=stroke, stroke_fill=(0, 0, 0, 180))
    layer = Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(size * 0.08)), layer)
    d = ImageDraw.Draw(layer)
    for i, ln in enumerate(lines):
        x = (W - d.textlength(ln, font=f)) / 2
        d.text((x, y0 + i * lh), ln, font=f, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    layer.save(out_path)
    return str(out_path)
