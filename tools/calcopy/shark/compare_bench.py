# -*- coding: utf-8 -*-
"""샥탬스토리 결과물 검사 — 벤치 vs 우리 완성본을 같은 잣대로 재서 기준표 + 같은 시각 나란히 시트 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/shark/compare_bench.py <벤치.mp4> <우리 final.mp4> <출력 폴더> [--tag 1차]

잣대는 영상 픽셀·소리에서만 잰다(계획·render_info 를 믿지 않는다). 통과 범위 = rules.json compare 절.
기준표 칸(원리서 절):
  훅(§2)        0~1초 안 빨간 원 픽셀 · 첫 자막 크게 여부 · 첫 컷 시각
  자막 크기(§3)  한 줄 칸 잉크 위·아래 끝 중앙
  강조 색(§4)    자막 칸 중 색 있는 칸 비율 · 부분 색(낱말) 칸 비율 · 쓴 색 가짓수
  넘김 흐림(§3)  자막 바뀔 때 가로로 흐린 프레임이 있는 비율
  효과(§5)       빨간 원·점선·화살표(빨강·분홍·초록)·돈다발 등장 수
  번쩍(§5)       색 번쩍 횟수·분당
  효과음(§6)     번쩍 직후 0.45초 안 높이 있는 소리(띠링) 시작 비율
  와우(§0)       번쩍 + 꾸밈 등장(0.5초 안 묶음) 분당
  원-얼굴(§2)    0~3초 빨간 실선 원 ↔ 같은 프레임 얼굴(YuNet): 중심 어긋남·반지름/얼굴 높이·얼굴이 원 안·원 크기·얼굴/창 폭(fx_measure)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.shark.caption_style import rules  # noqa: E402

BAND = (860, 1060)    # 자막 띠(한 줄 929~988·두 줄 895~1022 를 덮음)


def _frames(src, vf, w, h, fps):
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vf", f"fps={fps},{vf}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(w * h * 3)
        if len(b) < w * h * 3:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3).astype(np.int16)
    p.wait()


def _dur(src):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                                capture_output=True, text=True).stdout.strip())


def cap_mask(a):
    mx, mn = a.max(axis=2), a.min(axis=2)
    return (mn > 225) | ((mx > 215) & (mx - mn > 110))


def captions(src) -> dict:
    """30fps 자막 띠: 칸 바뀜(마스크 IoU<0.45) → 칸마다 바뀐 뒤 5프레임째로 잉크·색, 바뀜 앞뒤 2프레임 가로 흐림."""
    pal = {k: np.array(v) for k, v in rules()["caption"]["palette"].items()}
    H = BAND[1] - BAND[0]
    prev, cells, k = None, [], 0
    fr = []
    for a in _frames(src, f"crop=1080:{H}:0:{BAND[0]}", 1080, H, 30):
        m = cap_mask(a[:, 30:1050])
        iou = float((m & prev).sum() / max(1, (m | prev).sum())) if prev is not None else 0.0
        fr.append({"ink": int(m.sum()), "iou": iou})
        if iou < 0.45 and m.sum() > 400:
            cells.append({"f": k})
        prev, k = m, k + 1
    # 칸 뭉치기(0.25초 안 바뀜은 한 칸)
    merged = []
    for c in cells:
        if merged and c["f"] - merged[-1]["f_last"] <= 8:
            merged[-1]["f_last"] = c["f"]
        else:
            merged.append({"f": c["f"], "f_last": c["f"]})
    out = []
    for c in merged:
        fs = c["f_last"] + 5
        if fs >= len(fr):
            continue
        out.append({"t": round(c["f"] / 30, 2), "fs": fs})
    # 칸 프레임 다시 뽑아 색 재기(띠 전체 해상도)
    nxt = {id(c): (out[i + 1]["t"] * 30 if i + 1 < len(out) else 1e9) for i, c in enumerate(out)}
    for c in out:
        # 색 번쩍이 칸에 걸리면 바탕이 빨강·초록으로 물들어 '색 글자'로 잘못 센다(5편 10-18) → 칸 안 프레임 셋 중 바탕(글자 밖) 채도가 가장 낮은 것으로 잰다
        best = None
        for f in (c["fs"], c["fs"] + 10, c["fs"] + 20):
            if f >= nxt[id(c)] - 2 and f != c["fs"]:
                continue
            r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{f / 30:.3f}", "-i", str(src), "-frames:v", "1", "-vf",
                                f"crop=1080:{H}:0:{BAND[0]}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
            if len(r.stdout) < 1080 * H * 3:
                continue
            a_ = np.frombuffer(r.stdout, np.uint8).reshape(H, 1080, 3).astype(int)[:, 30:1050]
            bg = np.median(a_[~cap_mask(a_)], axis=0)
            sat = float(bg.max() - bg.min())
            if best is None or sat < best[0] - 15:
                best = (sat, a_)
        if best is None:
            continue
        a = best[1]
        white = int((a.min(axis=2) > 225).sum())
        cols = {n: int((np.abs(a - v).sum(axis=2) < 60).sum()) for n, v in pal.items()}
        colored = sum(v for v in cols.values() if v > 250)
        rows = np.where(cap_mask(a).sum(axis=1) > 8)[0]
        c.update({"white": white, "cols": {n: v for n, v in cols.items() if v > 250}, "colored": colored,
                  "frac": round(colored / max(1, colored + white), 2),
                  "ink": [int(rows.min() + BAND[0]), int(rows.max() + BAND[0])] if len(rows) else None})
        # 넘김 흐림: 흐린 프레임은 선명한 글자 픽셀(흰·진한 색)이 크게 준다 → 바뀜 −2~+2 프레임 최소 잉크 < 앞·뒤 안정 칸 잉크 작은 쪽 × 0.6
        f0 = int(round(c["t"] * 30))
        old = fr[max(0, f0 - 4)]["ink"]; new = fr[c["fs"]]["ink"]
        dip = min(fr[j]["ink"] for j in range(max(0, f0 - 2), min(len(fr), f0 + 3)))
        c["blur"] = bool(min(old, new) > 400 and dip < 0.6 * min(old, new))
    return {"cells": out}


def window(src) -> dict:
    """10fps 창(1/4): 색 번쩍(급등 후 감쇠) · 꾸밈 색 픽셀(빨간 원/화살표·분홍·초록 화살표). 자막 띠는 뺀다."""
    E = rules()["effects"]
    W, H = 270, 263
    red = np.array(E["red_circle"]["color"]); pink = np.array(E["arrow_pink_up"]["color"]); grn = np.array(E["arrow_green_down"]["color"])
    rows = []
    for a in _frames(src, f"crop=1080:1052:0:434,scale={W}:{H}", W, H, 10):
        a = a.astype(int)
        a[106:157] = 0    # 자막 띠(860~1060 → 창 좌표 426~626 → 1/4)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        rows.append({"red": int((np.abs(a - red).sum(axis=2) < 70).sum()), "pink": int(((r > 220) & (b > 180) & (g < 140)).sum()),
                     "green": int((np.abs(a - grn).sum(axis=2) < 80).sum()),
                     "gc": float(g.mean() - (r.mean() + b.mean()) / 2), "rc": float(r.mean() - (g.mean() + b.mean()) / 2)})
    flashes = []
    for key, nm in (("gc", "초록"), ("rc", "빨강")):
        for i in range(1, len(rows) - 3):
            x = rows[i][key]
            if x - rows[i - 1][key] > 35 and x > 40 and rows[i + 3][key] < x - 10:
                flashes.append({"t": round(i / 10, 1), "color": nm})
    objs = []
    for key, th, nm in (("red", 60, "빨강 꾸밈"), ("pink", 40, "분홍 화살표"), ("green", 60, "초록 꾸밈")):
        on = [x[key] > th for x in rows]
        i = 0
        while i < len(on):
            if on[i]:
                j = i
                while j < len(on) and on[j]:
                    j += 1
                if j - i >= 3 and not any(abs(f["t"] - i / 10) < 0.25 and f["color"] == "빨강" and key == "red" for f in flashes):
                    objs.append({"t": round(i / 10, 1), "kind": nm, "dur": round((j - i) / 10, 1)})
                i = j
            else:
                i += 1
    return {"flashes": sorted(flashes, key=lambda f: f["t"]), "objects": objs, "hook_red": int(sum(x["red"] for x in rows[:10]))}


def ding_after(src, times) -> list[bool]:
    """번쩍 직후 0.05~0.45초에 2~10kHz 한 주파수가 앞 0.45초보다 12dB 넘게 오르고(높이 있는 소리) 넓은 띠는 덜 오름."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "22050", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.float32); sr = 22050; win = 2048
    fq = np.fft.rfftfreq(win, 1 / sr); band = (fq > 2000) & (fq < 10000)

    def spec(a, b):
        s = x[max(0, int(a * sr)):int(b * sr)]
        n = max(1, (len(s) - win) // 512)
        return np.mean([np.abs(np.fft.rfft(s[i * 512:i * 512 + win] * np.hanning(win))) ** 2 for i in range(n)], axis=0)[band] + 1e-12
    out = []
    for t in times:
        if t < 0.5 or t + 0.5 > len(x) / sr:
            out.append(False); continue
        pre, post = spec(t - 0.5, t - 0.05), spec(t + 0.05, t + 0.5)
        d = 10 * np.log10(post / pre)
        out.append(bool(np.percentile(d, 99.5) > 12 and np.median(d) < 6))
    return out


MEASURE_VER = 4   # 잣대가 바뀌면 올린다(벤치 재기 저장본을 버리게)


def measure(src, cache: Path | None = None) -> dict:
    """cache 가 있으면 (경로·크기·수정 시각·잣대 판) 같을 때 저장본을 쓴다 — 벤치는 한 번만 잰다."""
    st = Path(src).stat()
    sig = f"{Path(src).resolve()}|{st.st_size}|{int(st.st_mtime)}|v{MEASURE_VER}"
    if cache and cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        if d.get("_sig") == sig:
            return d
    d = _measure(src)
    d["_sig"] = sig
    if cache:
        cache.write_text(json.dumps(d, ensure_ascii=False, default=str), encoding="utf-8")
    return d


def hook_face(src) -> dict | None:
    """0~3초 첫 빨간 실선 원 구간의 원·얼굴 관계(프레임 중앙값) — fx_measure.scan/summarize."""
    from tools.calcopy.shark import fx_measure as FM
    segs = [FM.summarize(s) for s in FM.segments(FM.scan(src, to=3.0)) if s["kind"] == "solid"]
    segs = [s for s in segs if s.get("rel")]
    return segs[0] if segs else None


def hook_face_ok(h: dict | None) -> tuple[bool, str]:
    """(판단 주인: 원-얼굴 관계 통과) rules effects.red_circle.face.check 범위."""
    K = rules()["effects"]["red_circle"]["face"]
    c = K["check"]
    if not h:
        return False, "0~3초 얼굴 원 없음"
    r = h["rel"]
    bad = []
    if r["off_fh"] > c["off_fh_max"]:
        bad.append(f"중심 어긋남 {r['off_fh']}>{c['off_fh_max']}")
    if not c["r_fh"][0] <= r["r_fh"] <= c["r_fh"][1]:
        bad.append(f"반지름/얼굴 {r['r_fh']}∉{c['r_fh']}")
    if r["face_inside"] < c["inside_min"]:
        bad.append(f"얼굴 원 안 {r['face_inside']}<{c['inside_min']}")
    if not c["r_px"][0] <= h["r"] <= c["r_px"][1]:
        bad.append(f"원 반지름 {h['r']}∉{c['r_px']}")
    if not K["fh_win_range"][0] <= r["face_h_win"] <= K["fh_win_range"][1]:
        bad.append(f"얼굴/창 {r['face_h_win']}∉{K['fh_win_range']}")
    if not c["eye_dy_fh"][0] <= r["eye_dy_fh"] <= c["eye_dy_fh"][1]:
        bad.append(f"눈 높이 차 {r['eye_dy_fh']}∉{c['eye_dy_fh']}")
    return (not bad), " · ".join(bad)


def _hf(h):
    if not h:
        return None
    r = h["rel"]
    return f"r{h['r']:.0f} 어긋남{r['off_fh']:.2f} r/얼굴{r['r_fh']:.2f} 안{r['face_inside']:.2f} 얼굴/창{r['face_h_win']:.2f} 눈차{r['eye_dy_fh']:.2f}"


def _measure(src) -> dict:
    C, Wn = captions(src), window(src)
    dur = _dur(src)
    cells = [c for c in C["cells"] if c.get("ink")]
    one = [c for c in cells if c["ink"][1] - c["ink"][0] < 90]
    col = [c for c in cells if c["colored"] > 300]
    part = [c for c in col if 0.05 < c["frac"] < 0.85]
    ncol = len({n for c in col for n in c["cols"]})
    d = ding_after(src, [f["t"] for f in Wn["flashes"]])
    ev = sorted([f["t"] for f in Wn["flashes"]] + [o["t"] for o in Wn["objects"]])
    wow = []
    for t in ev:
        if not wow or t - wow[-1] > 0.5:
            wow.append(t)
    return {"dur": round(dur, 2), "cells": len(cells), "cap_one_ink_med": [int(np.median([c["ink"][0] for c in one])), int(np.median([c["ink"][1] for c in one]))] if one else None,
            "colored_ratio": round(len(col) / max(1, len(cells)), 2), "partial_ratio": round(len(part) / max(1, len(cells)), 2), "colors": ncol,
            "blur_ratio": round(sum(1 for c in cells if c.get("blur")) / max(1, len(cells)), 2),
            "flashes": Wn["flashes"], "flash_per_min": round(len(Wn["flashes"]) / dur * 60, 1), "objects": Wn["objects"],
            "hook_red_px": Wn["hook_red"], "ding_ratio": round(sum(d) / max(1, len(d)), 2), "wow_per_min": round(len(wow) / dur * 60, 1),
            "cells_detail": cells, "hook_face": hook_face(src)}


def judge(b: dict, o: dict) -> list[tuple]:
    """기준표 행: (칸, 벤치, 우리, 통과?) — 범위는 rules compare."""
    K = rules()["compare"]
    tol = K["cap_one_ink_tol_px"]
    rows = [
        ("훅: 0~1초 빨간 원 픽셀", b["hook_red_px"], o["hook_red_px"], o["hook_red_px"] >= 0.3 * b["hook_red_px"]),
        ("자막 한 줄 잉크 위·아래(중앙)", b["cap_one_ink_med"], o["cap_one_ink_med"],
         bool(o["cap_one_ink_med"] and b["cap_one_ink_med"] and all(abs(x - y) <= tol for x, y in zip(o["cap_one_ink_med"], b["cap_one_ink_med"])))),
        ("강조: 색 있는 칸 비율", b["colored_ratio"], o["colored_ratio"], o["colored_ratio"] >= K["colored_cell_min"]),
        ("강조: 낱말만 색(부분) 칸 비율", b["partial_ratio"], o["partial_ratio"], o["partial_ratio"] >= K["partial_cell_min"]),
        ("강조: 쓴 색 가짓수", b["colors"], o["colors"], o["colors"] >= K["colors_min"]),
        ("자막 넘김 가로 흐림 비율", b["blur_ratio"], o["blur_ratio"], o["blur_ratio"] >= K["transition_blur_min"]),
        ("효과: 꾸밈 등장 수", len(b["objects"]), len(o["objects"]), len(o["objects"]) >= K["objects_min"]),
        ("번쩍: 분당 횟수", b["flash_per_min"], o["flash_per_min"], K["flash_per_min"][0] <= o["flash_per_min"] <= K["flash_per_min"][1]),
        ("효과음: 번쩍 뒤 띠링 비율", b["ding_ratio"], o["ding_ratio"], o["ding_ratio"] >= K["ding_after_flash_min"]),
        ("와우: 번쩍+꾸밈 분당", b["wow_per_min"], o["wow_per_min"], o["wow_per_min"] >= 0.6 * b["wow_per_min"]),
    ]
    ok, why = hook_face_ok(o.get("hook_face"))
    rows.append(("원-얼굴: 0초 빨간 원이 얼굴(머리) 전체를 감싸나", _hf(b.get("hook_face")), (_hf(o.get("hook_face")) or "없음") + (f" ✗ {why}" if why else ""), ok))
    return rows


def sheet(bench, ours, dst: Path, step=1.0):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 22)
    dur = min(_dur(bench), _dur(ours))
    ts = [round(t, 2) for t in np.arange(0.3, dur, step)]
    tw, th = 180, 320
    per = 6
    rows = (len(ts) + per - 1) // per
    sh = Image.new("RGB", (per * (2 * tw + 12), rows * (th + 4)), (30, 30, 30))
    for i, t in enumerate(ts):
        for j, src in enumerate((bench, ours)):
            r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", "-vf", f"scale={tw}:{th}",
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
            if len(r.stdout) < tw * th * 3:
                continue
            im = Image.frombytes("RGB", (tw, th), r.stdout[:tw * th * 3])
            ImageDraw.Draw(im).text((3, 2), f"{'벤치' if j == 0 else '우리'} {t:.1f}", font=font, fill=(255, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
            sh.paste(im, ((i % per) * (2 * tw + 12) + j * tw, (i // per) * (th + 4)))
    sh.save(dst, quality=85)


def main():
    bench, ours, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    out.mkdir(parents=True, exist_ok=True)
    b, o = measure(bench, out / f"bench_{bench.stem}.json"), measure(ours)
    rows = judge(b, o)
    (out / f"compare_{tag}.json").write_text(json.dumps({"bench": b, "ours": o, "rows": rows}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    md = [f"# 벤치 대조 기준표 — {tag}", f"벤치 {bench.name} {b['dur']}초 · 우리 {ours} {o['dur']}초", "", "| 칸 | 벤치 | 우리 | 판정 |", "|---|---|---|---|"]
    md += [f"| {r[0]} | {r[1]} | {r[2]} | {'통과' if r[3] else '떨어짐'} |" for r in rows]
    md += ["", f"- 벤치 번쩍 {[(f['t'], f['color']) for f in b['flashes']]}", f"- 우리 번쩍 {[(f['t'], f['color']) for f in o['flashes']]}",
           f"- 벤치 꾸밈 {[(x['t'], x['kind']) for x in b['objects']]}", f"- 우리 꾸밈 {[(x['t'], x['kind']) for x in o['objects']]}"]
    (out / f"compare_{tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if "--no-sheet" not in sys.argv:
        sheet(bench, ours, out / f"compare_{tag}_sheet.jpg")
    print("\n".join(md))
    fails = [r[0] for r in rows if not r[3]]
    print(f"\n떨어짐 {len(fails)}칸: {fails}")


if __name__ == "__main__":
    main()
