# -*- coding: utf-8 -*-
# _deprecated_2026-10-25 → tools/calcopy/hybrid/styles/신박판.json (관제 263 지시서 07 · 표준 §3-1: 새 편은 공용 렌더러로. 읽기 전용 참고물 — 설명서 프리셋 생성기는 회원 옛 길이 결과를 읽으므로 지우지 않는다)
"""신박발견(sinbak) 프리셋 손질 근거 실측 — 원본 1080×1920 프레임 픽셀로 잰다(눈대중 금지). sinbak_preset.py 머리 주석의 출처.
    PYTHONUTF8=1 py channel/sinbak/preset/sinbak_measure.py      → C:/숏템_칼카피/sinbak/work/preset/{measure.json, font_*.png}

잰 것: 바탕색 · 영상 창 경계·모서리 반경(4 모서리, 원 맞춤) · 로고 줄 잉크 · 제목/본문 잉크 상자·글꼴 묶음 판별(fontmatch.pooled_rank)·
       그 글꼴로 역산한 크기(to_frame.size_and_top)·자간·낱말 틈 · 본문 흰 테 고리 밝기 · 창 안 글씨 채움색·글꼴·검정 테 px(행 스캔).
판단은 엔진 함수(fontmatch.pooled_rank · to_frame.size_and_top/_css_line/family_of) — 여기는 크롭·글자를 모으기만 한다.
"""
import json, statistics as st, sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import fontmatch, to_frame as TF  # noqa: E402

SRC = Path("C:/숏템_칼카피/sinbak/src"); OUT = Path("C:/숏템_칼카피/sinbak/work/preset"); RD = ROOT / "channel/sinbak/줄판독"
IDS = ["rAt34vkQ0OY", "oT-SxFJcQ-4", "fzoZc7V_hDM", "CnRWZ3scVfk", "bpjoacs2S6Q", "edTkyQKrqMk"]
WIN = (19, 541, 1060, 1287)
# 글꼴 확정(묶음 점수 + 눈 대조 font_eye_title_caption.png): 제목 1위 NanumMyeongjoEB(정규 0.900·원점수 0.38·일치 2/6) 는 명조 부리가 원본에 없어 뺌 → 고딕 중 SUITBold(0.811, 획 굵기 대조) · 본문 1위 CcPretendard-SemiBold(0.946, 7/18)
FAM_TITLE, FAM_CAPTION = "SUITBold", "CcPretendard-SemiBold"


def frame(vid, t):
    cap = cv2.VideoCapture(str(SRC / f"{vid}.mp4")); cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read(); cap.release()
    return cv2.cvtColor(f, cv2.COLOR_BGR2RGB) if ok else None


def dark_mask(img, thr=110):
    return img.astype(int).sum(axis=2) / 3 < thr


