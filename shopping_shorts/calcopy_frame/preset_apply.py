# -*- coding: utf-8 -*-
"""프리셋 적용 — 저장된 프리셋(frame.json·manifest.json)에 그 편 값을 채워 설명서 하나로 만든다. 고객 묶음에 들어가는 쪽.
판단 주인은 이 파일 하나: 읽기(load)·채우기(apply)·종속값 규칙(apply_rules)·제목 잉크 재기(title_ink_bottom)·글꼴(font_faces·_pil_font).
프리셋 만들기(tools/calcopy/engine/preset_save.py)·틀 뜯기(to_frame.py)는 고객 묶음 밖이고, 이 함수들을 여기서 가져다 쓴다(두 벌 금지).
(11-04 회원 묶음 렌더가 preset_make → preset_save import 로 멈췄다 — 적용 기능이 만드는 기술 파일 안에 섞여 있었다. 선례 per_video.py)
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from shopping_shorts.calcopy_frame import schema
from shopping_shorts.calcopy_frame.per_video import NO_DEFAULT, VAR, flat, layer_order, unflat

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_MANIFEST = ("slug", "style", "made_by", "rule", "created_at", "updated_at", "variables", "sources")


@lru_cache(maxsize=1)
def font_faces() -> dict:
    """장면꾸미기 화면의 @font-face: 글꼴 이름 → 파일 경로(첫 등록). 렌더러가 실제로 쓰는 파일."""
    html = (ROOT / "out/scene-style-ui-showcase.html").read_text(encoding="utf-8")
    out = {}
    for fam, url in re.findall(r'@font-face\s*\{[^}]*?font-family:\s*"?([A-Za-z0-9_-]+)"?;\s*src:\s*url\("([^"]+)"', html):
        out.setdefault(fam, (ROOT / "out" / url).resolve())
    return out


def _pil_font(fam: str, size: float):
    return _pil_font_px(fam, max(1, int(round(size))))


@lru_cache(maxsize=256)
def _pil_font_px(fam: str, px: int):
    """woff2 는 열 때마다 압축을 풀어 느리다(시험 52초 실측) — 글꼴·크기별로 한 번만 연다."""
    from PIL import ImageFont
    return ImageFont.truetype(str(font_faces()[fam]), px)


def _line_w(fam: str, size: float, ls: float, line: str) -> float:
    b = _pil_font(fam, size).getbbox(line, anchor="ls")
    return (b[2] - b[0]) + ls * max(0, len(line) - 1)


def _scales(t: dict) -> list:
    n = int(t.get("lines") or 1)
    sc = t.get("line_scale") or []
    return [sc[i] if i < len(sc) else 1 for i in range(n)]


def title_ink_bottom(t: dict) -> float | None:
    """제목 마지막 줄 잉크 아래 끝(y) — 렌더러 규칙(줄 칸 line_h 안에 글꼴 ascent+descent 상자를 세로 가운데, to_frame.size_and_top 과
    같은 모형)으로 그 글꼴·줄 크기·글을 놓아 잰다. 글이 없으면 None."""
    if not t.get("text"):
        return None
    lines = t["text"].split(chr(10))
    i = len(lines) - 1
    size = t["size"] * _scales({**t, "lines": len(lines)})[i]
    f = _pil_font(t["font"], size)
    asc, desc = f.getmetrics()
    base = t["y"] + i * t["line_h"] + (t["line_h"] - (asc + desc)) / 2 + asc
    return base + f.getbbox(lines[i], anchor="ls")[3]


def apply_rules(F: dict, rules: dict) -> dict:
    """규칙으로 종속값(제목 크기·줄높이·위치, 창 y·h, 자막 y)을 계산해 넣는다. 제목 글자가 있어야 한다."""
    K = {k: v["default"] for k, v in (rules or {}).get("keys", {}).items()}
    L = {(l["kind"] + (":" + l["role"] if l.get("role") else "")): l for l in F.get("layers") or []}
    t, v, c = L.get("text:title"), L.get("video"), L.get("text:caption")
    if t and t.get("text") and "fill_w" in K:
        lines = t["text"].split(chr(10))
        # 크기는 잰 크기(중앙값) 그대로 — 글자 키(띠 높이)가 틀의 모양이다. 폭이 상한(fill_w)을 넘으면 먼저 자간을 줄이고
        #   (크기의 −15% 까지, to_frame.spacing_for 와 같은 바닥), 그래도 넘을 때만 크기를 줄인다.
        #   (2026-10-16 LOO: 폭 맞춤으로 크기부터 줄이니 제목 띠 높이가 원본 91~110 → 75~87 로 작아졌다)
        size = K.get("size_cap") or t["size"]
        sc = _scales({**t, "lines": len(lines)})               # 줄 배율(line_scale) — 줄마다 크기가 다른 제목
        k = max(range(len(lines)), key=lambda i: _line_w(t["font"], size * sc[i], 0, lines[i]))
        n = lines[k]
        nat = _line_w(t["font"], size * sc[k], 0, n)
        gaps = max(1, len(n) - 1)
        ls = t["letter_spacing"]
        if nat + ls * gaps > K["fill_w"]:
            ls = max(-0.15 * size, (K["fill_w"] - nat) / gaps)
            if nat + ls * gaps > K["fill_w"]:
                size = size * (K["fill_w"] - ls * gaps) / max(1, nat)
        t["letter_spacing"] = round(ls, 1)
        t["size"] = round(size, 1)
        t["line_h"] = round(t["size"] * K.get("lh_ratio", 1.15))
        t["lines"] = len(lines)
    if t and "title_top" in K:
        t["y"] = K["title_top"]
    if t and v and K.get("video_anchor") == "gap_ink" and "gap_ink" in K and title_ink_bottom(t) is not None:
        v["y"] = round(title_ink_bottom(t) + K["gap_ink"])
    elif v and K.get("video_anchor") == "constant" and "video_top" in K:
        v["y"] = K["video_top"]
    elif t and v and "gap" in K:
        v["y"] = round(t["y"] + t["lines"] * t["line_h"] + K["gap"])
    if v and "video_bottom" in K:
        v["h"] = K["video_bottom"] - v["y"]
    if c and v and "cap_dy" in K:
        c["y"] = v["y"] + v["h"] + K["cap_dy"]
    return F


def load(preset_dir: Path) -> tuple[dict, dict]:
    frame = json.loads((preset_dir / "frame.json").read_text(encoding="utf-8"))
    M = json.loads((preset_dir / "manifest.json").read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_MANIFEST if k not in M]
    if missing:
        raise ValueError(f"manifest 필수 항목 없음: {missing}")
    return frame, M


def apply(preset: dict, per_video: dict | None = None, overrides: dict | None = None,
          defaults: dict | None = None, caption_style: dict | None = None, rules: dict | None = None) -> dict:
    """프리셋의 변수 자리를 채운 설명서. 순서: overrides({자리: 값}) → per_video(그 편 설명서, to_frame 결과)
    → defaults(manifest variable_stats — 새 소재로 만들 때). 못 채운 변수가 하나라도 남으면 ValueError(목록).
    caption_style = manifest caption_styles 의 한 항목 — 자막 층을 그 하위 스타일의 잰 층으로 바꾼다(미측정이면 ValueError)."""
    P = flat(preset)
    V = flat(per_video) if per_video else {}
    left = []
    for path, v in P.items():
        if v != VAR:
            continue
        if overrides and path in overrides:
            P[path] = overrides[path]
        elif path in V and V[path] != VAR:
            P[path] = V[path]
        elif defaults and path in defaults and defaults[path].get("how") != NO_DEFAULT:
            P[path] = defaults[path]["default"]          # None(최빈이 '없음')도 값이다 — 예: template_off
        else:
            left.append(path)
    if caption_style is not None:
        if not caption_style.get("layer"):
            raise ValueError(f"자막 스타일 {caption_style.get('name')} 은 미측정 — 잰 층이 없다")
        for f, v in caption_style["layer"].items():
            if f != "kind":
                P[f"layers[text:caption].{f}"] = v
    if left:
        raise ValueError(f"채우지 못한 변수: {left}")
    out = unflat(P, layer_order(preset))
    if rules:
        out = apply_rules(out, rules)       # 종속값은 규칙이 정한다(독립 기본값을 채운 뒤)
    schema.validate(out)
    return out
