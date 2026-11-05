# -*- coding: utf-8 -*-
"""R7 편집 판단 칸 — 칼카피 엔진 v1 §3 (관제 319 · 묶음①). 판단 주인 = 이 파일 한 곳.

    짝 찾기     find_pair(info, longs)  — 쇼츠 ↔ 원본 롱폼. state = none | candidate | verified (Jev 해결 0.96·뿌리 0.74)
                  none      = 설명란 롱폼 링크 0 · 같은 채널 롱폼 제목 후보 0 (원본 추적 실패가 사실로 확정)
                  candidate = 후보 있음·미확정 — R7 짝 측정에 쓰지 않는다
                  verified  = 프레임 대조로 확정 — 이 판에는 만드는 곳이 없다(숏박스 시험 묶음에서)
    갈래 판정   branch_of(per)  — 갈래 판정은 이 함수 하나(규격 §9 B1·P2). 부르는 곳 = flow_bench.bm_tear_got(뜯기 끝) 한 곳
    쇼츠 자체 실측  measure(J, mp4)  — 짝이 없을 때 R7 칸을 벤치 쇼츠 자체 실측으로(Jev 해결 0.72·뿌리 0.57).
                  짝 대조로만 정해지는 칸(crop.mode = 원본 대비 x 차 · orig_caption.mode = 박힌 자막 vs 다시 얹음)은 null + '짝 없어 못 잼'
    같은 자       media(mp4, cut_at, win)  — 벤치·우리 시험 편 둘 다 이 함수로 재는 칸(crop 화면 상자 x · 끝 검정)만 대조 core
                  (Jev 해결 0.99·뿌리 0.57 — 같은 자가 없는 caption.size·title.lines 는 참고 칸)
    합치기       summarize(per)  — 편마다 값 → 프리셋 칸(r7.json summary). 저장은 preset_save.save_r7

확대는 1.0 고정(V0 0.93·0.80 — 원본 확대·반전은 회피 관행이라 엔진 기능으로 넣지 않는다).
seg(R1 구간)·signature·source_note 는 근거 Jev 가 채택 기준(conf≥0.6·fixroot≥0.5) 미달이라 이 판에 칸이 없다(보고 '보류').
"""
from __future__ import annotations

import re
import statistics

MADE_BY = "r7 v1 (칼카피 엔진 v1 §3 · 관제 319)"
ZOOM = 1.0
PAIR_STATES = ("none", "candidate", "verified")
BRANCH_BASE, BRANCH_CLIP = "기본", "짝없는클립형"
CROP_TOL_PX = 60          # §7-3 crop.x 중앙 ≤60px (1080 폭 기준)
END_TOL_S = 0.5           # §7-3 끝 길이 ±0.5초
BLACK_Y = 16              # 끝 검정 = 평균 밝기 16 아래(0~255)
END_LOOK_S = 3.0          # 끝 몇 초를 보나
END_STEP_S = 0.1
_LONG_LINK = re.compile(r"(?:youtube\.com/watch\?(?:[^ \n]*&)?v=|youtu\.be/|youtube\.com/live/)([0-9A-Za-z_-]{11})")
_SRC_WORD = re.compile(r"(출처|원본|원영상|source|credit)", re.I)
_TOKEN = re.compile(r"[0-9A-Za-z가-힣]{2,}")
_STOP = {"ㅋㅋ", "ㅋㅋㅋ", "레전드", "shorts", "쇼츠", "영상", "이번", "진짜", "그리고"}


# ---------------------------------------------------------------- 짝 찾기
def _tokens(s: str) -> set:
    return {t.lower() for t in _TOKEN.findall(s or "") if t.lower() not in _STOP}


def find_pair(info: dict, longs: list | None, longs_err: str | None = None) -> dict:
    """(판단 주인 · 짝) 벤치 쇼츠 한 편 → pair{state, how, url, cands, checked}. 프레임 대조는 하지 않는다(verified 를 만들지 않음).
    info = yt-dlp info.json(description·title·id) · longs = 같은 채널 롱폼 [{id, title}] (None = 못 읽음, longs_err 에 이유)."""
    vid = str(info.get("id") or "")
    desc = str(info.get("description") or "")
    links = [m for m in dict.fromkeys(_LONG_LINK.findall(desc)) if m != vid]
    tk = _tokens(str(info.get("title") or ""))
    title_c = []
    for L in longs or []:
        shared = tk & _tokens(str(L.get("title") or ""))
        if len(shared) >= 2 and L.get("id") and L["id"] != vid:
            title_c.append({"id": L["id"], "title": L.get("title"), "shared": sorted(shared)})
    cands = [{"id": x, "how": "설명란 링크"} for x in links] + [{**c, "how": "같은 채널 롱폼 제목"} for c in title_c]
    checked = {"desc_links": len(links), "desc_source_word": bool(_SRC_WORD.search(desc)),
               "channel_longs": None if longs is None else len(longs), "title_cands": len(title_c)}
    if longs_err:
        checked["longs_err"] = str(longs_err)[:160]
    first = cands[0] if cands else None
    return {"state": "candidate" if cands else "none", "how": first["how"] if first else None,
            "url": f"https://www.youtube.com/watch?v={first['id']}" if first else None, "cands": cands[:5], "checked": checked,
            "verified_by": None, "method": "설명란 롱폼 링크 + 같은 채널 롱폼 제목 낱말 2개 이상 겹침(프레임 대조 없음 — 확정 아님)"}


