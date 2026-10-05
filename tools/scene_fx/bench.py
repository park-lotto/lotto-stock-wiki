# -*- coding: utf-8 -*-
"""잘된 쇼핑쇼츠에서 장면 효과(컷 전환·확대·흔들림·번쩍·흐림)를 프레임 단위로 잰다 (관제 124).

무엇을 재나 (영상 1편마다, 30fps 로 맞춰 읽는다)
  cut        : 앞뒤 프레임 밝기 분포가 크게 바뀜 = 컷
  zoom_cut   : 컷이지만 같은 화면을 더 크게/작게 자른 것(점프 줌·펀치 줌) — 컷 양쪽 특징점이 확대 관계로 맞는다
  punch      : 컷 없이 3프레임 안에 8%+ 확대 (뚝 끊는 확대)
  push       : 컷 없이 0.7초+ 동안 꾸준히 5%+ 확대/축소 (천천히 밀고 들어가기·빠지기)
  shake      : 0.5초 안에 좌우·상하 방향이 3번+ 바뀌는 흔들림 (폭 화면 1%+)
  whip       : 한 프레임에 화면 폭 8%+ 이동 + 흐려짐 (휙 넘김)
  flash      : 밝기가 주변보다 확 올랐다 6프레임 안에 내려감 (흰 번쩍)
  blur       : 컷 앞뒤로 선명도가 절반 아래로 떨어짐 (흐림 전환)

★측정값은 반드시 시트(--sheet)로 눈으로 대조해라. 자막이 큰 화면에서는 특징점이 자막에 붙어 확대를 놓칠 수 있다.

사용:
  py tools/scene_fx/bench.py --dir <영상폴더> --list tools/scene_fx/bench_list.json --out <결과.json>
  py tools/scene_fx/bench.py --selftest
"""
import argparse, json, os, sys
import numpy as np
import cv2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W, H = 270, 480          # 분석 해상도(9:16)
FPS = 30.0


def read_frames(path):
    cap = cv2.VideoCapture(path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(src_fps / FPS)))
    frames, i = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step == 0:
            frames.append(cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA))
        i += 1
    cap.release()
    return frames, src_fps / step


def video_region(frames):
    """움직이는 영상 칸(y0,y1,x0,x1). 썰 채널은 위 30~40%가 상단바·제목·자막띠로 내내 고정이라
    통째로 재면 컷이 묻힌다(실측: 이븐쇼핑 ABjQ0YCZoes 컷 20+개를 2개로 셈). 시간에 따라 값이 크게
    바뀌는 행·열 중 가장 긴 연속 띠를 영상 칸으로 본다."""
    if len(frames) < 10:
        return 0, H, 0, W
    pick = frames[:: max(1, len(frames) // 60)]
    g = np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in pick])
    sd = g.std(axis=0)

    def band(act):
        thr = 0.45 * np.percentile(act, 90)
        best, cur, start = (0, len(act)), 0, 0
        blen = 0
        for i, on in enumerate(list(act > thr) + [False]):
            if on:
                if cur == 0:
                    start = i
                cur += 1
            else:
                if cur > blen:
                    blen, best = cur, (start, i)
                cur = 0
        return best
    y0, y1 = band(sd.mean(axis=1))
    x0, x1 = band(sd[y0:y1].mean(axis=0))
    if (y1 - y0) < H * 0.25 or (x1 - x0) < W * 0.4:
        return 0, H, 0, W
    return y0, y1, x0, x1


def _mask():
    m = np.zeros((H, W), np.uint8)
    m[int(H * 0.12):int(H * 0.88), :] = 255     # 위·아래 띠(제목·채널명) 제외
    return m


_ORB = cv2.ORB_create(600)
_BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
_MASKS = {}


def _mask_for(shape):
    if shape not in _MASKS:
        h, w = shape
        m = np.full((h, w), 255, np.uint8)
        if h >= H * 0.95:      # 영상 칸을 못 갈랐을 때만 위·아래 띠를 뺀다
            m[:int(h * 0.12)] = 0; m[int(h * 0.88):] = 0
        _MASKS[shape] = m
    return _MASKS[shape]


