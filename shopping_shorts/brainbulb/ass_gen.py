# -*- coding: utf-8 -*-
"""sub.ass 생성 — 스타일·좌표·태그는 spec 상수, 시각은 timing, 글자 크기는 measure(libass 실측)로.

검증: 실제 5편 sub.ass와 Dialogue 줄 단위로 같아야 한다 (tests/test_brainbulb_core.py).
"""
from decimal import Decimal, ROUND_HALF_EVEN

from . import spec, measure


def fmt_time(sec):
    """ASS 시각 'H:MM:SS.cc' — 반올림은 **HALF_EVEN** (실측: 2.595→02.60, 22.125→22.12, 44.105→44.10).
    HALF_UP이면 5편 중 4편에서 1cs씩 어긋난다."""
    cs = int((Decimal(str(sec)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _fit_prop(font, text, base, target, fonts_dir):
    """비례식: 기본 크기에서 잉크 폭을 한 번 재고 fs = floor(base × target / ink). 기본 크기에 들어가면 base.
    실측 10건 중 8건 정확히 일치, 2건은 1pt 차이(잉크 임계 방식은 어떤 값으로도 4건이 어긋난다 — 2026-09-12 검증)."""
    ink = measure.ink_width(font, base, text, fonts_dir)
    if ink <= target:
        return base
    return max(40, int(base * target / ink))


def title_sizes(h1, h2, fonts_dir=None):
    """제목 두 줄의 글자 크기 — 잉크 폭 1000px 목표 비례 축소(≤ 기본 123/134)."""
    f1, _, b1 = spec.STYLE_FONT["HL1"]
    f2, _, b2 = spec.STYLE_FONT["HL2"]
    return (_fit_prop(f1, h1, b1, spec.TITLE_TARGET_INK, fonts_dir),
            _fit_prop(f2, h2, b2, spec.TITLE_TARGET_INK, fonts_dir))


def card_size(card_text):
    return spec.CARD_FS_LONG if len(card_text) >= spec.POLICY_CARD_LONG_MIN_CHARS else spec.CARD_FS_SHORT


def _dlg(layer, t0, t1, style, text):
    return f"Dialogue: {layer},{fmt_time(t0)},{fmt_time(t1)},{style},,0,0,0,,{text}"


def build(title, card_text, timing, *, hl_fs=None, card_fs=None, fonts_dir=None):
    """title: {h1,h2} / card_text: 카드 문장 / timing: timing.build() 결과 → sub.ass 전문(str)"""
    fs1, fs2 = hl_fs or title_sizes(title["h1"], title["h2"], fonts_dir)
    cfs = card_fs or card_size(card_text)
    ce, total = timing["card_end"], timing["total"]
    lines = [spec.ASS_HEADER, "", spec.STYLE_BLOCK, "", "[Events]\n" + spec.EVENTS_FORMAT.rstrip("\n")]
    ev = []
    # 카드 띠 2장 + 카드 문장
    for layer, (col, y, h) in zip(spec.CARD_LAYER_BANDS, (spec.CARD_BAND_GRAY, spec.CARD_BAND_WHITE)):
        ev.append(_dlg(layer, 0, ce, "CARD", f"{{\\p1\\pos(0,{y})\\c{col}\\bord0\\shad0}}m 0 0 l 1080 0 l 1080 {h} l 0 {h}{{\\p0}}"))
    cx, cy = spec.CARD_TEXT_POS
    ev.append(_dlg(spec.CARD_LAYER_TEXT, 0, ce, "CARD", f"{{\\an5\\pos({cx},{cy})\\fs{cfs}\\c&H000000&\\bord0\\shad0}}{card_text}"))
    # 제목 (영상 내내)
    for sty, txt, fs in (("HL1", title["h1"], fs1), ("HL2", title["h2"], fs2)):
        x, y = spec.HL_POS[sty]
        ev.append(_dlg(spec.HL_LAYER, 0, total, sty, f"{{\\an8\\pos({x},{y})\\fs{fs}}}{txt}"))
    # 본문 — 마지막 컷의 End는 t+d가 아니라 total (0.1초 꼬리까지 자막을 유지, 5/5 실측)
    groups = timing["groups"]
    for k, g in enumerate(groups):
        t0 = g["t"]
        t1 = total if k == len(groups) - 1 else round(g["t"] + g["d"], 3)
        y0 = spec.BODY_Y[g["color"]]
        for j, ln in enumerate(g["lines"]):
            ev.append(_dlg(spec.BODY_LAYER, t0, t1, g["color"],
                           f"{{\\an8\\pos({spec.BODY_X},{y0 + spec.LINE_GAP * j}){spec.ENTRANCE}}}{ln}"))
    return "\n".join(lines) + "\n" + "\n".join(ev) + "\n"


def dialogue_lines(ass_text):
    """비교용 — Dialogue 줄만 순서대로."""
    return [l for l in ass_text.splitlines() if l.startswith("Dialogue:")]