def branch_of(per: dict) -> dict:
    """(판단 주인 · 갈래) 편마다 pair.state → 채널 갈래. 쓰는 편 전부가 verified 면 기본 길, 아니면 짝 없는 클립형(쇼츠 자체 실측).
    pair 가 없는 편(뜯기 실패 등)은 none 으로 센다 — 빠진 편은 missing 에 그대로 남긴다(조용히 넘어가지 않음)."""
    states, missing = {}, []
    for vid, r in (per or {}).items():
        s = ((r or {}).get("pair") or {}).get("state")
        if s not in PAIR_STATES:
            missing.append(vid)
            s = "none"
        states[vid] = s
    base = bool(states) and all(s == "verified" for s in states.values())
    n = {k: sum(v == k for v in states.values()) for k in PAIR_STATES}
    why = ("쓰는 편 전부 짝 확정(프레임 대조)" if base else
           f"짝 확정 편 {n['verified']}/{len(states)} — 확정 안 된 짝(후보 {n['candidate']}·없음 {n['none']})은 R7 짝 측정에 안 쓴다 → 쇼츠 자체 실측")
    return {"branch": BRANCH_BASE if base else BRANCH_CLIP, "why": why, "pairs": states, "missing": missing, "made_by": MADE_BY}


# ---------------------------------------------------------------- 같은 자(벤치·우리 둘 다)
def _bg_of(img, win_s) -> list:
    import numpy as np
    H = img.shape[0]
    if win_s:
        mask = np.ones(H, bool)
        mask[max(0, win_s[1]):min(H, win_s[1] + win_s[3])] = False
        if mask.any():
            return [int(v) for v in np.median(img[mask].reshape(-1, 3), axis=0)]
    return [0, 0, 0]


def media(mp4: str, cut_at: list | None, win: list | None = None) -> dict:
    """(같은 자 — 벤치 원본·우리 완성본 둘 다 이 함수로) 컷 가운데 프레임의 화면 상자 x 가운데 차(1080 폭 기준, 화면 가운데 0) + 끝 검정 길이.
    컷 시각은 부르는 쪽이 준다(벤치 = 뜯기 cuts.times, 우리 = kal_analyze.media_of cut_at — 같은 컷 자 bench.cuts)."""
    from shopping_shorts.channelkit.bench import layout, probe
    meta = probe.info(mp4)
    W, H, dur = int(meta["width"]), int(meta["height"]), float(meta.get("duration") or 0)
    gw, gh = 360, int(round(360 * H / W))
    s = W / gw
    win_s = [int(round(v / s)) for v in win] if win else None
    bounds = [0.0] + sorted(float(t) for t in cut_at or [] if 0 < float(t) < dur) + [dur]
    offs = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < 0.15:
            continue
        img = probe.grab(mp4, (a + b) / 2, f"scale={gw}:{gh}", gw, gh)
        if img is None:
            continue
        box = layout.picture_box(img, _bg_of(img, win_s), win_s)
        if box:
            offs.append(round(((box[0] + box[2] / 2) * s - W / 2) * 1080 / W, 1))
    lum = []
    t = dur - 0.05
    while t > dur - END_LOOK_S and t > 0:
        g = probe.grab(mp4, t, "scale=32:56", 32, 56, pix="gray")
        lum.append(None if g is None else float(g.mean()))
        t -= END_STEP_S
    black = 0
    for v in lum:
        if v is None or v >= BLACK_Y:
            break
        black += 1
    black_s = round(black * END_STEP_S, 2)
    last_shot = round(dur - bounds[-2], 2) if len(bounds) > 2 else round(dur, 2)
    med = round(statistics.median(offs), 1) if offs else None
    return {"crop": {"x_off": offs, "x_off_med": med, "abs_med": round(statistics.median(abs(x) for x in offs), 1) if offs else None,
                     "in60_share": round(sum(abs(x) <= CROP_TOL_PX for x in offs) / len(offs), 3) if offs else None, "n": len(offs)},
            "end": {"sec": black_s, "kind": "black" if black_s >= 0.2 else "none", "last_shot": last_shot},
            "dur": round(dur, 2), "method": "bench.layout.picture_box(컷 가운데 프레임, 360폭) + 끝 3초 0.1초 간격 평균 밝기<16"}


