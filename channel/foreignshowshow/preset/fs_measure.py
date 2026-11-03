# -*- coding: utf-8 -*-
"""샥탬스토리(벤치 해외쇼츠 @foreignshowshow) 프리셋 실측 — 제목 띠·자막·소리를 원본 픽셀/소리에서 잰다 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/foreignshowshow/preset/fs_measure.py title     # 제목 2줄: 잉크 y·x·높이·채움색·글꼴(fontmatch)
    PYTHONUTF8=1 py channel/foreignshowshow/preset/fs_measure.py scan      # 10fps 자막 칸 변화점(잉크 마스크 IoU)
    PYTHONUTF8=1 py channel/foreignshowshow/preset/fs_measure.py sound     # 통합 LUFS·트루피크
결과 = channel/foreignshowshow/preset/_hand/measure_*.json (손질 근거). 재는 일만 — 판단은 fs_preset.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

MP4 = Path("C:/숏템_칼카피/foreignshowshow/mp4")
HAND = Path(__file__).parent / "_hand"
WORK = Path("C:/숏템_칼카피/foreignshowshow/preset_work"); WORK.mkdir(parents=True, exist_ok=True)
IDS = ["QMJtjJz4M6w", "kmQGQNJgSVo", "2jJoIbdciDY", "vbxJ_v132ao", "hZgCO9PEnO8", "mVzrvBpMu3E", "aFqKN8s2cA8", "HI--3fL7nt4"]
# 제목 글 = 8초 프레임을 눈으로 읽음(클로드 판독 10-18, titles8.png)
TITLE = {"QMJtjJz4M6w": "홍수를 막을 수 있는\n역대급 모래 주머니?!", "kmQGQNJgSVo": "입기만 하면\n살 빠지는 땀복?!",
         "2jJoIbdciDY": "땅콩잼을 이제는\n안 긁어도 된다고?!", "vbxJ_v132ao": "구멍난 벽을 쉽게\n고쳐준다는 제품",
         "hZgCO9PEnO8": "오로지 낚시줄만\n자른다는 제품?!", "mVzrvBpMu3E": "여성만 쓸 수 있는 수건?!\n산다 vs 안산다",
         "aFqKN8s2cA8": "케첩을 이제\n안 부어도 된다고?!", "HI--3fL7nt4": "30초만에 와인 칠링?!\n산다 vs 안산다"}


def grab(vid: str, t: float) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(MP4 / f"{vid}.mp4"), "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(1920, 1080, 3)


def segs(b: np.ndarray, min_len: int = 1, gap: int = 0) -> list[tuple[int, int]]:
    out, s = [], None
    for i, v in enumerate(list(b) + [False]):
        if v and s is None:
            s = i
        elif not v and s is not None:
            out.append((s, i)); s = None
    if gap:
        m = []
        for a, e in out:
            if m and a - m[-1][1] <= gap:
                m[-1] = (m[-1][0], e)
            else:
                m.append((a, e))
        out = m
    return [x for x in out if x[1] - x[0] >= min_len]


def title(vid: str, t: float = 8.0) -> dict:
    from tools.calcopy.engine import fontmatch as FM
    img = grab(vid, t)
    band = img[60:430].astype(int)
    lum = band.mean(axis=2)
    ink = lum > 90
    rows = segs(ink.sum(axis=1) > 3, min_len=20, gap=6)
    texts = TITLE[vid].split("\n")
    lines = []
    for k, (a, e) in enumerate(rows[:2]):
        m = ink[a:e]
        cols = np.where(m.any(axis=0))[0]
        core = band[a:e][lum[a:e] > 200]
        sat = core[(core.max(axis=1) - core.min(axis=1)) > 60]
        wht = core[(core.max(axis=1) - core.min(axis=1)) <= 30]
        fill = np.median(sat, axis=0) if len(sat) > len(wht) else np.median(wht, axis=0)
        # 외곽선 확인: 글자 둘레 2~4px 밖 고리의 밝기(검정 바탕이라 검정 외곽선은 보이지 않음 — 밝은 고리면 번짐/광)
        mask = FM._bbox(m)
        lines.append({"text": texts[k] if k < len(texts) else None, "ink_y": [int(a + 60), int(e + 60)], "ink_h": int(e - a),
                      "ink_x": [int(cols.min()), int(cols.max() + 1)], "ink_w": int(cols.max() + 1 - cols.min()),
                      "fill_rgb": [int(x) for x in fill], "_mask": mask})
    samples = [(l["_mask"], l["text"].replace(" ", "")) for l in lines if l["text"]]
    pr = FM.pooled_rank([(m, tx) for m, tx in samples])
    for l in lines:
        l.pop("_mask")
    return {"vid": vid, "t": t, "lines": lines, "font_rank": pr}


CAP_Y0, CAP_H = 760, 440        # 자막 칸 훑는 띠(창 434~1486 가운데) — 1fps 시트에서 자막이 모두 이 안(y≈880~1080)


def cap_mask(a: np.ndarray) -> np.ndarray:
    """자막 글자 후보 = 아주 흰 픽셀 또는 밝고 진한 형광색 픽셀(자막 채움색 실측: 흰·민트·초록·노랑·주황·분홍·빨강)."""
    a = a.astype(int)
    mx, mn = a.max(axis=2), a.min(axis=2)
    return (mn > 225) | ((mx > 215) & (mx - mn > 110))


def scan(vid: str, fps: int = 10) -> dict:
    """10fps 로 자막 띠 마스크를 만들고 앞 프레임과 IoU 가 크게 떨어지는 시각 = 자막 칸 변화점."""
    W, H = 1080, CAP_H
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(MP4 / f"{vid}.mp4"), "-vf", f"fps={fps},crop={W}:{H}:0:{CAP_Y0}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    prev, k, rows = None, 0, []
    while True:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        m = cap_mask(np.frombuffer(buf, np.uint8).reshape(H, W, 3)[:, 40:1040])
        n = int(m.sum())
        iou = float((m & prev).sum() / max(1, (m | prev).sum())) if prev is not None else 0.0
        ys = np.where(m.sum(axis=1) > 6)[0]
        rows.append({"t": round(k / fps, 2), "ink": n, "iou": round(iou, 3),
                     "y": [int(ys.min() + CAP_Y0), int(ys.max() + CAP_Y0)] if len(ys) else None})
        prev, k = m, k + 1
    p.wait()
    change = [r["t"] for r in rows if r["iou"] < 0.45 and r["ink"] > 400]
    return {"vid": vid, "fps": fps, "rows": rows, "change": change}


def settled_times(vid: str) -> list[float]:
    """scan 변화점을 0.25초 안끼리 묶고 마지막 +0.15초(넘김 흐림이 끝난 프레임) — strips 시트와 같은 시각."""
    d = json.loads((WORK / f"scan_{vid}.json").read_text(encoding="utf-8"))
    groups = []
    for t in d["change"]:
        if groups and t - groups[-1][-1] <= 0.25:
            groups[-1].append(t)
        else:
            groups.append([t])
    return [round(g[-1] + 0.15, 2) for g in groups]


def caps(vid: str) -> dict:
    """자막 칸 실측: 바뀐 지점마다 줄 수·줄별 잉크 y·높이·x 가운데. 높이는 흰 채움(min>225)만으로(색 글자 번짐 빛이 부풀리지 않게)."""
    out = []
    for t in settled_times(vid):
        img = grab(vid, t)[800:1180, 20:1060].astype(int)
        mn, mx = img.min(axis=2), img.max(axis=2)
        anym = (mn > 225) | ((mx > 215) & (mx - mn > 110))
        white = mn > 225
        lines = segs(anym.sum(axis=1) > 8, min_len=25, gap=8)
        L = []
        for a, e in lines:
            cols = np.where(anym[a:e].any(axis=0))[0]
            wr = np.where(white[a:e].sum(axis=1) > 3)[0]
            L.append({"y": [int(a + 800), int(e + 800)], "h": int(e - a), "x": [int(cols.min() + 20), int(cols.max() + 21)],
                      "white_h": int(wr.max() - wr.min() + 1) if len(wr) > 20 else None, "white_px": int(white[a:e].sum())})
        out.append({"t": t, "lines": L})
    return {"vid": vid, "items": out}


def fx(vid: str, fps: int = 10) -> dict:
    """효과 후보 시각(10fps, 창만 1/4 크기): 순빨강 픽셀(빨간 원·점선 원) · 자홍 픽셀(분홍 화살표) ·
    색 필터(창 평균에서 초록/빨강 쪽 치우침). 후보 시각은 눈으로 프레임을 보고 확정한다(_hand/effects.json)."""
    W, H = 270, 263
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(MP4 / f"{vid}.mp4"), "-vf", f"fps={fps},crop=1080:1052:0:434,scale={W}:{H}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    rows, k = [], 0
    while True:
        buf = p.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        a = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(int)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        red = int(((r > 200) & (g < 70) & (b < 70)).sum())
        mag = int(((r > 200) & (b > 190) & (g < 110)).sum())
        mr, mg, mb = r.mean(), g.mean(), b.mean()
        rows.append({"t": round(k / fps, 2), "red": red, "mag": mag, "green_cast": round(mg - (mr + mb) / 2, 1),
                     "red_cast": round(mr - (mg + mb) / 2, 1)})
        k += 1
    p.wait()
    return {"vid": vid, "rows": rows}


def main():
    cmd = sys.argv[1]
    HAND.mkdir(exist_ok=True)
    if cmd == "title":
        out = {v: title(v) for v in IDS}
        (HAND / "measure_title.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        for v, d in out.items():
            print(v, [(l["ink_y"], l["ink_h"], l["ink_w"], l["fill_rgb"]) for l in d["lines"]], d["font_rank"]["top"][:3])
    elif cmd == "caps":
        import statistics as st
        allr = {}
        for v in sys.argv[2:] or IDS:
            d = caps(v)
            one = [i["lines"][0] for i in d["items"] if len(i["lines"]) == 1 and 30 <= i["lines"][0]["h"] <= 110]
            two = [i["lines"] for i in d["items"] if len(i["lines"]) == 2]
            s = {"n": len(d["items"]), "one": len(one), "two": len(two),
                 "one_center_y": st.median((l["y"][0] + l["y"][1]) / 2 for l in one) if one else None,
                 "one_h": st.median(l["h"] for l in one) if one else None,
                 "one_white_h": st.median(l["white_h"] for l in one if l["white_h"]) if any(l["white_h"] for l in one) else None,
                 "one_x_center": st.median((l["x"][0] + l["x"][1]) / 2 for l in one) if one else None,
                 "two_top": st.median(ls[0]["y"][0] for ls in two) if two else None,
                 "two_bottom": st.median(ls[1]["y"][1] for ls in two) if two else None,
                 "two_h": st.median((ls[0]["h"] + ls[1]["h"]) / 2 for ls in two) if two else None,
                 "two_pitch": st.median(ls[1]["y"][0] - ls[0]["y"][0] for ls in two) if two else None}
            allr[v] = {"summary": s, "items": d["items"]}
            print(v, json.dumps(s, ensure_ascii=False))
        (WORK / "caps.json").write_text(json.dumps(allr, ensure_ascii=False, indent=1), encoding="utf-8")
    elif cmd == "fx":
        for v in sys.argv[2:] or IDS:
            d = fx(v)
            (WORK / f"fx_{v}.json").write_text(json.dumps(d), encoding="utf-8")
            R = d["rows"]
            def spans(key, th):
                s = segs(np.array([x[key] > th for x in R]), min_len=2, gap=2)
                return [(R[a]["t"], R[e - 1]["t"]) for a, e in s]
            print(v, "red", spans("red", 250), "mag", spans("mag", 150), "green", spans("green_cast", 45), "redc", spans("red_cast", 70))
    elif cmd == "scan":
        ids = sys.argv[2:] or IDS
        for v in ids:
            d = scan(v)
            (WORK / f"scan_{v}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            print(v, "변화점", len(d["change"]), d["change"])


if __name__ == "__main__":
    main()
