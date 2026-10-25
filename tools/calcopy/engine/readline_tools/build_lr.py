# -*- coding: utf-8 -*-
"""줄판독 조립(build_lr) — 사람이 눈으로 적은 spec(.py) + capseg/cutdet/픽셀 실측 + sfx_events 신호 → 줄판독 json.

어디서 왔나: 06 잇템로그 워커(관제 263, 10-24)의 세션 임시 폴더 도구 build_lr.py 를 옮김. 판정 알고리즘은 그대로,
            박혀 있던 경로(C:/숏템_칼카피/ititemlog/...)·채널 상수(글꼴·외곽·층 이름)는 인자·프로필 json 으로 뺐다.
무엇을 재나(기계 칸): y·fill_hex = 줄 가운데 시각 프레임의 측정 띠에서 '검정 외곽 옆 밝은 채움' 가장 큰 행 덩어리(spec ex 가 이긴다,
            없으면 capseg 덩어리 yr/hex) · cut_at = 줄 안의 cutdet 컷 · transition = 줄 시작 ±0.05초 컷 종류 · motion = 샷 chg<6 still 아니면 cam ·
            sfx = sfx_raw 에서 고립>=0.5·유성<=0.3 솟음 첫 개(귀 확인 아님) · dur = ffprobe.
            나머지(글·화자·역할·등장·스티커·장면·fit)는 spec 에 사람이 적은 값.
spec 꼴(예: examples/ititemlog_SbW.py): ID · TITLE · LAYOUT · FRAME0 · LINES[(t0,t1,화자,글,역할,등장,변형,강조,스티커,장면,장면설명,fit[,ex])] ·
            NO_CAP · BEATS · NOTES · (선택) NAME_EV·PROFILE·SOURCE_LABEL·SOUND_MODE·EXTRA(문서 칸 추가)·ex 의 다른 칸(그대로 실림)·ex.sfx_none.
            spec 에 FONT·HAND_FONT·LAYER·MEASURE_BAND·MADE_BY 가 있으면 프로필보다 이긴다. (썰풀다 워커 mk.py 의 덧붙임을 여기로 합침)
입력: spec · capseg 결과(seg_<id>.json) · cutdet 결과(cut_<id>.json) · 원본 mp4 · (선택) sfx_raw.json({id:[솟음...]}) · 프로필 json
출력: 줄판독 json(kal_analyze check --strict 칸 꼴)

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/build_lr.py <spec.py> <out.json> --work <seg·cut 폴더> --mp4 <원본.mp4>
        [--sfx-raw sfx_raw.json] [--profile profiles/ititemlog.json] [--seg x.json --cut y.json]
    (잇템로그 예: --work C:/숏템_칼카피/ititemlog/work/lr6 --mp4 C:/숏템_칼카피/ititemlog/src/<id>.mp4 --sfx-raw C:/숏템_칼카피/ititemlog/kal/sfx_raw.json)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

EX_USED = {"y", "fill_hex", "transition", "layer", "enter_ms", "outline", "line_gap_px", "motion", "exit", "notes"}
TOOLS_NOTE = "tools/calcopy/engine/readline_tools capseg/cutdet/px/segsheet/build_lr"
DEFAULT_PROFILE = {"layer": None, "measure_band": [1180, 1470],
                   "font": {"name": "미확정", "basis": "없음"}, "hand_font": {"name": "미확정(손글씨체)", "basis": "없음"},
                   "outline": None, "hand_outline": None, "letter_gap_px": None, "made_by": "readline_tools.build_lr"}


def load_spec(spec_p: str):
    sp = importlib.util.spec_from_file_location("lr_spec", spec_p)
    S = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(S)
    return S


def load_profile(p: str | None) -> dict:
    prof = dict(DEFAULT_PROFILE)
    if p:
        prof.update({k: v for k, v in json.loads(Path(p).read_text(encoding="utf-8")).items() if not k.startswith("_")})
    return prof


PROFILES = Path(__file__).resolve().parent / "profiles"
CAP_PAD = 100   # 채널 프로필이 없을 때 뜯기 caption_band(OCR 글자 띠, 빡빡함) 위아래 여유 — 손 값 아님(재현 안 됨, README '띠 민감')


def channel_profile(slug: str) -> dict | None:
    """profiles/<slug>.json (채널 값 한 곳) — 없으면 None."""
    p = PROFILES / f"{slug}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def bands_for(slug: str, layout: dict | None, H: int = 1920, vid: str | None = None, mp4: str | None = None) -> dict:
    """capseg 띠·cutdet 창·capseg 모드를 정하는 주인 — kal.py step_frames 가 부른다. 돌려줌 {cap_band, window, mode, why}.
    띠: 프로필 bands{<편>} > 프로필 capseg_band(손 값) > autoband.find_band(mp4 를 주면 — 편마다 자동) > 뜯기 caption_band±CAP_PAD > 없음.
    창: 프로필 cutdet_window > 뜯기 layout.window > 전체."""
    prof = channel_profile(slug) or {}
    lay = layout or {}
    mode = prof.get("capseg_mode", "color")
    why = []
    cb = (prof.get("bands") or {}).get(vid) if vid else None
    if cb:
        why.append(f"capseg 띠 = profiles/{slug}.json bands[{vid}]")
    elif prof.get("capseg_band"):
        cb = prof["capseg_band"]
        why.append(f"capseg 띠 = profiles/{slug}.json capseg_band(손 값)")
    elif mp4:
        from tools.calcopy.engine.readline_tools.autoband import band_in_channel
        r = band_in_channel(mp4, mode)
        cb = r["band"]
        why.append(f"capseg 띠 = autoband 자동(핵 {r['core']}·{r['mask']}) — 손 값 아님, 고치면 profiles/{slug}.json bands 에")
    elif lay.get("caption_band") and len(lay["caption_band"]) == 2:
        c = lay["caption_band"]
        cb = [max(0, int(c[0]) - CAP_PAD), min(H, int(c[1]) + CAP_PAD)]
        why.append(f"capseg 띠 = 뜯기 caption_band±{CAP_PAD}(프로필·mp4 없음)")
    else:
        why.append("capseg 띠 없음 → 건너뜀")
    win = prof.get("cutdet_window")
    if win:
        why.append(f"cutdet 창 = profiles/{slug}.json")
    elif lay.get("window") and len(lay["window"]) == 4:
        w = lay["window"]
        win = [int(w[1]), min(H, int(w[1]) + int(w[3]))]
        why.append("cutdet 창 = 뜯기 layout.window")
    else:
        win = [0, H]
        why.append("cutdet 창 = 전체")
    return {"cap_band": cb, "window": win, "mode": mode, "why": " · ".join(why)}


def sfx_ok_of(sfx_raw: dict | None, vid: str) -> list[dict]:
    if not sfx_raw or vid not in sfx_raw:
        return []
    return [e for e in sfx_raw[vid] if e.get("isolated", 0) >= 0.5 and e.get("voiced", 1) <= 0.3]


def seg_for(segs: list[dict], t0: float, t1: float):
    best = None
    for s in segs:
        ov = min(t1, s["t1"]) - max(t0, s["t0"])
        if ov > 0.03 and s["hex"] and s["ink"] > 300:
            if best is None or s["ink"] * ov > best["ink"] * max(0.001, min(t1, best["t1"]) - max(t0, best["t0"])):
                best = s
    return best


def trans_at(cuts: list[dict], t0: float) -> str:
    for c in cuts:
        if abs(c["t"] - t0) <= 0.05 or (c["t"] - 0.05 <= t0 <= c["t_end"] + 0.05):
            return c["kind"].rstrip("?")
    return "none"


def cuts_in(cuts: list[dict], t0: float, t1: float) -> list[float]:
    return [c["t"] for c in cuts if t0 + 0.05 < c["t"] < t1 - 0.05]


def motion_at(shots: list[dict], t: float) -> str:
    """cutdet --v2 샷이면 그 motion(shotmotion: still/cam/zoom_in/zoom_out/pan, 'still?'→still) · 옛 샷이면 chg<6 still 아니면 cam."""
    for s in shots:
        if s["t0"] <= t < s["t1"]:
            if s.get("motion"):
                return str(s["motion"]).rstrip("?")
            c = s.get("chg", 0)
            return "still" if c < 6 else "cam"
    return "cam"


def _dominant_hex(px: np.ndarray) -> np.ndarray:
    """가장 많은 색 묶음(채널마다 32단계로 묶은 최빈 칸)의 중앙값 — 강조색(노랑·분홍)이 섞인 줄에서 바탕 글자색이 중간색으로 번지지 않게."""
    q = (px // 32).astype(np.int32)
    key = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]
    k = np.bincount(key).argmax()
    return np.median(px[key == k], 0)


def measure(cap, t: float, y0: int = 1180, y1: int = 1470, fill: str = "median"):
    """줄 가운데 프레임의 자막 y 범위·채움 hex(가장 큰 연속 행 덩어리)."""
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    if not ok:
        return None, None
    b = f[y0:y1]
    hsv = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    dark = (hsv[..., 2] < 45).astype(np.uint8)
    m = (hsv[..., 2] > 170) & (cv2.dilate(dark, np.ones((9, 9), np.uint8)) > 0)
    rows = m.sum(1)
    if rows.max() < 20:
        return None, None
    on = np.where(rows > 0.2 * rows.max())[0]
    runs = np.split(on, np.where(np.diff(on) > 6)[0] + 1)
    r = max(runs, key=lambda r: rows[r].sum())
    mm = np.zeros_like(m)
    mm[r.min():r.max() + 1] = m[r.min():r.max() + 1]
    c = (_dominant_hex(b[mm]) if fill == "dominant" else np.median(b[mm], 0)).astype(int)
    return [int(y0 + r.min()), int(y0 + r.max())], "#%02X%02X%02X" % (c[2], c[1], c[0])


def _dur(mp4: str) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                                capture_output=True, text=True).stdout.strip())


def build_doc(S, segs: list[dict], cd: dict, mp4: str, sfx_raw: dict | None = None, profile: dict | None = None) -> dict:
    P = dict(DEFAULT_PROFILE, **(profile or {}))
    P.update(getattr(S, "PROFILE", None) or {})          # spec 안 PROFILE 이 프로필 파일보다 이긴다(썰풀다 mk.py 꼴)
    FONT = getattr(S, "FONT", P["font"])
    HAND_FONT = getattr(S, "HAND_FONT", P["hand_font"])
    layer = getattr(S, "LAYER", P["layer"])
    my0, my1 = getattr(S, "MEASURE_BAND", P["measure_band"])
    vid = S.ID
    cuts = cd["cuts"]
    shots = cd["shots"]
    sfx_ok = sfx_ok_of(sfx_raw, vid)
    cap = cv2.VideoCapture(mp4)
    lines = []
    for L in S.LINES:
        t0, t1, spk, text, role, enter, variant, emph, sticker, scene, desc, fit = L[:12]
        ex = L[12] if len(L) > 12 else {}
        hand = "손글씨" in variant
        sg = seg_for(segs, t0, t1)
        my, mh = measure(cap, (t0 + t1) / 2, my0, my1, P.get("fill", "median"))
        y = ex.get("y") or my or (sg["yr"] if sg else None)
        fill = ex.get("fill_hex") or mh or (sg["hex"] if sg else None)
        sf = [e for e in sfx_ok if t0 - 0.1 <= e["t"] < t1]
        sfx = ({"kind": "기타", "t": sf[0]["t"], "basis": "파형 솟음",
                "note": f"5~10kHz 고립 솟음 +{sf[0]['db']}dB(유성 {sf[0]['voiced']}·고립 {sf[0]['isolated']}) — 귀 확인 못 함"} if sf else None)
        tr = ex.get("transition") or trans_at(cuts, t0)
        d = {"t0": t0, "t1": t1, "speaker": spk, "text": text, "layer": ex.get("layer", layer), "role": role,
             "enter": enter, "enter_ms": ex.get("enter_ms", 0), "variant": variant, "type_cps": None, "cursor": False,
             "y": y, "fill_hex": fill,
             "outline": ex.get("outline", P["hand_outline"] if hand else P["outline"]),
             "glow": None, "emph": emph, "sticker": sticker, "sfx": sfx, "scene": scene, "scene_desc": desc, "fit": fit,
             "cut_at": cuts_in(cuts, t0, t1), "font": HAND_FONT if hand else FONT,
             "letter_gap_px": P["letter_gap_px"], "line_gap_px": ex.get("line_gap_px"),
             "x": "가운데", "align": "center", "motion": ex.get("motion") or motion_at(shots, (t0 + t1) / 2), "transition": tr,
             "exit": ex.get("exit", "cut"),
             "confidence": "픽셀(시각·y·채움 hex·컷: capseg/cutdet 30fps)/눈(글·화자·역할·fit·스티커)/신호(motion·sfx)"}
        if ex.get("notes"):
            d["notes"] = ex["notes"]
        for k, v in ex.items():                           # 위 칸에 안 쓰인 ex 칸(box·size_px·emph 등)은 그대로 싣는다(썰풀다 mk.py 꼴)
            if k not in EX_USED:
                d[k] = v
        if ex.get("sfx_none"):
            d["sfx"] = None
            d.pop("sfx_none", None)
        lines.append(d)
    cap.release()
    doc = {"id": vid, "dur": round(_dur(mp4), 3), "fps": 30.0, "size": [1080, 1920], "title_lines": S.TITLE, "source_label": None,
           "layout": S.LAYOUT, "lines": lines, "no_caption": S.NO_CAP, "beats": S.BEATS, "narr_share": None,
           "notes": S.NOTES, "name_evidence": getattr(S, "NAME_EV", []), "frame0": S.FRAME0,
           "_made_by": getattr(S, "MADE_BY", P["made_by"]),
           "_tools": TOOLS_NOTE}
    if hasattr(S, "SOURCE_LABEL"):
        doc["source_label"] = S.SOURCE_LABEL
    if hasattr(S, "SOUND_MODE"):
        doc["sound_mode"] = S.SOUND_MODE
    for k, v in (getattr(S, "EXTRA", None) or {}).items():
        doc[k] = v
    nl = [l for l in lines if l["speaker"] == "나레"]
    doc["narr_share"] = f"나레 줄 {len(nl)}/{len(lines)}, 나레 {round(sum(l['t1'] - l['t0'] for l in nl), 1)}초/{doc['dur']}초"
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--work", help="capseg/cutdet 결과 폴더(seg_<id>.json·cut_<id>.json)")
    ap.add_argument("--seg")
    ap.add_argument("--cut")
    ap.add_argument("--mp4", required=True)
    ap.add_argument("--sfx-raw")
    ap.add_argument("--profile")
    A = ap.parse_args(argv)
    S = load_spec(A.spec)
    vid = S.ID
    if not (A.seg and A.cut) and not A.work:
        ap.error("--work 또는 --seg·--cut 이 필요하다")
    seg_p = A.seg or str(Path(A.work) / f"seg_{vid}.json")
    cut_p = A.cut or str(Path(A.work) / f"cut_{vid}.json")
    segs = json.load(open(seg_p))
    cd = json.load(open(cut_p))
    sfx_raw = json.load(open(A.sfx_raw, encoding="utf-8")) if A.sfx_raw else None
    if sfx_raw is not None and vid not in sfx_raw:
        print(f"경고: sfx_raw 에 {vid} 없음 — sfx 칸 전부 null", file=sys.stderr)
    doc = build_doc(S, segs, cd, A.mp4, sfx_raw, load_profile(A.profile))
    json.dump(doc, open(A.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lines = doc["lines"]
    print(A.out, len(lines), doc["narr_share"], "sfx", sum(1 for l in lines if l["sfx"]),
          "trans", {k: sum(1 for l in lines if l["transition"] == k) for k in set(l["transition"] for l in lines)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