def bbox(m):
    ys, xs = np.where(m)
    return None if not len(ys) else [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def word_gaps(m, h):
    """잉크 열 틈 중 줄 높이 20% 넘는 것 = 낱말 틈(px)."""
    col = m.any(axis=0); xs = np.where(col)[0]
    if not len(xs): return []
    col = col[xs[0]:xs[-1] + 1]; gaps, run = [], 0
    for c in col:
        if not c: run += 1
        else:
            if run > 0.2 * h: gaps.append(run)
            run = 0
    return gaps


def text_layer(samples, label, fixed_fam=None):
    """samples = [(mask(전체 줄 영역), 글, 잉크상자)] → 글꼴 판별 + 크기·자간·낱말 틈."""
    pool = [(fontmatch._bbox(m), t) for m, t, b in samples]
    R = fontmatch.pooled_rank(pool)
    reg = [dict(x, family=TF.family_of(x["font"])) for x in R["top"]]
    fontmatch.grid(pool[0][0], pool[0][1], R["top"][:4], str(OUT / f"font_{label}.png"))
    fam = fixed_fam or next((x["family"] for x in reg if x["family"]), None)
    sizes, ws, ls_, ys, gaps_m, gaps_o = [], [], [], [], [], []
    for m, t, b in samples:
        r = TF.size_and_top(fam, t, b[1], b[3] - b[1], None); sizes.append(r["size"])
    size = round(st.median(sizes), 1)
    font = TF._pil_font(fam, size)
    for m, t, b in samples:
        w0, g0 = TF._css_line(font, t, 0.0, 0.0)
        gm = word_gaps(m[b[1]:b[3], b[0]:b[2]], b[3] - b[1])
        n_ch = len(t.replace(" ", "")) - 1
        if len(gm) == t.strip().count(" ") and g0:
            gaps_m += gm; gaps_o += g0
            ls_.append(((b[2] - b[0]) - sum(gm) - (w0 - sum(g0))) / max(1, n_ch))
        ys.append(TF.size_and_top(fam, t, b[1], b[3] - b[1], round(size * 1.15))["y"])
    ls = round(st.median(ls_), 1) if ls_ else 0
    # 자간을 넣은 뒤 우리 낱말 틈 = 0 간격 틈 + ls(공백 글자 뒤에도 붙음) → 원본 틈과의 차 = 낱말 간격
    wsp = round(st.median(gaps_m) - (st.median(gaps_o) + ls), 1) if gaps_m else 0
    return {"pooled": {"top": reg, "n": R["n"], "agree": R["agree"], "per_sample_top1": R["per_sample_top1"]}, "family": fam,
            "size_each": sizes, "size": size, "y_each": ys, "y": int(st.median(ys)), "letter_spacing": ls, "word_spacing": wsp,
            "gap_measured_med": st.median(gaps_m) if gaps_m else None, "gap_font0_med": st.median(gaps_o) if gaps_o else None,
            "ink_boxes": [b for _, _, b in samples], "grid": str(OUT / f"font_{label}.png")}


def corner_radius(union, x0, y0, sx, sy):
    """창 모서리 원 맞춤 — 행마다 바깥 끝(바탕과 다른 첫 열)에서 들어간 양 → r."""
    xs = []
    for dy in range(0, 140):
        y = y0 + sy * dy
        row = union[y, :] if True else None
        nz = np.where(row)[0]
        if not len(nz): xs.append(None); continue
        xs.append((nz.min() - x0) if sx > 0 else (x0 - nz.max()))
    best = None
    for r in range(5, 140):
        err, n = 0.0, 0
        for dy, inset in enumerate(xs):
            if inset is None or dy >= r: continue
            exp = r - np.sqrt(max(0, r * r - (r - dy - 0.5) ** 2)); err += (inset - exp) ** 2; n += 1
        if n > 5 and (best is None or err / n < best[1]): best = (r, err / n)
    return {"r": best[0], "rmse": round(best[1] ** 0.5, 2), "inset_rows0_10": xs[:10]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    M = {"window": {}, "bg": {}, "logo": {}, "caption_rim": []}
    titles, caps, ovl = [], [], {}
    for vid in IDS:
        J = json.loads((RD / f"{vid}.json").read_text(encoding="utf-8"))
        dur = J["dur"]
        # 창 합집합(창 안 영상이 바탕과 다른 곳) — 고르게 24장
        bgs, union = [], None
        for k in range(24):
            f = frame(vid, (k + 0.5) * min(dur, 1.6 if vid == "oT-SxFJcQ-4" else dur) / 24)
            if f is None: continue
            bg = np.median(f[1450:1880, 60:1020].reshape(-1, 3), axis=0); bgs.append(bg)
            d = np.abs(f.astype(int) - bg).max(axis=2) > 18
            d[:530] = False; d[1290:] = False   # 1290~ = 본문 자막 잉크(창 아래 끝 1287)
            union = d if union is None else (union | d)
        bg = np.median(np.array(bgs), axis=0).round().astype(int).tolist(); M["bg"][vid] = bg
        bb = bbox(union); M["window"][vid] = {"box": bb}
        if vid != "oT-SxFJcQ-4" or True:
            x0, y0, x1, y1 = bb
            M["window"][vid]["corners"] = {"tl": corner_radius(union, x0, y0, 1, 1), "tr": corner_radius(union, x1 - 1, y0, -1, 1),
                                           "bl": corner_radius(union, x0, y1 - 1, 1, -1), "br": corner_radius(union, x1 - 1, y1 - 1, -1, -1)}
        tt = 0.8 if vid == "oT-SxFJcQ-4" else min(1.0, dur / 2)
        f = frame(vid, tt)
        lg = dark_mask(f[260:420]); lb = bbox(lg); M["logo"][vid] = [lb[0], lb[1] + 260, lb[2], lb[3] + 260] if lb else None
        tm = np.zeros(f.shape[:2], bool); tm[430:540] = dark_mask(f[430:540])
        titles.append((tm, J["title_lines"][0]["text"], bbox(tm)))
        body = [x for x in J["lines"] if x["layer"] == "신박발견-본문"]
        for x in body[:: max(1, len(body) // 3)][:3]:
            g = frame(vid, (x["t0"] + x["t1"]) / 2)
            cm = np.zeros(g.shape[:2], bool); cm[1288:1385] = dark_mask(g[1288:1385])
            b = bbox(cm)
            if not b: continue
            caps.append((cm, x["text"], b))
            # 흰 테: 잉크에서 1~6px 떨어진 고리 밝기 중앙 vs 바탕
            ink = cm.astype(np.uint8); prev = ink; ring = {}
            gray = g.astype(int).sum(axis=2) / 3
            for r in range(1, 7):
                dil = cv2.dilate(ink, np.ones((2 * r + 1, 2 * r + 1), np.uint8))
                rr = (dil > 0) & ~(prev > 0); ring[r] = round(float(np.median(gray[rr])), 1); prev = dil
            M["caption_rim"].append({"vid": vid, "text": x["text"], "ring_px1_6": ring, "bg": round(float(np.median(gray[1395:1500, 100:980])), 1)})
        for x in J["lines"]:
            if not x["layer"].startswith("신박발견-") or x["layer"] == "신박발견-본문" or not x.get("fill_hex"): continue
            hx = x["fill_hex"].lstrip("#"); rgb = np.array([int(hx[i:i + 2], 16) for i in (0, 2, 4)])
            g = frame(vid, (x["t0"] + x["t1"]) / 2)
            y0, y1 = x["y"]; xr = x.get("x") if isinstance(x.get("x"), list) else [WIN[0], WIN[2]]
            sub = g[max(0, y0 - 20):y1 + 20, max(0, xr[0] - 30):xr[1] + 30].astype(int)
            fill = np.abs(sub - rgb).max(axis=2) < 60
            fill = cv2.morphologyEx(fill.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
            if fill.sum() < 200: continue
            darkm = sub.sum(axis=2) / 3 < 70
            runs = []   # 행 스캔: 채움 오른쪽·왼쪽 끝에서 바깥으로 이어진 검정 길이
            for yy in range(fill.shape[0]):
                xs = np.where(fill[yy])[0]
                if not len(xs): continue
                for start, step in ((xs.max() + 1, 1), (xs.min() - 1, -1)):
                    n, xx = 0, start
                    while 0 <= xx < fill.shape[1] and darkm[yy, xx]: n += 1; xx += step
                    if n: runs.append(n)
            fm = fontmatch._bbox(fill)
            k = x["layer"].split("-")[1]
            ovl.setdefault(k, []).append({"vid": vid, "text": x["text"], "hex": x["fill_hex"], "outline_runs_med": st.median(runs) if runs else None,
                                          "fill_ink_h": int(fm.shape[0]) if fm is not None else None, "mask": fm})
    M["title"] = text_layer(titles, "title", FAM_TITLE); M["caption"] = text_layer(caps, "caption", FAM_CAPTION)
    # 창 안 글씨: 한 줄짜리 채움 마스크로 묶음 판별 + 테 px
    one = [(o["mask"], o["text"]) for v in ovl.values() for o in v if o["mask"] is not None and o["fill_ink_h"] and o["fill_ink_h"] < 110]
    R = fontmatch.pooled_rank(one[:16]); fontmatch.grid(one[0][0], one[0][1], R["top"][:4], str(OUT / "font_overlay.png"))
    M["overlay"] = {"pooled": {"top": [dict(x, family=TF.family_of(x["font"])) for x in R["top"]], "n": R["n"], "agree": R["agree"]},
                    "outline_px_med": st.median([o["outline_runs_med"] for v in ovl.values() for o in v if o["outline_runs_med"]]),
                    "fill_ink_h_med": st.median([o["fill_ink_h"] for v in ovl.values() for o in v if o["fill_ink_h"]]),
                    "by_layer": {k: [{kk: vv for kk, vv in o.items() if kk != "mask"} for o in v] for k, v in ovl.items()}}
    (OUT / "measure.json").write_text(json.dumps(M, ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)), encoding="utf-8")
    print(json.dumps({k: M[k] for k in ("bg", "window", "logo")}, ensure_ascii=False, default=int)[:3000])
    for k in ("title", "caption"):
        print(k, {kk: M[k][kk] for kk in ("family", "size", "size_each", "y", "letter_spacing", "word_spacing", "gap_measured_med", "gap_font0_med")})
        print("  top", [(x["font"], x["score"], x["raw"], x["family"]) for x in M[k]["pooled"]["top"]], "agree", M[k]["pooled"]["agree"])
    print("overlay", M["overlay"]["pooled"], M["overlay"]["outline_px_med"], M["overlay"]["fill_ink_h_med"])
    print("rim", M["caption_rim"][:4])


if __name__ == "__main__":
    main()
