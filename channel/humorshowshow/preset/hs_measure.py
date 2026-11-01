# -*- coding: utf-8 -*-
# _deprecated_2026-10-25 → tools/calcopy/hybrid/styles/썰템쇼판.json (관제 263 지시서 07 · 표준 §3-1: 새 편은 공용 렌더러로. 설명서 프리셋 썰템쇼_화자썰 생성기 — 회원 옛 길 preset_make 가 그 결과를 읽으므로 지우지 않는다)
"""썰템쇼(벤치 재밌쇼) 틀 픽셀 실측 — 편마다 본문·훅 프레임 한 장씩 떠서 층별 잉크 자리·색을 잰다 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/humorshowshow/preset/hs_measure.py [id ...]     → C:/숏템_칼카피/humorshowshow/preset_work/measure/<id>.json + all.json
    from channel.humorshowshow.preset.hs_measure import measure_body, measure_hook   (loo 렌더 대조도 같은 함수로 잰다 — 재는 규칙 한 곳)

시각 고르기 = 줄판독(channel/humorshowshow/줄판독/<id>.json) 자막 줄 — 본문 1줄 자막·2줄 자막 장면 가운데, 훅 = 첫 줄(훅 카드) 가운데.
틀숫자_뜯기_2026-10-18.md 의 값(NBdm·jECu·cj3 손 측정)을 8편으로 넓힌 것.
"""
from __future__ import annotations

import json
import statistics as st
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
MP4 = Path("C:/숏템_칼카피/humorshowshow/mp4")
WORK = Path("C:/숏템_칼카피/humorshowshow/preset_work")
READ = ROOT / "channel" / "humorshowshow" / "줄판독"


def grab(src: Path, t: float, out: Path) -> np.ndarray:
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", str(out)], check=True)
    return np.asarray(Image.open(out).convert("RGB")).astype(int)


def runs(mask: np.ndarray, gap: int = 2, min_len: int = 2) -> list[list[int]]:
    out = []
    for i in np.where(mask)[0]:
        if out and i - out[-1][1] <= gap + 1:
            out[-1][1] = int(i)
        else:
            out.append([int(i), int(i)])
    return [r for r in out if r[1] - r[0] + 1 >= min_len]


def bbox(m: np.ndarray, ox: int = 0, oy: int = 0):
    ys, xs = np.where(m)
    if not len(ys):
        return None
    return [int(xs.min()) + ox, int(ys.min()) + oy, int(xs.max()) + ox, int(ys.max()) + oy]


def med(px: np.ndarray):
    return [int(v) for v in np.median(px.reshape(-1, 3), axis=0)] if px.size else None


def logo_fill(a: np.ndarray) -> np.ndarray:
    """로고 채움(초록 168,216,130 · 흰) — 검정 외곽·연한 초록 그림자(170,195,138)·머리띠 바탕(228,240,214) 은 뺀다."""
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return ((G >= 205) & (G - R > 30) & (R < 200)) | ((R >= 235) & (G >= 235) & (B >= 228))


