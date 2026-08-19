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
#
# ══════════════════════════════════════════════════════════════════════════
# 2026-08-20 — 썰쇼핑 상위 20채널 실측 벤치마킹 (사장님: "유튜브 썰체널들
# 엄청많이 모여있으니 20개체널 디자인을 그대로 가져와서 / 똑같이 하면안되고
# 살짝씩 비틀어서 / 해드카피도 이 템플릿들과 맞춰서 한 세트로")
#
# 출처: 서버 reference.db의 썰쇼핑 태깅 채널 107개 → 채널별 최다조회 쇼츠를
#       YouTube API로 뽑아 조회수 상위 20개의 실제 썸네일을 내려받아 픽셀 실측.
#       실측 원장: docs/reference/썰쇼핑_상위20_썸네일실측.json
#
# ★"그대로"가 아니라 "살짝 비틀어서"(사장님 지시):
#   - 구조(띠+아이콘+2줄 헤드라인+흰 자막바)는 원본 그대로 — 이게 잘 되는 이유다
#   - 색조는 원본에서 의도적으로 밀었다(원본 헥사를 그대로 쓰지 않는다)
#   - 채널명은 **비워둔 채** 시작한다. 실제 채널명을 기본값으로 박으면 남의
#     상표를 그대로 내보내게 된다 — 사장님이 직접 적어야 한다.
#
# ★headcopy = 이 틀에 글자가 '딱 들어가는' 한 세트(폰트·크기·색·배치).
#   틀마다 띠 높이가 다르므로 헤드카피 y가 같으면 어떤 틀에선 띠에 먹힌다.
#   그래서 틀과 글자를 **한 벌로** 정의한다 — 고르면 둘 다 같이 적용된다.
# ══════════════════════════════════════════════════════════════════════════
#
# bar_h/white_h는 1920 기준 px(실측 %를 환산). ref=벤치마킹한 원본 채널.
def _hc(font, size, color, color2, y, outline_w=12):
    """헤드카피 한 세트. color=1줄, color2=2줄(형광 강조)."""
    return {"font": font, "size": size, "color": color, "color2": color2,
            "y": y, "weight": 900, "outline": True, "outline_color": "#000000",
            "outline_w": min(12, outline_w)}   # ★화면 슬라이더 상한이 12 — 넘기면 잘린다


