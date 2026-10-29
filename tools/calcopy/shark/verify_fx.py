# -*- coding: utf-8 -*-
"""샥탬스토리 완성본 실측 — 효과음·장면 효과가 **나온 영상 파일 안에** 실제로 들어갔나 (관제 097, 2026-10-18).

사장님 10-18 "완성본을 보니까 칼카피가 효과음이랑 장면효과가 된 거 맞는지 확인". render_info 의 계획(효과·sfx)을
기준으로 **완성 mp4 만** 잰다(계산 대조 아님).
  효과음: 팩 wav 를 완성본 소리와 겹쳐 대본 시각 ±0.15초 정규 상관(ncc). 사건 없는 시각 20곳의 상관(p95)보다 확실히 커야 들어간 것.
  장면 효과: 효과 시간 가운데 프레임 vs 시작 0.15초 전 프레임 — 효과 색 픽셀 수(자리 상자 안). 번쩍은 화면 평균 색이 효과 색 쪽으로 움직였나.
  + 효과마다 확대 칸(전·중) 시트 jpg — 눈으로 본다.

    PYTHONUTF8=1 py tools/calcopy/shark/verify_fx.py <render_info.json> <완성.mp4> <시트.jpg> [--upto 초]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.shark import fx as FX  # noqa: E402

SR = 48000
W, H = 1080, 1920
COLOR_TOL = 70
FLASH_RGB = {"초록": (0, 255, 0), "빨강": (255, 30, 40), "노랑": (255, 230, 0)}
FLASH_PUSH_MIN = 12.0   # 번쩍 판정 = 같은 샷 번쩍 직후 대비 색 쪽으로 민 양(0~255) — 10-20 실측 번쩍 29개 25.0~52.3 · 번쩍 없는 순간 81곳 중앙 1.3


def pcm(mp4: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def frame(mp4: str, t: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", mp4, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3)


def ncc_at(x: np.ndarray, s: np.ndarray, t: float, span=0.15) -> tuple[float, float]:
    """t 근처 ±span 에서 s 와 가장 닮은 자리의 정규 상관 (값, 어긋난 초)."""
    i0 = int((t - span) * SR); i1 = int((t + span) * SR) + len(s)
    i0 = max(0, i0); seg = x[i0:i1]
    if len(seg) < len(s):
        return 0.0, 0.0
    c = np.correlate(seg, s, "valid")
    e = np.sqrt(np.convolve(seg * seg, np.ones(len(s)), "valid")) * np.linalg.norm(s) + 1e-9
    r = c / e; k = int(np.argmax(r))
    return float(r[k]), round((i0 + k) / SR - t, 3)


def sfx_wav(slot: str) -> np.ndarray:
    from shopping_shorts import sfx_pack
    d = Path(dict(sfx_pack.list_packs())[FX.R()["sfx"]["pack"]])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(d / f"{slot}.wav"), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    s = np.frombuffer(raw, np.float32)
    return s[: int(0.35 * SR)]          # 앞 0.35초(울림 꼬리는 다른 소리에 묻힘)


def box_of(e: dict, E: dict) -> tuple[int, int, int, int]:
    k = e["kind"]; x, y = e["at"]
    if k == "red_circle":
        r = e.get("size", 430) / 2 + 20
    elif k == "dashed_circle":
        r = e.get("radius", E["dashed_circle"]["radius"]) * 1.15
    else:
        r = max(E.get(k, {}).get("w", 200), E.get(k, {}).get("h", 200)) * 0.8 + 30
    return int(max(0, x - r)), int(max(0, y - r)), int(min(W, x + r)), int(min(H, y + r))


def color_mask(img: np.ndarray, box, rgb) -> np.ndarray:
    x0, y0, x1, y1 = box
    a = img[y0:y1, x0:x1].astype(int)
    return np.abs(a - np.array(rgb)).max(axis=2) < COLOR_TOL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("info"); ap.add_argument("mp4"); ap.add_argument("sheet")
    ap.add_argument("--upto", type=float, default=None, help="이 초까지만(하이브리드 앞부분)")
    a = ap.parse_args()
    I = json.loads(Path(a.info).read_text(encoding="utf-8"))
    E = FX.R()["effects"]
    upto = a.upto if a.upto is not None else 1e9
    x = pcm(a.mp4); dur = len(x) / SR
    out = {"mp4": a.mp4, "sfx": [], "fx": []}

    # 효과음
    ev = [s for s in (I.get("sfx") or []) if s["t"] + 0.35 < min(upto, dur)]
    rng = np.random.default_rng(7); cache = {}
    for s in ev:
        w = cache.setdefault(s["slot"], sfx_wav(s["slot"]))
        r, lag = ncc_at(x, w, s["t"])
        far = [t for t in rng.uniform(0.5, min(upto, dur) - 0.6, 60) if all(abs(t - q["t"]) > 0.8 for q in I["sfx"])][:20]
        base = sorted(ncc_at(x, w, t)[0] for t in far)
        p95 = base[int(len(base) * 0.95) - 1] if base else 0.0
        ok = r > max(0.25, p95 * 1.5) and abs(lag) <= 0.05
        out["sfx"].append({"t": s["t"], "slot": s["slot"], "why": s["why"], "ncc": round(r, 3), "lag": lag, "base_p95": round(p95, 3), "ok": ok})

    # 장면 효과
    tiles = []
    effs = FX.timed(I)                   # 그리기·효과음과 같은 시각(번쩍 점선 안으로 옮김·컷 붙임) — render_info effects 는 옮기기 전 값
    flashes = [e["T"] for e in effs if e["kind"] == "flash"]
    for e in sorted(effs, key=lambda e: e["T"][0]):
        T0, T1 = e["T"]
        if T0 >= min(upto, dur):
            continue
        k = e["kind"]
        if k == "flash":
            on = frame(a.mp4, T0 + 0.05); off = frame(a.mp4, max(0, T0 - 0.1)); aft = frame(a.mp4, T1 + 0.15)
            c = np.array(FLASH_RGB[e["color"]], float)
            em = FX._edge_mask(1080, 1052) > 0.5 if E["flash"].get("style") == "edge" else np.ones((1052, 1080), bool)   # R4 가장자리 빛 = 가장자리 띠만 잰다
            win = lambda f: f[434:434 + 1052][em].mean(0)        # 창 안만(위아래 검정·제목 띠 빼고)
            d_on, d_off, d_aft = (float(np.linalg.norm(win(f) - c)) for f in (on, off, aft))
            # ★판정 = 같은 샷 안에서 번쩍 순간이 번쩍 직후(빛이 다 빠진 edge_dur+0.08초)보다 번쩍 색 쪽으로 민 양(픽셀마다 바탕→색 방향 성분 평균).
            #   옛 판정(평균색 거리, 앞 프레임·0.6초 뒤와 비교)은 번쩍이 컷 첫 프레임에 걸려 앞이 다른 컷이고 뒤 0.6초에 장면이 바뀌면 틀렸다
            #   (10-20 9편 N2: 옛 거리차 9 '안 보임' — 같은 샷 비교 민 양 51.8, 통과한 O4 29.2 보다 큼). 번쩍 없는 순간 81곳 중앙 1.3.
            base = frame(a.mp4, T0 + E["flash"].get("edge_dur", 0.22) + 0.08)
            px_on, px_b = on[434:434 + 1052][em].astype(float), base[434:434 + 1052][em].astype(float)
            dv = c - px_b
            push = float((((px_on - px_b) * dv).sum(1) / (np.linalg.norm(dv, axis=1) + 1e-6)).mean())
            luma = float((px_b @ np.array([0.299, 0.587, 0.114])).mean())
            ok = push >= FLASH_PUSH_MIN
            out["fx"].append({"kind": k, "line": e["line"], "T": [T0, T1], "moved": bool(e.get("moved_into_dashed")), "color": e["color"], "push": round(push, 1), "edge_luma": round(luma),
                              "dist_off": round(d_off, 1), "dist_on": round(d_on, 1), "dist_after": round(d_aft, 1), "ok_old": bool(d_on < d_off - 15 or d_on < d_aft - 15), "ok": bool(ok)})
            box = (0, 434, W, 434 + 1052)
        else:
            cands = [(T0 + T1) / 2] if k == "red_circle" else [T0 + min(0.6, (T1 - T0) / 2), T1 - 0.25, T0 + 0.45]
            tm = next((t for t in cands if not any(f[0] - 0.05 <= t <= f[1] + 0.05 for f in flashes)), cands[0])   # 번쩍 물듦 피함
            on = frame(a.mp4, tm); off = frame(a.mp4, T0 - 0.15) if T0 >= 0.15 else None
            box = box_of(e, E); rgb = E[k].get("main", E[k].get("color")) if k in E else None
            if k == "money_emoji" or rgb is None:
                n_on = int(np.abs(on[box[1]:box[3], box[0]:box[2]].astype(int) - (off if off is not None else on)[box[1]:box[3], box[0]:box[2]].astype(int)).max(axis=2).__gt__(60).sum())
                n_off = 0
            else:
                m_on = color_mask(on, box, rgb); m_off = color_mask(off, box, rgb) if off is not None else np.zeros_like(m_on)
                n_on = int(m_on.sum()); n_off = int(m_off.sum())
            new = int((m_on & ~m_off).sum()) if k != "money_emoji" and rgb is not None else n_on   # 전엔 없던 효과 색 = 새로 그려진 것(바탕에 원래 빨강이 있어도)
            ok = new > 800
            mark = None
            if e.get("target_path") or e.get("target_box"):   # 그 프레임의 대상 상자·끝점(적중 눈 확인)
                tp = e.get("target_path") or [[0.0, *e["target_box"]]]
                p = FX.pose(e, tm)
                mark = {"box": FX.track_at(tp, tm - T0), "tip": FX.place(e, p)["tip"] if p else None}
            out["fx"].append({"kind": k, "line": e["line"], "T": [T0, T1], "at": e["at"], "t_seen": round(tm, 3), "px_on": n_on, "px_before": n_off if off is not None else None, "px_new": new, "ok": bool(ok),
                              "hit": (e.get("hit") or {}).get("why"), "target": e.get("target_what") or (e.get("target") if isinstance(e.get("target"), str) else "손 상자" if e.get("target") else None)})
            if mark:
                bx = mark["box"]
                box = (int(max(0, min(box[0], bx[0] - 20))), int(max(0, min(box[1], bx[1] - 20))), int(min(W, max(box[2], bx[2] + 20))), int(min(H, max(box[3], bx[3] + 20))))
        tiles.append((f"{e['line']} {k} {T0:.2f}s" + (f" -> {out['fx'][-1].get('target')}" if k != "flash" else ""), off if k != "flash" else frame(a.mp4, max(0, T0 - 0.1)), on, box,
                      mark if k != "flash" else None))

    # 시트: 효과마다 [전 | 중] 확대
    from PIL import Image, ImageDraw
    th = 300; rows = []
    for name, off, on, (x0, y0, x1, y1), mark in tiles:
        pad = 60; x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
        ims = []
        for j, f in enumerate((off, on)):
            im = Image.fromarray(f[y0:y1, x0:x1].copy() if f is not None else np.zeros((y1 - y0, x1 - x0, 3), np.uint8))
            if j == 1 and mark:     # 하늘색 = 대상 상자, 노랑 점 = 그 프레임 효과 끝점(화살표)·중심(원)
                d = ImageDraw.Draw(im); b = mark["box"]
                d.rectangle([b[0] - x0, b[1] - y0, b[2] - x0, b[3] - y0], outline=(0, 220, 255), width=4)
                if mark["tip"]:
                    tx, ty = mark["tip"][0] - x0, mark["tip"][1] - y0
                    d.ellipse([tx - 9, ty - 9, tx + 9, ty + 9], fill=(255, 255, 0), outline=(0, 0, 0), width=2)
            ims.append(im.resize((int(im.width * th / im.height), th)))
        row = Image.new("RGB", (ims[0].width + ims[1].width + 10, th + 28), "white")
        row.paste(ims[0], (0, 28)); row.paste(ims[1], (ims[0].width + 10, 28))
        from PIL import ImageFont
        ImageDraw.Draw(row).text((4, 2), f"{name}   [전 | 중]  하늘색=대상 상자 노랑=끝점", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 18))
        rows.append(row)
    if rows:
        sw = max(r.width for r in rows); sh = sum(r.height + 6 for r in rows)
        S = Image.new("RGB", (sw, sh), "white"); y = 0
        for r in rows:
            S.paste(r, (0, y)); y += r.height + 6
        S.save(a.sheet, quality=85)
    out["sheet"] = a.sheet
    out["dropped"] = I.get("fx_dropped") or []
    out["summary"] = {"dropped": len(out["dropped"]), "sfx_ok": f"{sum(s['ok'] for s in out['sfx'])}/{len(out['sfx'])}", "fx_ok": f"{sum(f['ok'] for f in out['fx'])}/{len(out['fx'])}"}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
