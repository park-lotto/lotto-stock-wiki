# -*- coding: utf-8 -*-
"""카드뉴스 렌더러 — 정본 `renderer.ts`(683줄, canvas)의 PIL 이식본.

자릿수는 `cardnews_layout.py` 가 맡는다(차동검증 n=500 · 18,292항목 · 불일치 0).
여기서는 **그 자리에 실제로 칠하는 일**만 한다.

■ 캔버스와 PIL 이 어긋나는 지점 — 여기서 틀리면 그림이 달라진다
    캔버스                          PIL
    ─────────────────────────────  ──────────────────────────────────────
    textBaseline='alphabetic'      anchor='ls'(왼쪽) / 직접 누적(가운데)
    ctx.measureText(t).width       font.getlength(t)  ※폴백 감안 필요
    shadowBlur = b                 GaussianBlur(radius=b/2)
                                   ★캔버스 shadowBlur 는 표준편차의 **2배** 규격
    없는 글자 자동 대체(폰트 폴백)   ★안 한다 → 직접 구현(split_runs)
    그라데이션 디더링               ★안 한다 → 직접 구현(_dither)

■ 왜 폰트를 두 개 받는가
    정본은 제목을 가족 최대 굵기로, 본문을 **500** 으로 그린다(`renderer.ts:559`
    `ctx.font = '500 ...'`). 브라우저는 `fontLoaderService` 가 등록한 여러 @font-face
    중에서 500 에 맞는 것을 알아서 고르지만, PIL 은 파일을 직접 받아야 한다.
    한 파일로 둘 다 그리면 본문까지 초굵게 나와 **위계가 사라진다**(1차 이식본의 실패).
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import cardnews_layout as L

# ── 폰트 ────────────────────────────────────────────────────

_FONT_CACHE = {}
_CMAP_CACHE = {}

#: 없는 글자를 대신 그릴 폰트. 호출부가 폰트팩 경로로 바꿔 넣는다.
#: 실측: 138가족 중 79종(57%)이 공백·₩·…·따옴표 중 하나 이상을 안 갖고 있다
#: (공백 U+0020 이 없는 가족만 9종). 브라우저는 이걸 몰래 메워주고 PIL 은 안 메운다.
FALLBACK_FONT = None


def set_fallback_font(path):
    """폴백 폰트를 지정한다. 없는 파일을 주면 즉시 알린다 — 조용히 넘기지 않는다."""
    global FALLBACK_FONT
    if path is not None and not os.path.exists(path):
        raise FileNotFoundError(f"폴백 폰트가 없습니다: {path}")
    FALLBACK_FONT = path


def load_font(path, size):
    key = (path, int(size))
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, int(size))
    return _FONT_CACHE[key]


def _cmap(path):
    """이 폰트가 가진 글자 집합. 파일당 한 번만 읽는다."""
    if path not in _CMAP_CACHE:
        from fontTools.ttLib import TTFont

        _CMAP_CACHE[path] = set(TTFont(path, lazy=True).getBestCmap().keys())
    return _CMAP_CACHE[path]


def split_runs(text, font, size):
    """글자를 '이 폰트로 그릴 구간' 과 '폴백으로 그릴 구간' 으로 쪼갠다.

    브라우저가 글자 단위로 폰트를 갈아끼우는 것과 같은 동작이다.
    폴백이 지정돼 있지 않으면 쪼개지 않는다(=원래 폰트로 두부가 찍힌다).
    조용히 다른 폰트로 바꾸지 않기 위해서다 — 폴백은 **명시해야** 걸린다."""
    if not text:
        return []
    if not FALLBACK_FONT or not getattr(font, "path", None):
        return [(text, font)]
    have = _cmap(font.path)
    runs, cur, cur_ok = [], "", None
    for ch in text:
        ok = ord(ch) in have
        if cur_ok is None or ok == cur_ok:
            cur += ch
            cur_ok = ok
        else:
            runs.append((cur, cur_ok))
            cur, cur_ok = ch, ok
    runs.append((cur, cur_ok))
    fb = None
    out = []
    for t, ok in runs:
        if ok:
            out.append((t, font))
        else:
            if fb is None:
                fb = load_font(FALLBACK_FONT, size)
            out.append((t, fb))
    return out


def text_length(text, font, size):
    """폴백까지 감안한 실제 폭 — 캔버스 measureText 와 같은 값이어야 한다."""
    return sum(f.getlength(t) for t, f in split_runs(text, font, size))


# ── 색 · 그라데이션 ─────────────────────────────────────────


def hex_rgb(h):
    c = L.parse_hex_color(h)
    return (c["r"], c["g"], c["b"]) if c else (0, 0, 0)


# 8×8 Bayer — 그라데이션 띠(밴딩) 제거용 결정적 디더 패턴.
#
# 왜 필요한가: 1080px 폭에 색이 몇 단계밖에 안 변하는 완만한 그라데이션은 8비트로
# 양자화하면 **동심원/가로 띠**로 보인다. 브라우저 캔버스는 자체 디더를 넣어 이걸
# 감추지만 PIL 은 그냥 반올림해서 띠가 그대로 남는다(사진 없는 카드에서 실제로 보였다).
# 난수가 아니라 고정 패턴을 쓰는 이유는 **같은 입력이면 같은 PNG** 가 나와야 하기 때문이다.
_BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=np.float64)


def _dither(arr):
    """부동소수 채널값(0~255) → 디더링한 uint8. 띠 대신 미세한 점무늬가 된다."""
    h, w = arr.shape[:2]
    t = (_BAYER8 + 0.5) / 64.0 - 0.5  # -0.5 ~ +0.5
    tile = np.tile(t, (h // 8 + 1, w // 8 + 1))[:h, :w]
    if arr.ndim == 3:
        tile = tile[:, :, None]
    return np.clip(arr + tile, 0, 255).astype(np.uint8)


def linear_gradient(size, p0, p1, c0, c1):
    """캔버스 createLinearGradient 과 같은 축 투영 보간 (+ 디더링)."""
    w, h = size
    x = np.arange(w, dtype=np.float64)[None, :]
    y = np.arange(h, dtype=np.float64)[:, None]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    denom = dx * dx + dy * dy
    t = np.zeros((h, w)) if denom == 0 else ((x - p0[0]) * dx + (y - p0[1]) * dy) / denom
    t = np.clip(t, 0.0, 1.0)
    a = np.array(c0, dtype=np.float64)
    b = np.array(c1, dtype=np.float64)
    return Image.fromarray(_dither(a[None, None, :] + (b - a)[None, None, :] * t[:, :, None]), "RGB")


def radial_alpha(size, center, radius, a0, a1):
    """중심에서 바깥으로 흐려지는 알파 마스크 (코너 글로우, + 디더링)."""
    w, h = size
    x = np.arange(w, dtype=np.float64)[None, :]
    y = np.arange(h, dtype=np.float64)[:, None]
    d = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)
    t = np.clip(d / max(radius, 1e-9), 0.0, 1.0)
    return Image.fromarray(_dither((a0 + (a1 - a0) * t) * 255.0), "L")


def vertical_shade(size, stops):
    """세로 다단 그라데이션 — 캔버스 addColorStop 여러 개와 같다.

    stops = [(위치0~1, (r,g,b), 알파0~1), ...]"""
    w, h = size
    ys = np.linspace(0.0, 1.0, h)
    pos = np.array([s[0] for s in stops])
    rgb = np.array([s[1] for s in stops], dtype=np.float64)
    alp = np.array([s[2] for s in stops], dtype=np.float64)
    col = np.stack([np.interp(ys, pos, rgb[:, i]) for i in range(3)], axis=1)
    col = col[:, None, :].repeat(w, axis=1)
    mask = (np.interp(ys, pos, alp) * 255.0)[:, None].repeat(w, axis=1)
    return Image.fromarray(_dither(col), "RGB"), Image.fromarray(_dither(mask), "L")


#: 정본 drawShade 의 색·알파 그대로 (rgba(6,7,12,·)).
SHADE_STOPS = {
    "bottom": [(0.0, (6, 7, 12), 0.12), (0.5, (6, 7, 12), 0.02),
               (0.72, (6, 7, 12), 0.55), (1.0, (6, 7, 12), 0.92)],
    "top": [(0.0, (6, 7, 12), 0.9), (0.32, (6, 7, 12), 0.5),
            (0.55, (6, 7, 12), 0.05), (1.0, (6, 7, 12), 0.25)],
    "center": [(0.0, (6, 7, 12), 0.18), (0.35, (6, 7, 12), 0.6),
               (0.65, (6, 7, 12), 0.6), (1.0, (6, 7, 12), 0.18)],
}


# ── 텍스트 ──────────────────────────────────────────────────


def _run_prefix_width(text, upto, font, size):
    """앞에서 `upto` 글자까지의 폭. 폴백 구간이 섞여도 맞게 잰다."""
    if upto <= 0:
        return 0.0
    w, seen = 0.0, 0
    for t, f in split_runs(text, font, size):
        if seen + len(t) <= upto:
            w += f.getlength(t)
            seen += len(t)
        else:
            w += f.getlength(t[:upto - seen])
            break
    return w


def mark_range(text, mark):
    """강조할 낱말의 글자 범위. 못 찾으면 None.

    ★실물이 실제로 쓰는 문법이다 — `@detailed` 는 `EVERYTHING **DISNEY** JUST
      ANNOUNCED` 처럼 낱말 하나만 빨강으로 칠하고, `@newstoon556` 은 `**전쟁** 편
      출간!` 을 그렇게 쓴다. 박스도 밑줄도 없다.
    ★못 찾으면 **아무것도 강조하지 않는다.** 비슷한 자리를 찾아 칠하지 않는다 —
      엉뚱한 낱말이 강조되면 뜻이 바뀐다."""
    if not mark:
        return None
    i = text.find(mark)
    return None if i < 0 else (i, i + len(mark))


def draw_text(img, xy, text, font, fill, centered, size,
              shadow_blur=0.0, shadow_rgba=None,
              mark=None, mark_fill=None):
    """baseline 기준 글자 그리기 (+ 그림자, + 글자 단위 폰트 폴백, + 낱말 강조).

    가운데 정렬은 PIL 의 'ms' 앵커를 쓰지 않고 **총 폭을 재서 시작점을 잡는다** —
    구간마다 폰트가 다를 수 있어 앵커 하나로는 못 맞춘다.

    ■ 낱말 강조를 **글자 단위로 그리지 않는다**
        한 글자씩 따로 그리면 커닝이 사라져 자리가 밀린다(실제로 그렇게 만들었다가
        고쳤다). 대신 **같은 문장을 강조색으로 한 번 더 그리고 그 낱말 구간만
        오려서** 덮는다. 글자 위치가 바뀔 여지가 없다."""
    runs = split_runs(text, font, size)
    if not runs:
        return
    total = sum(f.getlength(t) for t, f in runs)
    x0 = xy[0] - total / 2 if centered else xy[0]

    def paint(target, ox, oy, color):
        x = x0 + ox
        d = ImageDraw.Draw(target)
        for t, f in runs:
            d.text((x, xy[1] + oy), t, font=f, fill=color, anchor="ls")
            x += f.getlength(t)

    if shadow_blur > 0 and shadow_rgba:
        pad = int(shadow_blur * 3) + 8
        lay = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
        paint(lay, pad, pad, shadow_rgba)
        lay = lay.filter(ImageFilter.GaussianBlur(radius=shadow_blur / 2.0))
        img.alpha_composite(lay.crop((pad, pad, pad + img.width, pad + img.height)))
    paint(img, 0, 0, fill)

    rng = mark_range(text, mark) if mark_fill else None
    if rng:
        a = x0 + _run_prefix_width(text, rng[0], font, size)
        b = x0 + _run_prefix_width(text, rng[1], font, size)
        lay = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 0))
        paint(lay, 0, 0, mark_fill)
        x1 = max(0, int(a) - 2)
        x2 = min(img.width, int(b) + 3)
        if x2 > x1:
            img.alpha_composite(lay.crop((x1, 0, x2, img.height)), (x1, 0))


def rounded_rect(img, rect, fill):
    r = min(rect["radius"], rect["w"] / 2, rect["h"] / 2)
    d = ImageDraw.Draw(img)
    box = (rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"])
    if r <= 0:
        d.rectangle(box, fill=fill)
    else:
        d.rounded_rectangle(box, radius=r, fill=fill)


# ── 카드 1장 ────────────────────────────────────────────────


def fit_title_size(font_path, text, target_ratio, width, height,
                  template, backdrop_color="#FFFFFF"):
    """줄 잉크 높이가 `target_ratio` 가 되는 `title_size_px` 를 **그려서** 찾는다.

    ■ 왜 필요한가 (2026-08-17)
        실물 레퍼런스의 제목은 우리 기본값(92px)보다 훨씬 크다 — 실측 잉크 높이
        비율 0.094~0.101 이면 글꼴에 따라 **138~150px** 다. 크기가 다르면
        같은 글꼴이라도 전혀 다른 물건으로 보인다.

    ■ ★산식을 지어내지 않는다
        글꼴마다 잉크 높이가 다르고 받침 유무로도 달라진다. 이 저장소는 그것 때문에
        어랍숏 대사가 25% 컸던 적이 있다(합성 표본에 받침이 없었다).
        그래서 **실제로 그려서 재고** 이웃을 확인한다. 잉크 높이는 크기에 거의
        비례하므로 한 번 재서 풀고 네 이웃만 더 본다.
    """
    # ★재는 판은 **언제나 흰 바탕 + 검은 글자**로 만든다.
    #   실제 배경색을 깔고 «흰색과 다른 화소»를 세면 **화면 전체가 글자**가 된다
    #   (실측: @lifebookcase 파란 바탕 → 12px · @ho1y_time → 271px 라는 엉뚱한 값).
    #   잉크 높이는 배경색과 무관하므로 재는 판만 고정하면 된다.
    p = dict(template)
    p["shade"] = "none"
    p["plate"] = "none"
    p["frame"] = "none"
    p["deco"] = "none"
    p["ink"] = "dark"

    def ratio_at(px):
        card = render_card(width, height, text, "", "", p, font_path,
                           title_size_px=px, accent_color="#FFFFFF",
                           highlight="none", backdrop_color="#FFFFFF")
        a = np.asarray(card.convert("RGB")).astype(np.int32)
        h = a.shape[0]
        # ★실물을 잴 때와 **똑같은 기준**을 쓴다 — 흰 바탕과의 채널 차 합이 40 초과.
        #   한쪽은 회색 차 40, 한쪽은 3채널 합 40 이었더니 같은 그림에서 잉크
        #   높이가 **두 배** 차이 났고(0.10 vs 0.21) 크기가 절대 안 맞았다.
        #   그리고 열을 건너뛰지 않는다 — 가는 획을 놓친다.
        #   (2026-10-08: 같은 기준을 numpy 로 — 화소 하나씩 도는 파이썬 이중 반복이 한 번에 1.4백만 번이라
        #    렌더에서 부를 수 없었다. 판정식은 그대로다.)
        rows = ((765 - a.sum(2)) > 40).sum(1)
        on = np.flatnonzero(rows > 0)
        if not len(on):
            return 0.0
        # 가장 긴 연속 구간(=제목 줄)
        best = cur = 0
        prev = None
        for i in on:
            cur = cur + 1 if (prev is not None and i == prev + 1) else 1
            best = max(best, cur)
            prev = i
        return best / h

    # ★비례식으로 풀 수 없다 — **폭 자동축소** 때문이다.
    #   문구가 길면 크기를 올려도 렌더러가 폭에 맞춰 줄여서 잉크 높이가 **포화**한다
    #   (실측: 580px 를 줘도 결과가 0.08 에 머문다). 비례로 찍으면 절대 안 맞는다.
    #   그래서 **실제로 그려서 재며 이분 탐색**한다. 못 닿으면 못 닿는다고 말한다.
    lo, hi = 24, 320
    r_hi = ratio_at(hi)
    r_lo = ratio_at(lo)
    if r_lo <= 0:
        return None
    if target_ratio >= r_hi:
        # ★아무리 키워도 못 닿는다 — **문구 길이가 다르기 때문**이다.
        #   실물 제목이 두세 글자로 크게 박혀 있으면 그 비율(예: 0.34)은 우리
        #   문구가 길 때 도달할 수 없다(폭에 맞춰 줄어든다).
        #   그럴 때는 **닿을 수 있는 최대**를 주고 그것이 최대라고 말한다 —
        #   억지로 키워 봐야 렌더러가 다시 줄인다.
        return hi
    if target_ratio <= r_lo:
        return lo
    for _ in range(9):
        mid = (lo + hi) // 2
        if ratio_at(mid) < target_ratio:
            lo = mid
        else:
            hi = mid
    return lo if abs(ratio_at(lo) - target_ratio) <= abs(ratio_at(hi) - target_ratio) else hi


class DirtyTextError(ValueError):
    """카드에 찍힐 글자에 이스케이프 흔적·제어 문자가 남아 있다."""


def assert_clean_text(**texts):
    """★렌더 직전 글자 검사 — 역슬래시(«\\n» 두 글자 같은 이스케이프 흔적, 한글 글꼴에선 «₩n» 으로 보인다)·«₩n»·제어 문자가
    글자로 남아 있으면 그리지 않고 실패로 올린다(10-08 실측 @anavocado12345 2~4번 카드 본문에 «\\n» 이 그대로 찍혔다).
    줄 바꿈(진짜 \\n)은 본문·부제에서만 허용한다."""
    bad = []
    for k, v in texts.items():
        if not isinstance(v, str):
            continue
        if "\\" in v or "₩n" in v or any(ord(ch) < 32 and not (ch == "\n" and k in ("body", "subtitle")) for ch in v):
            bad.append(f"{k}={v[:40]!r}")
    if bad:
        raise DirtyTextError("카드 글자에 이스케이프 흔적·제어 문자가 있어 그리지 않습니다: " + " · ".join(bad))


def render_card(
    width,
    height,
    title_line1,
    title_line2,
    body,
    template,
    font_path,
    title_size_px,
    accent_color,
    highlight,
    image_path=None,
    page_index=None,
    page_count=1,
    body_font_path=None,
    shade_stops=None,
    emphasis_word=None,
    backdrop_color=None,
    title_ratio=None,
    layout=None,
    handle=None,
    kicker=None,
    subtitle=None,
):
    """정본 `renderCardToCanvas` 의 ①~⑦ 순서를 그대로 따른다.

    `body_font_path` — 본문 전용 굵기 파일. 없으면 제목 파일을 쓴다(굵기 1개 가족).
    `shade_stops` — 가독 그늘의 색·알파. **서버가 준다.** 없으면 정본 값을 쓴다.
      러너에 값을 박으면 서버가 고쳐도 안 따라온다.
    `emphasis_word` — `highlight='word'` 일 때 강조색으로 칠할 낱말(2행 안의 부분문자열).
      못 찾으면 아무것도 강조하지 않는다."""
    assert_clean_text(title_line1=title_line1, title_line2=title_line2, body=body, kicker=kicker, subtitle=subtitle,
                      handle=handle, emphasis_word=emphasis_word)
    body_font_path = body_font_path or font_path
    line1 = (title_line1 or "").strip()
    line2 = (title_line2 or "").strip()
    body_lines = [l.strip() for l in (body or "").split("\n") if l.strip()][:3]

    # ★레퍼런스를 **재서** 만든 배치가 있으면 틀 12종을 거치지 않고 잰 자리·크기·색으로 그린다(2026-10-08).
    if layout:
        return render_layout_card(width, height, line1, line2, body_lines, layout, font_path,
                                  body_font_path=body_font_path, image_path=image_path,
                                  page_index=page_index, page_count=page_count,
                                  emphasis_word=emphasis_word, shade_stops=shade_stops,
                                  accent_color=accent_color, handle=handle, kicker=kicker, subtitle=subtitle)
    # ★레퍼런스 글자 크기 비율이 오면 **이 카드의 문구로** 크기를 역산한다(2026-10-08 수리).
    #   전에는 미리보기(`/render`)만 역산하고 실제 산출물은 92px 로 그려 «미리보기와 결과가 다른» 자리였다.
    #   두 길이 이 한 곳을 지난다. 폭에 걸리는 쪽(더 긴 줄)으로 잰다 — 두 줄은 같은 크기로 그려진다.
    if title_ratio:
        f100 = load_font(font_path, 100)
        probe = max((t for t in (line1, line2) if t), key=lambda t: text_length(t, f100, 100), default="")
        if probe:
            fitted = fit_title_size(font_path, probe, float(title_ratio), width, height, template)
            if fitted:
                title_size_px = fitted

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    is_polaroid = template["frame"] == "polaroid"

    # ① 배경 — 프레임 / 사진 / 셰이드
    if is_polaroid:
        ImageDraw.Draw(img).rectangle((0, 0, width, height), fill=(250, 249, 246, 255))
    photo = L.compute_photo_rect(width, height, template["frame"])

    def backdrop(rect, ink):
        """사진이 없는 카드의 배경. 새까만 판이 아니라 강조색을 머금은 딥톤이다 —
        정본 주석: 고정 검정이던 시절 사용자가 '고장난 화면' 으로 읽었다(피드백 3건).

        ★`backdrop_color` 를 주면 **그 색으로 통째로** 칠한다. 실물 레퍼런스 중에는
          사진도 그림도 아니고 **연분홍 단색** 위에 글자만 얹는 계정이 있다
          (@anavocado12345 · @ho1y_time — 가장자리 밝기편차 0.0). 그걸 강조색에서
          유도한 딥톤으로 그리면 전혀 다른 물건이 된다."""
        if backdrop_color:
            ImageDraw.Draw(img).rectangle(
                (rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"]),
                fill=hex_rgb(backdrop_color) + (255,))
            return
        bd = L.compute_no_image_backdrop(accent_color, ink)
        g = linear_gradient((rect["w"], rect["h"]), (0, 0), (rect["w"], rect["h"]),
                            hex_rgb(bd["from"]), hex_rgb(bd["to"])).convert("RGBA")
        cx, cy = rect["w"] * 0.78, rect["h"] * 0.2
        radius = max(rect["w"], rect["h"]) * 0.62
        a = 0.16 if ink == "dark" else 0.13
        glow = Image.new("RGBA", (rect["w"], rect["h"]), hex_rgb(bd["glow"]) + (255,))
        glow.putalpha(radial_alpha((rect["w"], rect["h"]), (cx, cy), radius, a, 0.0))
        g.alpha_composite(glow)
        img.alpha_composite(g, (rect["x"], rect["y"]))

    if image_path:
        src = Image.open(image_path).convert("RGBA")
        fit = L.compute_cover_fit(src.width, src.height, photo["w"], photo["h"])
        if not is_polaroid:
            ImageDraw.Draw(img).rectangle(
                (photo["x"], photo["y"], photo["x"] + photo["w"], photo["y"] + photo["h"]),
                fill=(13, 13, 16, 255))
        scaled = src.resize((max(1, L.js_round(fit["dw"])), max(1, L.js_round(fit["dh"]))),
                            Image.LANCZOS)
        # 사진 영역 밖은 잘라낸다 (캔버스 clip 과 같다)
        sx, sy = max(0, -L.js_round(fit["dx"])), max(0, -L.js_round(fit["dy"]))
        layer = Image.new("RGBA", (photo["w"], photo["h"]), (0, 0, 0, 0))
        layer.alpha_composite(scaled, dest=(0, 0), source=(
            sx, sy, min(scaled.width, sx + photo["w"]), min(scaled.height, sy + photo["h"])))
        img.alpha_composite(layer, (photo["x"], photo["y"]))
        if not is_polaroid and template["shade"] != "none":
            if template["shade"] == "full":
                fa = float((shade_stops or {}).get("full_alpha") or 0.55)
                img.alpha_composite(
                    Image.new("RGBA", (width, height), (6, 7, 12, L.js_round(fa * 255))))
            else:
                stops = ((shade_stops or {}).get(template["shade"])
                         or SHADE_STOPS[template["shade"]])
                stops = [(float(a), tuple(b), float(c)) for a, b, c in stops]
                col, mask = vertical_shade((width, height), stops)
                col = col.convert("RGBA")
                col.putalpha(mask)
                img.alpha_composite(col)
    elif not is_polaroid:
        backdrop({"x": 0, "y": 0, "w": width, "h": height}, template["ink"])
    else:
        backdrop(photo, "dark")

    # ② fit-to-width → fit-to-zone (제목 두 줄 공통 스케일 — 줄별 축소는 위계를 깬다)
    avail_width = width - L.js_round(width * L.SIDE_PAD_FRAC) * 2
    base_font = load_font(font_path, title_size_px)
    measured = max(text_length(line1, base_font, title_size_px) if line1 else 0,
                   text_length(line2, base_font, title_size_px) if line2 else 0)
    width_fitted = L.compute_fitted_font_size(measured, title_size_px, avail_width)
    zf = L.compute_zone_fitted_layout(width, height, width_fitted, bool(line1), bool(line2),
                                      len(body_lines), template["anchor"], template["frame"])
    layout, fitted_title = zf["layout"], zf["titleSizePx"]

    centered = template["align"] == "center"
    anchor_x = width / 2 if centered else layout["textX"]
    dark_ink = template["ink"] == "dark"
    title_ink = (23, 23, 30, 255) if dark_ink else (255, 255, 255, 255)
    body_ink = ((23, 23, 30, L.js_round(0.82 * 255)) if dark_ink
                else (255, 255, 255, L.js_round(0.92 * 255)))
    shadow_on = not dark_ink
    title_font = load_font(font_path, fitted_title)
    has_text = bool(line1 or line2 or body_lines)

    # ③ 플레이트 (bar = 전폭 솔리드, box = 블록 반투명 라운드 박스)
    if template["plate"] == "bar" and has_text:
        pad_v = L.js_round(fitted_title * 0.5)
        top = 0 if template["anchor"] == "top" else layout["blockTop"] - pad_v
        bottom = ((layout["blockBottom"] + pad_v) if template["anchor"] == "top"
                  else min(height, layout["blockBottom"] + pad_v))
        img.alpha_composite(
            Image.new("RGBA", (width, max(1, L.js_round(bottom - top))),
                      (10, 10, 14, L.js_round(0.92 * 255))),
            (0, L.js_round(top)))
    elif template["plate"] == "box" and has_text:
        max_w = max(text_length(line1, title_font, fitted_title) if line1 else 0,
                    text_length(line2, title_font, fitted_title) if line2 else 0)
        body_font0 = load_font(body_font_path, layout["bodyFontSize"])
        for bl in body_lines:
            max_w = max(max_w, text_length(bl, body_font0, layout["bodyFontSize"]))
        pad_x = L.js_round(fitted_title * 0.55)
        pad_v = L.js_round(fitted_title * 0.45)
        box_w = min(avail_width + pad_x * 2, max_w + pad_x * 2)
        box_x = (width - box_w) / 2 if centered else layout["textX"] - pad_x
        lay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        rounded_rect(lay, {"x": box_x, "y": layout["blockTop"] - pad_v, "w": box_w,
                           "h": layout["blockBottom"] - layout["blockTop"] + pad_v * 2,
                           "radius": L.js_round(fitted_title * 0.3)},
                     (8, 8, 12, L.js_round(0.6 * 255)))
        img.alpha_composite(lay)

    # ④ 장식 (따옴표)
    if template["deco"] == "quotes":
        q_size = L.js_round(fitted_title * 1.6)
        qf = load_font(font_path, q_size)
        qcol = hex_rgb(accent_color) + (L.js_round(0.85 * 255),)
        draw_text(img, (width / 2, layout["blockTop"] - L.js_round(q_size * 0.25)),
                  "“", qf, qcol, True, q_size)
        draw_text(img, (width / 2, layout["blockBottom"] + L.js_round(q_size * 0.95)),
                  "”", qf, qcol, True, q_size)

    # ⑤ 본문 (최장 줄 기준 fit)
    if body_lines:
        bf0 = load_font(body_font_path, layout["bodyFontSize"])
        max_body = max(text_length(l, bf0, layout["bodyFontSize"]) for l in body_lines)
        fitted_body = L.compute_fitted_font_size(max_body, layout["bodyFontSize"], avail_width)
        bf = load_font(body_font_path, fitted_body)
        blur = fitted_body * 0.3 if shadow_on else 0
        for i, t in enumerate(body_lines):
            draw_text(img, (anchor_x, layout["bodyBaselineYs"][i]), t, bf, body_ink,
                      centered, fitted_body, blur, (0, 0, 0, L.js_round(0.45 * 255)))

    # ⑥ 제목 2줄 — line1 은 잉크색, line2 는 강조 스타일
    if line1:
        draw_text(img, (anchor_x, layout["line1BaselineY"]), line1, title_font, title_ink,
                  centered, fitted_title, fitted_title * 0.28 if shadow_on else 0,
                  (0, 0, 0, L.js_round(0.5 * 255)))
    if line2:
        tw = text_length(line2, title_font, fitted_title)
        base_y = layout["line2BaselineY"]
        rect_base_x = (width - tw) / 2 if centered else layout["textX"]
        if highlight in ("pen", "band"):
            rect = L.compute_highlight_rect(
                highlight,
                (width - layout["textX"] * 2) if highlight == "band" else tw,
                layout["textX"] if highlight == "band" else rect_base_x,
                base_y, fitted_title)
            lay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            rounded_rect(lay, rect, hex_rgb(accent_color) + (255,))
            img.alpha_composite(lay)
            draw_text(img, (anchor_x, base_y), line2, title_font,
                      hex_rgb(L.pick_ink_on_accent(accent_color)) + (255,), centered,
                      fitted_title)
        elif highlight == "under":
            u = L.compute_underline_rect(tw, rect_base_x, base_y, fitted_title)
            lay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            ImageDraw.Draw(lay).rectangle(
                (u["x"], u["y"], u["x"] + u["w"], u["y"] + u["h"]),
                fill=hex_rgb(accent_color) + (L.js_round(0.9 * 255),))
            img.alpha_composite(lay)
            draw_text(img, (anchor_x, base_y), line2, title_font, title_ink, centered,
                      fitted_title, fitted_title * 0.28 if shadow_on else 0,
                      (0, 0, 0, L.js_round(0.5 * 255)))
        elif highlight == "color":
            # 줄 전체를 강조색 **글자색**으로. 박스도 밑줄도 없다.
            # 실물: `@unni_secret_note` — "세대별로 모아보는 / **아이돌 응원봉**"
            draw_text(img, (anchor_x, base_y), line2, title_font,
                      hex_rgb(accent_color) + (255,), centered,
                      fitted_title, fitted_title * 0.3 if shadow_on else 0,
                      (0, 0, 0, L.js_round(0.55 * 255)))
        elif highlight == "word":
            # 낱말 하나만 강조색. 실물: `@detailed` · `@newstoon556`
            draw_text(img, (anchor_x, base_y), line2, title_font, title_ink, centered,
                      fitted_title, fitted_title * 0.3 if shadow_on else 0,
                      (0, 0, 0, L.js_round(0.55 * 255)),
                      mark=emphasis_word, mark_fill=hex_rgb(accent_color) + (255,))
        else:
            draw_text(img, (anchor_x, base_y), line2, title_font, title_ink, centered,
                      fitted_title, fitted_title * 0.3 if shadow_on else 0,
                      (0, 0, 0, L.js_round(0.55 * 255)))

    # ⑦ 페이지 표시 (우상단 알약)
    if page_index is not None and page_count > 1:
        label = f"{page_index}/{page_count}"
        pill_px = L.js_round(width * 0.026)
        pf = load_font(body_font_path, pill_px)
        tw = text_length(label, pf, pill_px)
        pad_x = pill_px * 0.7
        pill_h = pill_px * 1.9
        px = width - layout["textX"] - tw - pad_x * 2
        py = L.js_round(height * 0.045)
        lay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        rounded_rect(lay, {"x": px, "y": py, "w": tw + pad_x * 2, "h": pill_h,
                           "radius": pill_h / 2},
                     (23, 23, 30, L.js_round(0.65 * 255)) if dark_ink
                     else (10, 10, 14, L.js_round(0.45 * 255)))
        img.alpha_composite(lay)
        draw_text(img, (px + pad_x, py + pill_h * 0.68), label, pf,
                  (255, 255, 255, L.js_round(0.9 * 255)), False, pill_px)

    return img.convert("RGB")


# ── 잰 배치로 그리기 (2026-10-08) ─────────────────────────────


def _ink_layer(text, font, size, fill, stroke_px=0, stroke_fill=None, mark=None, mark_fill=None, track=0.0, grad=None):
    """글자 한 줄 → (RGBA 층, 채움 글자의 잉크 상자(층 좌표 l,t,r,b)).

    ★자리는 **채움 글자의 잉크 상자**로 맞춘다 — 레퍼런스를 잴 때 글자 색 화소로 상자를 잡았으므로(외곽선 제외),
      같은 것끼리 맞춰야 같은 자가 된다. 외곽선은 그 둘레에 덧칠한다."""
    runs = split_runs(text, font, size)
    # ★자간(track, px) — 0 이 아니면 글자마다 놓는다(레퍼런스 자간에 맞출 때만 · 0 이면 예전과 같은 한 번 그리기)
    if track:
        runs = [(ch, f) for t, f in runs for ch in t]
    total = sum(f.getlength(t) for t, f in runs) + track * max(0, len(runs) - 1)
    pad = int(size * 0.7) + int(stroke_px) * 2 + 4 + int(abs(track) * 2)
    w, h = int(total + pad * 2), int(size * 2.2 + pad * 2)
    base = (pad, pad + size * 1.4)

    def paint(target, color, sw=0, sf=None):
        d = ImageDraw.Draw(target)
        x = base[0]
        for t, f in runs:
            d.text((x, base[1]), t, font=f, fill=color, anchor="ls",
                   stroke_width=int(sw), stroke_fill=sf)
            x += f.getlength(t) + track

    m = Image.new("L", (w, h), 0)
    paint(m, 255)
    bbox = m.getbbox()
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if stroke_px and stroke_fill:
        paint(lay, fill, stroke_px, stroke_fill)
    else:
        paint(lay, fill)
    if grad and bbox:
        # 세로 그라데이션 글자 — 채움 글자 자리(m)만 위→아래 색으로 덮는다(외곽선은 그대로). 잰 위·아래 색은 서버가 준다.
        gh = max(1, bbox[3] - bbox[1])
        t = np.clip((np.arange(h, dtype=np.float64) - bbox[1]) / gh, 0.0, 1.0)[:, None, None]
        top, bot = np.array(grad[0], dtype=np.float64), np.array(grad[1], dtype=np.float64)
        col = np.broadcast_to(top[None, None, :] * (1 - t) + bot[None, None, :] * t, (h, w, 3))
        gl = Image.fromarray(np.dstack([_dither(col), np.asarray(m)]).astype(np.uint8), "RGBA")
        lay.alpha_composite(gl)
    rng = mark_range(text, mark) if (mark and mark_fill) else None
    if rng:
        a = base[0] + _run_prefix_width(text, rng[0], font, size) + track * rng[0]
        b = base[0] + _run_prefix_width(text, rng[1], font, size) + track * (rng[1] - 1)
        hl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if stroke_px and stroke_fill:
            paint(hl, mark_fill, stroke_px, stroke_fill)
        else:
            paint(hl, mark_fill)
        x1, x2 = max(0, int(a) - 1), min(w, int(b) + 2)
        if x2 > x1:
            lay.alpha_composite(hl.crop((x1, 0, x2, h)), (x1, 0))
    return lay, bbox


def _fit_ink(text, font_path, target_h, max_w, advance=None, track_limit=None):
    """채움 잉크 높이가 target_h(px)가 되고 폭이 max_w 를 넘지 않는 (글자 크기, 자간 px). **그려서** 잰다(산식을 지어내지 않는다).

    advance(레퍼런스 줄의 «잉크 폭 /(글자 수 × 잉크 높이)») 가 오고 우리 글도 한글이면, 같은 값이 되게 자간을 정한다."""
    size = 100
    for _ in range(3):
        f = load_font(font_path, size)
        _, bb = _ink_layer(text, f, size, (0, 0, 0, 255))
        if not bb:
            return size, 0.0
        ih = bb[3] - bb[1]
        new = max(12, int(round(size * target_h / max(1, ih))))
        if new == size:
            break
        size = new
    f = load_font(font_path, size)
    _, bb = _ink_layer(text, f, size, (0, 0, 0, 255))
    ih, iw = bb[3] - bb[1], bb[2] - bb[0]
    n = len(text)
    track = 0.0
    hangul = sum(1 for ch in text if "\uac00" <= ch <= "\ud7a3") >= 0.5 * max(1, len(text.replace(" ", "")))
    if advance and hangul and n >= 2 and track_limit:
        # 자간 한계(글자 크기 대비)는 서버가 준다(`layout.trackLimit`) — 실행기에 숫자를 두지 않는다
        track = (float(advance) * n * ih - iw) / (n - 1)
        track = max(float(track_limit[0]) * size, min(float(track_limit[1]) * size, track))
    width = iw + track * (n - 1)
    if width > max_w:
        k = max_w / max(1.0, width)
        size = max(12, int(size * k))
        track *= k
    return size, track


def _paste_line(img, text, font_path, size, slot, x_anchor, cy, align, stroke_px, emphasis_word, track=0.0, bounds=None):
    """한 줄을 잉크 상자 기준으로 놓는다 — 가로는 정렬 기준점, 세로는 칸 가운데. 형광펜·밑줄·그림자도 여기서.
    bounds = (왼쪽 끝, 오른쪽 끝) 화소 — 줄(글자 상자 여백 포함)이 넘으면 안으로 당긴다(10-09 · 레퍼런스 줄 시작점이 오른쪽이면
    우리 글이 더 길 때 그림 밖으로 나갔다 — @morethan.look 둘째 줄)."""
    f = load_font(font_path, size)
    fill = hex_rgb(slot["color"]) + (255,)
    ol = slot.get("outline") or None
    lay, bb = _ink_layer(text, f, size, fill,
                         stroke_px=stroke_px if ol else 0,
                         stroke_fill=(hex_rgb(ol["color"]) + (255,)) if ol else None,
                         mark=emphasis_word if slot.get("wordColor") else None,
                         mark_fill=(hex_rgb(slot["wordColor"]) + (255,)) if slot.get("wordColor") else None,
                         track=track,
                         grad=((hex_rgb(slot["gradient"][0]), hex_rgb(slot["gradient"][1]))
                               if slot.get("gradient") else None))
    if not bb:
        return None
    iw, ih = bb[2] - bb[0], bb[3] - bb[1]
    if align == "center":
        ix = x_anchor - iw / 2
    elif align == "right":
        ix = x_anchor - iw
    else:
        ix = x_anchor
    iy = cy - ih / 2
    box = slot.get("box")
    if bounds:
        pl_, pr_ = ((box.get("pad") or (0.28, 0.16, 0.28, 0.2))[0], (box.get("pad") or (0.28, 0.16, 0.28, 0.2))[2]) \
            if (box and not box.get("band")) else (0.0, 0.0)
        lo, hi = bounds[0] + max(0.0, pl_) * ih, bounds[1] - max(0.0, pr_) * ih
        if ix + iw > hi:
            ix = hi - iw
        if ix < lo:
            ix = lo
    ox, oy = int(round(ix - bb[0])), int(round(iy - bb[1]))
    W, H = img.size
    if box:
        pl, pt, pr, pb = box.get("pad") or (0.28, 0.16, 0.28, 0.2)
        if box.get("band"):
            x0, x1 = 0, W
        else:
            x0, x1 = ix - pl * ih, ix + iw + pr * ih
        r = (int(round(x0)), int(round(iy - pt * ih)), int(round(x1)), int(round(iy + ih + pb * ih)))
        # 잰 여백이 음수(상자가 글자보다 좁게 재짐)여도 뒤집힌 상자를 그리지 않는다 — 최소 글자 잉크 상자
        r = (min(r[0], int(ix)), min(r[1], int(iy)), max(r[2], int(ix + iw)), max(r[3], int(iy + ih)))
        rad = float(box.get("radius") or 0.0) * (r[3] - r[1])
        if rad >= 1:
            ImageDraw.Draw(img).rounded_rectangle(r, radius=int(rad), fill=hex_rgb(box["color"]) + (255,))
        else:
            ImageDraw.Draw(img).rectangle(r, fill=hex_rgb(box["color"]) + (255,))
    ul = slot.get("underline")
    if ul:
        y0 = iy + ih + float(ul.get("dy") or 0) * ih
        t = max(2.0, float(ul.get("t") or 0.15) * ih)
        ImageDraw.Draw(img).rectangle((int(ix), int(y0), int(ix + iw), int(y0 + t)), fill=hex_rgb(ul["color"]) + (255,))
    if slot.get("shadow"):
        sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
        sh.putalpha(lay.getchannel("A").point(lambda v: int(v * 0.55)))
        sh = sh.filter(ImageFilter.GaussianBlur(radius=max(1.0, size * 0.05)))
        _composite(img, sh, ox + int(size * 0.03), oy + int(size * 0.04))
    _composite(img, lay, ox, oy)
    return {"ink": (ix, iy, ix + iw, iy + ih), "size": size}


def _composite(img, lay, x, y):
    """화면 밖으로 나가는 층도 붙인다(alpha_composite 는 음수 자리를 못 받는다)."""
    W, H = img.size
    sx, sy = max(0, -x), max(0, -y)
    dx, dy = max(0, x), max(0, y)
    w = min(lay.width - sx, W - dx)
    h = min(lay.height - sy, H - dy)
    if w > 0 and h > 0:
        img.alpha_composite(lay.crop((sx, sy, sx + w, sy + h)), (dx, dy))


#: 마지막 `render_layout_card` 가 실제로 놓은 글자 잉크 상자(px) — 자 시험·검증 도구가 «정답» 으로 읽는다(그리기와 무관).
LAST_LAYOUT_REPORT = {}


def wrap_words(text, n, weights=None):
    """제목을 낱말 경계에서 n 줄로 나눈다 — 줄 글자 수가 레퍼런스 줄 폭 비율(weights)에 가깝게.
    낱말이 n 개보다 적으면 그만큼만 나온다(억지로 낱말을 쪼개지 않는다)."""
    words = [w for w in (text or "").split() if w]
    n = max(1, min(n, len(words)))
    if n == 1:
        return [" ".join(words)]
    weights = list(weights or [1.0] * n)[:n]
    tot = sum(len(w) for w in words) + len(words) - 1
    ws = sum(weights) or 1.0
    best, best_cost = None, None
    # 낱말 수가 작아(제목 4~14자 두 줄) 모든 나눔을 다 본다
    import itertools
    for cut in itertools.combinations(range(1, len(words)), n - 1):
        parts = [" ".join(words[a:b]) for a, b in zip((0,) + cut, cut + (len(words),))]
        # 두 글자 이하 외톨이 줄은 피한다(«이유» 한 줄 — agy 1회차 지적 «마지막 줄이 짧아 여백이 크게 빈다»)
        cost = sum((len(p) / tot - w / ws) ** 2 for p, w in zip(parts, weights)) + \
            0.05 * sum(1 for p in parts if len(p.replace(" ", "")) <= 2)
        if best_cost is None or cost < best_cost:
            best, best_cost = parts, cost
    return best


def _photo_lum_bands(src_rgba, bands):
    """사진(놓인 그대로)의 띠별 평균 밝기."""
    a = np.asarray(src_rgba.convert("RGB")).astype(np.float64)
    lum = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    h = lum.shape[0]
    return [float(lum[h * i // bands:h * (i + 1) // bands].mean()) for i in range(bands)]


def _lum_shade(layer, ref_lum, cap=0.97):
    """레퍼런스 사진 영역의 띠별 밝기(ref_lum)가 되도록 띠마다 검은 막의 알파를 정해 덮는다.

    ■ 왜 (10-08 · 같은 자로 잰 실측: @aim___ing 아래 띠 밝기 레퍼런스 26 대 우리 61)
        «medium» 같은 낱말로 그늘을 고르면 사진마다 결과 밝기가 다르다(밝은 사진은 덜 어두워진다).
        우리 사진의 밝기 P 를 재서 막 색(6,7,12 → 밝기 ≈7)과 섞었을 때 레퍼런스 밝기 L 이 되는 알파
        a = (P − L)/(P − 7) 를 띠마다 정한다 — 같은 자로 다시 재면 같은 밝기가 나온다. 밝게 만들 수는 없으니 a ≥ 0.
    """
    bands = len(ref_lum)
    P = _photo_lum_bands(layer, bands)
    alphas = []
    for p, l in zip(P, ref_lum):
        if l is None or p <= 8:
            alphas.append(0.0)
            continue
        alphas.append(max(0.0, min(cap, (p - l) / (p - 7.0))))
    w, h = layer.size
    pos = [(i + 0.5) / bands for i in range(bands)]
    stops = [(0.0, (6, 7, 12), alphas[0])] + [(q, (6, 7, 12), a) for q, a in zip(pos, alphas)] + \
        [(1.0, (6, 7, 12), alphas[-1])]
    col, mask = vertical_shade((w, h), stops)
    col = col.convert("RGBA")
    col.putalpha(mask)
    layer.alpha_composite(col)
    return alphas


def render_layout_card(width, height, line1, line2, body_lines, layout, font_path, body_font_path=None,
                       image_path=None, page_index=None, page_count=1, emphasis_word=None,
                       shade_stops=None, accent_color=None, handle=None, kicker=None, subtitle=None):
    """서버가 레퍼런스를 재서 준 배치(`render.layout`)대로 그린다. 자리·크기·색은 전부 배치에서 온다.

    ■ 순서: 바탕(단색·사진 칸 · 흑백) → 그늘(사진 칸 안 · 레퍼런스 밝기에 맞춤) → 단색 면 → 장식(테두리·선·동그란 인셋)
      → 머리말 → 제목 줄들(형광펜·밑줄·외곽선·그림자·색 낱말) → 부제 → 본문 → 쪽 번호·계정명
    ■ 글자 크기: 칸 높이 = 채움 잉크 높이가 되게 **그려서** 맞추고, 폭(span)을 넘으면 줄인다. 칸 높이가 원래 같았으면
      가장 작은 쪽에 맞춘다(위계를 지킨다).
    """
    W, H = width, height
    LAST_LAYOUT_REPORT.clear()
    body_font_path = body_font_path or font_path
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    bg = layout.get("bg") or {}
    pr = bg.get("photoRect") or [0.0, 0.0, 1.0, 1.0]
    prect = (int(round(pr[0] * W)), int(round(pr[1] * H)), int(round(pr[2] * W)), int(round(pr[3] * H)))
    accent = layout.get("accent") or accent_color or "#FFE14D"
    if bg.get("kind") == "solid" and bg.get("color"):
        ImageDraw.Draw(img).rectangle((0, 0, W, H), fill=hex_rgb(bg["color"]) + (255,))
    else:
        if bg.get("color"):
            ImageDraw.Draw(img).rectangle((0, 0, W, H), fill=hex_rgb(bg["color"]) + (255,))
        pw, ph = prect[2] - prect[0], prect[3] - prect[1]
        if image_path and pw > 0 and ph > 0:
            src = Image.open(image_path).convert("RGBA")
            if bg.get("grayscale"):
                src = src.convert("L").convert("RGBA")
            fit = L.compute_cover_fit(src.width, src.height, pw, ph)
            scaled = src.resize((max(1, L.js_round(fit["dw"])), max(1, L.js_round(fit["dh"]))), Image.LANCZOS)
            sx, sy = max(0, -L.js_round(fit["dx"])), max(0, -L.js_round(fit["dy"]))
            layer = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
            layer.alpha_composite(scaled, dest=(0, 0), source=(sx, sy, min(scaled.width, sx + pw),
                                                                min(scaled.height, sy + ph)))
            sh = layout.get("shade") or {}
            k = float(sh.get("alpha") or 0.0)
            ref_lum = sh.get("lum")
            if isinstance(ref_lum, list) and ref_lum and any(v is not None for v in ref_lum):
                LAST_LAYOUT_REPORT["shade_alphas"] = _lum_shade(layer, ref_lum)
            elif k > 0 and sh.get("kind") in ("bottom", "top", "center"):
                stops = ((shade_stops or {}).get(sh["kind"]) or SHADE_STOPS[sh["kind"]])
                stops = [(float(a), tuple(b), float(c) * k) for a, b, c in stops]
                col, mask = vertical_shade((pw, ph), stops)
                col = col.convert("RGBA")
                col.putalpha(mask)
                layer.alpha_composite(col)
            elif k > 0 and sh.get("kind") == "full":
                fa = float((shade_stops or {}).get("full_alpha") or 0.55) * k
                layer.alpha_composite(Image.new("RGBA", (pw, ph), (6, 7, 12, L.js_round(fa * 255))))
            img.alpha_composite(layer, (prect[0], prect[1]))
        elif pw > 0 and ph > 0:
            # 사진을 못 구한 카드 — 강조색을 머금은 딥톤(정본 갈래). 단색 바탕 계정은 위에서 이미 그 색이다.
            bd = L.compute_no_image_backdrop(accent, "dark" if layout.get("inkDark") else "light")
            g = linear_gradient((pw, ph), (0, 0), (pw, ph), hex_rgb(bd["from"]), hex_rgb(bd["to"])).convert("RGBA")
            img.alpha_composite(g, (prect[0], prect[1]))
    d = ImageDraw.Draw(img)
    for p in layout.get("panels") or []:
        r = p["rect"]
        d.rectangle((int(round(r[0] * W)), int(round(r[1] * H)), int(round(r[2] * W)) - 1, int(round(r[3] * H)) - 1),
                    fill=hex_rgb(p["color"]) + (255,))
    for dc in layout.get("decor") or []:
        r = dc["rect"]
        box = (int(round(r[0] * W)), int(round(r[1] * H)), int(round(r[2] * W)) - 1, int(round(r[3] * H)) - 1)
        if dc.get("kind") == "border":
            d.rectangle(box, outline=hex_rgb(dc["color"]) + (255,), width=max(2, int(0.004 * W)))
        elif dc.get("kind") == "line":
            d.rectangle(box, fill=hex_rgb(dc["color"]) + (255,))
        elif dc.get("kind") == "inset_circle" and image_path:
            # 동그란 인셋 — 같은 사진의 가운데를 1.6배로 당겨 원 안에 넣고 잰 색·두께로 테두리를 두른다
            #   (레퍼런스의 인셋 사진은 다른 사진이다 — 우리는 그 모양만 옮긴다).
            dia = min(box[2] - box[0], box[3] - box[1])
            if dia > 20:
                src = Image.open(image_path).convert("RGB")
                if bg.get("grayscale"):
                    src = src.convert("L").convert("RGB")
                side = int(min(src.width, src.height) / 1.6)
                cx, cy = src.width // 2, src.height // 2
                crop = src.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)).resize((dia, dia), Image.LANCZOS)
                m = Image.new("L", (dia, dia), 0)
                ImageDraw.Draw(m).ellipse((0, 0, dia - 1, dia - 1), fill=255)
                img.paste(crop, (box[0], box[1]), m)
                bw = max(2, int(round(float(dc.get("w") or 0.03) * dia)))
                ImageDraw.Draw(img).ellipse((box[0], box[1], box[0] + dia - 1, box[1] + dia - 1),
                                            outline=hex_rgb(dc["color"]) + (255,), width=bw)
    d = ImageDraw.Draw(img)

    align = layout.get("align") or "left"
    span = layout.get("span") or [0.065, 0.935]
    sx0, sx1 = span[0] * W, span[1] * W
    max_w = sx1 - sx0
    slots = list(layout.get("titles") or [])
    if layout.get("titleMode") == "wrap":
        widths = [s_["rect"][2] - s_["rect"][0] for s_ in slots]
        texts = wrap_words(" ".join(t for t in (line1, line2) if t), len(slots), widths)
        if len(texts) < len(slots):
            # 낱말이 모자라 줄이 적다 — 레퍼런스 덩어리가 앉은 쪽의 칸을 쓴다
            slots = slots[-len(texts):] if layout.get("anchor") == "bottom" else slots[:len(texts)]
    else:
        texts = [line1, line2]
    jobs = [(t, s_) for t, s_ in zip(texts, slots)]
    same = bool(layout.get("sameSize"))
    common_h = max((s_["rect"][3] - s_["rect"][1]) for _, s_ in jobs) * H if (same and jobs) else None
    fits = []
    for text, slot in jobs:
        if not text:
            fits.append(None)
            continue
        r = slot["rect"]
        th = common_h or (r[3] - r[1]) * H
        bx = slot.get("box") if not (slot.get("box") or {}).get("band") else None
        # 글자 상자(라벨) 좌우 여백도 글 자리 폭 안에 들어가야 한다 — 여백은 잉크 높이 배수라 목표 높이로 뺀다(10-09)
        bpad = (max(0.0, (bx.get("pad") or (0.28, 0.16, 0.28, 0.2))[0]) + max(0.0, (bx.get("pad") or (0.28, 0.16, 0.28, 0.2))[2])) * th \
            if bx else 0.0
        fits.append(_fit_ink(text, font_path, th, max(1.0, max_w - bpad), slot.get("advance"),
                             layout.get("trackLimit")))
    if same and fits and all(fits):
        # 같은 크기 덩어리 — 가장 작게 맞은 크기로 모두 그리고, 자간도 그 크기 비율로 줄인다
        smin = min(f_[0] for f_ in fits)
        fits = [(smin, f_[1] * smin / f_[0]) for f_ in fits]
    sizes = [f_[0] if f_ else None for f_ in fits]
    tracks = [f_[1] if f_ else 0.0 for f_ in fits]

    def x_anchor(slot):
        if align == "center":
            return (sx0 + sx1) / 2
        if align == "right":
            return min(sx1, slot["rect"][2] * W)
        return max(sx0, slot["rect"][0] * W)

    cys = [((slot["rect"][1] + slot["rect"][3]) / 2) * H for _, slot in jobs]
    # 강조 낱말 — 그 낱말이 든 줄에 칠한다(줄 바꿈으로 2행이 다른 줄로 갈 수 있다)
    wcol = layout.get("wordColor")
    word_line = None
    if emphasis_word and wcol:
        for i, (t, _) in enumerate(jobs):
            if t and emphasis_word in t:
                word_line = i
    body_size = None
    body_h = 0.0
    ref_size = next((x for x in reversed(sizes) if x), None) or int(0.07 * H)
    if body_lines:
        body_size = max(14, int(round(ref_size * float((layout.get("body") or {}).get("sizeRatio") or 0.42))))
        bf = load_font(body_font_path, body_size)
        widest = max(text_length(t, bf, body_size) for t in body_lines)
        if widest > max_w:
            body_size = max(14, int(body_size * max_w / widest))
        body_h = len(body_lines) * body_size * 1.45
    lower = max((i for i in range(len(sizes)) if sizes[i]), default=None)
    shift = 0.0
    if body_lines and lower is not None:
        need = cys[lower] + sizes[lower] * 0.5 + sizes[lower] * float((layout.get("body") or {}).get("gapRatio") or 0.55) + body_h
        if need > H * 0.955:
            shift = need - H * 0.955
    placed = []
    for i, (text, slot) in enumerate(jobs):
        if not sizes[i]:
            continue
        ol = slot.get("outline") or None
        sp = int(round(float(ol["w"]) * sizes[i] * 0.75)) if ol else 0
        sl = dict(slot)
        if i == word_line:
            sl["wordColor"] = wcol
        elif not (i == word_line):
            sl["wordColor"] = None
        got = _paste_line(img, text, font_path, sizes[i], sl, x_anchor(slot), cys[i] - shift, align, sp,
                          emphasis_word if i == word_line else None, tracks[i], bounds=(sx0, sx1))
        if got:
            placed.append(got)
            LAST_LAYOUT_REPORT["line%d" % (i + 1)] = dict(got, color=slot.get("color"))
    # 머리말·부제 — 카드에 그 글이 있을 때만(레퍼런스 자리·모양 그대로)
    small = [(kicker, layout.get("kicker"))] if kicker and layout.get("kicker") else []
    subs = [x for x in (subtitle or "").split("\n") if x.strip()]
    small += list(zip(subs, layout.get("subtitles") or []))
    for text, slot in small:
        r = slot["rect"]
        # 머리말·부제도 잰 굵기를 따른다 — 굵게(bold·heavy)면 제목 파일, 아니면 본문 파일(agy 비교 «부제가 얇다» 지적)
        fp = font_path if slot.get("weight") in ("bold", "heavy") else body_font_path
        fs, tr = _fit_ink(text, fp, (r[3] - r[1]) * H, max_w, slot.get("advance"), layout.get("trackLimit"))
        ol = slot.get("outline") or None
        sp = int(round(float(ol["w"]) * fs * 0.75)) if ol else 0
        got = _paste_line(img, text, fp, fs, dict(slot, wordColor=None), x_anchor(slot),
                          (r[1] + r[3]) / 2 * H - shift, align, sp, None, tr, bounds=(sx0, sx1))
        if got:
            placed.append(got)
            LAST_LAYOUT_REPORT["small%d" % len(placed)] = dict(got, color=slot.get("color"))
    if body_lines:
        bcol = (layout.get("body") or {}).get("color") or "#FFFFFF"
        if placed:
            y = max(p["ink"][3] for p in placed) + (sizes[lower] if lower is not None else body_size) * \
                float((layout.get("body") or {}).get("gapRatio") or 0.55)
        else:
            y = H * 0.5
        # ★본문이 계정명·쪽 표시 자리(extras)에 닿으면 본문 글자를 줄인다 — 레퍼런스 표지 아래의 계정명 자리와 안쪽 카드 본문이
        #   겹쳤다(10-08 실측 @forest.kr_ 2~4번 카드 · 본문 셋째 줄 끝에 «@my_account» 가 겹침).
        below = [ex["rect"][1] * H for ex in (layout.get("extras") or [])
                 if ex.get("kind") == "page" and page_index is not None and (page_count or 0) > 1
                 or ex.get("kind") == "handle" and (ex.get("text") or handle)]
        below = [b for b in below if b > y]
        if below:
            room = min(below) - y - body_size * 0.5
            need = body_size * (0.85 + 1.45 * (len(body_lines) - 1) + 0.35)
            if need > room > 0:
                body_size = max(12, int(body_size * room / need))
        bf = load_font(body_font_path, body_size)
        base_y = int(body_size * 0.7) + 4 + body_size * 1.4      # _ink_layer 의 기준선 자리(외곽선 없음)
        baseline = y + body_size * 0.85
        for t in body_lines:
            lay, bb = _ink_layer(t, bf, body_size, hex_rgb(bcol) + (L.js_round(0.92 * 255),))
            if not bb:
                continue
            iw = bb[2] - bb[0]
            xa = (sx0 + sx1) / 2 - iw / 2 if align == "center" else (sx1 - iw if align == "right" else sx0)
            # 본문 줄은 기준선 간격 1.45 로 쌓는다(정본 BODY_LINE_HEIGHT)
            _composite(img, lay, int(round(xa - bb[0])), int(round(baseline - base_y)))
            baseline += body_size * 1.45
    for ex in layout.get("extras") or []:
        r = ex["rect"]
        if ex.get("kind") == "page":
            if page_index is None or not page_count or page_count < 2:
                continue
            text = f"{page_index}/{page_count}"
        else:
            text = ex.get("text") or handle or ""
        if not text:
            continue
        hpx = (r[3] - r[1]) * H
        fs, _ = _fit_ink(text, body_font_path, hpx, max(10.0, (r[2] - r[0]) * W * 1.6))
        f = load_font(body_font_path, fs)
        lay, bb = _ink_layer(text, f, fs, hex_rgb(ex["color"]) + (255,))
        if not bb:
            continue
        cx = (r[0] + r[2]) / 2 * W
        iw = bb[2] - bb[0]
        if abs(cx / W - 0.5) < 0.1:
            xa = cx - iw / 2
        elif cx / W < 0.5:
            xa = r[0] * W
        else:
            xa = r[2] * W - iw
        _composite(img, lay, int(round(xa - bb[0])), int(round((r[1] + r[3]) / 2 * H - (bb[3] - bb[1]) / 2 - bb[1])))
    return img.convert("RGB")