PRESETS = {
    # ── ① 컬러 UI 바 + ☰🔍 (가장 전형·상위권 다수) ─────────────────────
    "sul_pink": {
        "name": "커뮤니티 핑크", "ref": "살림킹왕짱(1,050만)",
        "bar": "#F98B8C", "on_bar": "#FFFFFF", "bar_h": 268, "white_h": 210,
        "headcopy": _hc("BMDOHYEON.ttf", 88, "#FFFFFF", "#7BF7D0", 26),
    },
    "sul_coral": {
        "name": "커뮤니티 코랄", "ref": "방구석꿀템(263만)",
        "bar": "#FB5F5C", "on_bar": "#FFFFFF", "bar_h": 272, "white_h": 150,
        "headcopy": _hc("BMDOHYEON.ttf", 90, "#FFFFFF", "#8CFFD6", 27),
    },
    "sul_teal": {
        "name": "커뮤니티 청록", "ref": "이거였네(85만)",
        "bar": "#0B6C82", "on_bar": "#FFFFFF", "bar_h": 294, "white_h": 190,
        "headcopy": _hc("BMJUA.ttf", 86, "#FFFFFF", "#FFE14D", 29),
    },
    "sul_navy": {
        "name": "커뮤니티 네이비", "ref": "꿀팁꿀템(55만)",
        "bar": "#1F2A55", "on_bar": "#FFFFFF", "bar_h": 230, "white_h": 160,
        "headcopy": _hc("BMDOHYEON.ttf", 86, "#FFFFFF", "#66D9FF", 24),
    },
    "sul_olive": {
        "name": "커뮤니티 올리브", "ref": "쇼핑 치트키(219만)",
        "bar": "#6B7C52", "on_bar": "#FFFFFF", "bar_h": 172, "white_h": 190,
        "headcopy": _hc("BMDOHYEON.ttf", 92, "#FFFFFF", "#FF5B5B", 19),
    },
    "sul_sand": {
        "name": "커뮤니티 샌드", "ref": "무슨템(40만)",
        "bar": "#7E7357", "on_bar": "#FFFFFF", "bar_h": 176, "white_h": 120,
        "headcopy": _hc("BMJUA.ttf", 88, "#FFFFFF", "#FFD84D", 20),
    },
    "sul_brick": {
        "name": "커뮤니티 벽돌", "ref": "활용정점(1,214만)",
        "bar": "#C34B4B", "on_bar": "#FFFFFF", "bar_h": 152, "white_h": 200,
        "headcopy": _hc("BMDOHYEON.ttf", 90, "#FFFFFF", "#7BF7D0", 17),
    },
    "sul_wine": {
        "name": "커뮤니티 와인", "ref": "럭키박스(246만)",
        "bar": "#7A4444", "on_bar": "#FFFFFF", "bar_h": 240, "white_h": 200,
        "headcopy": _hc("BMDOHYEON.ttf", 88, "#FFFFFF", "#FFB3C7", 25),
    },
    "sul_forest": {
        "name": "커뮤니티 포레스트", "ref": "다있슈(47만)",
        "bar": "#42706B", "on_bar": "#FFFFFF", "bar_h": 172, "white_h": 190,
        "headcopy": _hc("BMJUA.ttf", 88, "#FFFFFF", "#9CFF7B", 19),
    },
    "sul_plum": {
        "name": "커뮤니티 자두", "ref": "코어장바구니(122만)",
        "bar": "#5E2A38", "on_bar": "#FFFFFF", "bar_h": 220, "white_h": 120,
        "headcopy": _hc("BMDOHYEON.ttf", 86, "#FFFFFF", "#FFD84D", 24),
    },

    # ── ② 어두운/반투명 바 (영상 위에 얹힌 느낌) ────────────────────────
    "sul_ink": {
        "name": "다크 잉크", "ref": "쇼핑천재(104만)",
        "bar": "#121214", "on_bar": "#FFFFFF", "bar_h": 328, "white_h": 130,
        "headcopy": _hc("BMDOHYEON.ttf", 92, "#FFFFFF", "#FFE14D", 31),
    },
    "sul_charcoal": {
        "name": "다크 차콜", "ref": "이븐쇼핑(88만)",
        "bar": "#26262A", "on_bar": "#FFFFFF", "bar_h": 174, "white_h": 200,
        "headcopy": _hc("BMDOHYEON.ttf", 90, "#FFFFFF", "#7BF7D0", 19),
    },
    "sul_slate": {
        "name": "다크 슬레이트", "ref": "나만또모르고있었지(46만)",
        "bar": "#3C4147", "on_bar": "#FFFFFF", "bar_h": 140, "white_h": 160,
        "headcopy": _hc("BMJUA.ttf", 86, "#FFFFFF", "#66D9FF", 16),
    },
    "sul_midnight": {
        "name": "다크 미드나잇", "ref": "요새난리(44만)",
        "bar": "#0A0F26", "on_bar": "#FFFFFF", "bar_h": 160, "white_h": 120,
        "headcopy": _hc("BMDOHYEON.ttf", 94, "#FFFFFF", "#FFE14D", 18),
    },
    "sul_smoke": {
        "name": "다크 스모크", "ref": "살림장착(104만)",
        "bar": "#1C1D22", "on_bar": "#FFFFFF", "bar_h": 274, "white_h": 170,
        "headcopy": _hc("BMDOHYEON.ttf", 88, "#FFFFFF", "#8CFFD6", 27),
    },
    "sul_graphite": {
        "name": "다크 그라파이트", "ref": "집돌이(29만)",
        "bar": "#232428", "on_bar": "#FFFFFF", "bar_h": 124, "white_h": 120,
        "headcopy": _hc("BMDOHYEON.ttf", 90, "#FFFFFF", "#FFD84D", 14),
    },

    # ── ③ 밝은 톤·가벼운 UI ──────────────────────────────────────────
    "sul_cream": {
        "name": "라이트 크림", "ref": "가구공방/집돌이 계열(29만)",
        "bar": "#C4834F", "on_bar": "#FFFFFF", "bar_h": 208, "white_h": 120,
        "headcopy": _hc("BMJUA.ttf", 86, "#FFFFFF", "#FF5B5B", 23),
    },
    "sul_khaki": {
        "name": "라이트 카키", "ref": "썰칩12(415만)",
        "bar": "#6E6B54", "on_bar": "#FFFFFF", "bar_h": 118, "white_h": 120,
        "headcopy": _hc("BMDOHYEON.ttf", 92, "#FFFFFF", "#9CFF7B", 13),
    },
    "sul_stone": {
        "name": "라이트 스톤", "ref": "인생갓템(47만)",
        "bar": "#857A5C", "on_bar": "#FFFFFF", "bar_h": 176, "white_h": 140,
        "headcopy": _hc("BMDOHYEON.ttf", 88, "#FFFFFF", "#FFE14D", 20),
    },
    "sul_rose": {
        "name": "라이트 로즈", "ref": "달래샵(69만)",
        "bar": "#D98C8C", "on_bar": "#FFFFFF", "bar_h": 222, "white_h": 120,
        "headcopy": _hc("BMJUA.ttf", 88, "#FFFFFF", "#3BE0B0", 24),
    },

    # ── 기존 4종(옛 작업이 가리키고 있다 — id 재사용·삭제 금지) ──────────
    "news_coral":  {"name": "커뮤니티 · 살구", "bar": "#F08080", "on_bar": "#FFFFFF"},
    "news_lime":   {"name": "커뮤니티 · 연두", "bar": "#B5D46A", "on_bar": "#1A1A1A"},
    "news_gray":   {"name": "커뮤니티 · 그레이", "bar": "#6E6E6E", "on_bar": "#FFFFFF"},
    "news_navy":   {"name": "커뮤니티 · 네이비", "bar": "#2B3A67", "on_bar": "#FFFFFF"},
}

