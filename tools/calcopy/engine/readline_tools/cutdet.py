# -*- coding: utf-8 -*-
"""컷 검출(cutdet) — 창 안 매 프레임 밝기차·히스토그램차로 컷·전환 종류·샷별 움직임.

어디서 왔나: 06 잇템로그 워커(관제 263, 10-24)의 세션 임시 폴더 도구 cutdet.py 를 그대로 옮김(알고리즘 바꾸지 않음).
무엇을 재나: 창[y0,y1)을 360폭 회색으로 줄여 프레임차 > max(12, 3.5×이웃 중앙값) 또는 히스토그램차 > 0.35 = 컷(2프레임 안 붙은 것 합침).
            컷 앞뒤 ±4프레임 최소 밝기 <10 = black, 앞뒤보다 +50 밝으면 flash, 선명도(라플라시안)가 앞뒤 45% 미만 3프레임↑ = zoomblur, 나머지 cut.
            샷마다 첫·끝 프레임 평균차 chg(움직임 신호 — build_lr 은 6 미만을 still 로 본다).
입력: mp4 · 창 y0 y1 (줄판독 layout.window 의 세로, 예: 잇템로그 486 1920)
출력(json): {n(프레임 수), cuts:[{t, t_end, kind, diff, blurfr}], shots:[{t0, t1, chg}]}

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/cutdet.py <mp4> <y0> <y1> <out.json> [--v2 [--cap-band y0,y1]]
--v2(10-25 추가, 06 키치잇 결손): 자막 띠를 뺀 라플라시안으로 컷 직후 7프레임·직전 6프레임 블러(바탕의 50% 밑 2프레임↑)를 zoomblur 로,
     영상 시작 블러를 t=0 사건으로, 샷마다 shotmotion.shot_motion(ORB 닮음변환 — 배율·이동)으로 motion still/cam/zoom_in/zoom_out/pan.
     옛 분류는 kind_v1 에 남는다. v2 없이 부르면 출력은 옛 도구와 같다.
"""
from __future__ import annotations

import json
import subprocess
import sys

from pathlib import Path

import cv2
import numpy as np

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def cutdet(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080, v2: bool = False, cap_band: tuple | None = None,
           use_color_flash: bool = False, motion: bool = True) -> dict:
    """v2=False = 옛 도구 그대로(재현). v2=True = 자막 띠를 뺀 선명도로 전환 종류를 다시 가르고(kind, 옛 값은 kind_v1),
    영상 시작 블러를 사건으로 더하고, 샷마다 shotmotion 움직임(motion: still/cam/zoom_in/zoom_out/pan)을 붙인다(06 키치잇 10-25 결손)."""
    H = y1 - y0
    w, h = 360, int(H / 3)
    from tools.calcopy.engine.readline_tools.capseg import fps_filter      # 60fps 원본 → 30 (주인 = capseg.fps_filter)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", fps_filter(mp4, fps) + f"crop={width}:{H}:0:{y0}:exact=1,scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    n = len(raw) // (w * h)
    F = np.frombuffer(raw, np.uint8)[:n * w * h].reshape(n, h, w).astype(np.float32)
    mean = F.mean((1, 2))
    sharp = np.array([cv2.Laplacian(f[:int(h * 0.55)], cv2.CV_32F).var() for f in F])
    diff = np.r_[0, [np.abs(F[i] - F[i - 1]).mean((0, 1)) for i in range(1, n)]] if n > 1 else np.zeros(n)   # 프레임마다(긴 영상 통째 빼기는 메모리 2배 — 56초 편에서 MemoryError)
    hist = [cv2.calcHist([f.astype(np.uint8)], [0], None, [32], [0, 256]).ravel() for f in F]
    hist = [x / x.sum() for x in hist]
    hd = np.r_[0, [0.5 * np.abs(hist[i] - hist[i - 1]).sum() for i in range(1, n)]]
    med = np.array([np.median(diff[max(0, i - 15):i + 15]) for i in range(n)])
    cuts = [i for i in range(1, n) if (diff[i] > max(12, 3.5 * med[i]) or hd[i] > 0.35)]
    cm = []
    for c in cuts:
        if cm and c - cm[-1][-1] <= 2:
            cm[-1].append(c)
        else:
            cm.append([c])
    res = []
    for g in cm:
        a, b = g[0], g[-1]
        lo = max(0, a - 4)
        hi = min(n - 1, b + 4)
        kind = "cut"
        lowblur = 0
        if mean[lo:hi + 1].min() < 10:
            kind = "black"
        elif mean[lo:hi + 1].max() > max(mean[max(0, a - 8)], mean[min(n - 1, b + 8)]) + 50:
            kind = "flash"
        else:
            pre = np.median(sharp[max(0, a - 10):max(1, a - 4)])
            post = np.median(sharp[min(n - 1, b + 5):min(n, b + 11)])
            win = sharp[max(0, a - 3):min(n, b + 3)]
            lowblur = int((win < 0.45 * min(pre, post)).sum())
            if lowblur >= 3:
                kind = "zoomblur"
        res.append({"t": round(a / fps, 3), "t_end": round(b / fps, 3), "kind": kind, "diff": round(float(diff[a:b + 1].max()), 1),
                    "blurfr": lowblur if kind not in ("black", "flash") else 0})
    bounds = [0] + [int(r["t"] * fps) for r in res] + [n]
    shots = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1] - 1
        if b - a < 3:
            shots.append({"t0": round(a / fps, 3), "t1": round((b + 1) / fps, 3), "motion": "still?", "chg": 0})
            continue
        A = F[a + 1]
        B = F[b - 1]
        chg = float(np.abs(A - B).mean())
        shots.append({"t0": round(a / fps, 3), "t1": round((b + 1) / fps, 3), "chg": round(chg, 1)})
    if v2:
        _refine_v2(F, mean, res, shots, fps, h, y0, cap_band, mp4, y1, use_color_flash, motion)
    return {"n": n, "cuts": res, "shots": shots, **({"v2": True} if v2 else {})}