# ---------------------------------------------------------------- 쇼츠 자체 실측(벤치 뜯기 → 칸)
def _med(xs):
    xs = [float(x) for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 2) if xs else None


def from_tear(J: dict) -> dict:
    """뜯기.json(analyze)에서 바로 읽는 칸 — 자막 글자 높이·자리, 제목 줄·글자 수, 꾸밈 종류. 판독이 실패한 칸은 null + failed(통과 아님)."""
    H = float(((J.get("probe") or {}).get("h")) or 1920)
    L, C = J.get("layout") or {}, J.get("captions") or {}
    gl = [g.get("line_h") for g in C.get("glyph") or [] if isinstance(g, dict)]
    size = _med(gl)
    cap = {"mode": None, "why": "짝 없어 박힌 자막 vs 다시 얹음을 못 가름", "size_px": round(size * 1920 / H, 1) if size else None,
           "pos": L.get("caption_pos"), "band": L.get("caption_band"), "core": False,
           **({} if size else {"failed": "자막 글자 높이(captions.glyph) 없음"})}
    tb = ((J.get("fonts") or {}).get("title_bands") or {})
    bands = [b for b in tb.get("bands") or [] if isinstance(b, dict) and b.get("role") == "title"]
    texts = [" ".join(b.get("text") or []) if isinstance(b.get("text"), list) else str(b.get("text") or "") for b in bands]
    texts = [t for t in texts if t.strip()]
    title = {"lines": len(texts), "chars": sum(len(t.replace(" ", "")) for t in texts), "core": False}
    if not texts:
        title = {"lines": None, "chars": None, "core": False, "failed": tb.get("failed") or "제목 띠 글자 없음"}
    o = J.get("overlay_rules") or {}
    deco = sorted((o.get("kind_share") or {}).keys()) if o.get("ok") else None
    return {"orig_caption": cap, "title": title, "deco_kinds": deco, **({} if deco is not None else {"deco_failed": o.get("failed") or "꾸밈 판독 없음"}),
            "window": L.get("window"), "cut_at": list(((J.get("cuts") or {}).get("times")) or [])}


def measure(J: dict, mp4: str, pair: dict) -> dict:
    """벤치 한 편 R7 칸(쇼츠 자체 실측). 짝 확정(verified)이 없으므로 crop.mode·orig_caption.mode 는 null — 값은 분포로만."""
    T = from_tear(J)
    M = media(mp4, T["cut_at"], T["window"])
    crop = {"mode": None, "zoom": ZOOM, "why": "짝 없어 원본 대비 x 차를 못 잼 — 쇼츠 화면 상자 분포만", **M["crop"]}
    return {"pair": pair, "crop": crop, "orig_caption": T["orig_caption"], "title": T["title"], "end": M["end"],
            "deco_kinds": T["deco_kinds"], **({"deco_failed": T["deco_failed"]} if "deco_failed" in T else {}),
            "window": T["window"], "src": "쇼츠 자체 실측(짝 없음)", "made_by": MADE_BY, "media_method": M["method"]}


def _mode(xs):
    xs = [x for x in xs if x is not None]
    return max(set(xs), key=xs.count) if xs else None


def summarize(per: dict) -> dict:
    """(판단 주인 · 합치기) 편마다 R7 칸 → 프리셋 칸. 숫자 = 편 중앙값, 종류 = 최빈, 꾸밈 = 합집합. 편 수가 3 미만이면 confidence low."""
    rows = [r for r in (per or {}).values() if isinstance(r, dict)]
    g = lambda *ks: [_dig(r, ks) for r in rows]
    deco = sorted({k for r in rows for k in (r.get("deco_kinds") or [])})
    return {"n": len(rows), "confidence": "low" if len(rows) < 3 else "ok", "src": "쇼츠 자체 실측(짝 없음)",
            "crop": {"mode": None, "zoom": ZOOM, "x_off_med": _med(g("crop", "x_off_med")), "abs_med": _med(g("crop", "abs_med")),
                     "in60_share": _med(g("crop", "in60_share")), "core": True, "why": "짝 없어 원본 대비 x 차 대신 쇼츠 화면 상자 분포"},
            "orig_caption": {"mode": None, "size_px": _med(g("orig_caption", "size_px")), "pos": _mode(g("orig_caption", "pos")), "core": False},
            "title": {"lines": _mode(g("title", "lines")), "chars": [min(c), max(c)] if (c := [x for x in g("title", "chars") if x is not None]) else None, "core": False},
            "end": {"sec": _med(g("end", "sec")), "kind": _mode(g("end", "kind")), "last_shot": _med(g("end", "last_shot")), "core": True},
            "deco_kinds": deco if any(r.get("deco_kinds") is not None for r in rows) else None,
            "made_by": MADE_BY}


def _dig(d, ks):
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return d