def affine(g0, g1):
    """g0→g1 닮음변환(확대 s, 이동 tx·ty 화면비, 인라이어 비율). 못 구하면 None."""
    mk = _mask_for(g0.shape)
    k0, d0 = _ORB.detectAndCompute(g0, mk)
    k1, d1 = _ORB.detectAndCompute(g1, mk)
    if d0 is None or d1 is None or len(k0) < 20 or len(k1) < 20:
        return None
    ms = _BF.match(d0, d1)
    if len(ms) < 15:
        return None
    p0 = np.float32([k0[m.queryIdx].pt for m in ms])
    p1 = np.float32([k1[m.trainIdx].pt for m in ms])
    M, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=2.5)
    if M is None:
        return None
    s = float(np.hypot(M[0, 0], M[1, 0]))
    # 화면 가운데 기준 이동으로 바꾼다
    hh, ww = g0.shape
    cx, cy = ww / 2, hh / 2
    nx = M[0, 0] * cx + M[0, 1] * cy + M[0, 2]
    ny = M[1, 0] * cx + M[1, 1] * cy + M[1, 2]
    rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    inr = float(inl.sum()) / max(1, len(ms))
    return {"s": s, "tx": (nx - cx) / ww, "ty": (ny - cy) / hh, "rot": rot,
            "inl": inr, "n": int(inl.sum()),
            # 편집기에서 넣은 확대·이동은 화면 전체가 한 덩어리로 움직인다(특징점 대부분이 같은 변환, 회전 없음).
            # 손으로 찍은 카메라 움직임은 원근·시차 때문에 맞는 비율이 낮고 회전이 섞인다(이븐쇼핑 실측).
            "rigid": inr >= 0.75 and abs(rot) < 0.4 and int(inl.sum()) >= 40}


def scdet_cuts(path, region, fps, n, thr=10.0):
    import re, subprocess
    fy0, fy1, fx0, fx1 = region
    vf = (f"crop=iw*{fx1 - fx0:.4f}:ih*{fy1 - fy0:.4f}:iw*{fx0:.4f}:ih*{fy0:.4f},"
          f"scdet=threshold={thr}")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vf", vf, "-an", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ts = [float(m.group(1)) for m in re.finditer(r"lavfi\.scd\.time: ([\d.]+)", r.stderr)]
    out = []
    for t in ts:
        i = int(round(t * fps))
        if 0 < i < n and (not out or i - out[-1] > int(0.15 * fps)):
            out.append(i)
    return out


