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
    from PIL import Image, ImageDraw, ImageFilter
    E = R()["effects"]
    o = {**E.get(kind, {}), **dict(key)}
    if kind == "red_circle":
        d = int(o.get("size", 430)); sw = int(o["stroke"]); pad = 4
        im = Image.new("RGBA", (d + 2 * pad, d + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([pad, pad, pad + d, pad + d], outline=tuple(o["color"]) + (255,), width=sw)
        return im
    if kind == "arrow_green_down":
        w, h = int(o["w"]), int(o["h"])
        S = 4; W_, H_ = w * S, h * S
        g = 28 * S   # 번짐 여백
        im = Image.new("RGBA", (W_ + 2 * g, H_ + 2 * g), (0, 0, 0, 0))
        sh = 0.18 * W_          # 몸통 폭(확대 실측: 몸통 23px / 전체 131)
        head = 0.42 * H_        # 화살촉 높이
        arm = 0.27 * W_         # 화살촉 팔 굵기
        cx = g + W_ / 2
        body = [(cx - sh / 2, g), (cx + sh / 2, g), (cx + sh / 2, g + H_ - head), (cx - sh / 2, g + H_ - head)]
        tip = (cx, g + H_)
        chev = [(g, g + H_ - head), (g + arm, g + H_ - head - arm * 0.9), (cx, g + H_ - arm * 1.6), (g + W_ - arm, g + H_ - head - arm * 0.9),
                (g + W_, g + H_ - head), tip]
        col = tuple(o["color"])
        dark = tuple(int(c * 0.55) for c in col)
        m = Image.new("L", im.size, 0); dm = ImageDraw.Draw(m); dm.polygon(body, fill=255); dm.polygon(chev, fill=255)
        glow = m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(10 * S))
        gl = Image.new("RGBA", im.size, col + (0,)); gl.putalpha(glow.point(lambda v: int(v * 0.8)))
        im.alpha_composite(gl)
        bev = Image.new("RGBA", im.size, dark + (0,)); bev.putalpha(m); im.alpha_composite(bev, (3 * S, 3 * S))   # 오른쪽 아래 입체 테
        face = Image.new("RGBA", im.size, col + (0,)); face.putalpha(m); im.alpha_composite(face)
        return im.resize((im.size[0] // S, im.size[1] // S), Image.LANCZOS)
    if kind == "arrow_pink_up":
        w, h, px = int(o["w"]), int(o["h"]), int(o["pixel"])
        gw, gh = max(5, w // px), max(8, h // px)
        sm = Image.new("L", (gw + 2, gh + 2), 0); d = ImageDraw.Draw(sm)
        mid = (gw + 1) / 2
        hh = int(gh * 0.38)
        d.polygon([(mid, 1), (1, 1 + hh), (gw, 1 + hh)], fill=255)
        bw = max(2, gw // 3)
        d.rectangle([mid - bw / 2, 1 + hh, mid + bw / 2 - 1, gh], fill=255)
        big = sm.resize(((gw + 2) * px, (gh + 2) * px), Image.NEAREST)
        out = Image.new("RGBA", big.size, (0, 0, 0, 0))
        edge = big.filter(ImageFilter.MaxFilter(9))
        k = Image.new("RGBA", big.size, (10, 10, 10, 0)); k.putalpha(edge); out.alpha_composite(k)
        f = Image.new("RGBA", big.size, tuple(o["color"]) + (0,)); f.putalpha(big); out.alpha_composite(f)
        return out.resize((w + 2 * px, h + 2 * px), Image.NEAREST)
    if kind == "arrow_curve_red":
        w, h, sw = int(o["w"]), int(o["h"]), int(o["stroke"])
        S = 4
        im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        col = tuple(o["color"]) + (255,)
        p0, p1, p2 = (0.05 * w * S, 0.95 * h * S), (0.62 * w * S, 0.88 * h * S), (0.92 * w * S, 0.1 * h * S)   # 왼쪽 아래 → 오른쪽 위로 휘는 곡선
        pts = [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
               for t in np.linspace(0, 1, 60)]
        d.line(pts, fill=col, width=sw * S, joint="curve")
        ang = math.atan2(p2[1] - pts[-4][1], p2[0] - pts[-4][0])
        L = 0.28 * min(w, h) * S
        for s in (+1, -1):
            a = ang + math.pi + s * 0.55
            d.line([p2, (p2[0] + L * math.cos(a), p2[1] + L * math.sin(a))], fill=col, width=sw * S)
            d.ellipse([p2[0] - sw * S / 2, p2[1] - sw * S / 2, p2[0] + sw * S / 2, p2[1] + sw * S / 2], fill=col)
        return im.resize((w, h), Image.LANCZOS)
    if kind in ("money_emoji", "emoji"):
        src = Image.open(ROOT / E["money_emoji"]["asset"]).convert("RGBA")
        src = src.crop(src.getbbox())
        return src.resize((int(o.get("w", E["money_emoji"]["w"])), int(o.get("h", E["money_emoji"]["h"]))), Image.LANCZOS)
    raise ValueError(f"모르는 꾸밈 {kind}")


def dashed(r: int, sw: int, n: int, duty: float, deg: float, color):
    from PIL import Image, ImageDraw
    pad = sw
    im = Image.new("RGBA", (2 * (r + pad), 2 * (r + pad)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    box = [pad, pad, pad + 2 * r, pad + 2 * r]
    step = 360 / n
    for k in range(n):
        a = deg + k * step
        d.arc(box, a, a + step * duty, fill=tuple(color) + (255,), width=sw)
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
    if e["kind"] != "red_circle" and left <= E["exit_frames"] and e["kind"] != "flash":
        f = left / (E["exit_frames"] + 1)
        p["scale"] *= 0.6 + 0.4 * f; p["alpha"] = f
    if e["kind"] == "arrow_green_down":
        p["dy"] = o["bob_px"] * math.sin(2 * math.pi * (t - a) / o["bob_period"])
    if e["kind"] == "arrow_curve_red":
        s = o["poke_px"] * (0.5 - 0.5 * math.cos(2 * math.pi * (t - a) / o["poke_period"])) / math.sqrt(2)
        p["dx"], p["dy"] = s, -s
    if e["kind"] == "dashed_circle":
        p["deg"] = o["deg_per_s"] * (t - a)
    if e["kind"] == "flash":
        p["alpha"] = max(0.0, E["flash"]["alpha0"] * (1 - (t - a) / E["flash"]["dur"]))
    return p


# ── 그리기(미리곱한 알파 numpy) ─────────────────────────────────────────
def _pm(im):
    a = np.asarray(im).astype(np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return a


def _blit(dst, src_pm, cx, cy, alpha=1.0):
    """미리곱한 src 를 dst(층 좌표) 가운데 (cx, cy) 에 덮어 그림."""
    h, w = src_pm.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    X0, Y0_, X1, Y1_ = max(0, x0), max(0, y0), min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    if X1 <= X0 or Y1_ <= Y0_:
        return
    s = src_pm[Y0_ - y0:Y1_ - y0, X0 - x0:X1 - x0] * alpha
    d = dst[Y0_:Y1_, X0:X1]
    d *= (1 - s[..., 3:4]); d += s


@lru_cache(maxsize=256)
def _pm_sprite(kind, key, scale_q, deg_q):
    from PIL import Image
    im = sprite(kind, key)
    if kind == "dashed_circle":
        o = {**R()["effects"]["dashed_circle"], **dict(key)}
        im = dashed(int(o["radius"]), int(o["stroke"]), int(o["dashes"]), float(o["duty"]), deg_q, o["color"])
    if abs(scale_q - 1.0) > 1e-3:
        im = im.resize((max(1, int(im.size[0] * scale_q)), max(1, int(im.size[1] * scale_q))), Image.LANCZOS)
    return _pm(im)


@lru_cache(maxsize=512)
def _pm_caption(text, emph_key, big, blur):
    im = CS.caption_image(text, [dict(x) for x in emph_key], big)
    if blur:
        im = CS.hblur(im, blur)
    return _pm(im.crop((0, Y0, 1080, Y1)))


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
    fx = sorted(P["effects"], key=lambda e: e["T"][0])
    H = Y1 - Y0
    n = int(math.ceil(dur * FPS))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"1080x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "qtrle", str(out)]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    drawn = {"captions": 0, "effects": {}, "flash": []}
    buf = np.zeros((H, 1080, 4), np.float32)
    for f in range(n):
        t = f / FPS
        buf[:] = 0
        for e in fx:
            p = pose(e, t)
            if p is None:
                continue
            if e["kind"] == "flash":
                c = np.array(E["flash"]["colors"][e.get("color", "초록")], np.float32) / 255
                a = p["alpha"]
                buf[4:H - 4, :, :3] = buf[4:H - 4, :, :3] * (1 - a) + c * a
                buf[4:H - 4, :, 3] = buf[4:H - 4, :, 3] * (1 - a) + a
                continue
            key = tuple(sorted((k, v) for k, v in e.items() if k in ("size", "w", "h", "radius", "stroke")))
            spr = _pm_sprite(e["kind"], key, round(p["scale"], 2), round(p["deg"] / 3) * 3.0)
            _blit(buf, spr, e["at"][0] + p["dx"], e["at"][1] - Y0 + p["dy"], p["alpha"])
        c, blur = caption_at(caps, t)
        if c is not None:
            big = c.get("style") == "원음반응"
            cap = _pm_caption(c["text"], emph_for(S, c["line"], c["text"]), big, blur)
            d = buf; d *= (1 - cap[..., 3:4]); d += cap
        a = buf[..., 3:4]
        rgb = np.where(a > 1e-4, buf[..., :3] / np.maximum(a, 1e-4), 0)
        pr.stdin.write((np.concatenate([rgb, a], axis=2) * 255 + 0.5).clip(0, 255).astype(np.uint8).tobytes())
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


# ── 효과음 ─────────────────────────────────────────────────────────────
def sfx_events(P: dict) -> list[dict]:
    """(판단 주인: 효과음 자리) 꾸밈 사건 → [{t, slot, why}] (rules sfx.on·lead)."""
    Sx = R()["sfx"]
    out = []
    for e in P["effects"]:
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
                    "-c:v", "copy", "-c:a", "pcm_s16le", str(out.with_suffix(".mov"))], check=True)
    return out.with_suffix(".mov")


def main():
    if sys.argv[1] == "sheet":
        from PIL import Image
        E = R()["effects"]
        tiles = [sprite("red_circle", (("size", 430),)), dashed(E["dashed_circle"]["radius"], E["dashed_circle"]["stroke"], E["dashed_circle"]["dashes"],
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