# 기본 치수(1080x1920 기준). 사장님이 화면에서 바 높이를 조절하면 bar_h만 바뀐다.
DEFAULTS = {
    "preset": "news_coral",
    "bar_h": 190,          # 상단 띠 높이(px)
    "bottom_h": 0,         # 하단 띠 높이(px) — 0이면 없음
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
    # ★프리셋이 자기 띠 높이를 갖고 있으면 그게 기본이다(실측한 원본 비율).
    #   화면이 bar_h를 직접 보내오면 그건 사장님이 손으로 민 것이므로 존중한다.
    #   이 분기가 없으면 20종이 전부 같은 190px 띠가 돼 "비율이 원본과 다르다"가 된다.
    p = PRESETS[s["preset"]]
    if "bar_h" not in (spec or {}) and p.get("bar_h"):
        s["bar_h"] = p["bar_h"]
    # 위·아래 띠는 **같은 규칙**으로 자른다 — 한쪽만 다르게 자르면 언젠가 어긋난다
    for k in ("bar_h", "bottom_h"):
        try:
            s[k] = int(s[k])
        except (TypeError, ValueError):
            s[k] = DEFAULTS[k]
        s[k] = max(0, min(400, s[k]))    # 0이면 띠 없음, 400 넘으면 화면을 먹는다
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

    if s["bottom_h"] > 0:
        d.rectangle([0, H - s["bottom_h"], W, H - 1], fill=bar_col)

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
