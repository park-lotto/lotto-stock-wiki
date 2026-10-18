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
@lru_cache(maxsize=32)
def sprite(kind: str, key: tuple = ()):
    """(판단 주인: 꾸밈 모양) → RGBA PIL. key = 크기 등 덮어쓰기 (이름, 값) 쌍."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    E = R()["effects"]
    o = {**E.get(kind, {}), **dict(key)}
    if kind == "red_circle":
        # 벤치 확대(QMJ·hZg·mVz 0.25): 선 11px + 양쪽 2px 부드러운 테, 그림자 없음 → 4배로 그려 줄이고 살짝 흐림
        d = int(o.get("size", 430)); sw = int(o["stroke"]); pad = 6; S = 4
        D = (d + 2 * pad) * S
        m = Image.new("L", (D, D), 0)
        ImageDraw.Draw(m).ellipse([pad * S, pad * S, (pad + d) * S, (pad + d) * S], outline=255, width=sw * S)
        m = m.resize((d + 2 * pad, d + 2 * pad), Image.LANCZOS).filter(ImageFilter.GaussianBlur(float(o.get("aa_blur", 0.8))))
        im = Image.new("RGBA", m.size, tuple(o["color"]) + (0,)); im.putalpha(m)
        return im
    if kind == "arrow_green_down":
        # 벤치 QMJ 0.8 확대: 가는 몸통 + 굵은 V 갈매기 머리(팔 굵기 arm·W, 45°), 밝은 초록 채움 + 안쪽 입체 테 + 바깥 번짐
        w, h = int(o["w"]), int(o["h"])
        S = 4; W_, H_ = w * S, h * S
        g = 28 * S   # 번짐 여백
        im = Image.new("RGBA", (W_ + 2 * g, H_ + 2 * g), (0, 0, 0, 0))
        sh = 0.18 * W_
        arm = float(o.get("arm", 0.24)) * W_
        top = float(o.get("head_top", 0.56)) * H_
        cx = g + W_ / 2
        tip = (cx, g + H_)
        m = Image.new("L", im.size, 0); dm = ImageDraw.Draw(m)
        dm.rectangle([cx - sh / 2, g, cx + sh / 2, g + H_ - arm], fill=255)
        a2 = arm / math.sqrt(2)
        dm.polygon([(g, g + top), (g + a2, g + top - a2), (cx, g + H_ - 2 * a2), (g + W_ - a2, g + top - a2), (g + W_, g + top), tip], fill=255)
        col = tuple(o["color"])
        dark = (0, 120, 0); lite = (150, 255, 140)
        glow = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(9 * S))
        gl = Image.new("RGBA", im.size, col + (0,)); gl.putalpha(glow.point(lambda v: int(v * 0.85)))
        im.alpha_composite(gl)
        face = Image.new("RGBA", im.size, col + (0,)); face.putalpha(m); im.alpha_composite(face)
        inner = m.filter(ImageFilter.MinFilter(4 * S + 1))
        rim_d = ImageChops.subtract(inner, ImageChops.offset(inner, -2 * S, -2 * S))   # 안쪽 오른쪽 아래 어두운 테
        rim_l = ImageChops.subtract(inner, ImageChops.offset(inner, S, S))             # 안쪽 왼쪽 위 밝은 테
        for rim, c in ((rim_d, dark), (rim_l, lite)):
            t = Image.new("RGBA", im.size, c + (0,)); t.putalpha(rim.point(lambda v: int(v * 0.9))); im.alpha_composite(t)
        return im.resize((im.size[0] // S, im.size[1] // S), Image.LANCZOS)
    if kind == "arrow_pink_up":
        # 벤치 QMJ 12.5 확대(칸 12px): 칸 그림 15×24 — 머리 계단 7줄·몸통 5칸·검정 테 1칸, 왼쪽 진한·오른쪽 연한 분홍 띠
        cw, ch = o.get("cells", [15, 24]); px = int(o["pixel"])
        K, MAIN, DK, LT = (10, 10, 10), tuple(o.get("main", o["color"])), tuple(o["dark"]), tuple(o["light"])
        grid = {}
        c = cw // 2
        grid[(c, 0)] = K
        for k in range(7):                       # 머리 줄 k: 분홍 c−k..c+k, 테 c±(k+1)
            y = 1 + k
            for x in range(c - k, c + k + 1):
                grid[(x, y)] = MAIN
            grid[(c - k, y)] = DK if k else LT
            grid[(c + k, y)] = LT
            grid[(c - k - 1, y)] = K; grid[(c + k + 1, y)] = K
        for x in range(1, cw - 1):
            grid[(x, 8)] = K
        for yy in range(8, ch - 1):              # 몸통 5칸(c−2..c+2)
            grid[(c - 3, yy)] = K; grid[(c + 3, yy)] = K
            for x in range(c - 2, c + 3):
                grid[(x, yy)] = MAIN
            grid[(c - 2, yy)] = DK; grid[(c + 2, yy)] = LT
        for x in range(c - 3, c + 4):
            grid[(x, ch - 1)] = K
        sm = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        for (x, y), v in grid.items():
            sm.putpixel((x, y), v + (255,))
        return sm.resize((cw * px, ch * px), Image.NEAREST)
    if kind == "arrow_curve_red":
        # 벤치 QMJ 20.45 확대: 붓 손그림 — 꼬리(왼쪽 아래, 가늘게) → 오른쪽 위 끝으로 휘는 굵기 변하는 선 + 열린 V 두 팔(끝 가늘게)
        w, h, sw = int(o["w"]), int(o["h"]), float(o["stroke"])
        S = 4
        im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        col = tuple(o["color"]) + (255,)

        def P(x, y):
            return (x * w * S, y * h * S)

        def brush(pts, w0, w1, w2):
            n = len(pts)
            for k in range(n - 1):
                f = k / (n - 1)
                ww = (w0 + (w1 - w0) * f / 0.6) if f < 0.6 else (w1 + (w2 - w1) * (f - 0.6) / 0.4)
                r_ = max(1.0, ww * S / 2)
                (x0, y0), (x1, y1) = pts[k], pts[k + 1]
                for t in np.linspace(0, 1, 4):
                    x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                    d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=col)

        def bez(p0, p1, p2, p3, n=80):
            a0, a1, a2, a3 = (np.array(v) for v in (p0, p1, p2, p3))
            return [tuple((1 - t) ** 3 * a0 + 3 * (1 - t) ** 2 * t * a1 + 3 * (1 - t) * t * t * a2 + t ** 3 * a3) for t in np.linspace(0, 1, n)]
        tip = P(0.87, 0.03)
        brush(bez(P(0.03, 0.97), P(0.40, 0.92), P(0.72, 0.62), tip), 0.25 * sw, 1.25 * sw, 0.9 * sw)
        brush(bez(tip, P(0.75, 0.10), P(0.55, 0.30), P(0.40, 0.42), 30), 1.0 * sw, 0.8 * sw, 0.25 * sw)     # 왼팔
        brush(bez(tip, P(0.92, 0.20), P(0.97, 0.40), P(0.98, 0.58), 30), 1.0 * sw, 0.8 * sw, 0.25 * sw)     # 오른팔
        return im.resize((w, h), Image.LANCZOS)
    if kind in ("money_emoji", "emoji"):
        src = Image.open(ROOT / E["money_emoji"]["asset"]).convert("RGBA")
        src = src.crop(src.getbbox())
        return src.resize((int(o.get("w", E["money_emoji"]["w"])), int(o.get("h", E["money_emoji"]["h"]))), Image.LANCZOS)
    raise ValueError(f"모르는 꾸밈 {kind}")


def dashed(r: int, sw: int, n: int, duty: float, deg: float, color):
    """점선 원(벤치: 점 6개·점 25°·납작한 끝) — r = 선 가운데 반지름. 4배로 그려 줄임(부드러운 테)."""
    from PIL import Image, ImageDraw
    S = 4
    pad = sw
    D = 2 * (r + pad)
    m = Image.new("L", (D * S, D * S), 0); d = ImageDraw.Draw(m)
    ro = r + sw / 2
    box = [(pad + r - ro) * S, (pad + r - ro) * S, (pad + r + ro) * S, (pad + r + ro) * S]
    step = 360 / n
    for k in range(n):
        a = deg + k * step
        d.arc(box, a, a + step * duty, fill=255, width=int(sw * S))
    m = m.resize((D, D), Image.LANCZOS)
    im = Image.new("RGBA", (D, D), tuple(color) + (0,)); im.putalpha(m)
    return im


# ── 움직임 ───────────────────────────────────────────────────────────
def pose(e: dict, t: float) -> dict | None:
    """(판단 주인: 꾸밈 움직임) 시각 t 의 {scale, dx, dy, alpha, deg} — 꾸밈 시간 밖이면 None."""
    E = R()["effects"]
    a, b = e["T"]
    if t < a - 1e-6 or t >= b - 1e-6:
        return None
    k = int(round((t - a) * FPS))
    left = int(round((b - t) * FPS))
    o = E.get(e["kind"], {})
    p = {"scale": 1.0, "dx": 0.0, "dy": 0.0, "alpha": 1.0, "deg": 0.0}
    if e["kind"] in ("arrow_pink_up", "money_emoji", "emoji") and k < len(E["pop"]["scales"]):
        p["scale"] = E["pop"]["scales"][k]
    if e["kind"] == "dashed_circle" and k < len(o["pop"]):     # 벤치 3편: 1.08 → 0.85(5~10프레임) → 1.0(14프레임째)
        p["scale"] = o["pop"][k]
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
        if e.get("track"):        # 대상이 움직일 때만(fx_place.fix 가 사람 검출로 적음): 꾸밈 시작 기준 [[초, x, y], …] 사이를 직선으로
            tr, u = e["track"], t - a
            k = max(0, min(len(tr) - 2, next((i for i in range(len(tr) - 1) if tr[i + 1][0] >= u), len(tr) - 2)))
            (t0_, x0_, y0_), (t1_, x1_, y1_) = tr[k], tr[k + 1]
            f = min(1.0, max(0.0, (u - t0_) / max(1e-6, t1_ - t0_)))
            p["dx"], p["dy"] = x0_ + (x1_ - x0_) * f - e["at"][0], y0_ + (y1_ - y0_) * f - e["at"][1]
    if e["kind"] == "flash":
        p["alpha"] = max(0.0, E["flash"]["alpha0"] * (1 - (t - a) / E["flash"]["dur"]))
    return p


# ── 그리기(미리곱한 알파 numpy) ─────────────────────────────────────────
@lru_cache(maxsize=512)
def _sprite_im(kind, key, scale_q, deg_q, alpha_q):
    """그릴 모양 한 장(PIL RGBA, 곧은 알파) — 배율·회전·투명도 값마다 한 번만 만든다."""
    from PIL import Image
    if kind == "dashed_circle":
        o = {**R()["effects"]["dashed_circle"], **dict(key)}
        r_ = int(round(o["radius"] * scale_q))
        im = dashed(r_, int(round(o.get("stroke") or o["stroke_ratio"] * r_)), int(o["dashes"]), float(o["duty"]), deg_q, o["color"])
        scale_q = 1.0   # 점선 원은 배율을 반지름으로 그렸다(선 두께 비 유지)
    else:
        im = sprite(kind, key)
    if abs(scale_q - 1.0) > 1e-3:
        im = im.resize((max(1, int(im.size[0] * scale_q)), max(1, int(im.size[1] * scale_q))), Image.LANCZOS)
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


def build_layer(P: dict, S: dict | None, out: Path, dur: float) -> dict:
    """완성본 길이 dur 의 RGBA 층(1080×(Y1−Y0), 30fps, qtrle mov) — 아래부터 번쩍 → 꾸밈 → 자막. 반환: 그린 사건 기록(검사·효과음용)."""
    E = R()["effects"]
    caps = sorted(P["captions"], key=lambda c: c["t0"])
    fx = sorted(timed(P), key=lambda e: e["T"][0])
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
                col = tuple(E["flash"]["colors"][e.get("color", "초록")])
                fl = Image.new("RGBA", (1080, H - 8), col + (int(round(p["alpha"] * 255)),))
                cv.alpha_composite(fl, (0, 4))
                continue
            key = tuple(sorted((k, v) for k, v in e.items() if k in ("size", "w", "h", "radius", "stroke")))
            im = _sprite_im(e["kind"], key, round(p["scale"], 2), round(p["deg"] / 3) * 3.0, round(p["alpha"], 2))
            x0 = int(round(e["at"][0] + p["dx"] - im.size[0] / 2)); y0 = int(round(e["at"][1] - Y0 + p["dy"] - im.size[1] / 2))
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
    drawn["captions"] = len(caps)
    drawn["emph_caps"] = sum(1 for c in caps if emph_for(S, c["line"], c["text"]))
    return drawn


def outside(effects: list[dict]) -> list[str]:
    """(판단 주인: 꾸밈이 창 안에 온전한가) 번쩍 빼고 제 크기 모양 상자(움직임 폭 포함)가 rules effects.window 안이어야 한다."""
    E = R()["effects"]
    wx, wy, ww, wh = E["window"]
    m = E["inside_window"]["margin_px"]
    out = []
    for e in effects:
        if e["kind"] == "flash":
            continue
        key = tuple(sorted((k, v) for k, v in e.items() if k in ("size", "w", "h", "radius", "stroke")))
        if e["kind"] == "dashed_circle":
            o = {**E["dashed_circle"], **dict(key)}
            rr = int(o["radius"]) * max(o.get("pop") or [1.0])          # 등장 때 1.08배로 커진 순간까지 창 안(6편 L4 페이블 10-18)
            w = h = 2 * rr + int(o.get("stroke") or o["stroke_ratio"] * rr)
        else:
            w, h = sprite(e["kind"], key).size
        o = E.get(e["kind"], {})
        mx = o.get("poke_px", 0) / math.sqrt(2)
        my = o.get("bob_px", 0) + mx
        for ax, ay in [e["at"]] + [p[1:] for p in e.get("track") or []]:   # 따라가는 점선 원은 길 위 모든 점
            x0, x1 = ax - w / 2 - mx, ax + w / 2 + mx
            y0, y1 = ay - h / 2 - my, ay + h / 2 + my
            if x0 < wx + m or x1 > wx + ww - m or y0 < wy + m or y1 > wy + wh - m:
                out.append(f"{e.get('line')} {e['kind']} 상자 x{x0:.0f}~{x1:.0f} y{y0:.0f}~{y1:.0f}")
                break
    return out


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
        from PIL import Image
        E = R()["effects"]
        tiles = [sprite("red_circle", (("size", 430),)), dashed(E["dashed_circle"]["radius"], int(E["dashed_circle"]["stroke_ratio"] * E["dashed_circle"]["radius"]), E["dashed_circle"]["dashes"],
                 E["dashed_circle"]["duty"], 0, E["dashed_circle"]["color"]), sprite("arrow_green_down"), sprite("arrow_pink_up"),
                 sprite("arrow_curve_red"), sprite("money_emoji")]
        W = sum(t.size[0] for t in tiles) + 20 * len(tiles)
        sh = Image.new("RGBA", (W, max(t.size[1] for t in tiles) + 20), (110, 90, 70, 255))
        x = 10
        for t in tiles:
            sh.alpha_composite(t, (x, 10)); x += t.size[0] + 20
        sh.convert("RGB").save(sys.argv[2])
        print(sys.argv[2])


if __name__ == "__main__":
    main()
