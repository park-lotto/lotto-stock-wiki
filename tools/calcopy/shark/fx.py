# -*- coding: utf-8 -*-
"""샥탬스토리 꾸밈 층 — 자막(낱말 색)·빨간 원·점선 원·화살표 3종·날개 돈다발·색 번쩍 + 효과음 자리 (관제 097, 2026-10-18).

판단 주인(한 함수씩, 값은 전부 rules.json):
  꾸밈 모양      sprite()          — 벤치 QMJ 10fps·30fps 실측 모양·크기·색
  꾸밈 움직임    pose()            — 등장(pop)·흔들(bob)·찌르기(poke)·돌기·끝 줄어듦, 시각 t → (배율, 이동, 회전, 투명도)
  자막 넘김      caption_at()      — 옛 자막 가로 흐림 1프레임 → 새 자막 가로 흐림 1프레임 → 선명
  효과음 자리    sfx_events()      — 번쩍 = 띠링, 빨간 곡선 화살표 = 휙(벤치 슬라이드 소리 대체)
render.py 는 build_layer()(RGBA 층 mov 한 개)·add_sfx()(소리 얹기)를 부르기만 한다.

    PYTHONUTF8=1 py tools/calcopy/shark/fx.py sheet <out.jpg>     # 꾸밈 견본 시트(벤치와 눈 대조용)
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.shark import caption_style as CS  # noqa: E402

FPS = 30
Y0, Y1 = 430, 1490          # 층 = 창(434~1486)을 덮는 띠 — 번쩍은 창 안만(벤치 창 밖 제목 띠는 안 물듦)
KINDS = ("red_circle", "dashed_circle", "arrow_green_down", "arrow_pink_up", "arrow_curve_red", "money_emoji", "emoji", "flash")


def R():
    return CS.rules()


# ── 모양 ─────────────────────────────────────────────────────────────
def _finish(m, color, S: int, outline=True, grad="down", light_k="grad_light"):
    """(판단 주인: 모양 마감, R4 고급화) 4배 마스크 m(L, 여백 포함) → 줄인 RGBA. 그림자(아래 부드럽게) → 진한 외곽선 → 은은한 그라데이션 채움.
    값은 rules effects.style 한 곳."""
    from PIL import Image, ImageChops, ImageFilter
    st = R()["effects"]["style"]
    col = np.array(color, float)
    W_, H_ = m.size
    out = Image.new("RGBA", m.size, (0, 0, 0, 0))
    sh = st["shadow"]
    base = m.filter(ImageFilter.MaxFilter(2 * st["outline_px"] * S + 1)) if outline else m
    sm = ImageChops.offset(base, int(sh["dx"] * S), int(sh["dy"] * S)).filter(ImageFilter.GaussianBlur(sh["blur"] * S))
    s_ = Image.new("RGBA", m.size, (0, 0, 0, 0)); s_.putalpha(sm.point(lambda v: int(v * sh["alpha"]))); out.alpha_composite(s_)
    if outline:
        o_ = Image.new("RGBA", m.size, tuple(int(v) for v in col * st["outline_dark"]) + (0,)); o_.putalpha(base); out.alpha_composite(o_)
    light = col + (255 - col) * st[light_k]
    ys = np.linspace(0, 1, H_)[:, None]
    if grad == "up":
        ys = 1 - ys
    g = (light[None, None, :] * (1 - ys[..., None]) + col[None, None, :] * ys[..., None]) * np.ones((1, W_, 1))
    f_ = Image.fromarray(np.dstack([g.astype(np.uint8), np.array(m)]), "RGBA")
    out.alpha_composite(f_)
    return out.resize((W_ // S, H_ // S), Image.LANCZOS)


def _round(m, S):
    """마스크 모서리 둥글게(흐린 뒤 문턱) — rules style.round_px."""
    from PIL import ImageFilter
    r = R()["effects"]["style"]["round_px"] * S
    return m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v >= 128 else 0)


PAD = 14   # 모양 둘레 여백(그림자·외곽선 자리, 위아래 같은 크기 → 모양 가운데 = 그림 가운데)


def tip_offset(kind: str, key: tuple = ()) -> tuple[float, float]:
    """(판단 주인: 꾸밈이 가리키는 점) 제 크기 그림 가운데(= 재료 at) 기준 끝점(px). 화살표 = 끝, 원·이모지 = 가운데(0,0). on_target·적중 검사·그리기가 같이 쓴다.
    재료 at 기준점 = 그림 가운데: 초록 ↓ 끝 = (at.x, at.y + h/2) · 분홍 ↑ 끝 = (at.x, at.y − h/2) · 빨간 곡선 끝 = at + (0.37w, −0.47h).
    손으로 적을 땐 at 대신 tip(가리킬 점)을 적으면 렌더가 at_from_tip 으로 바꾼다 — 가장 좋은 건 target(상자) + fx_place.fix."""
    E = R()["effects"]
    o = {**E.get(kind, {}), **dict(key)}
    if kind == "arrow_green_down":
        return 0.0, o["h"] / 2
    if kind == "arrow_pink_up":
        return 0.0, -o["h"] / 2
    if kind == "arrow_curve_red":
        return (0.87 - 0.5) * o["w"], (0.03 - 0.5) * o["h"]
    return 0.0, 0.0


def at_from_tip(kind: str, tip, key: tuple = ()) -> list:
    """재료 effects[].tip(가리킬 점, 완성본 좌표) → at(그림 가운데). ★at 은 끝점이 아니다(10-20 10편: at 에 끝점을 적어 30/30 빗나감)."""
    tx, ty = tip_offset(kind, key)
    return [int(round(tip[0] - tx)), int(round(tip[1] - ty))]


def _straight_arrow(w, h, shaft, head_h, S, up=False):
    from PIL import Image, ImageDraw
    p = PAD * S
    W_, H_ = w * S + 2 * p, h * S + 2 * p
    m = Image.new("L", (W_, H_), 0); d = ImageDraw.Draw(m)
    cx = W_ / 2; sw = shaft * w * S; hh = head_h * h * S
    top, bot = p, p + h * S
    d.rectangle([cx - sw / 2, top, cx + sw / 2, bot - hh + S], fill=255)
    d.polygon([(p, bot - hh), (W_ - p, bot - hh), (cx, bot)], fill=255)
    m = _round(m, S)
    if up:
        m = m.transpose(Image.FLIP_TOP_BOTTOM)
    return m


@lru_cache(maxsize=64)
def sprite(kind: str, key: tuple = ()):
    """(판단 주인: 꾸밈 모양) → RGBA PIL(둘레 여백 PAD, 가운데 = 모양 가운데). key = 크기 등 덮어쓰기 (이름, 값) 쌍. sweep = 빨간 원 그려진 비율(0~1)."""
    from PIL import Image, ImageDraw, ImageFilter
    E = R()["effects"]
    S = int(E["style"]["ss"])
    o = {**E.get(kind, {}), **dict(key)}
    if kind == "red_circle":
        # 벤치 확대: 선 11px + 부드러운 테. R4: 그려지듯 나타남(sweep, 12시부터 시계 방향, 둥근 끝) + 은은한 그림자
        d = int(o.get("size", 430)); sw = float(o.get("stroke") or E["red_circle"]["stroke"]); sweep = float(o.get("sweep", 1.0))
        p = PAD * S; D = d * S + 2 * p
        m = Image.new("L", (D, D), 0); dr = ImageDraw.Draw(m)
        box = [p + sw * S / 2, p + sw * S / 2, D - p - sw * S / 2, D - p - sw * S / 2]
        rr = (box[2] - box[0]) / 2; c0 = D / 2
        if sweep >= 0.999:
            dr.ellipse([c0 - rr - sw * S / 2, c0 - rr - sw * S / 2, c0 + rr + sw * S / 2, c0 + rr + sw * S / 2], outline=255, width=int(sw * S))
        else:
            a1 = -90 + 360 * sweep
            dr.arc([c0 - rr - sw * S / 2, c0 - rr - sw * S / 2, c0 + rr + sw * S / 2, c0 + rr + sw * S / 2], -90, a1, fill=255, width=int(sw * S))
            for ang in (-90, a1):      # 둥근 끝
                x = c0 + rr * math.cos(math.radians(ang)); y = c0 + rr * math.sin(math.radians(ang))
                dr.ellipse([x - sw * S / 2, y - sw * S / 2, x + sw * S / 2, y + sw * S / 2], fill=255)
        return _finish(m, o["color"], S, outline=False, light_k="ring_grad_light")
    if kind == "arrow_green_down":
        return _finish(_straight_arrow(int(o["w"]), int(o["h"]), float(o["shaft"]), float(o["head_h"]), S), o["color"], S)
    if kind == "arrow_pink_up":
        return _finish(_straight_arrow(int(o["w"]), int(o["h"]), float(o["shaft"]), float(o["head_h"]), S, up=True), o.get("main", o["color"]), S, grad="up")
    if kind == "arrow_curve_red":
        # 벤치 QMJ 20.45 확대: 붓 손그림 — 꼬리(왼쪽 아래, 가늘게) → 오른쪽 위 끝으로 휘는 굵기 변하는 선 + 열린 V 두 팔(끝 가늘게)
        w, h, sw = int(o["w"]), int(o["h"]), float(o["stroke"])
        p = PAD * S
        m = Image.new("L", (w * S + 2 * p, h * S + 2 * p), 0); d = ImageDraw.Draw(m)

        def P(x, y):
            return (p + x * w * S, p + y * h * S)

        def brush(pts, w0, w1, w2):
            n = len(pts)
            for k in range(n - 1):
                f = k / (n - 1)
                ww = (w0 + (w1 - w0) * f / 0.6) if f < 0.6 else (w1 + (w2 - w1) * (f - 0.6) / 0.4)
                r_ = max(1.0, ww * S / 2)
                (x0, y0), (x1, y1) = pts[k], pts[k + 1]
                for t in np.linspace(0, 1, 4):
                    x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                    d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=255)

        def bez(p0, p1, p2, p3, n=80):
            a0, a1, a2, a3 = (np.array(v) for v in (p0, p1, p2, p3))
            return [tuple((1 - t) ** 3 * a0 + 3 * (1 - t) ** 2 * t * a1 + 3 * (1 - t) * t * t * a2 + t ** 3 * a3) for t in np.linspace(0, 1, n)]
        tip = P(0.87, 0.03)
        brush(bez(P(0.03, 0.97), P(0.40, 0.92), P(0.72, 0.62), tip), 0.25 * sw, 1.25 * sw, 0.9 * sw)
        brush(bez(tip, P(0.75, 0.10), P(0.55, 0.30), P(0.40, 0.42), 30), 1.0 * sw, 0.8 * sw, 0.25 * sw)     # 왼팔
        brush(bez(tip, P(0.92, 0.20), P(0.97, 0.40), P(0.98, 0.58), 30), 1.0 * sw, 0.8 * sw, 0.25 * sw)     # 오른팔
        return _finish(m, o["color"], S)
    if kind in ("money_emoji", "emoji"):
        src = Image.open(ROOT / E["money_emoji"]["asset"]).convert("RGBA")
        src = src.crop(src.getbbox())
        im = src.resize((int(o.get("w", E["money_emoji"]["w"])), int(o.get("h", E["money_emoji"]["h"]))), Image.LANCZOS)
        out = Image.new("RGBA", (im.size[0] + 2 * PAD, im.size[1] + 2 * PAD), (0, 0, 0, 0))
        sh = E["style"]["shadow"]
        a = Image.new("L", out.size, 0); a.paste(im.getchannel("A"), (PAD + sh["dx"], PAD + sh["dy"]))
        s_ = Image.new("RGBA", out.size, (0, 0, 0, 0)); s_.putalpha(a.filter(ImageFilter.GaussianBlur(sh["blur"])).point(lambda v: int(v * sh["alpha"])))
        out.alpha_composite(s_); out.alpha_composite(im, (PAD, PAD))
        return out
    raise ValueError(f"모르는 꾸밈 {kind}")


def dashed(r: int, sw: int, n: int, duty: float, deg: float, color):
    """점선 원(벤치: 점 6개·점 25°) — r = 선 가운데 반지름. 4배로 그려 줄임 + 둥근 끝 + 마감(그림자, R4)."""
    from PIL import Image, ImageDraw
    S = int(R()["effects"]["style"]["ss"])
    pad = sw + PAD
    D = 2 * (r + pad)
    m = Image.new("L", (D * S, D * S), 0); d = ImageDraw.Draw(m)
    c0 = D * S / 2
    step = 360 / n
    for k in range(n):
        a = deg + k * step
        d.arc([c0 - r * S - sw * S / 2, c0 - r * S - sw * S / 2, c0 + r * S + sw * S / 2, c0 + r * S + sw * S / 2], a, a + step * duty, fill=255, width=int(sw * S))
        for ang in (a, a + step * duty):
            x = c0 + r * S * math.cos(math.radians(ang)); y = c0 + r * S * math.sin(math.radians(ang))
            d.ellipse([x - sw * S / 2, y - sw * S / 2, x + sw * S / 2, y + sw * S / 2], fill=255)
    return _finish(m, color, S, outline=False, light_k="ring_grad_light")


# ── 움직임 ───────────────────────────────────────────────────────────
ARROWS = ("arrow_green_down", "arrow_pink_up", "arrow_curve_red")
POPS = ARROWS + ("money_emoji", "emoji")


def _pop(k: int) -> tuple[float, float]:
    """(배율, 흔들 각도) 등장 k 프레임째 — ease-out-back 팝 + 감쇠 흔들(rules effects.pop)."""
    o = R()["effects"]["pop"]
    n = o["frames"]
    sc = 1.0
    if k < n:
        u = (k + 1) / n
        c1 = o["overshoot"]; c3 = c1 + 1
        e = 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2
        sc = o["from"] + (1 - o["from"]) * e
    rot = 0.0
    if k < o["wobble_frames"]:
        u = k / o["wobble_frames"]
        rot = o["wobble_deg"] * math.sin(2 * math.pi * o["wobble_cycles"] * u) * (1 - u)
    return sc, rot


def track_at(tr: list, u: float) -> list:
    """[[초, a, b, …], …] 사이를 직선으로(끝은 멈춤) — 대상 길·꾸밈 길 공통."""
    if len(tr) == 1:
        return list(tr[0][1:])
    k = max(0, min(len(tr) - 2, next((i for i in range(len(tr) - 1) if tr[i + 1][0] >= u), len(tr) - 2)))
    (t0_, *a), (t1_, *b) = tr[k], tr[k + 1]
    f = min(1.0, max(0.0, (u - t0_) / max(1e-6, t1_ - t0_)))
    return [x + (y - x) * f for x, y in zip(a, b)]


def pose(e: dict, t: float) -> dict | None:
    """(판단 주인: 꾸밈 움직임) 시각 t 의 {scale, dx, dy, alpha, deg, rot, sweep} — 꾸밈 시간 밖이면 None.
    dx/dy = 대상 따라감(track) + 흔들(bob)·찌르기(poke). 화살표 배율·회전은 끝점 기준(place)."""
    E = R()["effects"]
    a, b = e["T"]
    if t < a - 1e-6 or t >= b - 1e-6:
        return None
    k = int(round((t - a) * FPS))
    left = int(round((b - t) * FPS))
    o = E.get(e["kind"], {})
    p = {"scale": 1.0, "dx": 0.0, "dy": 0.0, "alpha": 1.0, "deg": 0.0, "rot": 0.0, "sweep": 1.0}
    if e["kind"] in POPS:
        p["scale"], p["rot"] = _pop(k)
    if e["kind"] == "dashed_circle" and k < len(o["pop"]):     # 벤치 3편: 1.08 → 0.85(5~10프레임) → 1.0(14프레임째)
        p["scale"] = o["pop"][k]
    if e["kind"] == "red_circle":
        p["sweep"] = min(1.0, (k + 1) / max(1, int(o.get("draw_frames", 1))))
    if e["kind"] not in ("red_circle", "flash", "dashed_circle") and left <= E["exit_frames"]:   # 실선·점선 원은 컷과 같이 사라짐(실측)
        f = left / (E["exit_frames"] + 1)
        p["scale"] *= 0.6 + 0.4 * f; p["alpha"] = f
    if e["kind"] == "arrow_green_down":
        p["dy"] = o["bob_px"] * math.sin(2 * math.pi * (t - a) / o["bob_period"])
    if e["kind"] == "arrow_curve_red":
        s = o["poke_px"] * (0.5 - 0.5 * math.cos(2 * math.pi * (t - a) / o["poke_period"])) / math.sqrt(2)
        p["dx"], p["dy"] = s, -s
    if e["kind"] == "dashed_circle":
        p["deg"] = o["deg_per_s"] * (t - a)
    if e.get("track"):        # 대상 따라감(fx_place.fix 가 추적으로 적음): 꾸밈 시작 기준 [[초, x, y], …] = 그 시각 at
        x, y = track_at(e["track"], t - a)
        p["dx"] += x - e["at"][0]; p["dy"] += y - e["at"][1]
    if e["kind"] == "flash":
        F = E["flash"]
        if F.get("style") == "edge":
            u = min(1.0, (t - a) / F["edge_dur"])
            p["alpha"] = max(0.0, F["edge_alpha0"] * (1 - u) ** 2)     # 감속으로 사라짐
        else:
            p["alpha"] = max(0.0, F["alpha0"] * (1 - (t - a) / F["dur"]))
    return p


def _rot(v, deg):
    th = math.radians(deg)
    return v[0] * math.cos(th) + v[1] * math.sin(th), -v[0] * math.sin(th) + v[1] * math.cos(th)


def _key(e: dict) -> tuple:
    return tuple(sorted((k, v) for k, v in e.items() if k in ("size", "w", "h", "radius", "stroke")))


def place(e: dict, p: dict) -> dict:
    """(판단 주인: 그리는 자리) pose → {cx, cy, tip:[x,y]}(완성본 좌표). 화살표는 끝점이 제자리(at+끝+움직임)에 고정된 채 커지고 돈다."""
    tx, ty = tip_offset(e["kind"], _key(e))
    tip = (e["at"][0] + tx + p["dx"], e["at"][1] + ty + p["dy"])
    if e["kind"] in ARROWS:
        vx, vy = _rot((tx * p["scale"], ty * p["scale"]), p["rot"])
        return {"cx": tip[0] - vx, "cy": tip[1] - vy, "tip": list(tip)}
    return {"cx": e["at"][0] + p["dx"], "cy": e["at"][1] + p["dy"], "tip": [e["at"][0] + p["dx"], e["at"][1] + p["dy"]]}


@lru_cache(maxsize=8)
def _edge_mask(w: int, h: int):
    """번쩍 가장자리 빛 모양(0~1) — 타원 거리 clear 안쪽 0, 가장자리 1(부드럽게). rules effects.flash.clear·soft."""
    F = R()["effects"]["flash"]
    ys, xs = np.mgrid[0:h, 0:w]
    dd = np.sqrt(((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2) / math.sqrt(2)   # 모서리 = 1, 변 가운데 = 0.71
    c0 = F["clear"] * 0.7071
    u = np.clip((dd - c0) / max(1e-6, (0.7071 - c0) * (1 + F["soft"])), 0, 1)
    return (u * u * (3 - 2 * u)).astype(np.float32)


def flash_look(luma: float | None) -> tuple[float, float]:
    """(판단 주인: 번쩍 세기·색을 장면 밝기에 맞춤) 가장자리 평균 밝기 luma(0~255, 없으면 옛 값) → (tint, α 배율).
    밝은(흰) 장면에선 흰빛 섞은 색이 바탕에 묻힌다 → tint 를 줄이고 α 를 조금 올린다(rules effects.flash.bright)."""
    F = R()["effects"]["flash"]
    b = F.get("bright")
    if luma is None or not b:
        return F["tint"], 1.0
    u = min(1.0, max(0.0, (luma - b["luma"][0]) / (b["luma"][1] - b["luma"][0])))
    return F["tint"] * (1 - u), 1.0 + b["alpha_gain"] * u


def flash_scene_luma(fx: list[dict], bed: Path) -> None:
    """번쩍마다 그 시각 바탕 영상(번쩍 얹기 전)의 창 가장자리(_edge_mask>0.5) 평균 밝기를 e['scene_luma'] 에 적는다."""
    E = R()["effects"]; wx, wy, ww, wh = E["window"]
    em = _edge_mask(ww, wh) > 0.5
    for e in fx:
        if e["kind"] != "flash":
            continue
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{e['T'][0] + 0.02:.3f}", "-i", str(bed), "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if len(raw) != 1080 * 1920 * 3:
            continue
        f = np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3)[wy:wy + wh, wx:wx + ww][em].astype(float)
        e["scene_luma"] = round(float((f @ np.array([0.299, 0.587, 0.114])).mean()), 1)


def flash_image(color, alpha: float, w: int, h: int, tint: float | None = None):
    """(판단 주인: 번쩍 모양) R4 가장자리 빛(edge) — 옛 전면 원색(style 없음)도 그대로 그릴 수 있다. tint = flash_look 값(없으면 rules)."""
    from PIL import Image
    F = R()["effects"]["flash"]
    col = np.array(color, float)
    if F.get("style") == "edge":
        col = col + (255 - col) * (F["tint"] if tint is None else tint)
        a = (_edge_mask(w, h) * alpha * 255).astype(np.uint8)
    else:
        a = np.full((h, w), int(round(alpha * 255)), np.uint8)
    rgb = np.broadcast_to(col.astype(np.uint8), (h, w, 3))
    return Image.fromarray(np.dstack([rgb, a]), "RGBA")


# ── 그리기(미리곱한 알파 numpy) ─────────────────────────────────────────
@lru_cache(maxsize=512)
def _sprite_im(kind, key, scale_q, deg_q, alpha_q, rot_q=0.0, sweep_q=1.0):
    """그릴 모양 한 장(PIL RGBA, 곧은 알파) — 배율·회전·투명도·그려진 비율 값마다 한 번만 만든다."""
    from PIL import Image
    if kind == "dashed_circle":
        o = {**R()["effects"]["dashed_circle"], **dict(key)}
        r_ = int(round(o["radius"] * scale_q))
        im = dashed(r_, int(round(o.get("stroke") or o["stroke_ratio"] * r_)), int(o["dashes"]), float(o["duty"]), deg_q, o["color"])
        scale_q = 1.0   # 점선 원은 배율을 반지름으로 그렸다(선 두께 비 유지)
    else:
        im = sprite(kind, key + ((("sweep", sweep_q),) if sweep_q < 0.999 else ()))
    if abs(scale_q - 1.0) > 1e-3:
        im = im.resize((max(1, int(im.size[0] * scale_q)), max(1, int(im.size[1] * scale_q))), Image.LANCZOS)
    if abs(rot_q) > 0.05:
        im = im.rotate(rot_q, resample=Image.BICUBIC, expand=True)
    if alpha_q < 0.999:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha_q)))
    return im


@lru_cache(maxsize=512)
def _cap_im(text, emph_key, big, blur):
    """자막 띠 한 장(PIL RGBA, CS.BAND 높이)."""
    im = CS.caption_image(text, [dict(x) for x in emph_key], big).crop((0, CS.BAND[0], 1080, CS.BAND[1]))
    return CS.hblur(im, blur) if blur else im


def emph_for(S: dict | None, line: str, text: str) -> tuple:
    """대본 final.lines[line].emph 에서 이 자막 조각의 (span, color) — 없으면 ()."""
    if not S:
        return ()
    for l in S["final"]["lines"]:
        if l["id"] == line:
            for e in l.get("emph") or []:
                if e["cap"] == text:
                    return (tuple(sorted({"span": e["span"], "color": e["color"]}.items())),)
    return ()


def caption_at(caps: list[dict], t: float):
    """(판단 주인: 자막 넘김) 시각 t 에 그릴 (자막, 흐림 px). 넘김 = 옛 자막 흐림 1프레임 → 새 자막 흐림 1프레임 → 선명(rules caption.transition)."""
    T = R()["caption"]["transition"]
    for i, c in enumerate(caps):
        if c["t0"] - 1e-6 <= t < c["t1"] - 1e-6:
            k = int(round((t - c["t0"]) * FPS))
            prev = caps[i - 1] if i > 0 and abs(caps[i - 1]["t1"] - c["t0"]) < 0.02 else None
            if prev is not None and k == 0:
                return prev, T["old_blur_px"]
            if prev is not None and k == 1:
                return c, T["new_blur_px"]
            return c, 0
    return None, 0


def build_layer(P: dict, S: dict | None, out: Path, dur: float, bed: Path | None = None) -> dict:
    """완성본 길이 dur 의 RGBA 층(1080×(Y1−Y0), 30fps, qtrle mov) — 아래부터 번쩍 → 꾸밈 → 자막. 반환: 그린 사건 기록(검사·효과음용).
    bed = 번쩍 얹기 전 바탕 영상 — 주면 번쩍 세기·색을 장면 밝기에 맞춘다(flash_look)."""
    E = R()["effects"]
    caps = sorted(P["captions"], key=lambda c: c["t0"])
    fx = sorted(timed(P), key=lambda e: e["T"][0])
    if bed is not None:
        flash_scene_luma(fx, bed)
    bad = outside(fx)
    if bad:
        raise ValueError(f"꾸밈이 창 밖으로 나감(rules effects.inside_window) — 재료 크롭/자리 고칠 것: {bad}")
    H = Y1 - Y0
    n = int(math.ceil(dur * FPS))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"1080x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "qtrle", str(out)]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    drawn = {"captions": 0, "effects": {}, "flash": []}
    from PIL import Image
    for f in range(n):
        t = f / FPS
        cv = Image.new("RGBA", (1080, H), (0, 0, 0, 0))
        for e in sorted(fx, key=lambda e: e["kind"] == "flash"):   # 겹침 순서 = 꾸밈 → 번쩍 → 자막(rules effects.flash.order)
            p = pose(e, t)
            if p is None:
                continue
            if e["kind"] == "flash":
                tint, gain = flash_look(e.get("scene_luma"))
                cv.alpha_composite(flash_image(E["flash"]["colors"][e.get("color", "초록")], round(min(1.0, p["alpha"] * gain), 3), 1080, H - 8, round(tint, 3)), (0, 4))
                continue
            im = _sprite_im(e["kind"], _key(e), round(p["scale"], 2), round(p["deg"] / 3) * 3.0, round(p["alpha"], 2),
                            round(p["rot"], 1), round(p["sweep"], 3))
            pl = place(e, p)
            x0 = int(round(pl["cx"] - im.size[0] / 2)); y0 = int(round(pl["cy"] - Y0 - im.size[1] / 2))
            cv.alpha_composite(im, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))
        c, blur = caption_at(caps, t)
        if c is not None:
            cv.alpha_composite(_cap_im(c["text"], emph_for(S, c["line"], c["text"]), c.get("style") == "원음반응", blur), (0, CS.BAND[0] - Y0))
        pr.stdin.write(cv.tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise RuntimeError(f"층 인코딩 실패 {out}")
    for e in fx:
        drawn["effects"][e["kind"]] = drawn["effects"].get(e["kind"], 0) + 1
        if e["kind"] == "flash":
            drawn["flash"].append(e["T"][0])
            if e.get("scene_luma") is not None:
                drawn.setdefault("flash_luma", []).append([e["T"][0], e["scene_luma"], *[round(v, 3) for v in flash_look(e["scene_luma"])]])
    drawn["captions"] = len(caps)
    drawn["emph_caps"] = sum(1 for c in caps if emph_for(S, c["line"], c["text"]))
    return drawn


def outside(effects: list[dict]) -> list[str]:
    """(판단 주인: 꾸밈이 창 안에 온전한가) 번쩍 빼고 제 크기 모양 상자(움직임 폭 포함, 그림자 여백 PAD 뺌)가 rules effects.window 안이어야 한다."""
    E = R()["effects"]
    wx, wy, ww, wh = E["window"]
    m = E["inside_window"]["margin_px"]
    out = []
    for e in effects:
        if e["kind"] == "flash":
            continue
        key = _key(e)
        if e["kind"] == "dashed_circle":
            o = {**E["dashed_circle"], **dict(key)}
            rr = int(o["radius"]) * max(o.get("pop") or [1.0])          # 등장 때 1.08배로 커진 순간까지 창 안(6편 L4 페이블 10-18)
            w = h = 2 * rr + int(o.get("stroke") or o["stroke_ratio"] * rr)
        else:
            w, h = (v - 2 * PAD for v in sprite(e["kind"], key).size)
        o = E.get(e["kind"], {})
        mx = o.get("poke_px", 0) / math.sqrt(2)
        my = o.get("bob_px", 0) + mx
        for ax, ay in [e["at"]] + [p[1:3] for p in e.get("track") or []]:   # 따라가는 꾸밈은 길 위 모든 점
            x0, x1 = ax - w / 2 - mx, ax + w / 2 + mx
            y0, y1 = ay - h / 2 - my, ay + h / 2 + my
            if x0 < wx + m or x1 > wx + ww - m or y0 < wy + m or y1 > wy + wh - m:
                out.append(f"{e.get('line')} {e['kind']} 상자 x{x0:.0f}~{x1:.0f} y{y0:.0f}~{y1:.0f}")
                break
    return out


# ── 적중 검사(R4 "확실할 때만") ─────────────────────────────────────────
def _dist_box(x, y, b) -> float:
    dx = max(b[0] - x, 0, x - b[2]); dy = max(b[1] - y, 0, y - b[3])
    return math.hypot(dx, dy)


def hit_report(e: dict) -> dict:
    """(판단 주인: 효과가 대상에 맞나) 꾸밈 프레임마다 끝점(화살표)·원 중심이 대상 상자(target_path / target_box) 위·안인가 + 추적 신뢰도.
    flash 는 대상 없음(통과). 이모지는 얼굴 가림만 fx_place 가 본다(face_cover). 0초 빨간 원은 물건 원(how=object)·얼굴 검사 통과(face_clear)여야 한다(R3).
    반환 {ok, why, n, miss, worst_px}. render.effects 가 ok=False 면 뺀다."""
    E = R()["effects"]; G = R()["target"]
    k = e["kind"]
    if k == "flash":
        return {"ok": True, "why": "대상 없음(번쩍)"}
    if k in ("money_emoji", "emoji"):
        if e.get("face_cover") is not None and e["face_cover"] > G["face_cover_max"]:
            return {"ok": False, "why": f"얼굴 가림 {e['face_cover']:.2f}>{G['face_cover_max']}"}
        return {"ok": True, "why": "장식(대상 없음)" + ("" if e.get("face_cover") is not None else " · 얼굴 가림 안 잼")}
    if k == "red_circle" and not (e.get("how") == "object" and e.get("face_clear") is True):
        return {"ok": False, "why": "R3: 0초 원은 물건 원(fx_place.hook_object — 얼굴 겹침 거절 통과)만 — 얼굴 원·검사 안 한 원은 뺀다"}
    if e.get("drop"):
        return {"ok": False, "why": e["drop"]}
    box0 = e.get("target_box") or (e["target"] if isinstance(e.get("target"), list) else None)    # 계산된 상자 | 손 상자(target 목록, 고정)
    tp = e.get("target_path") or ([[0.0, *box0]] if box0 else None)
    if not tp:
        return {"ok": False, "why": "대상 상자 없음(target) — 확실하지 않은 효과는 넣지 않는다(R4)"}
    th = G["det_min"] if e.get("track_how") == "detect" else G["ncc_min"]
    if e.get("track_conf") is not None and e["track_conf"] < th:
        return {"ok": False, "why": f"대상 추적 신뢰도 {e['track_conf']:.2f}<{th} ({e.get('track_how')})"}
    a, b = e["T"]
    n, miss, worst = 0, 0, 0.0
    for f in range(int(math.ceil((b - a) * FPS))):
        t = a + f / FPS
        p = pose(e, t)
        if p is None:
            continue
        box = track_at(tp, t - a)
        pl = place(e, p)
        n += 1
        if k in ARROWS:
            d = _dist_box(pl["tip"][0], pl["tip"][1], box)
            bad = d > G["tip_tol_px"]
        else:
            d = _dist_box(pl["cx"], pl["cy"], box)
            bad = d > 0
            if k == "red_circle":     # 물건 전체를 감싸나: 선 안쪽 반지름 ≥ 상자 반대각선(페이블 10-20)
                r_in = e.get("size", E["red_circle"]["size"]) / 2 - float(e.get("stroke") or E["red_circle"]["stroke"])
                bad = bad or r_in < 0.5 * ((box[2] - box[0]) ** 2 + (box[3] - box[1]) ** 2) ** 0.5 - 1
        worst = max(worst, d)
        miss += bad
    ok = n > 0 and miss == 0
    return {"ok": ok, "n": n, "miss": miss, "worst_px": round(worst, 1),
            "why": ("대상 위 " if ok else f"빗나감 {miss}/{n}프레임 ") + f"(최대 {worst:.0f}px, 추적 {e.get('track_how', '고정')} {e.get('track_conf', '')})"}


def gate(effects: list[dict]) -> tuple[list[dict], list[dict]]:
    """적중 검사로 (그릴 것, 뺀 것[{line, kind, why}]) — render.effects 가 부른다(뺀 이유는 render_info fx_dropped)."""
    keep, drop = [], []
    for e in effects:
        h = hit_report(e)
        (keep if h["ok"] else drop).append({**e, "hit": h} if h["ok"] else {"line": e.get("line"), "kind": e["kind"], "why": h["why"]})
    return keep, drop


def E_FLASH_DUR():
    return R()["effects"]["flash"]["dur"]


def timed(P: dict) -> list[dict]:
    """(판단 주인: 번쩍 시각·점선 원 끝) 점선 원은 컷 끝에서 끝난다. 번쩍은 컷 프레임에 걸린다(벤치 QMJ 38.667·44.367·45.667 = 컷 첫 프레임) — 재료 t 가 컷 시작과 0.1초 안이면 컷 시작으로 붙인다.
    층 그리기·효과음 자리가 둘 다 이 결과를 쓴다(따로 계산하지 않는다)."""
    starts = [c["t0"] for c in P.get("cuts") or [] if not c.get("dropped")]
    out = []
    ends = sorted(c["t1"] for c in P.get("cuts") or [] if not c.get("dropped"))
    for e in sorted(P["effects"], key=lambda e: e["kind"] != "dashed_circle"):   # 점선 원 먼저(빨강 번쩍이 그 끝을 본다)
        if e["kind"] == "dashed_circle" and ends:   # 점선 원은 컷과 같이 사라진다(벤치 3편 실측) — 다음 장면으로 넘어가지 않게 컷 끝에서 자름
            c1 = next((x for x in ends if x > e["T"][0] + 1e-3), None)
            if c1 is not None and c1 < e["T"][1]:
                e = {**e, "T": [e["T"][0], round(c1, 3)], "cut_end": True}
        if e["kind"] == "flash" and e.get("color") == "빨강":   # 불편 줄 빨강 번쩍은 점선 원이 떠 있는 동안(벤치 QMJ 11.2 = 점선 9.27~11.53 안, 번쩍이 원을 물들임)
            dc = next((x for x in out if x["kind"] == "dashed_circle" and x["line"] == e["line"]), None)
            if dc and e["T"][0] > dc["T"][1] - 0.3:
                t0 = round(max(dc["T"][0] + 0.3, dc["T"][1] - 0.35), 3)
                e = {**e, "T": [t0, round(t0 + E_FLASH_DUR(), 3)], "moved_into_dashed": True}
        if e["kind"] == "flash" and starts:
            c = min(starts, key=lambda x: abs(x - e["T"][0]))
            if 1e-6 < abs(c - e["T"][0]) <= 0.1:
                d = c - e["T"][0]
                e = {**e, "T": [round(c, 3), round(e["T"][1] + d, 3)], "snapped": round(d, 3)}
        out.append(e)
    return out


# ── 효과음 ─────────────────────────────────────────────────────────────
def sfx_events(P: dict) -> list[dict]:
    """(판단 주인: 효과음 자리) 꾸밈 사건 → [{t, slot, why}] (rules sfx.on·lead)."""
    Sx = R()["sfx"]
    out = []
    for e in timed(P):
        slot = Sx["on"].get(e["kind"])
        if slot:
            out.append({"t": round(max(0.0, e["T"][0] + Sx["lead"].get(slot, 0.0)), 3), "slot": slot, "why": e["kind"]})
    return sorted(out, key=lambda x: x["t"])


def add_sfx(bed_mp4: Path, events: list[dict], R_: Path) -> Path:
    """소리 바닥(mp4 의 소리)에 효과음을 얹은 새 mp4(영상 복사). 크기 = sfx_pack 칸 목표 크기(_gain_for) + rules sfx.gain_db."""
    if not events:
        return bed_mp4
    from shopping_shorts import sfx_pack
    Sx = R()["sfx"]
    packs = dict(sfx_pack.list_packs())
    if Sx["pack"] not in packs:
        raise RuntimeError(f"효과음 팩 {Sx['pack']} 없음")
    d = Path(packs[Sx["pack"]])
    ins, fc, lab = [], [], []
    for k, e in enumerate(events):
        f = d / f"{e['slot']}.wav"
        g = sfx_pack._gain_for(str(f), e["slot"]) * 10 ** (Sx["gain_db"] / 20)
        ins += ["-i", str(f)]
        fc.append(f"[{k + 1}:a]aresample=48000,aformat=channel_layouts=mono,volume={g:.4f},adelay={int(e['t'] * 1000)}:all=1[s{k}]")
        lab.append(f"[s{k}]")
    fc.append(f"[0:a]aresample=48000,aformat=channel_layouts=mono[b];[b]{''.join(lab)}amix=inputs={len(lab) + 1}:normalize=0:duration=first[a]")
    out = R_ / "final_src_sfx.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bed_mp4), *ins, "-filter_complex", ";".join(fc), "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "pcm_f32le", str(out.with_suffix(".mov"))], check=True)
    return out.with_suffix(".mov")


def main():
    if sys.argv[1] == "sheet":
        # 꾸밈 견본 시트: 1줄 = 제 크기 모양 6종 / 2줄 = 등장(원 그려짐·화살표 팝·흔들) 프레임 / 3줄 = 번쩍(창 1/3 축소, --bg 그림 위)
        from PIL import Image
        E = R()["effects"]
        bg = Image.open(sys.argv[sys.argv.index("--bg") + 1]).convert("RGBA") if "--bg" in sys.argv else None
        tiles = [sprite("red_circle", (("size", 430),)), dashed(E["dashed_circle"]["radius"], int(E["dashed_circle"]["stroke_ratio"] * E["dashed_circle"]["radius"]), E["dashed_circle"]["dashes"],
                 E["dashed_circle"]["duty"], 0, E["dashed_circle"]["color"]), sprite("arrow_green_down"), sprite("arrow_pink_up"),
                 sprite("arrow_curve_red"), sprite("money_emoji")]
        anim = []
        for k in (0, 2, 4, 6):
            sw = min(1.0, (k + 1) / E["red_circle"]["draw_frames"])
            anim.append(_sprite_im("red_circle", (("size", 240),), 1.0, 0.0, 1.0, 0.0, round(sw, 3)))
        for k in (0, 2, 4, 6, 9, 13):
            sc, rot = _pop(k)
            anim.append(_sprite_im("arrow_green_down", (), round(sc, 2), 0.0, 1.0, round(rot, 1), 1.0))
        rows = [tiles, anim]
        if "flash" in E and hasattr(sys, "argv"):
            fl = []
            for col in ("초록", "빨강"):
                for t in (0.0, 0.1):
                    p = pose({"kind": "flash", "T": [0.0, 1.0], "at": [540, 960]}, t)
                    base = (bg.resize((360, 351)) if bg else Image.new("RGBA", (360, 351), (110, 90, 70, 255))).copy()
                    base.alpha_composite(flash_image(E["flash"]["colors"][col], p["alpha"], 1080, 1052).resize((360, 351)))
                    fl.append(base)
            rows.append(fl)
        W = max(sum(t.size[0] for t in r) + 20 * len(r) for r in rows) + 10
        Hs = [max(t.size[1] for t in r) + 20 for r in rows]
        sh = Image.new("RGBA", (W, sum(Hs)), (110, 90, 70, 255))
        y = 0
        for r, hh in zip(rows, Hs):
            x = 10
            for t in r:
                sh.alpha_composite(t, (x, y + 10)); x += t.size[0] + 20
            y += hh
        sh.convert("RGB").save(sys.argv[2])
        print(sys.argv[2])


if __name__ == "__main__":
    main()