def measure_body(a: np.ndarray) -> dict:
    H, W, _ = a.shape
    hdr = med(a[20:110, 20:W - 20])
    col = a[:300, 5:60]                                 # 아이콘 없는 왼쪽 끝 줄
    off = np.abs(col - np.array(hdr)).sum(2).mean(1) > 30
    hdr_end = int(np.argmax(off[100:]) + 100)           # 머리띠 아래 끝(첫 다른 줄)
    head = a[:hdr_end]
    d = np.abs(head - np.array(hdr)).sum(2) > 60
    out = {"hdr_rgb": hdr, "hdr_end": hdr_end}
    for name, (x0, x1) in {"arrow": (100, 330), "logo": (330, 760), "bookmark": (760, 1000)}.items():
        m = d[:, x0:x1]
        out[name] = bbox(m, x0)
        if out[name]:
            sel = head[:, x0:x1][m]
            out[name + "_rgb"] = med(sel[sel.sum(1) < 600]) if name != "logo" else None
    lf = logo_fill(head[:, 330:760])
    out["logo_fill"] = bbox(lf, 330)
    # 로고 글자 셋(채움 덩어리 가로 빈틈으로 가름)
    cols = runs(lf.sum(0) > 1, gap=8, min_len=10)
    out["logo_chars"] = [[c[0] + 330, c[1] + 330] for c in cols]
    g = head[:, 330:760][((head[:, 330:760][..., 1] >= 205) & (head[:, 330:760][..., 1] - head[:, 330:760][..., 0] > 30))]
    out["logo_green"] = med(g)
    # 게시글 제목
    reg = a[245:372]
    dark = reg.sum(2) < 300
    rr = runs(dark.sum(1) > 2)
    out["title_rows"] = [rr[0][0] + 245, rr[-1][1] + 245] if rr else None
    out["title_x"] = [bbox(dark)[0], bbox(dark)[2]] if dark.any() else None
    out["title_rgb"] = med(reg[reg.sum(2) < 120])
    # 메타 줄
    reg = a[365:401]
    ink = np.abs(reg - 255).sum(2) > 90
    rr = runs(ink.sum(1) > 1, gap=1, min_len=1)
    out["meta_rows"] = [rr[0][0] + 365, rr[-1][1] + 365] if rr else None
    out["meta_x"] = [bbox(ink)[0], bbox(ink)[2]] if ink.any() else None
    R, G, B = reg[..., 0], reg[..., 1], reg[..., 2]
    red = (R > 150) & (R - G > 55) & (R - B > 55)
    red[:, :560] = False                               # 댓글 수는 줄 끝(x 607~655) — 앞 글자 가장자리 색 번짐(렌더 서브픽셀)을 빼려고
    out["meta_red_x"] = [bbox(red)[0], bbox(red)[2]] if red.any() else None
    out["meta_red_rgb"] = med(reg[red])
    blk = reg.sum(2) < 200
    out["meta_dark_x"] = [bbox(blk)[0], bbox(blk)[2]] if blk.any() else None
    out["meta_dark_rgb"] = med(reg[blk])
    gray = ink & ~red & ~blk
    out["meta_gray_rgb"] = med(reg[gray])
    # 구분선
    lum = a[395:415, 20:W - 20].mean(2).mean(1)
    rr = runs(lum < 200, gap=0, min_len=1)
    out["divider_rows"] = [rr[0][0] + 395, rr[-1][1] + 395] if rr else None
    out["divider_rgb"] = med(a[395 + rr[0][0]:395 + rr[-1][1] + 1, 20:W - 20]) if rr else None
    # 자막(창 위 흰 칸)
    reg = a[420:668]
    dark = reg.sum(2) < 300
    rr = runs(dark.sum(1) > 2, gap=3)
    out["cap_lines"] = [[r[0] + 420, r[1] + 420] for r in rr]
    out["cap_x"] = [[bbox(dark[r[0]:r[1] + 1])[0], bbox(dark[r[0]:r[1] + 1])[2]] for r in rr]
    # 그림 창(흰 바탕과 다른 줄)
    rowdiff = np.abs(a[640:H] - 255).sum(2).mean(1) > 25
    rr = runs(rowdiff, gap=6, min_len=40)
    out["window_rows"] = [rr[0][0] + 640, rr[-1][1] + 640] if rr else None
    return out


