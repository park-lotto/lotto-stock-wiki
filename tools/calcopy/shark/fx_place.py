# -*- coding: utf-8 -*-
"""샥탬스토리 꾸밈 자리 제안 — 대본 줄 박자(fn)로 벤치 QMJ 와 같은 박자·같은 대상에 꾸밈을 놓는다 (관제 097, 2026-10-18).

(판단 주인)
  어느 줄에 어떤 꾸밈      propose()      — 박자 낱말·기본 자리는 rules.json placement
  0초 빨간 원 자리·첫 컷 크롭  hook_circle()  — ★얼굴 검출(YuNet)로 계산. 눈대중 금지(사장님 10-18 "빨간원 너무 안맞는다").
                              원 크기는 벤치 고정(r 209), 크롭을 얼굴 높이 337px(창 폭 0.31 = 상반신 중간 샷)로 맞추고 원 중심 = 얼굴 가운데·눈 +0.05fh.
                              초근접이라 크롭을 넓혀도 얼굴이 벤치 범위보다 크면 멈춘다(다른 컷을 고를 것).
  대상 꾸밈 자리           on_target()    — 재료 effects[].target = 'person'(NanoDet 사람 검출, 점선 원 기본) | 'face'(YuNet 머리) | 완성본 상자 [x0,y0,x1,y1](검출 못 하는 물건)
                              → 자리·크기는 벤치 비율로 계산. 대상 검출은 render.py --tts-only 의 실제 컷 시각(render_info)으로 소스 프레임을 잰다
  (how: 'face' = hook_circle 결과 / 'target' = on_target 결과 / 'auto' = propose — 손 좌표(how='hand')는 fix 가 대상 상자로 바꾼다)

    PYTHONUTF8=1 py tools/calcopy/shark/fx_place.py <편 폴더> <작업 폴더> [--write]   # 제안 표 + 1차 완성본 그 시각 프레임 시트(<작업>/fx_place.jpg)
    PYTHONUTF8=1 py tools/calcopy/shark/fx_place.py fix <편 폴더> [직전 render_info.json]   # 0초 원(얼굴)·대상 꾸밈 자리를 계산해 재료.json 에 씀
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.shark.caption_style import rules  # noqa: E402


def beat(fn: str) -> str:
    P = rules()["placement"]["beats"]
    for k, words in P.items():
        if any(w in (fn or "") for w in words):
            return k
    return "기타"


def propose(S: dict, info: dict) -> list[dict]:
    """줄 박자 → 꾸밈 목록[{line, kind, at, t, color?, why}]. t 는 줄 안 시각(렌더러 effects 가 완성본 시각으로 바꿈)."""
    PL = rules()["placement"]
    L = S["final"]["lines"]
    li = {x["id"]: x for x in info["lines"]}
    caps = {}
    for c in info["captions"]:
        caps.setdefault(c["line"], []).append(c)
    cuts = {}
    for c in info["cuts"]:
        if not c.get("dropped"):
            cuts.setdefault(c["line"], []).append(c)
    kind = {l["id"]: ("O" if l.get("kind") in ("orig", "원음") else "N") for l in L}
    bt = {l["id"]: beat(l.get("fn")) for l in L}
    out, used = [], set()

    def add(line, k, why, t=None, at=None, **kw):
        x = li[line]
        out.append({"line": line, "kind": k, "at": at or PL["at"][k], "t": t or [0.0, round(x["t1"] - x["t0"], 3)], "why": why, **kw})
        used.add((line, k))

    first = L[0]["id"]
    add(first, "red_circle", "벤치 0초 결말 반응 얼굴 빨간 원(첫 컷 내내) — 얼굴 자리는 눈으로", t=[0.0, round(cuts[first][0]["t1"] - li[first]["t0"], 3)])
    demo = [l["id"] for l in L if bt[l["id"]] == "시연" and kind[l["id"]] == "N"]
    if demo:
        add(demo[0], "arrow_green_down", "벤치 0.567~1.267 둘째 컷 제품 위 초록 아래 화살표 — 제품 자리는 눈으로", t=[0.0, 0.7])
    pain = [l["id"] for l in L if bt[l["id"]] == "불편"]
    if pain:
        p = next((x for x in pain if kind[x] == "O"), pain[0])
        d = li[p]["t1"] - li[p]["t0"]
        add(p, "dashed_circle", "벤치 9.3~11.6 기존 불편 장면 빨간 점선 원(돌며)", t=[0.2, round(min(d, 3.7), 3)])
        if d > 2.5:
            add(p, "flash", "벤치 11.2 불편 줄 빨강 번쩍", t=[round(min(d - 0.5, 3.0), 3), round(min(d, 3.45), 3)], color="빨강")
    num = re.compile(r"[0-9]")
    for l in L:   # 분홍 위 화살표 = 숫자 박자 줄의 숫자 조각 하나(벤치 12.017 '수십키로')
        if bt[l["id"]] == "숫자":
            c = next((c for c in caps.get(l["id"], []) if num.search(c["text"])), None)
            if c:
                x = li[l["id"]]
                add(l["id"], "arrow_pink_up", f"벤치 12.017~13.82 숫자 조각 분홍 위 화살표 — '{c['text']}'",
                    t=[round(c["t0"] - x["t0"], 3), round(min(c["t1"] - x["t0"], c["t0"] - x["t0"] + 1.8), 3)])
                break
    if len(demo) >= 2:
        d2 = demo[1]
        add(d2, "arrow_curve_red", "벤치 20.367~22.9 해결 장면 빨간 곡선 화살표(찌르기)+휙", t=[0.0, round(min(2.5, li[d2]["t1"] - li[d2]["t0"]), 3)])
    money = re.compile(PL["money_re"])
    def _offer(beats):
        return next((l["id"] for l in L if kind[l["id"]] == "O" and l["id"] != first and bt[l["id"]] in beats
                     and money.search(" ".join(c["text"] for c in caps.get(l["id"], [])))), None)
    offer = _offer(("제안",)) or _offer(("숫자",))   # 벤치 돈다발 = 투자 제안 금액 줄(매출 숫자 줄보다 먼저 고름)
    if offer:
        add(offer, "flash", "벤치 38.667 투자 제안 컷 초록 번쩍", t=[0.0, 0.45], color="초록")
        add(offer, "money_emoji", "벤치 38.7~40.0 날개 돈다발", t=[0.033, 1.333])
    dec = next((l["id"] for l in L if bt[l["id"]] == "성사" and l["id"] != offer), None)
    if dec:
        add(dec, "flash", "벤치 44.367 결정 빨강 번쩍", t=[0.0, 0.45], color="빨강")
    after = next((l["id"] for l in L if bt[l["id"]] == "결과"), None)
    if after:
        add(after, "flash", "벤치 45.667 거래 성공·결과 초록 번쩍", t=[0.0, 0.45], color="초록")
    # 번쩍이 분당 placement.flash_per_min 아래면 숫자·시연 줄 둘째 컷 시작(벤치 7.1·28.1 = 장면 넘김)에 초록을 보탠다
    dur = info["dur"]
    have = [li[e["line"]]["t0"] + e["t"][0] for e in out if e["kind"] == "flash"]
    for l in L:
        if len(have) / dur * 60 >= PL["flash_per_min"]:
            break
        if bt[l["id"]] in ("숫자", "시연", "불편") and len(cuts.get(l["id"], [])) >= 2:
            t = cuts[l["id"]][1]["t0"]
            if all(abs(t - h) > 3.0 for h in have):
                x = li[l["id"]]
                add(l["id"], "flash", "벤치 7.1·28.1 장면 넘김 초록 번쩍(분당 횟수 채움)", t=[round(t - x["t0"], 3), round(t - x["t0"] + 0.45, 3)], color="초록")
                have.append(t)
    return out


# ── 0초 빨간 원 = 얼굴 검출 ────────────────────────────────────────────
def _src_frame(path: Path, t: float):
    import numpy as np
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    W, H = (int(v) for v in r.stdout.strip().split(",")[:2])
    b = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True).stdout
    return np.frombuffer(b[:W * H * 3], np.uint8).reshape(H, W, 3), W, H


def hook_circle(src: Path, ss: float, dur: float, old_crop=None, old_at=None) -> dict:
    """(판단 주인: 0초 원 자리·첫 컷 크롭) 소스 컷의 얼굴(프레임 3장 중앙값) → {src_crop, at, size, face_src, fh_win, why}.
    창 1080×1052, 크롭은 창 비율 그대로(늘이기 없음) — narr_video.shot_clip 이 src_crop 을 잘라 창에 꽉 채운다."""
    import numpy as np
    from tools.calcopy.shark import fx_measure as FM, fx as FX
    E = rules()["effects"]
    RC = E["red_circle"]; F_ = RC["face"]
    wx, wy, ww, wh = E["window"]
    picks = []
    W = H = None
    for t in (ss + 0.1, ss + dur / 2, ss + max(0.1, dur - 0.1)):
        a, W, H = _src_frame(src, t)
        fs = FM.faces(a)
        if not fs:
            continue
        if old_crop and old_at:        # 원래 원이 가리키던 사람(소스 좌표로 되돌림) 가까운 얼굴
            x0, y0, cw, ch = old_crop
            sc = max(ww / cw, wh / ch)
            ox = x0 + (cw - ww / sc) / 2 + old_at[0] / sc
            oy = y0 + (ch - wh / sc) / 2 + (old_at[1] - wy) / sc
            f = min(fs, key=lambda f: (f["cx"] - ox) ** 2 + (f["cy"] - oy) ** 2)
        else:
            f = fs[0]
        picks.append(f)
    if not picks:
        raise ValueError(f"얼굴 못 찾음 {src.name}@{ss}")
    med = lambda k: float(np.median([f[k] for f in picks]))
    fh, fcx = med("h"), med("cx")
    eye_y = float(np.median([f["eye"][1] for f in picks]))
    s = F_["fh_target"] / fh
    s_min = max(wh / H, ww / W)            # 크롭이 소스보다 클 수 없다
    if s < s_min:
        s = s_min
    fh_win = fh * s / ww
    if not F_["fh_win_range"][0] <= fh_win <= F_["fh_win_range"][1]:
        raise ValueError(f"초근접 — 크롭을 다 넓혀도 얼굴/창 {fh_win:.2f} ∉ {F_['fh_win_range']} ({src.name}@{ss}, 얼굴 높이 {fh:.0f}px) → 다른 컷(상반신 중간 샷)을 고를 것")
    r_out = RC["size"] / 2
    tx, ty = F_["win_center"]

    def place(s, dy):
        ch = min(H, int(round(wh / s))); cw = min(W, int(round(ch * ww / wh)))
        s_ = wh / ch
        csx, csy = fcx, eye_y + dy * fh
        x0 = int(round(min(max(0, csx - tx / s_), W - cw)))
        y0 = int(round(min(max(0, csy - (ty - wy) / s_), H - ch)))
        cx, cy = (csx - x0) * s_, (csy - y0) * s_ + wy
        fits = not FX.outside([{"line": "hook", "kind": "red_circle", "at": [int(round(cx)), int(round(cy))], "size": RC["size"]}])   # 렌더가 막는 상자와 같은 판단(fx.outside)
        return fits, s_, x0, y0, cw, ch, cx, cy
    # 얼굴이 소스 가장자리(위·옆)에 붙어 원이 창 밖이면 ① 원 중심을 눈 아래로(벤치 범위 eye_dy 0.05→0.15) ② 그래도 안 되면 얼굴 범위 안에서 조금씩 당긴다(확대)
    tries = [(s, dy) for dy in (F_["eye_dy_fh"], 0.10, 0.15)]
    k = 1
    while fh * s * 1.02 ** k / ww <= F_["fh_win_range"][1]:
        tries.append((s * 1.02 ** k, 0.15)); k += 1
    for s_try, dy in tries:
        fits, s_, x0, y0, cw, ch, cx, cy = place(s_try, dy)
        if fits:
            break
    fh_win = fh * s_ / ww
    used_dy = dy
    s = s_
    if not fits:
        raise ValueError(f"원이 창 밖(중심 {cx:.0f},{cy:.0f}) — 얼굴이 소스 가장자리라 크롭으로 못 옮김 ({src.name}@{ss}) → 다른 컷")
    return {"src_crop": [x0, y0, cw, ch], "at": [int(round(cx)), int(round(cy))], "size": RC["size"], "scale": round(s, 4),
            "fh_win": round(fh_win, 3), "face_src": {"cx": round(fcx, 1), "eye_y": round(eye_y, 1), "h": round(fh, 1), "n": len(picks)},
            "why": f"얼굴 검출(YuNet {len(picks)}프레임) 얼굴 높이 {fh:.0f}px×{s:.3f} = 창 폭 {fh_win:.2f} · 원 중심 = 얼굴 가운데·눈+{used_dy}fh", "eye_dy_fh": used_dy}


# ── 대상 꾸밈 = 대상 상자 → 벤치 비율 ─────────────────────────────────────
def on_target(kind: str, box: list) -> dict:
    """(판단 주인: 대상 꾸밈 자리) box = 완성본 좌표 [x0,y0,x1,y1](무엇을 가리킬지 = 사람이 고름) → {at, radius?} (벤치 QMJ 실측 비율).
      점선 원  : 중심 = 상자 가운데, 반지름 = 상자 반대각선 × target_pad (r_range 안) — QMJ 9.3 자루를 통째로 감쌈
      초록 ↓   : 화살 끝 = 상자 위 끝 + 0.17×상자 높이(자루 윗부분에 꽂힘, QMJ 0.8 끝 y811·자루 위 673·자루 높이 ~800), 가로 = 상자 가운데
      빨간 곡선 : 화살 끝(틀 0.87,0.03) = 상자 왼쪽 아래 1/3 지점(QMJ 20.45 끝이 자루 아래 가장자리를 찌름)"""
    E = rules()["effects"]
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    wx, wy, ww, wh = E["window"]
    if kind == "dashed_circle":
        o = E["dashed_circle"]
        r = max(o["r_range"][0], min(o["r_range"][1], 0.5 * (bw ** 2 + bh ** 2) ** 0.5 * o["target_pad"]))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rp = r * max(o.get("pop") or [1.0])          # 등장 때 커진 크기까지 창 안(fx.outside 와 같은 상자)
        m = rp + o["stroke_ratio"] * rp / 2 + 2
        cx = min(max(cx, wx + m), wx + ww - m); cy = min(max(cy, wy + m), wy + wh - m)
        return {"at": [int(round(cx)), int(round(cy))], "radius": int(round(r))}
    if kind == "arrow_green_down":
        o = E["arrow_green_down"]
        tip_y = y0 + 0.17 * bh
        cy = tip_y - o["h"] / 2
        cy = max(cy, wy + o["h"] / 2 + o["bob_px"] + 30)
        cap0, cap1 = 880, 1030          # 자막 띠(한 줄 929~988·두 줄 895~1022) — 벤치 화살표는 자막을 안 덮는다(QMJ 614~811, 자막 위)
        if cy + o["h"] / 2 + o["bob_px"] > cap0 and cy - o["h"] / 2 - o["bob_px"] < cap1:
            cy = cap1 + o["bob_px"] + 5 + o["h"] / 2 if tip_y > (cap0 + cap1) / 2 else cap0 - o["bob_px"] - 5 - o["h"] / 2
        return {"at": [int(round((x0 + x1) / 2)), int(round(cy))]}
    if kind == "arrow_curve_red":
        o = E["arrow_curve_red"]
        tx, ty = x0 + bw / 3, y1
        ax, ay = tx - (0.87 - 0.5) * o["w"], ty - (0.03 - 0.5) * o["h"]
        m = o["poke_px"] / 2 ** 0.5 + 2           # 찌르기 폭까지 창 안(fx.outside 와 같은 상자)
        ax = min(max(ax, wx + o["w"] / 2 + m), wx + ww - o["w"] / 2 - m)
        ay = min(max(ay, wy + o["h"] / 2 + m), wy + wh - o["h"] / 2 - m)
        return {"at": [int(round(ax)), int(round(ay))]}
    raise ValueError(f"대상 자리 규칙 없음: {kind}")


def _final_frame(info: dict, cand: Path, t: float):
    """완성본 시각 t 의 소스 프레임 + 소스→완성본 좌표 바꾸기(직전 렌더/--tts-only render_info 컷의 소스·초·크롭)."""
    E = rules()["effects"]; wx, wy, ww, wh = E["window"]
    c = next(c for c in info["cuts"] if not c.get("dropped") and c["t0"] <= t < c["t1"])
    a, W, H = _src_frame(cand / c["src"], c["ss"] + (t - c["t0"]))
    x0, y0, cw, ch = c.get("src_crop") or [0, 0, W, H]
    sc = max(ww / cw, wh / ch)
    ox, oy = x0 + (cw - ww / sc) / 2, y0 + (ch - wh / sc) / 2

    def to_final(bx0, by0, bx1, by1):
        return [round((bx0 - ox) * sc + wx), round((by0 - oy) * sc + wy), round((bx1 - ox) * sc + wx), round((by1 - oy) * sc + wy)]
    inside = lambda x, y: ox <= x <= ox + ww / sc and oy <= y <= oy + wh / sc
    return a, to_final, inside, c


def scene_end(info: dict, cand: Path, t0: float, t1: float, th: float = 0.3) -> float:
    """완성본 [t0,t1) 안에서 화면이 처음 바뀌는 시각(컷 경계 또는 한 컷 안 원본 편집 경계, ffmpeg scene>th). 없으면 t1.
    점선 원은 장면과 같이 사라진다(벤치) — 렌더 컷 하나 안에 방송 편집 경계가 있으면 거기서 끊어야 다음 장면에 원이 남지 않는다(6편 L4)."""
    c = next(c for c in info["cuts"] if not c.get("dropped") and c["t0"] <= t0 < c["t1"])
    t1 = min(t1, c["t1"])
    a = c["ss"] + (t0 - c["t0"])
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{a:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(cand / c["src"]), "-vf",
                        f"select='gt(scene,{th})',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    ts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    return round(t0 + ts[0], 3) if ts else t1


def final_face(info: dict, cand: Path, t: float) -> list:
    """완성본 시각 t 의 창 안 머리 상자 [x0,y0,x1,y1](완성본 좌표, YuNet 상자 위로 0.35fh = 정수리)."""
    from tools.calcopy.shark import fx_measure as FM
    a, to_final, inside, _ = _final_frame(info, cand, t)
    fs = [f for f in FM.faces(a) if inside(f["cx"], f["cy"])]
    if not fs:
        raise ValueError(f"얼굴 없음 t={t}")
    f = fs[0]
    return to_final(f["x"], f["y"] - 0.35 * f["h"], f["x"] + f["w"], f["y"] + f["h"])


def final_person(info: dict, cand: Path, t0: float, t1: float) -> list:
    """완성본 [t0,t1) 동안 창 안에 계속 있는 사람 상자(NanoDet 'person') — 세 시각에서 겹침(IoU) 합이 가장 큰 사람(같으면 큰 사람).
    벤치 점선 원 = 불편을 겪는 사람(QMJ 9.3 허리 숙인 작업자)을 감싼다(페이블 10-18)."""
    from tools.calcopy.shark import fx_measure as FM
    ts = [t0 + 0.05, (t0 + t1) / 2, max(t0 + 0.05, t1 - 0.1)]
    sets = []
    for t in ts:
        a, to_final, inside, _ = _final_frame(info, cand, t)
        sets.append([to_final(p["x0"], p["y0"], p["x1"], p["y1"]) for p in FM.persons(a) if inside((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2)])
    if not sets[0]:
        raise ValueError(f"사람 없음 t={t0}")

    def iou(a, b):
        ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
        u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
        return ix * iy / max(1, u)
    E = rules()["effects"]; wx, wy, ww, wh = E["window"]
    def score(b):
        st = sum(max([iou(b, o) for o in S] or [0]) for S in sets[1:])
        area = (min(b[2], wx + ww) - max(b[0], wx)) * (min(b[3], wy + wh) - max(b[1], wy)) / (ww * wh)
        return st + 0.5 * area
    best = max(sets[0], key=score)
    return [max(wx, best[0]), max(wy, best[1]), min(wx + ww, best[2]), min(wy + wh, best[3])]


def track_person(info: dict, cand: Path, box: list, t0: float, t1: float, n: int = 13) -> list:
    """고른 사람 상자를 [t0,t1) 동안 따라간 중심 [[t−t0, cx, cy], …](완성본 좌표) — 매 시각 앞 상자와 가장 많이 겹치는 사람."""
    from tools.calcopy.shark import fx_measure as FM
    def iou(a, b):
        ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
        u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
        return ix * iy / max(1, u)
    out, cur = [], box
    for k in range(n):
        t = t0 + (t1 - t0 - 0.05) * k / (n - 1)
        a, to_final, inside, _ = _final_frame(info, cand, t)
        ps = [to_final(q["x0"], q["y0"], q["x1"], q["y1"]) for q in FM.persons(a)]
        if ps:
            b = max(ps, key=lambda b: iou(b, cur))
            if iou(b, cur) > 0.2:
                cur = b
        out.append([round(t - t0, 3), round((cur[0] + cur[2]) / 2), round((cur[1] + cur[3]) / 2)])
    sm = []   # 검출 흔들림을 3점 평균으로 펴서(원이 떨지 않게)
    for k in range(len(out)):
        w = out[max(0, k - 1):k + 2]
        sm.append([out[k][0], round(sum(x[1] for x in w) / len(w)), round(sum(x[2] for x in w) / len(w))])
    return sm


def fix(doc: Path, info: dict | None = None) -> list[str]:
    """재료.json: 0초 빨간 원 → hook_circle(첫 컷 크롭·자리), target 있는 꾸밈 → on_target(target='face' 면 직전 렌더 컷으로 머리 상자를 잼). 쓴 내용 줄 목록."""
    p = doc / "재료.json"
    M = json.loads(p.read_text(encoding="utf-8"))
    cand = Path(M["cand_dir"])
    log = []
    li = {x["id"]: x for x in (info or {}).get("lines", [])}
    for e in M["effects"]:
        if e["kind"] == "red_circle":
            sh = next(s for s in M["shots"] if s["line"] == e["line"])
            r = hook_circle(cand / sh["src"], float(sh["ss"]), float(sh["dur"]), sh.get("src_crop"), e.get("at"))
            sh["src_crop"] = r["src_crop"]; sh["scale"] = r["scale"]
            sh["why_crop"] = "fx_place.hook_circle: " + r["why"]
            for k in ("stroke",):
                e.pop(k, None)
            e.update({"at": r["at"], "size": r["size"], "how": "face", "face_src": r["face_src"], "fh_win": r["fh_win"]})
            log.append(f"{e['line']} red_circle at {r['at']} crop {r['src_crop']} 얼굴/창 {r['fh_win']}")
        elif e.get("target"):
            box = e["target"]
            if box in ("face", "person"):
                if not info:
                    raise ValueError("target face/person 은 render_info(--tts-only 로 만든 실제 컷 시각)가 필요")
                t = li[e["line"]]["t0"] + (e.get("t") or [0.0])[0]
                c = next(c for c in info["cuts"] if not c.get("dropped") and c["t0"] <= t + 0.2 < c["t1"])
                t_end = min(c["t1"], li[e["line"]]["t0"] + (e.get("t") or [0, 9])[1])
                if e["kind"] == "dashed_circle":
                    t_end = scene_end(info, cand, t + 0.05, t_end)
                    e["t"] = [e["t"][0], round(t_end - li[e["line"]]["t0"], 3)]
                box = final_face(info, cand, t + 0.2) if box == "face" else final_person(info, cand, t + 0.1, t_end)
                e["target_box"] = box
            r = on_target(e["kind"], box)
            e.update(r); e["how"] = "target"
            e.pop("track", None)
            if e["kind"] == "dashed_circle" and e["target"] == "person":
                # 벤치 점선 원은 대상이 가만있어 중심 고정(≤2.5px). 우리 대상이 움직이면(반지름 0.2 넘게) 원이 사람을 따라간다
                tr = track_person(info, cand, box, t + 0.1, t_end)
                mv = max(((x - tr[0][1]) ** 2 + (y - tr[0][2]) ** 2) ** 0.5 for _, x, y in tr)
                if mv > 0.2 * r["radius"]:
                    E_ = rules()["effects"]; wx, wy, ww, wh = E_["window"]
                    rp = r["radius"] * max(E_["dashed_circle"].get("pop") or [1.0])
                    m = rp + E_["dashed_circle"]["stroke_ratio"] * rp / 2 + 2
                    dx0, dy0 = r["at"][0] - tr[0][1], r["at"][1] - tr[0][2]
                    e["track"] = [[round(tt + 0.1 - (e["t"][0] - (t - li[e["line"]]["t0"])), 3),
                                   int(min(max(x + dx0, wx + m), wx + ww - m)), int(min(max(y + dy0, wy + m), wy + wh - m))] for tt, x, y in tr]
                    r["track_move_px"] = round(mv)
            log.append(f"{e['line']} {e['kind']} 대상 {e['target']} → {r}")
    p.write_text(json.dumps(M, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return log


def sheet(final: Path, info: dict, eff: list[dict], dst: Path):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 26)
    li = {x["id"]: x for x in info["lines"]}
    tiles = []
    for e in eff:
        t = li[e["line"]]["t0"] + e["t"][0] + 0.15
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(final), "-frames:v", "1", "-vf",
                            "crop=1080:1052:0:434,drawgrid=w=100:h=100:t=2:c=yellow@0.5,scale=360:351", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True)
        im = Image.frombytes("RGB", (360, 351), r.stdout[:360 * 351 * 3])
        d = ImageDraw.Draw(im)
        x, y = e["at"][0] / 3, (e["at"][1] - 434) / 3
        d.ellipse([x - 8, y - 8, x + 8, y + 8], outline=(255, 0, 255), width=3)
        d.text((4, 2), f"{e['line']} {e['kind']} {t:.1f}", font=font, fill=(255, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
        tiles.append(im)
    sh = Image.new("RGB", (360 * 4, 351 * ((len(tiles) + 3) // 4)))
    for i, im in enumerate(tiles):
        sh.paste(im, ((i % 4) * 360, (i // 4) * 351))
    sh.save(dst, quality=85)


def main():
    if sys.argv[1] == "fix":
        info = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")) if len(sys.argv) > 3 else None
        for x in fix(Path(sys.argv[2]), info):
            print(x)
        return
    doc, work = Path(sys.argv[1]), Path(sys.argv[2])
    S = json.loads((doc / "대본.json").read_text(encoding="utf-8"))
    info = json.loads((work / "render" / "render_info.json").read_text(encoding="utf-8"))
    eff = propose(S, info)
    for e in eff:
        print(e["line"], e["kind"], e["t"], e["at"], e.get("color", ""), "—", e["why"])
    sheet(work / "render" / "final.mp4", info, eff, work / "fx_place.jpg")
    print(work / "fx_place.jpg")
    if "--write" in sys.argv:
        p = doc / "재료.json"
        M = json.loads(p.read_text(encoding="utf-8"))
        hand = [e for e in M.get("effects") or [] if e.get("how") == "hand"]
        M["effects"] = hand + [{**e, "how": "auto"} for e in eff if not any(h["kind"] == e["kind"] and h["line"] == e["line"] for h in hand)]
        p.write_text(json.dumps(M, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("재료.json effects", len(M["effects"]))


if __name__ == "__main__":
    main()
