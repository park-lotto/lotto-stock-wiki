"""Reusable, deterministic social-comment card renderer.

The editor preview and the final video both consume PNGs from this module so
layout, wrapping and typography have one source of truth.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


CARD_WIDTH = 920
RENDER_VERSION = 2
_FONT = Path(__file__).parent / "assets" / "NanumGothic.ttf"
CACHE_DIR = Path(__file__).parent / "data" / "comment_card_cache"
_STYLE_META = (
    {"id": "dark_social", "name": "다크 소셜", "description": "실제 댓글창처럼 단정한 암전형 카드"},
    {"id": "premium_pop", "name": "프리미엄 팝", "description": "밝은 유리 질감과 포인트 컬러를 쓴 카드"},
)

_DEFAULTS = {
    "style": "dark_social",
    "author": "시청자",
    "age": "방금 전",
    "text": "정말 유용한 정보네요!",
    "likes": 0,
    "avatar_file": "",
    "x": 50.0,
    "y": 72.0,
    "width": 880,
    "alpha": 1.0,
    "start": 0.4,
    "dur": 3.5,
    "animation": "slide_up",
}


def styles():
    return [dict(item) for item in _STYLE_META]


def _number(value, default, lo, hi):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)
    return max(lo, min(hi, value))


def normalize(spec):
    raw = dict(spec or {})
    out = dict(_DEFAULTS)
    if raw.get("style") in {item["id"] for item in _STYLE_META}:
        out["style"] = raw["style"]
    out["author"] = str(raw.get("author") or out["author"]).strip()[:40]
    out["age"] = str(raw.get("age") or out["age"]).strip()[:30]
    out["text"] = str(raw.get("text") or "").strip()[:280]
    try:
        out["likes"] = max(0, min(999_999_999, int(float(raw.get("likes", out["likes"])))))
    except (TypeError, ValueError):
        out["likes"] = 0
    out["avatar_file"] = Path(str(raw.get("avatar_file") or "")).name[:100]
    # avatar_path is trusted only by internal callers and never persisted.
    out["avatar_path"] = str(raw.get("avatar_path") or "")
    out["x"] = _number(raw.get("x"), out["x"], 0, 100)
    out["y"] = _number(raw.get("y"), out["y"], 0, 100)
    out["width"] = int(_number(raw.get("width"), out["width"], 320, 980))
    out["alpha"] = _number(raw.get("alpha"), out["alpha"], 0.1, 1)
    out["start"] = _number(raw.get("start"), out["start"], 0, 3600)
    out["dur"] = _number(raw.get("dur"), out["dur"], 0.5, 120)
    out["animation"] = "slide_up"
    return out


def cache_key(spec):
    clean = normalize(spec)
    clean.pop("avatar_path", None)
    payload = f"v{RENDER_VERSION}:" + json.dumps(
        clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    avatar_path = str((spec or {}).get("avatar_path") or "")
    if avatar_path and Path(avatar_path).is_file():
        payload += ":" + hashlib.sha1(Path(avatar_path).read_bytes()).hexdigest()
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:20]


def _font(size, bold=False):
    # NanumGothic is the repository font and reliably covers Korean. Pillow's
    # synthetic stroke is used for emphasis instead of a second font file.
    return ImageFont.truetype(str(_FONT), size=size)


def _wrap(draw, text, font, max_width, max_lines=4):
    words = str(text or "").split()
    lines, current = [], ""
    consumed = 0
    for index, word in enumerate(words):
        trial = f"{current} {word}".strip()
        if not current or draw.textlength(trial, font=font) <= max_width:
            current = trial
            consumed = index + 1
            continue
        lines.append(current)
        if len(lines) >= max_lines - 1:
            current = word
            consumed = index + 1
            break
        current = word
        consumed = index + 1
        # A URL or a space-free token may itself exceed the card. Only that
        # exceptional token is split by characters; ordinary Korean words stay whole.
        if draw.textlength(current, font=font) > max_width:
            chunk = ""
            for ch in current:
                if chunk and draw.textlength(chunk + ch, font=font) > max_width:
                    lines.append(chunk)
                    chunk = ch
                    if len(lines) >= max_lines - 1:
                        break
                else:
                    chunk += ch
            current = chunk
    if current and len(lines) < max_lines:
        truncated = consumed < len(words)
        line = current
        if truncated:
            while line and draw.textlength(line + "…", font=font) > max_width:
                line = line[:-1]
            line = line.rstrip() + "…"
        lines.append(line)
    return lines or [""]


def _format_likes(value):
    value = int(value or 0)
    if value >= 10_000:
        return f"{value / 10_000:.1f}만".replace(".0만", "만")
    if value >= 1_000:
        return f"{value / 1_000:.1f}천".replace(".0천", "천")
    return str(value)


def _avatar(spec, size, colors):
    path = Path(spec.get("avatar_path") or "")
    if path.is_file():
        try:
            with Image.open(path) as source:
                avatar = ImageOps.fit(source.convert("RGB"), (size, size), method=Image.Resampling.LANCZOS).convert("RGBA")
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
            avatar.putalpha(mask)
            return avatar
        except (OSError, ValueError):
            pass
    avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ad = ImageDraw.Draw(avatar)
    ad.ellipse((0, 0, size - 1, size - 1), fill=colors[0])
    ad.ellipse((5, 5, size - 6, size - 6), fill=colors[1])
    initial = (spec.get("author") or "?")[0]
    font = _font(round(size * .42))
    box = ad.textbbox((0, 0), initial, font=font, stroke_width=1)
    ad.text(((size - (box[2] - box[0])) / 2, (size - (box[3] - box[1])) / 2 - box[1]),
            initial, font=font, fill="#FFFFFF", stroke_width=1, stroke_fill="#FFFFFF")
    return avatar


def _shadowed_canvas(height, radius, shadow_color):
    shadow = Image.new("RGBA", (CARD_WIDTH, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((34, 34, CARD_WIDTH - 34, height - 42), radius=radius, fill=shadow_color)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    return shadow


def _render_dark(spec):
    probe = Image.new("RGBA", (CARD_WIDTH, 300), (0, 0, 0, 0))
    pd = ImageDraw.Draw(probe)
    body_font = _font(35)
    lines = _wrap(pd, spec["text"], body_font, 720, 4)
    height = 178 + len(lines) * 52 + 82
    image = _shadowed_canvas(height, 32, (0, 0, 0, 165))
    draw = ImageDraw.Draw(image)
    box = (28, 24, CARD_WIDTH - 28, height - 48)
    draw.rounded_rectangle(box, radius=32, fill=(17, 18, 22, 235), outline=(255, 255, 255, 34), width=2)
    draw.rounded_rectangle((box[0] + 1, box[1] + 1, box[2] - 1, box[1] + 7), radius=28,
                           fill=(255, 255, 255, 22))
    image.alpha_composite(_avatar(spec, 76, ("#20D6B4", "#175B5A")), (62, 56))
    draw.text((158, 57), spec["author"], font=_font(29), fill="#FFFFFF", stroke_width=1, stroke_fill="#FFFFFF")
    author_w = draw.textlength(spec["author"], font=_font(29))
    draw.text((172 + author_w, 61), spec["age"], font=_font(23), fill=(175, 180, 190, 255))
    y = 154
    for line in lines:
        draw.text((64, y), line, font=body_font, fill="#F7F7F9")
        y += 52
    draw.line((64, y + 4, CARD_WIDTH - 64, y + 4), fill=(255, 255, 255, 24), width=2)
    draw.text((68, y + 26), "♡", font=_font(30), fill=(210, 214, 222, 255))
    draw.text((110, y + 30), _format_likes(spec["likes"]), font=_font(23), fill=(192, 197, 207, 255))
    draw.text((255, y + 30), "댓글", font=_font(23), fill=(192, 197, 207, 255))
    return image


def _render_premium(spec):
    probe = Image.new("RGBA", (CARD_WIDTH, 300), (0, 0, 0, 0))
    pd = ImageDraw.Draw(probe)
    body_font = _font(36)
    lines = _wrap(pd, spec["text"], body_font, 700, 4)
    height = 190 + len(lines) * 54 + 86
    image = _shadowed_canvas(height, 40, (15, 28, 70, 105))
    panel = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gradient = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(gradient)
    top, bottom = (252, 253, 255, 247), (231, 239, 255, 242)
    for y in range(28, height - 50):
        t = (y - 28) / max(1, height - 78)
        color = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(4))
        gd.line((28, y, CARD_WIDTH - 28, y), fill=color)
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((28, 24, CARD_WIDTH - 28, height - 48), radius=40, fill=255)
    panel.paste(gradient, (0, 0), mask)
    image.alpha_composite(panel)
    draw = ImageDraw.Draw(image)
    box = (28, 24, CARD_WIDTH - 28, height - 48)
    draw.rounded_rectangle(box, radius=40, outline=(255, 255, 255, 230), width=3)
    draw.rounded_rectangle((box[0] + 2, box[1] + 2, box[0] + 13, box[3] - 2), radius=8, fill="#6C5CE7")
    image.alpha_composite(_avatar(spec, 82, ("#FF5BA6", "#6C5CE7")), (60, 54))
    draw.text((164, 56), spec["author"], font=_font(29), fill="#17213A", stroke_width=1, stroke_fill="#17213A")
    draw.text((164, 96), spec["age"], font=_font(22), fill="#75809A")
    draw.text((CARD_WIDTH - 125, 48), "“", font=_font(76), fill=(108, 92, 231, 100))
    y = 160
    for i, line in enumerate(lines):
        if i == max(0, len(lines) - 1):
            tw = min(720, draw.textlength(line, font=body_font))
            draw.rounded_rectangle((58, y + 35, 76 + tw, y + 47), radius=6, fill=(255, 207, 76, 145))
        draw.text((64, y), line, font=body_font, fill="#17213A")
        y += 54
    draw.text((66, y + 28), "♥", font=_font(28), fill="#FF4D8D")
    draw.text((106, y + 31), _format_likes(spec["likes"]), font=_font(22), fill="#68738B")
    draw.rounded_rectangle((CARD_WIDTH - 212, y + 22, CARD_WIDTH - 64, y + 65), radius=21, fill=(108, 92, 231, 235))
    draw.text((CARD_WIDTH - 181, y + 31), "반응 댓글", font=_font(19), fill="#FFFFFF")
    return image


def render_to(spec, out_path):
    clean = normalize(spec)
    image = _render_premium(clean) if clean["style"] == "premium_pop" else _render_dark(clean)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG", optimize=True)
    return out