def color_flash(mp4: str, y0: int, y1: int, fps: float = 30.0, width: int = 1080) -> list[dict]:
    """색 번쩍(06 샤크탱크 워커 fsseg.py 그대로): 창 1/4 크기 평균 색편차 G-(R+B)/2(초록)·R-(G+B)/2(빨강)가 한 프레임에 +12↑ 뛰고
    14프레임 뒤 뛴 양의 절반 넘게 줄면 번쩍. 같은 색 0.2초 안은 하나. 밝기 번쩍(흰)은 cutdet 의 flash(평균 +50)가 잡는다."""
    from tools.calcopy.engine.readline_tools.capseg import fps_filter
    w, h = width // 4, (y1 - y0) // 4
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", fps_filter(mp4, fps) + f"crop={width}:{y1 - y0}:0:{y0}:exact=1,scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = len(raw) // (w * h * 3)
    A = np.frombuffer(raw, np.uint8)[:n * w * h * 3].reshape(n, h, w, 3).astype(float)
    r, g, b = A[..., 0].mean((1, 2)), A[..., 1].mean((1, 2)), A[..., 2].mean((1, 2))
    fl = []
    for name, S in (("초록", g - (r + b) / 2), ("빨강", r - (g + b) / 2)):
        for i in range(1, len(S) - 14):
            j = S[i] - S[i - 1]
            if j > 12 and S[i] - S[min(len(S) - 1, i + 14)] > 0.5 * j and S[i] >= S[i + 1] - 2:
                if not fl or abs(fl[-1]["t"] - i / fps) > 0.2 or fl[-1]["color"] != name:
                    fl.append({"t": round(i / fps, 3), "color": name, "jump": round(float(j), 1)})
    fl.sort(key=lambda e: e["t"])
    return fl