def measure_hook(a: np.ndarray) -> dict:
    H, W, _ = a.shape
    bg = med(a[20:100, 20:W - 20])
    reg = a[90:485]
    R, G, B = reg[..., 0], reg[..., 1], reg[..., 2]
    white = (R > 235) & (G > 235) & (B > 235)
    green = (G > 200) & (R < 190) & (B < 140) & (G - R > 60)
    out = {"bg_rgb": bg}
    for name, m in (("white", white), ("green", green)):
        rr = runs(m.sum(1) > 6, gap=4, min_len=8)
        big = max(rr, key=lambda r: r[1] - r[0]) if rr else None
        out[name + "_rows"] = [big[0] + 90, big[1] + 90] if big else None
        if big:
            sub = m[big[0]:big[1] + 1]
            out[name + "_x"] = [bbox(sub)[0], bbox(sub)[2]]
            out[name + "_rgb"] = med(reg[big[0]:big[1] + 1][sub])
    # 글자 둘레 검정(외곽선·그림자) — 흰 글자 오른쪽 아래로 몇 px 가 어두운가
    if out.get("white_rows"):
        y0, y1 = out["white_rows"]
        m = white[y0 - 90:y1 - 90 + 1]
        sub = reg[y0 - 90:y1 - 90 + 1]
        lum = sub.mean(2)
        dk = lum < 50
        out["white_dark_px"] = int(dk.sum())
        offs = {}
        for k in (2, 4, 6, 8, 10):
            sh = np.zeros_like(m); sh[k:, k:] = m[:-k, :-k]
            offs[k] = round(float((dk & sh & ~m).sum() / max(1, m.sum())), 3)
        out["white_dark_shift_frac"] = offs
    # 띠 줄 밝기(480~760, 가운데 열)
    prof = a[470:770, 300:780].mean(2).mean(1)
    out["band_profile"] = {str(470 + i): int(v) for i, v in enumerate(prof) if i % 4 == 0}
    out["band_mid_rgb"] = med(a[490:520, 300:780])
    out["box_rgb"] = med(a[545:575, 30:100])
    lab = a[540:690]
    dark = lab.sum(2) < 300
    rr = runs(dark.sum(1) > 2, gap=3)
    out["label_rows"] = [rr[0][0] + 540, rr[-1][1] + 540] if rr else None
    out["label_x"] = [bbox(dark)[0], bbox(dark)[2]] if dark.any() else None
    out["label_rgb"] = med(lab[lab.sum(2) < 150])
    return out


def pick_times(vid: str) -> dict:
    R = json.loads((READ / f"{vid}.json").read_text(encoding="utf-8"))
    L = R["lines"]
    hook = L[0]
    body = [l for l in L[1:] if l["t1"] - l["t0"] >= 0.8 and "화자" not in (l.get("kind") or "")]
    one = next((l for l in body if "/" not in l["caption"]), None)
    two = next((l for l in body if "/" in l["caption"]), None)
    return {"hook": round((hook["t0"] + min(hook["t1"], 1.8)) / 2, 2),
            "body1": round((one["t0"] + one["t1"]) / 2, 2) if one else None,
            "body2": round(two["t1"] - 0.3, 2) if two else None,     # 누적형 — 2줄째가 붙은 뒤(장면 끝 가까이)
            "title_card": R.get("title_card"), "post_title": R.get("post_title"),
            "lines": {"one": one and one["caption"], "two": two and two["caption"]}}


def run(vid: str) -> dict:
    T = pick_times(vid)
    src = MP4 / f"{vid}.mp4"
    fr = WORK / "frames"
    res = {"id": vid, "times": T}
    res["hook"] = measure_hook(grab(src, T["hook"], fr / f"{vid}_hook_{T['hook']}.png"))
    for k in ("body1", "body2"):
        if T[k] is not None:
            res[k] = measure_body(grab(src, T[k], fr / f"{vid}_{k}_{T[k]}.png"))
    p = WORK / "measure" / f"{vid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


IDS = ["NBdmq90aJus", "jECuoRljWj0", "GPeF16iUHNo", "cHynO-CRdYE", "BlA9f8rBPuc", "cj3-wcltAao", "xJvwMApZwnE", "0Q-CAw_iaNw"]

