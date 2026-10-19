# -*- coding: utf-8 -*-
"""샥탬스토리 꾸밈 자리 제안 — 대본 줄 박자(fn)로 벤치 QMJ 와 같은 박자·같은 대상에 꾸밈을 놓는다 (관제 097, 2026-10-18).

(판단 주인)
  어느 줄에 어떤 꾸밈      propose()      — 박자 낱말·기본 자리는 rules.json placement
  0초 빨간 원 = 물건        hook_object()  — R3(사장님 10-19 "처음에 빨간원 얼굴에 하지말고"): 물건 상자(손 상자 | 제미나이 무료 키풀 object_box)
                              → 추적 → 원 중심 = 물건 가운데. 얼굴 상자(YuNet)와 원판이 겹치면 거절(ValueError). hook_circle(얼굴)은 옛 크롭 계산용으로만 남김
  대상 꾸밈 자리           on_target()    — 끝점(fx.tip_offset)이 대상 상자 가장자리에 닿게. 자막 띠 덮음·창 밖이면 drop(억지로 안 둠, R4)
  대상 따라가기            track_box()    — 정규 상관 템플릿(물건) / NanoDet 연속(사람), 신뢰도 → 렌더 fx.hit_report 가 적중 검사
  대상 재는 화면           cut_canvas()   — 렌더와 같은 narr_video.shot_clip 으로 컷을 그려 잰다(src_crop·세로 영상·그림 move 다 같은 길, 좌표 = 완성본)

    PYTHONUTF8=1 py tools/calcopy/shark/fx_place.py <편 폴더> <작업 폴더> [--write]   # 제안 표 + 1차 완성본 그 시각 프레임 시트(<작업>/fx_place.jpg)
    PYTHONUTF8=1 py tools/calcopy/shark/fx_place.py fix <편 폴더> <--tts-only render_info.json>   # 물건 원·대상 꾸밈 자리·길을 계산해 재료.json 에 씀
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

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


# ── 대상 꾸밈 = 대상 상자 → 끝점이 상자 가장자리에 닿게(R4) ─────────────────
CAP_BAND = (880, 1030)   # 자막 띠(한 줄 929~988·두 줄 895~1022) — 화살표가 자막을 덮으면 대상을 못 가리킨다(벤치 화살표도 자막을 안 덮음)


def on_target(kind: str, box: list, avoid_caption: bool = True) -> dict:
    """(판단 주인: 대상 꾸밈 자리) box = 완성본 좌표 [x0,y0,x1,y1] → {at, radius?} 또는 {drop: 이유}.
    끝점(fx.tip_offset)이 상자 가장자리에 정확히 닿는다(tip_gap_px 만큼 안쪽):
      초록 ↓   : 끝 = 상자 위 변 가운데 · 분홍 ↑ : 끝 = 상자 아래 변 가운데 · 빨간 곡선 : 끝 = 아래 변 왼쪽 1/3(찌르기가 상자 안으로)
      점선 원  : 중심 = 상자 가운데, 반지름 = 상자 반대각선 × target_pad (r_range 안) — 창 밖이면 줄이거나(r_range 하한까지) 상자 안에서 옮긴다
    화살표 몸통이 자막 띠를 덮거나 창 밖이면 놓지 않는다(drop) — 억지로 딴 데 두지 않는다(R4). 대상이 자막 자체면(avoid_caption=False) 띠 검사 안 함(끝이 자막 잉크 가장자리)."""
    from tools.calcopy.shark import fx as FX
    E = rules()["effects"]; G = rules()["target"]
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    wx, wy, ww, wh = E["window"]
    gap = G["tip_gap_px"]
    if kind == "dashed_circle":
        o = E["dashed_circle"]
        r = max(o["r_range"][0], min(o["r_range"][1], 0.5 * (bw ** 2 + bh ** 2) ** 0.5 * o["target_pad"]))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        k = max(o.get("pop") or [1.0]) * (1 + o["stroke_ratio"] / 2)
        room = min(cx - wx, wx + ww - cx, cy - wy, wy + wh - cy) - 2
        if r * k > room:                                  # 줄인다(하한까지) → 그래도 넘치면 상자 안에서 창 안쪽으로 옮긴다
            r = max(o["r_range"][0], room / k)
            m = r * k + 2
            cx2 = min(max(cx, wx + m), wx + ww - m); cy2 = min(max(cy, wy + m), wy + wh - m)
            if not (x0 <= cx2 <= x1 and y0 <= cy2 <= y1):
                return {"drop": f"점선 원이 창 안에 안 들어감(대상 상자 {box}, 반지름 {r:.0f})"}
            cx, cy = cx2, cy2
        return {"at": [int(round(cx)), int(round(cy))], "radius": int(round(r))}
    if kind not in FX.ARROWS:
        raise ValueError(f"대상 자리 규칙 없음: {kind}")
    o = E[kind]
    if kind == "arrow_green_down":
        tip = ((x0 + x1) / 2, y0 + gap)
    elif kind == "arrow_pink_up":
        tip = ((x0 + x1) / 2, y1 - gap)
    else:
        tip = (x0 + bw / 3, y1 - gap)
    tx, ty = FX.tip_offset(kind)
    at = [tip[0] - tx, tip[1] - ty]
    mx = o.get("poke_px", 0) / 2 ** 0.5
    my = o.get("bob_px", 0) + mx
    ax0, ax1 = at[0] - o["w"] / 2 - mx, at[0] + o["w"] / 2 + mx
    ay0, ay1 = at[1] - o["h"] / 2 - my, at[1] + o["h"] / 2 + my
    if ax0 < wx or ax1 > wx + ww or ay0 < wy or ay1 > wy + wh:
        return {"drop": f"{kind} 몸통이 창 밖(끝 {tip[0]:.0f},{tip[1]:.0f}) — 대상이 창 가장자리"}
    if avoid_caption and ay1 > CAP_BAND[0] and ay0 < CAP_BAND[1]:
        return {"drop": f"{kind} 몸통이 자막 띠({CAP_BAND})를 덮음 — 대상 상자 {box}"}
    return {"at": [int(round(at[0])), int(round(at[1]))]}


# ── 완성본 화면 = 렌더와 같은 길(narr_video.shot_clip)로 그린 컷 캔버스 ──────────
WINDOW = {"x": 0, "y": 434, "w": 1080, "h": 1052}   # 캔버스 창 top = (1920−1052)/2 = 434 = 완성본 창 y → 캔버스 좌표 = 완성본 좌표


def _cut_at(info: dict, t: float) -> dict:
    return next(c for c in info["cuts"] if not c.get("dropped") and c["t0"] <= t < c["t1"])


def cut_canvas(info: dict, cand: Path, c: dict) -> Path:
    """(판단 주인: 효과 대상 재기용 화면) 컷 하나를 렌더와 **같은 함수**(narr_video.shot_clip: src_crop·ar·fit·move·그림 파일)로 1080×1920 캔버스 mp4 로.
    소스 좌표 바꾸기를 따로 계산하지 않는다(그림 움직임·세로 영상·박힌 자막 crop 이 다 같은 길) — 결과 좌표 = 완성본 좌표."""
    from tools.calcopy import narr_video as nv
    d = Path(info.get("_dir") or Path(info.get("narr_placed", ".")).parent) / "fxcut"
    d.mkdir(parents=True, exist_ok=True)
    key = f"{Path(c['src']).stem}_{c['ss']}_{c['dur']}_{'-'.join(map(str, c.get('src_crop') or []))}_{c.get('ar')}_{c.get('fit')}_{json.dumps(c.get('move'))}"
    out = d / (re.sub(r"[^0-9A-Za-z_.-]", "_", key)[:120] + ".mp4")
    if not out.exists():
        nv.shot_clip(cand / c["src"], c["ss"], c["dur"], WINDOW, 750, True, out, c.get("ar"), None, c.get("fit") or "cover", 0,
                     c.get("src_crop"), bool(c.get("loop")), True, None, None, c.get("move"))
    return out


def canvas_frames(info: dict, cand: Path, t0: float, t1: float, fps: float) -> tuple[list[float], np.ndarray, dict]:
    """완성본 [t0, min(t1, 컷 끝)) 을 fps 로 — (시각들, 프레임 (n,1920,1080,3) 반 크기 아님, 컷)."""
    c = _cut_at(info, t0)
    t1 = min(t1, c["t1"] - 1e-3)
    p = cut_canvas(info, cand, c)
    a = t0 - c["t0"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{max(0.04, t1 - t0):.3f}", "-i", str(p), "-vf", f"fps={fps}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (1080 * 1920 * 3)
    fr = np.frombuffer(raw[:n * 1080 * 1920 * 3], np.uint8).reshape(n, 1920, 1080, 3)
    return [round(t0 + k / fps, 3) for k in range(n)], fr, c


def _final_frame(info: dict, cand: Path, t: float):
    """완성본 시각 t 의 화면(캔버스 = 완성본 좌표) — (rgb, to_final(항등), inside(창 안), 컷)."""
    _, fr, c = canvas_frames(info, cand, t, t + 0.05, 30)
    E = rules()["effects"]; wx, wy, ww, wh = E["window"]
    return fr[0], (lambda a, b, c_, d: [round(a), round(b), round(c_), round(d)]), (lambda x, y: wx <= x <= wx + ww and wy <= y <= wy + wh), c


def scene_end(info: dict, cand: Path, t0: float, t1: float, th: float = 0.3) -> float:
    """완성본 [t0,t1) 안에서 화면이 처음 바뀌는 시각(컷 경계 또는 한 컷 안 원본 편집 경계, ffmpeg scene>th). 없으면 t1.
    꾸밈은 장면과 같이 사라진다(벤치) — 렌더 컷 하나 안에 방송 편집 경계가 있으면 거기서 끊어야 다음 장면에 꾸밈이 남지 않는다(6편 L4)."""
    c = _cut_at(info, t0)
    t1 = min(t1, c["t1"])
    p = cut_canvas(info, cand, c)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{t0 - c['t0']:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(p), "-vf",
                        f"select='gt(scene,{th})',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    ts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr) if float(x) > 0.02]
    return round(t0 + ts[0], 3) if ts else t1


def face_boxes(rgb: np.ndarray) -> list[list]:
    """완성본 프레임의 창 안 얼굴 상자들 [x0,y0,x1,y1](YuNet = cv2.FaceDetectorYN, 위로 0.35fh = 정수리까지)."""
    from tools.calcopy.shark import fx_measure as FM
    E = rules()["effects"]; wx, wy, ww, wh = E["window"]
    out = []
    for f in FM.faces(rgb):
        if wx <= f["cx"] <= wx + ww and wy <= f["cy"] <= wy + wh:
            out.append([f["x"], f["y"] - 0.35 * f["h"], f["x"] + f["w"], f["y"] + f["h"]])
    return out


def final_face(info: dict, cand: Path, t: float) -> list:
    """완성본 시각 t 의 창 안 머리 상자 [x0,y0,x1,y1]."""
    a, _, _, _ = _final_frame(info, cand, t)
    fs = face_boxes(a)
    if not fs:
        raise ValueError(f"얼굴 없음 t={t}")
    return [round(v) for v in fs[0]]


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / max(1, u)


def final_person(info: dict, cand: Path, t0: float, t1: float) -> list:
    """완성본 [t0,t1) 동안 창 안에 계속 있는 사람 상자(NanoDet 'person') — 세 시각에서 겹침(IoU) 합이 가장 큰 사람(같으면 큰 사람).
    벤치 점선 원 = 불편을 겪는 사람(QMJ 9.3 허리 숙인 작업자)을 감싼다(페이블 10-18)."""
    from tools.calcopy.shark import fx_measure as FM
    E = rules()["effects"]; wx, wy, ww, wh = E["window"]
    sets = []
    for t in [t0 + 0.05, (t0 + t1) / 2, max(t0 + 0.05, t1 - 0.1)]:
        a, _, inside, _ = _final_frame(info, cand, t)
        sets.append([[p["x0"], p["y0"], p["x1"], p["y1"]] for p in FM.persons(a) if inside((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2)])
    if not sets[0]:
        raise ValueError(f"사람 없음 t={t0}")

    def score(b):
        st = sum(max([_iou(b, o) for o in S] or [0]) for S in sets[1:])
        area = (min(b[2], wx + ww) - max(b[0], wx)) * (min(b[3], wy + wh) - max(b[1], wy)) / (ww * wh)
        return st + 0.5 * area
    best = max(sets[0], key=score)
    return [round(max(wx, best[0])), round(max(wy, best[1])), round(min(wx + ww, best[2])), round(min(wy + wh, best[3]))]


def object_box(rgb: np.ndarray, what: str) -> tuple[list | None, str]:
    """(판단 주인: 물건 상자) 완성본 프레임 창에서 '무엇'의 상자 — 제미나이 무료 키풀(engine/gemini_free.ask, 버텍스 0).
    반환 ([x0,y0,x1,y1] 완성본 좌표 | None, 까닭). 못 찾음·확신 낮음·상자가 창의 60% 넘게 = None(확실할 때만, R4)."""
    import io
    from PIL import Image
    from tools.calcopy.engine import gemini_free as GF
    E = rules()["effects"]; wx, wy, ww, wh = E["window"]
    win = Image.fromarray(rgb[wy:wy + wh, wx:wx + ww])
    buf = io.BytesIO(); win.save(buf, "JPEG", quality=90)
    prompt = (f"In this video frame, find exactly this object: \"{what}\". "
              "Return JSON {\"found\": true|false, \"box_2d\": [ymin, xmin, ymax, xmax] normalized 0-1000 tightly around the whole object, "
              "\"label\": short name of what you boxed, \"confidence\": 0..1}. If it is not clearly visible, found=false. Do not box a person's face unless asked.")
    d, err = GF.ask([buf.getvalue()], prompt, tag="shark_object_box")
    if d is None:
        return None, f"제미나이 실패 {err}"
    model = d.get("_model")
    if isinstance(d.get("items"), list) and d["items"]:
        d = d["items"][0]
    if d.get("found") is False or not d.get("box_2d") or len(d["box_2d"]) != 4 or float(d.get("confidence") or 0.7) < 0.6:   # 3.x 는 found·confidence 를 빼고 상자만 줄 때가 있다(10-19 실측)
        return None, f"제미나이: 못 찾음/확신 낮음 {json.dumps({k: d.get(k) for k in ('found', 'confidence', 'label')}, ensure_ascii=False)}"
    y0, x0, y1, x1 = (float(v) for v in d["box_2d"])
    b = [wx + x0 / 1000 * ww, wy + y0 / 1000 * wh, wx + x1 / 1000 * ww, wy + y1 / 1000 * wh]
    if (b[2] - b[0]) * (b[3] - b[1]) > 0.6 * ww * wh or b[2] - b[0] < 20 or b[3] - b[1] < 20:
        return None, f"제미나이 상자 크기 이상 {b}"
    return [round(v) for v in b], f"제미나이 {model} '{d.get('label')}' 확신 {d.get('confidence')}"


def caption_box(S: dict, info: dict, t: float) -> list | None:
    """완성본 시각 t 의 자막 잉크 상자(강조 색 덩어리가 있으면 그 덩어리) — 숫자 자막을 가리키는 분홍 ↑ 대상. 우리가 그린 자막이라 추적 불필요."""
    from tools.calcopy.shark import caption_style as CS, fx as FX
    c = next((c for c in info["captions"] if c["t0"] <= t < c["t1"]), None)
    if c is None:
        return None
    em = [dict(x) for x in FX.emph_for(S, c["line"], c["text"])]
    im = np.array(CS.caption_image(c["text"], em, c.get("style") == "원음반응"))
    a = im[..., 3] > 200
    col = a & ((im[..., :3].astype(int).min(axis=2)) < 200)       # 흰 글자 아닌 색 글자
    m = col if col.sum() > 200 else a
    ys, xs = np.nonzero(m)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None


def track_box(info: dict, cand: Path, box: list, t0: float, t1: float, how: str = "template") -> dict:
    """(판단 주인: 대상 따라가기) 완성본 [t0,t1) 동안 대상 상자의 길. cv2 5.0(contrib 없음 → CSRT·KCF 없음)이라
      template = 첫 프레임 상자 그림을 다음 프레임마다 주변(search_frac)·크기 ×0.96/1/1.04 에서 정규 상관(TM_CCOEFF_NORMED)으로 찾음(크기 따라감), 신뢰도 = 첫 그림과의 상관 최솟값
      detect   = 프레임마다 NanoDet 사람 중 앞 상자와 가장 겹치는 것(IoU>0.3), 신뢰도 = 잡힌 프레임 비율
    반환 {path: [[t−t0, x0,y0,x1,y1], …](3점 평균), conf, how, t_end}."""
    import cv2
    from tools.calcopy.shark import fx_measure as FM
    G = rules()["target"]
    ts, fr, c = canvas_frames(info, cand, t0, t1, G["track_fps"])
    cur = [float(v) for v in box]
    path, confs = [], []
    if how == "template":
        g0 = cv2.cvtColor(np.ascontiguousarray(fr[0]), cv2.COLOR_RGB2GRAY)
        x0, y0, x1, y1 = (int(round(v)) for v in cur)
        x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(1080, x1), min(1920, y1)
        tpl = g0[y0:y1, x0:x1]
        tw0, th0 = x1 - x0, y1 - y0
        sc = 1.0                         # 대상 크기 배율(카메라 줌·다가옴) — 프레임마다 앞 배율 ×{0.96,1,1.04} 중 가장 닮은 것(10-20 8편 0초 폰: 고정 크기면 1.35초에 41px 밀림)
        cur = [x0, y0, x1, y1]
        for k, t in enumerate(ts):
            if k:
                g = cv2.cvtColor(np.ascontiguousarray(fr[k]), cv2.COLOR_RGB2GRAY)
                cx, cy = (cur[0] + cur[2]) / 2, (cur[1] + cur[3]) / 2
                best = None
                for s_ in (sc * 0.96, sc, sc * 1.04):
                    tw, th = max(8, int(round(tw0 * s_))), max(8, int(round(th0 * s_)))
                    tp_ = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA if s_ < 1 else cv2.INTER_LINEAR)
                    m = int(G["search_frac"] * max(tw, th))
                    sx0, sy0 = max(0, int(cx - tw / 2) - m), max(0, int(cy - th / 2) - m)
                    sx1, sy1 = min(1080, int(cx + tw / 2) + m), min(1920, int(cy + th / 2) + m)
                    reg = g[sy0:sy1, sx0:sx1]
                    if reg.shape[0] < th or reg.shape[1] < tw:
                        continue
                    _, mv, _, ml = cv2.minMaxLoc(cv2.matchTemplate(reg, tp_, cv2.TM_CCOEFF_NORMED))
                    if best is None or mv > best[0]:
                        best = (mv, s_, [sx0 + ml[0], sy0 + ml[1], sx0 + ml[0] + tw, sy0 + ml[1] + th])
                if best is None:
                    confs.append(0.0); path.append([round(t - t0, 3), *cur]); continue
                confs.append(float(best[0])); sc = best[1]; cur = best[2]
            path.append([round(t - t0, 3), *cur])
    else:
        for k, t in enumerate(ts):
            ps = [[q["x0"], q["y0"], q["x1"], q["y1"]] for q in FM.persons(fr[k])]
            b = max(ps, key=lambda b: _iou(b, cur)) if ps else None
            ok = b is not None and _iou(b, cur) > 0.3
            if ok:
                cur = b
            if k:
                confs.append(1.0 if ok else 0.0)
            path.append([round(t - t0, 3), *cur])
    sm = []
    for k in range(len(path)):
        w = path[k - 1:k + 2] if 0 < k < len(path) - 1 else path[k:k + 1]     # 3점 평균은 안쪽만(끝점 평균은 빠른 대상에서 한 칸 늦어진다)
        sm.append([path[k][0]] + [round(sum(x[i] for x in w) / len(w), 1) for i in range(1, 5)])
    conf = (min(confs) if how == "template" else sum(confs) / len(confs)) if confs else 1.0
    return {"path": sm, "conf": round(conf, 3), "how": how, "t_end": round(ts[-1] + 1 / G["track_fps"], 3) if ts else t1, "cut": c["i"]}


def _disk_box(cx, cy, r, b) -> bool:
    """원판(cx,cy,r)과 상자 b 가 겹치나."""
    dx = max(b[0] - cx, 0, cx - b[2]); dy = max(b[1] - cy, 0, cy - b[3])
    return dx * dx + dy * dy < r * r


def hook_object(info: dict, cand: Path, e: dict, t0: float, t1: float) -> dict:
    """(판단 주인: 0초 빨간 원 = 물건, R3) 물건 상자(손 상자 e.target 목록 | 제미나이 e.target_what) → 추적 → 원 중심 = 상자 가운데,
    크기 = 물건 전체를 감쌈(선 안쪽 ≥ 상자 반대각선×enclose_pad, size_range 상한 960). 창에 다 안 들어가거나 얼굴(YuNet)과 원판이 겹치면 그 순간 거절 →
    추적 길의 뒤 순간부터 다시(t_shift). 맞는 순간이 없으면 ValueError.
    반환 e 에 넣을 값 {at, size, how:'object', face_clear, target_box, target_path, track, track_conf, why}."""
    E = rules()["effects"]; O = E["red_circle"]["object"]
    a, _, _, _ = _final_frame(info, cand, t0 + 0.05)
    box = e["target"] if isinstance(e.get("target"), list) else None      # 손 상자 = target 에 [x0,y0,x1,y1](target_box 는 계산 결과 칸)
    why = "손 상자(재료 target)"
    if box is None:
        if not e.get("target_what"):
            raise ValueError(f"{e['line']} red_circle: 물건 이름(target_what) 또는 상자(target_box) 필요 — 얼굴 원 금지(R3)")
        box, why = object_box(a, e["target_what"])
        if box is None:
            raise ValueError(f"{e['line']} red_circle 물건 '{e['target_what']}' 못 잡음: {why} → 다른 컷 또는 손 상자")
    tr = track_box(info, cand, box, t0, t1)
    sw = float(e.get("stroke") or E["red_circle"]["stroke"])
    wx, wy, ww, wh = E["window"]
    G = rules()["target"]
    from tools.calcopy.shark import fx as FX
    P_ = tr["path"]
    hd = [0.5 * ((q[3] - q[1]) ** 2 + (q[4] - q[2]) ** 2) ** 0.5 for q in P_]          # 상자 반대각선 = 물건 전체를 감싸는 최소 반지름
    ctr = [[q[0], round((q[1] + q[3]) / 2), round((q[2] + q[4]) / 2)] for q in P_]
    why_skip = []
    n = O["face_check_frames"]
    # 원 = 물건 전체를 감싸는 크기(선 안쪽 가장자리 ≥ 반대각선 × enclose_pad). 창에 다 안 들어가거나 얼굴과 겹치면 그 순간은 거절 →
    # 추적 길에서 더 뒤 순간부터(남은 길이 ≥ target.min_len) 다시 본다(페이블 10-20 '원은 물건 전체를 감싸는 게 우선').
    for k in range(len(P_)):
        if P_[-1][0] - P_[k][0] + 1 / G["track_fps"] < G["min_len"]:
            break
        size = int(round(max(O["size_range"][0], 2 * (max(hd[k:]) * O["enclose_pad"] + sw))))
        r = size / 2
        room = min(min(x - wx, wx + ww - x, y - wy, wy + wh - y) for _, x, y in ctr[k:]) - 2
        if size > O["size_range"][1] or r > room:
            why_skip.append(f"{P_[k][0]:.2f}초 원 {size}px 창에 안 들어감(여유 반지름 {room:.0f})"); continue
        sh = P_[k][0]
        track = [[round(c[0] - sh, 3), c[1], c[2]] for c in ctr[k:]]
        tpath = [[round(q[0] - sh, 3), *q[1:]] for q in P_[k:]]
        hits = []
        for j in range(n):
            tt = t0 + sh + 0.03 + (track[-1][0] - 0.06) * j / max(1, n - 1)
            fa, _, _, _ = _final_frame(info, cand, tt)
            cx, cy = FX.track_at(track, tt - t0 - sh)
            hits += [(round(tt, 2), [round(v) for v in fb]) for fb in face_boxes(fa) if _disk_box(cx, cy, r, fb)]
        if hits:
            why_skip.append(f"{P_[k][0]:.2f}초 얼굴 겹침 {hits[:2]}"); continue
        moved = max(abs(c[1] - track[0][1]) + abs(c[2] - track[0][2]) for c in track)
        return {"at": track[0][1:], "size": size, "how": "object", "face_clear": True, "target_box": [round(v) for v in P_[k][1:]],
                "target_path": tpath, "track": track if moved > 4 else None, "track_conf": tr["conf"], "track_how": tr["how"], "t_shift": round(sh, 3),
                "why_target": f"{why} · 추적 {tr['how']} 신뢰 {tr['conf']} · 원 {size}px = 물건 반대각선 {max(hd[k:]):.0f}×{O['enclose_pad']}+선 · 얼굴 {n}프레임 겹침 0"
                              + (f" · {sh:.2f}초 뒤 순간부터(앞 순간 거절 {len(why_skip)})" if sh else "")}
    raise ValueError(f"{e['line']} red_circle 거절(R3·물건 전체 감쌈): 맞는 순간 없음 — {why_skip[:3]}… → 다른 컷·크롭(물건이 창의 가운데·작게)")


def fix(doc: Path, info: dict | None = None) -> list[str]:
    """재료.json effects 의 대상·자리·길을 계산해 쓴다(R3·R4). 직전 --tts-only render_info(실제 컷 시각)가 필요하다.
      red_circle         → hook_object(물건, 얼굴 겹침 거절)
      target 있는 꾸밈   → 대상 상자(list=손 상자 | 'person' NanoDet | 'face' | 'object'+target_what 제미나이 | 'caption' 자막 잉크)
                          → track_box(컷·장면 끝까지) → on_target(끝점이 상자 가장자리) → track(꾸밈 길) · 못 맞추면 e.drop = 이유
      이모지             → 얼굴 가림 비율(face_cover)
    적중 판정 자체는 렌더(fx.hit_report)가 한다 — 여기선 값만 적는다."""
    from tools.calcopy.shark import fx as FX
    p = doc / "재료.json"
    M = json.loads(p.read_text(encoding="utf-8"))
    S = json.loads((doc / "대본.json").read_text(encoding="utf-8"))
    cand = Path(M["cand_dir"])
    if not info:
        raise ValueError("fix 는 render_info(--tts-only 로 만든 실제 컷 시각)가 필요")
    log = []
    li = {x["id"]: x for x in info["lines"]}
    for e in M["effects"]:
        for k in ("drop", "track", "target_path", "target_box", "track_conf", "track_how", "face_cover", "face_clear", "why_target"):
            e.pop(k, None)
        if e["kind"] == "flash" or e["line"] not in li:
            continue
        L0 = li[e["line"]]["t0"]
        tt = e.get("t") or [0.0, li[e["line"]]["t1"] - L0]
        t0 = L0 + tt[0]
        c = _cut_at(info, t0 + 0.02)
        t1 = min(L0 + tt[1], c["t1"])
        try:
            if e["kind"] == "red_circle":
                t1 = scene_end(info, cand, t0 + 0.02, t1)
                r = hook_object(info, cand, e, t0, t1)
                e.update({k: v for k, v in r.items() if v is not None and k != "t_shift"})
                e["t"] = [round(tt[0] + r["t_shift"], 3), round(min(t1, r["target_path"][-1][0] + t0 + r["t_shift"] + 1 / 15) - L0, 3)]
                log.append(f"{e['line']} red_circle 물건 원 at {r['at']} size {r['size']} — {r['why_target']}")
                continue
            if e["kind"] in ("money_emoji", "emoji"):
                a, _, _, _ = _final_frame(info, cand, (t0 + t1) / 2)
                w, h = (v - 2 * FX.PAD for v in FX.sprite(e["kind"], FX._key(e)).size)
                eb = [e["at"][0] - w / 2, e["at"][1] - h / 2, e["at"][0] + w / 2, e["at"][1] + h / 2]
                cov = 0.0
                for fb in face_boxes(a):
                    ix = max(0, min(eb[2], fb[2]) - max(eb[0], fb[0])); iy = max(0, min(eb[3], fb[3]) - max(eb[1], fb[1]))
                    cov = max(cov, ix * iy / max(1, (fb[2] - fb[0]) * (fb[3] - fb[1])))
                e["face_cover"] = round(cov, 3)
                log.append(f"{e['line']} {e['kind']} 얼굴 가림 {cov:.2f}")
                continue
            tg = e.get("target")
            if not tg:
                e["drop"] = "대상 없음(target) — R4 확실할 때만"
                log.append(f"{e['line']} {e['kind']} 뺌: 대상 없음"); continue
            t1 = scene_end(info, cand, t0 + 0.02, t1)
            how, why = "template", ""
            if isinstance(tg, list):
                box, why = tg, "손 상자"
            elif tg == "person":
                box, why, how = final_person(info, cand, t0 + 0.05, t1), "NanoDet 사람", "detect"
            elif tg == "face":
                box, why = final_face(info, cand, t0 + 0.05), "YuNet 머리"
            elif tg == "caption":
                box, why = caption_box(S, info, t0 + 0.05), "자막 잉크(강조 덩어리)"
                how = None
            elif tg == "object":
                a, _, _, _ = _final_frame(info, cand, t0 + 0.05)
                box, why = object_box(a, e.get("target_what") or "")
            else:
                raise ValueError(f"target 모름 {tg}")
            if box is None:
                e["drop"] = f"대상 못 잡음: {why}"
                log.append(f"{e['line']} {e['kind']} 뺌: {e['drop']}"); continue
            if how:
                tr = track_box(info, cand, box, t0, t1, how)
                tp, conf, t_end = tr["path"], tr["conf"], min(t1, t0 + tr["t_end"] - t0)
            else:
                tp, conf, t_end = [[0.0, *box]], 1.0, t1
            r = on_target(e["kind"], box, avoid_caption=tg != "caption")
            if r.get("drop"):
                e["drop"] = r["drop"]
                log.append(f"{e['line']} {e['kind']} 뺌: {r['drop']}"); continue
            e.update(r)
            e["target_box"] = [round(v) for v in box]
            e["target_path"] = tp
            e["track_conf"] = conf
            e["track_how"] = how or "static"
            e["t"] = [tt[0], round(t_end - L0, 3)]
            if len(tp) > 1:
                b0 = tp[0]
                e["track"] = [[q[0], round(e["at"][0] + (q[1] + q[3] - b0[1] - b0[3]) / 2), round(e["at"][1] + (q[2] + q[4] - b0[2] - b0[4]) / 2)] for q in tp]
                if max(abs(q[1] - e["at"][0]) + abs(q[2] - e["at"][1]) for q in e["track"]) <= 4:
                    e.pop("track")
            bad = FX.outside([{**e, "T": [0, 1]}])
            if bad and e["kind"] == "dashed_circle" and e.get("track"):
                e.pop("track")                 # 점선 원은 벤치처럼 중심 고정으로 되돌림(상자 안 중심이면 적중)
                bad = FX.outside([{**e, "T": [0, 1]}])
            if bad:
                e["drop"] = f"따라가다 창 밖: {bad}"
            e["why_target"] = f"{why} · 추적 {e['track_how']} 신뢰 {conf}"
            log.append(f"{e['line']} {e['kind']} 대상 {tg if not isinstance(tg, list) else '손 상자'} {e['target_box']} → at {e.get('at')} 신뢰 {conf}"
                       + (f" 뺌: {e['drop']}" if e.get("drop") else ""))
        except ValueError as er:
            if e["kind"] == "red_circle":
                raise
            e["drop"] = str(er)
            log.append(f"{e['line']} {e['kind']} 뺌: {er}")
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
        info = None
        if len(sys.argv) > 3:
            info = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
            info["_dir"] = str(Path(sys.argv[3]).resolve().parent)
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