V2_RATIO = 0.30     # 컷 직후 가장 흐린 프레임 선명도 ÷ 같은 샷 바탕 — 이 밑이면 블러. 5채널 정답 56곳·cut 447줄로 고름(0.30: 일치 52/56·오탐 11, 0.45: 52/56·22)
V2_RISE = 1.25      # 컷 뒤 6프레임째 선명도 ÷ 처음 3프레임 — 블러가 풀린다(1.8 이면 오탐 9 지만 키치잇 BRa 1.97 를 놓친다)
V2_LOW = 0.5        # 바탕 선명도의 이 비율 밑 = 흐린 프레임
V2_MIN_FR = 3       # (정보용) 흐린 프레임 수 blur_post 를 셀 때 문턱 — 판정은 V2_RATIO·V2_RISE(10-25 아이템홈 소프트포커스 오탐 뒤)


def _masked_sharp(F, h, y0, cap_band):
    keep = np.ones(h, bool)
    if cap_band:
        r0 = max(0, int((cap_band[0] - y0) / 3) - 3)
        r1 = min(h, int((cap_band[1] - y0) / 3) + 3)
        keep[r0:r1] = False
    return np.array([cv2.Laplacian(f[keep], cv2.CV_32F).var() for f in F])


def _refine_v2(F, mean, res, shots, fps, h, y0, cap_band, mp4, y1, use_color_flash=False, motion=True):
    n = len(F)
    sh = _masked_sharp(F, h, y0, cap_band)
    dark = (F < 20).mean((1, 2))
    cut_fr = sorted(int(round(r["t"] * fps)) for r in res)
    for r in res:
        r["kind_v1"] = r["kind"]
        a = int(round(r["t"] * fps))
        b = int(round(r["t_end"] * fps))
        post_base = np.median(sh[min(n - 1, b + 8):min(n, b + 18)]) if b + 9 < n else np.nan
        pre_base = np.median(sh[max(0, a - 18):max(1, a - 8)]) if a - 9 > 0 else np.nan
        post_low = int((sh[a:min(n, b + 7)] < V2_LOW * post_base).sum()) if post_base == post_base else 0   # 블러 프레임이 컷 묶음(a~b) 안에 들 수 있다(꿀템노트 cLk: a~b 7프레임)
        pre_low = int((sh[max(0, a - 6):a] < V2_LOW * pre_base).sum()) if pre_base == pre_base else 0
        r["blur_post"] = post_low
        r["blur_pre"] = pre_low
        # 블러 비율은 '같은 샷 안' 바탕과 견준다(다음 컷 넘어 바탕을 잡으면 소프트포커스 원본에서 오탐 — 아이템홈 10-25) · 블러는 풀려야 한다(rise)
        nxt = min([c for c in cut_fr if c > b + 1] + [n])
        base_in = np.median(sh[b + 8:min(nxt, b + 18)]) if nxt - (b + 8) >= 3 else post_base
        win = sh[a:min(n, b + 7)]
        ratio = float(win.min() / base_in) if len(win) and base_in == base_in and base_in > 0 else 1.0
        rise = float(sh[min(n - 1, b + 6)] / (win[:3].mean() + 1e-6)) if len(win) else 1.0
        r["blur_post_in"] = int((win < V2_LOW * base_in).sum()) if base_in == base_in and base_in > 0 else 0
        r["blur_ratio"] = round(ratio, 2)
        r["blur_rise"] = round(rise, 2)
        w0, w1 = max(1, a - 1), min(n, b + 6)
        pre_mean = float(mean[max(0, a - 3)])
        # 검정: 창의 60%↑ 가 거의 검정(<20)이고 평균이 앞의 1/3 밑 — 60fps 원본의 검정 1프레임 뒤 밝아지는 페이드인도 잡는다(꿀템노트 KCx 13.4)
        is_black = r["kind"] == "black" or (dark[w0:w1].max() >= 0.6 and mean[w0:w1].min() < max(25.0, pre_mean / 3))
        # 밝기 번쩍: 컷 프레임에서 바로 +40↑ 밝아짐(어두워졌다 밝아지는 방사 줌블러와 가른다 — 꿀템노트 cLk 12.0 / 키치잇 BRa 0.8)
        jumps = [float(mean[i] - mean[i - 1]) for i in range(max(1, a - 1), min(n, a + 2))]
        big = max(jumps, key=abs) if jumps else 0.0
        pk = int(np.argmax(mean[a:min(n, a + 4)])) + a if a < n else a
        tail = mean[pk:min(n, pk + 6)]
        fading = len(tail) >= 6 and bool(np.all(np.diff(tail) < 0.5)) and float(tail[0] - tail[-1]) >= 10   # 번쩍은 뒤로 서서히 어두워진다
        is_flash = big >= 40 and float(mean[pk]) >= pre_mean + 40 and fading
        if is_black:
            r["kind"] = "black"
        elif is_flash:
            r["kind"] = "flash"
        elif rise >= V2_RISE and (ratio <= V2_RATIO or r["kind"] == "zoomblur"):
            r["kind"] = "zoomblur"
        elif r["kind"] == "zoomblur":                  # 옛 zoomblur 인데 선명해지지 않음 = 원본이 원래 흐림(소프트포커스)
            r["kind"] = "cut"
        elif r["kind"] == "flash":                 # 옛 flash 인데 바로 밝아지지 않음 = 번쩍 아님
            r["kind"] = "cut"
    # 색 번쩍 ±0.15초 안 컷 = flash (샤크탱크 mkfs.py 규칙) — 채널 프로필 color_flash=true 일 때만(키치잇에 켜면 장면 색 바뀐 컷 4곳을 flash 로 오탐, 10-25 실측)
    for f in (color_flash(mp4, y0, y1, fps) if use_color_flash else []):
        near = [r for r in res if abs(r["t"] - f["t"]) <= 0.15]
        if near:
            near[0]["kind"] = "flash"
            near[0]["color_flash"] = f["color"]
        else:
            res.append({"t": f["t"], "t_end": f["t"], "kind": "flash", "diff": 0.0, "blurfr": 0, "color_flash": f["color"], "kind_v1": None})
    res.sort(key=lambda r: r["t"])
    if n > 20:                                   # 영상 시작 블러(컷이 없다): 첫 6프레임이 8~20프레임 바탕보다 흐림
        base = np.median(sh[8:20])
        low = int((sh[:6] < V2_LOW * base).sum())
        recovered = float(sh[5:8].mean()) >= 0.85 * base   # 블러는 몇 프레임 안에 선명해진다(키치잇 Cs-Ka: 0.47→0.51 평평 = 블러 아님)
        if low >= 2 and recovered:
            res.insert(0, {"t": 0.0, "t_end": 0.0, "kind": "zoomblur", "diff": 0.0, "blurfr": low, "start": True, "kind_v1": None})
    if not motion:                               # 전환만 볼 때(점검 도구) — 샷마다 ORB 는 느리다
        return
    from tools.calcopy.engine.readline_tools.shotmotion import shot_motion   # 움직임 주인 = shotmotion(ORB 닮음변환, 유머쇼쇼 워커 motion.py)
    cap = cv2.VideoCapture(mp4)
    orb = cv2.ORB_create(1500)
    for s in shots:
        if s["t1"] - s["t0"] < 0.15:
            s["motion"] = "still?"
            continue
        cut = next((c for c in res if abs(c["t"] - s["t0"]) < 0.5 / fps), None)
        skip = (cut.get("blur_post") or cut.get("blurfr") or 0) / fps if cut and cut["kind"] == "zoomblur" else 0.0
        a = min(s["t0"] + skip, max(s["t0"], s["t1"] - 0.3))     # 블러 프레임은 ORB 가 못 잡는다 → 블러가 풀린 뒤부터
        m = shot_motion(cap, a, s["t1"], y0, y1, orb)
        s["motion"] = m["motion"]
        s.update({k: m[k] for k in ("scale", "tx", "ty") if k in m})
    cap.release()


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 4:
        print(__doc__)
        return 2
    v2 = "--v2" in a
    cb = None
    if "--cap-band" in a:
        i = a.index("--cap-band")
        cb = tuple(int(x) for x in a[i + 1].split(","))
        del a[i:i + 2]
    a = [x for x in a if x != "--v2"]
    mp4, y0, y1, out = a[0], int(a[1]), int(a[2]), a[3]
    d = cutdet(mp4, y0, y1, v2=v2, cap_band=cb)
    json.dump(d, open(out, "w"), indent=0)
    for r in d["cuts"]:
        print(r)
    print("shots", len(d["shots"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