if __name__ == "__main__":
    ids = sys.argv[1:] or IDS
    allr = {v: run(v) for v in ids}
    (WORK / "measure" / "all.json").write_text(json.dumps(allr, ensure_ascii=False, indent=1), encoding="utf-8")
    for v, r in allr.items():
        b = r.get("body2") or r.get("body1")
        print(v, "hook", {k: r["hook"].get(k) for k in ("bg_rgb", "white_rows", "green_rows", "green_rgb", "label_rows")})
        print("   body", {k: b.get(k) for k in ("hdr_rgb", "hdr_end", "arrow", "logo", "logo_fill", "bookmark", "title_rows", "meta_rows",
                                               "meta_x", "meta_red_x", "divider_rows", "cap_lines", "window_rows")})


# ── 글꼴 판별(fontmatch.pooled_rank — 8편 묶음) ── 층마다 잉크 마스크 + 줄판독 글자
def _ink(a, y0, y1, kind):
    reg = a[y0:y1 + 1]
    R, G, B = reg[..., 0], reg[..., 1], reg[..., 2]
    if kind == "white":
        return (R > 200) & (G > 200) & (B > 200)
    if kind == "green":
        return (G > 180) & (G - R > 60) & (G - B > 100)
    return reg.sum(2) < 330


def font_samples(ids=None) -> dict:
    from tools.calcopy.engine import fontmatch as FM
    ids = ids or IDS
    A = json.loads((WORK / "measure" / "all.json").read_text(encoding="utf-8"))
    S = {"hook_title": [], "hook_label": [], "post_title": [], "caption": []}
    fr = WORK / "frames"
    for v in ids:
        r, T = A[v], A[v]["times"]
        tc = (T["title_card"] or "").split("/")
        hk = np.asarray(Image.open(fr / f"{v}_hook_{T['hook']}.png").convert("RGB")).astype(int)
        h = r["hook"]
        if h.get("white_rows") and len(tc) == 2:
            S["hook_title"].append((FM._bbox(_ink(hk, *h["white_rows"], "white")), tc[0].strip()))
            S["hook_title"].append((FM._bbox(_ink(hk, *h["green_rows"], "green")), tc[1].strip()))
        if h.get("label_rows"):
            S["hook_label"].append((FM._bbox(_ink(hk, *h["label_rows"], "dark")), " ".join(x.strip() for x in tc)))
        k = "body2" if r.get("body2") else "body1"
        bd = np.asarray(Image.open(fr / f"{v}_{k}_{T[k]}.png").convert("RGB")).astype(int)
        b = r[k]
        if b.get("title_rows") and T.get("post_title"):
            S["post_title"].append((FM._bbox(_ink(bd, *b["title_rows"], "dark")), T["post_title"]))
        lines = (T["lines"]["two"] if k == "body2" else T["lines"]["one"]).split("/")
        for (y0, y1), txt in zip(b["cap_lines"], lines):
            S["caption"].append((FM._bbox(_ink(bd, y0, y1, "dark")), txt.strip()))
    return S


def fonts(ids=None) -> dict:
    from tools.calcopy.engine import fontmatch as FM, to_frame as TF
    import os
    faces = {p.stem.lower(): fam for fam, p in TF.font_faces().items()}
    out = {}
    for role, sm in font_samples(ids).items():
        sm = [(m, t) for m, t in sm if m is not None and t]
        r = FM.pooled_rank(sm)
        for x in r.get("top", []):
            x["family"] = faces.get(os.path.splitext(x["font"])[0].lower())
        out[role] = r
    (WORK / "measure" / "fonts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def hook_end(vid: str, src: Path | None = None, hdr=(227, 239, 210)) -> float | None:
    """훅 카드가 끝나는 시각 = 머리띠(y40~60 줄)가 연두로 바뀌는 첫 프레임(0.8~3.5초, 30fps 프레임마다)."""
    src = src or MP4 / f"{vid}.mp4"
    W, H, y0, h = 1080, 20, 40, 20
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", "0.8", "-t", "2.7", "-i", str(src),
                        "-vf", f"fps=30,crop=1080:{h}:0:{y0}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    a = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, W, 3).astype(int)
    for i, f in enumerate(a):
        if np.abs(f.reshape(-1, 3).mean(0) - np.array(hdr)).sum() < 20:
            return round(0.8 + i / 30, 3)
    return None
