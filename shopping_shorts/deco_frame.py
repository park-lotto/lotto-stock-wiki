"""꾸미기 '내용물 있는 틀' — 1080x1920 RGBA 오버레이를 **그리는 유일한 곳**.

★0순위-B: 미리보기와 최종 렌더가 **이 함수 하나**를 쓴다.
  화면에서 CSS로 흉내내고 렌더에서 따로 그리면, 언젠가 반드시 어긋나서
  "미리보기랑 다르게 나왔다"가 된다. 그래서 미리보기도 여기가 만든 PNG를 받아 얹는다.

기존 12종(빈 색띠, deco_templates.py)은 그대로 살아 있다 — 이건 그 위에 얹는 새 갈래다.
저장된 작업이 옛 template를 가리키면 옛 경로가 계속 돈다(id 재사용·삭제 금지).
"""
import hashlib
import json
import pathlib

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
_FONT_DIR = pathlib.Path(__file__).resolve().parent / "static" / "fonts"

# 프리셋 = 사장님이 가져온 '실제로 잘되는' 유튜브 포맷.
# ★색·기본 높이를 여기 한 곳에서만 정한다. 화면 드롭다운도 이 표를 읽는다.
PRESETS = {
    "news_coral":  {"name": "커뮤니티 · 살구", "bar": "#F08080", "on_bar": "#FFFFFF"},
    "news_lime":   {"name": "커뮤니티 · 연두", "bar": "#B5D46A", "on_bar": "#1A1A1A"},
    "news_gray":   {"name": "커뮤니티 · 그레이", "bar": "#6E6E6E", "on_bar": "#FFFFFF"},
    "news_navy":   {"name": "커뮤니티 · 네이비", "bar": "#2B3A67", "on_bar": "#FFFFFF"},
}

# 기본 치수(1080x1920 기준). 사장님이 화면에서 바 높이를 조절하면 bar_h만 바뀐다.
DEFAULTS = {
    "preset": "news_coral",
    "bar_h": 190,          # 상단 띠 높이(px)
    "channel": "",         # 가짜 채널명
    "ad_badge": False,     # [광고] 뱃지
    "icons": True,         # ☰ / 🔍
    "title": "",           # 굵은 후킹 제목(자동 줄바꿈)
    "views": "",           # "264만"
    "comments": "",        # "587"
    "head_bg": "#FFFFFF",  # 제목·메타가 얹히는 흰 블록
}

_FONTS = {
    "bar": "Pretendard-Bold.otf",
    "title": "Pretendard-ExtraBold.otf",
    "meta": "Pretendard-Regular.otf",
}


def _font(kind, size):
    p = _FONT_DIR / _FONTS[kind]
    if p.exists():
        return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _rgb(hex_color):
    h = (hex_color or "#000000").lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def normalize(spec):
    """화면이 준 값에 기본값을 채우고 범위를 자른다.

    ★범위 검사도 여기 한 곳 — 화면과 서버가 따로 자르면 미리보기와 결과가 갈린다.
    """
    s = dict(DEFAULTS)
    for k, v in (spec or {}).items():
        if k in s:
            s[k] = v
    if s["preset"] not in PRESETS:
        s["preset"] = DEFAULTS["preset"]
    try:
        s["bar_h"] = int(s["bar_h"])
    except (TypeError, ValueError):
        s["bar_h"] = DEFAULTS["bar_h"]
    s["bar_h"] = max(0, min(400, s["bar_h"]))     # 0이면 띠 없음, 400 넘으면 화면을 먹는다
    for k in ("channel", "title", "views", "comments"):
        s[k] = str(s[k] or "").strip()[:60]
    s["ad_badge"] = bool(s["ad_badge"])
    s["icons"] = bool(s["icons"])
    return s


def cache_key(spec):
    """같은 spec이면 같은 파일 — 렌더마다 다시 그리지 않게."""
    s = normalize(spec)
    raw = json.dumps(s, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _wrap(draw, text, font, max_w):
    """글자 단위가 아니라 어절 단위로 접는다(한국어는 어절이 끊기면 못 읽는다)."""
    if not text:
        return []
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines[:3]        # 4줄부터는 제목이 아니라 본문이다


def _hamburger(d, cx, cy, color, w=54, gap=18, th=8):
    for i in (-1, 0, 1):
        y = cy + i * gap
        d.rounded_rectangle([cx - w // 2, y - th // 2, cx + w // 2, y + th // 2],
                            radius=th // 2, fill=color)


def _search(d, cx, cy, color, r=22, th=7):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=th)
    d.line([cx + r * 0.72, cy + r * 0.72, cx + r * 1.5, cy + r * 1.5],
           fill=color, width=th)


def render(spec):
    """spec → 1080x1920 RGBA 이미지. 가운데는 투명(영상이 비쳐야 한다)."""
    s = normalize(spec)
    p = PRESETS[s["preset"]]
    bar_col, on_bar = _rgb(p["bar"]), _rgb(p["on_bar"])

    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    bar_h = s["bar_h"]
    if bar_h > 0:
        d.rectangle([0, 0, W, bar_h - 1], fill=bar_col)   # PIL은 끝점 포함 → -1
        cy = bar_h // 2
        if s["icons"]:
            _hamburger(d, 92, cy, on_bar)
            _search(d, W - 96, cy, on_bar)
        if s["channel"]:
            f = _font("bar", max(28, int(bar_h * 0.30)))
            tw = d.textlength(s["channel"], font=f)
            d.text((W / 2 - tw / 2, cy), s["channel"], font=f, fill=on_bar, anchor="lm")
            if s["ad_badge"]:
                fb = _font("meta", 24)
                d.text((W / 2 + tw / 2 + 16, cy), "[광고]", font=fb, fill=on_bar, anchor="lm")

    # 제목·메타가 얹히는 흰 블록 — 내용이 있을 때만 그린다(빈 블록이 영상을 가리면 손해).
    y = bar_h
    if s["title"] or s["views"] or s["comments"]:
        ft = _font("title", 62)
        fm = _font("meta", 30)
        lines = _wrap(d, s["title"], ft, W - 120)
        line_h = 78
        meta = ""
        if s["views"]:
            meta = f"조회수 {s['views']}"
        if s["comments"]:
            meta = (meta + " | " if meta else "") + f"댓글 {s['comments']}개"
        block_h = 36 + len(lines) * line_h + (52 if meta else 0) + 24
        d.rectangle([0, y, W, y + block_h - 1], fill=_rgb(s["head_bg"]))
        ty = y + 36
        for ln in lines:
            d.text((W / 2, ty), ln, font=ft, fill=(20, 20, 20, 255), anchor="ma")
            ty += line_h
        if meta:
            d.text((60, ty + 6), meta, font=fm, fill=(120, 120, 120, 255), anchor="la")
            ty += 46
            d.rectangle([60, ty + 8, W - 60, ty + 11], fill=(30, 30, 30, 255))
    return im


def cache_path(spec):
    """그림 파일이 놓일 자리. ★화면(API)과 렌더(mix_pipeline)가 **같은 자리**를 봐야
    미리보기에서 만든 그림을 렌더가 그대로 쓴다. 경로를 두 곳에 적지 않는다(0순위-B)."""
    return (pathlib.Path(__file__).resolve().parent / "data" / "frame_cache"
            / f"{cache_key(spec)}.png")


def render_to(spec, out_path):
    """파일로 저장하고 경로를 돌려준다. 이미 있으면 다시 그리지 않는다(cache_key가 같으면 같은 그림)."""
    out_path = pathlib.Path(out_path)
    if out_path.exists():
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    render(spec).save(out_path, "PNG")
    return out_path