def frame_stats(frames):
    out = []
    prev_h = None
    for f in frames:
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        h = cv2.calcHist([cv2.cvtColor(f, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 8], [0, 180, 0, 256])
        cv2.normalize(h, h)
        corr = 1.0 if prev_h is None else float(cv2.compareHist(prev_h, h, cv2.HISTCMP_CORREL))
        out.append({"luma": float(g.mean()),
                    "sharp": float(cv2.Laplacian(g, cv2.CV_64F).var()),
                    "corr": corr, "g": g,
                    "small": cv2.resize(g, (68, 120)).astype(np.float32)})
        prev_h = h
    return out


def analyze(path):
    frames, fps = read_frames(path)
    y0, y1, x0, x1 = video_region(frames)
    frames = [f[y0:y1, x0:x1] for f in frames]
    n = len(frames)
    st = frame_stats(frames)
    dur = n / fps
    ev = []
    # 컷 = ffmpeg scdet(영상 칸만) 점수 10+ , 0.15초 안에 붙은 것은 하나로.
    # 직접 만든 판정(색 분포+특징점)은 빠른 손동작을 컷으로 세서 62개(정답 약 22)를 냈다 — 실측 후 교체.
    cuts = scdet_cuts(path, (y0 / H, y1 / H, x0 / W, x1 / W), fps, n)
    # 컷 사이 같은 화면 확대(점프 줌) 판정 + 흐림·휙 판정
    for i in cuts:
        a = affine(st[i - 1]["g"], st[i]["g"])
        if a and a["n"] >= 25 and a["inl"] >= 0.35 and abs(a["s"] - 1) >= 0.06:
            ev.append({"t": i / fps, "kind": "zoom_cut", "scale": round(a["s"], 3), "edit": a["rigid"]})
        else:
            ev.append({"t": i / fps, "kind": "cut"})
        # 흐림 전환 = 앞 장면 끝도, 뒤 장면 시작도 각자 자기 장면 평소보다 흐려짐.
        # 컷 앞뒤 전체 중앙값과 비교하면 무늬 없는 장면(흰 벽)으로 넘어가는 맨 컷을 흐림으로 셌다(이븐쇼핑 실측).
        pre = [st[j]["sharp"] for j in range(max(0, i - 20), i - 4)]
        post = [st[j]["sharp"] for j in range(i + 4, min(n, i + 20))]
        if len(pre) >= 5 and len(post) >= 5:
            out_dip = min(st[j]["sharp"] for j in range(max(0, i - 3), i)) < 0.4 * np.median(pre)
            in_dip = min(st[j]["sharp"] for j in range(i, min(n, i + 3))) < 0.4 * np.median(post)
            if out_dip and in_dip:
                ev.append({"t": i / fps, "kind": "blur"})
    cutset = set(cuts)
    # 부드러운 전환(디졸브·줌 블러·회전 블러 등) — 장면 검출(scdet)은 뚝 끊는 컷만 잡아 통째로 놓친다
    # (미스터살림왕 B_kS9Mri1no: 60초에 컷 1개로 셌지만 실제는 0.3초 겹침 전환이 연달아 있다).
    # 0.27초 앞뒤가 다른 장면(특징점이 안 이어짐)인데 그 사이에 한 프레임짜리 급변이 없으면 부드러운 전환.
    # 단순 섞기(알파 블렌드)로 판정하면 확대·흐림이 섞인 전환을 못 잡았다(설명비 0.8~0.9) — 그래서 이 기준.
    k = int(round(0.27 * fps))
    i = k
    while i < n - k:
        if any(abs(c - i) <= k for c in cuts):
            i += 1; continue
        A, B = st[i - k]["small"], st[i + k]["small"]
        dAB = float(np.abs(A - B).mean())
        if dAB > 22:
            steps = [float(np.abs(st[j]["small"] - st[j - 1]["small"]).mean()) for j in range(i - k + 1, i + k + 1)]
            if max(steps) < 0.45 * dAB:
                ab = affine(st[i - k]["g"], st[i + k]["g"])
                if not ab or ab["inl"] < 0.3:
                    sh = min(st[j]["sharp"] for j in range(i - 2, i + 3)) < 0.6 * min(st[i - k]["sharp"], st[i + k]["sharp"])
                    ev.append({"t": i / fps, "kind": "soft", "blur": bool(sh), "edit": True})
                    cuts.append(i)
                    i += 2 * k; continue
        i += 1
    cuts.sort()
    cutset = set(cuts)
    # 컷 없는 구간의 프레임간 움직임
    mot = [None] * n
    for i in range(1, n):
        if i in cutset:
            continue
        a = affine(st[i - 1]["g"], st[i]["g"])
        # 특징점이 적게 맞으면 움직임으로 치지 않는다(엉터리 확대·휙 방지)
        mot[i] = a if a and a["n"] >= 20 and a["inl"] >= 0.4 else None
    # punch: 3프레임 누적 확대 ≥ 8%
    i = 1
    while i < n - 3:
        seg = [mot[j] for j in range(i, i + 3)]
        if all(seg):
            s = float(np.prod([m["s"] for m in seg]))
            if s >= 1.08 or s <= 1 / 1.08:
                after = [mot[j] for j in range(i + 3, min(n, i + 9))]
                held = bool(after) and all(after) and all(abs(m["s"] - 1) < 0.012 for m in after)
                ev.append({"t": i / fps, "kind": "punch", "scale": round(s, 3),
                           "edit": all(m["rigid"] for m in seg) and held})
                i += 6
                continue
        i += 1
    # push: 0.7초+ 꾸준한 확대/축소 누적 5%+
    win = int(0.7 * fps)
    i = 1
    while i < n - win:
        seg = [mot[j] for j in range(i, i + win)]
        if all(seg):
            ss = [m["s"] for m in seg]
            s = float(np.prod(ss))
            same_dir = sum(1 for x in ss if (x > 1) == (s > 1)) >= 0.8 * len(ss)
            if (s >= 1.05 or s <= 1 / 1.05) and same_dir and max(abs(x - 1) for x in ss) < 0.04:
                ls = np.log(ss)
                smooth = float(np.std(np.diff(ls))) < 0.004      # 키프레임 확대는 매끈하다
                ev.append({"t": i / fps, "kind": "push", "scale": round(s, 3), "len": round(win / fps, 2),
                           "edit": smooth and sum(m["rigid"] for m in seg) >= 0.8 * len(seg)})
                i += win
                continue
        i += 1
    # shake: 0.5초 창에서 이동 방향 전환 3번+ 이고 폭 1%+
    win = int(0.5 * fps)
    i = 1
    while i < n - win:
        seg = [mot[j] for j in range(i, i + win)]
        if all(seg):
            for ax in ("tx", "ty"):
                v = [m[ax] for m in seg if abs(m[ax]) > 0.004]
                flips = sum(1 for a, b in zip(v, v[1:]) if a * b < 0)
                if flips >= 3 and max(abs(x) for x in v) >= 0.01:
                    ev.append({"t": i / fps, "kind": "shake", "axis": ax,
                               "edit": sum(m["rigid"] for m in seg) >= 0.8 * len(seg)})
                    i += win
                    break
            else:
                i += 1
                continue
            continue
        i += 1
    # whip: 한 프레임 이동 8%+ 이면서 흐려짐
    for i in range(1, n):
        m = mot[i]
        if m and max(abs(m["tx"]), abs(m["ty"])) >= 0.08:
            ev.append({"t": i / fps, "kind": "whip", "dx": round(float(m["tx"]), 3), "dy": round(float(m["ty"]), 3),
                       "edit": m["rigid"]})
    # flash: 밝기 주변 중앙값보다 +45 올랐다 6프레임 안에 복귀
    lum = np.array([s["luma"] for s in st])
    for i in range(1, n - 1):
        ctx = np.median(lum[max(0, i - 15):min(n, i + 15)])
        if lum[i] - ctx >= 45 and lum[i] >= 200 and lum[i] > lum[i - 1] + 25:
            back = any(lum[j] < ctx + 20 for j in range(i + 1, min(n, i + 7)))
            if back:
                ev.append({"t": i / fps, "kind": "flash"})
    ev.sort(key=lambda e: e["t"])
    for e in ev:
        e["t"] = round(e["t"], 2)
        e["zone"] = "hook" if e["t"] < 3.0 else ("end" if e["t"] > dur - 3.0 else "body")
    n_cuts = sum(1 for e in ev if e["kind"] in ("cut", "zoom_cut", "soft"))
    return {"dur": round(dur, 2), "fps": fps, "cuts": n_cuts, "region": [int(y0), int(y1), int(x0), int(x1)],
            "cut_len_median": round(float(np.median(np.diff([0] + cuts + [n]))) / fps, 2) if cuts else round(dur, 2),
            "events": ev}


def sheet(path, events, out_png, kinds=None):
    """사건 시각 앞뒤 프레임을 한 장에 — 측정을 눈으로 대조하는 용도."""
    frames, fps = read_frames(path)
    rows = []
    for e in events:
        if kinds and e["kind"] not in kinds:
            continue
        i = int(round(e["t"] * fps))
        offs = (0, 4, 8, 12, 16, 20) if e["kind"] == "push" else (-3, -1, 0, 1, 3, 6)   # 밀기는 넓게 봐야 보인다
        idx = [max(0, min(len(frames) - 1, i + d)) for d in offs]
        strip = np.hstack([cv2.resize(frames[j], (135, 240)) for j in idx])
        cv2.putText(strip, f'{e["t"]:.2f}s {e["kind"]} {e.get("scale","")} {"EDIT" if e.get("edit") else ""}', (4, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        rows.append(strip)
    if rows:
        cv2.imencode(".png", np.vstack(rows[:30]))[1].tofile(out_png)
    return len(rows)


def _selftest():
    """합성 정답 영상: 1초 펀치 줌(1.15배), 2초 컷(앞뒤 흐림), 3초 흰 번쩍. 넷 다 찾아야 통과."""
    import tempfile
    rng = np.random.default_rng(0)

    def shapes(seed_bg):
        # 흐린 잡음은 특징점이 0개라 확대를 못 잰다(실측) — 실제 화면처럼 모서리 있는 도형을 그린다
        img = np.full((H * 2, W * 2, 3), seed_bg, np.uint8)
        for _ in range(160):
            c = tuple(int(x) for x in rng.integers(0, 255, 3))
            x, y = int(rng.integers(0, W * 2)), int(rng.integers(0, H * 2))
            r = int(rng.integers(6, 40))
            if rng.random() < .5:
                cv2.rectangle(img, (x, y), (x + r, y + r), c, -1)
            else:
                cv2.circle(img, (x, y), r // 2, c, -1)
        return img
    base = shapes(90)
    other = shapes(30)
    tmp = os.path.join(tempfile.mkdtemp(), "t.mp4")
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), 30, (W, H))
    for k in range(120):
        t = k / 30
        src = base if t < 2 else other
        z = 1.0 if t < 1 else (1.15 if t < 2 else 1.0)
        if 1 <= t < 1.07:
            z = 1.0 + 0.15 * (t - 1) / 0.07
        ch, cw = int(H * 2 / (z * 1.0) / 1.0), int(W * 2 / z)
        y0, x0 = (H * 2 - ch) // 2, (W * 2 - cw) // 2
        f = cv2.resize(src[y0:y0 + ch, x0:x0 + cw], (W, H))
        if 1.9 <= t < 2.1:                  # 2초 컷 앞뒤 흐림 전환
            f = cv2.GaussianBlur(f, (0, 0), 6)
        if 3.0 <= t < 3.1:
            f = np.full_like(f, 250)
        vw.write(f)
    vw.release()
    r = analyze(tmp)
    kinds = {e["kind"] for e in r["events"]}
    ok = {"punch", "flash", "blur"} <= kinds and ("cut" in kinds or "zoom_cut" in kinds)
    print("selftest", "통과" if ok else "실패", sorted(kinds), r["events"])
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--list")
    ap.add_argument("--out")
    ap.add_argument("--sheets")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if _selftest() else 1)
    items = json.load(open(a.list, encoding="utf-8"))
    res = []
    for it in items:
        # bench_list.json = [채널, id, 조회수] / bench_rank.json(collect_rank.py) = {"channel","id","views",...}
        ch, vid, views = (it["channel"], it["id"], it["views"]) if isinstance(it, dict) else it
        p = os.path.join(a.dir, vid + ".mp4")
        if not os.path.exists(p):
            print("없음", vid); continue
        r = analyze(p)
        r.update({"channel": ch, "id": vid, "views": views})
        res.append(r)
        c = {}
        for e in r["events"]:
            c[e["kind"]] = c.get(e["kind"], 0) + 1
        print(f'{ch:10s} {vid} {r["dur"]:5.1f}s 컷{r["cuts"]:3d} 컷길이중앙{r["cut_len_median"]}s', c)
        if a.sheets:
            os.makedirs(a.sheets, exist_ok=True)
            sheet(p, [e for e in r["events"] if e["kind"] != "cut"], os.path.join(a.sheets, vid + ".png"))
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
