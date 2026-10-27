# -*- coding: utf-8 -*-
"""④ 컷 계획 — 판단 주인: plan(B, T, S, W, narr=None) (관제 097, 2026-10-17).

정본(channel/yanshottem/장윤정_덴마크수건/build_plan.py)과 같은 꼴의 대본.json·재료.json·frame.json 을 쓴다.
블록 차례 = 원음 O1 → N1 → 원음 O2… → N2(끝) (만템: 원음 시작·나레 끝).
컷 판단(전부 여기 한 곳):
  · 원음 블록 = 그 말을 하는 본인 화면(소리와 같은 원본 시각, 원본 자체 컷 경계에서 나눔) — 크롭은 원본 장면마다 하나(점프 줌 0).
  · 원음 화면이 쓸 수 없으면(남의 신체 근접 A13 · 크롭 안 글자 A5 · 사람 없음) 그 조각만 제품/본인 B롤로 바꾸고 소리는 원음 그대로.
  · 나레 블록 = 본인+제품 → 제품 → 본인 순 B롤. 같은 원본 ±3초 재사용 0(B13), 같은 장면 앞 컷보다 앞 시각 0(되감김),
    한 컷 끼움(A-B-A) 0(B16), 컷 길이 ≥ 벤치 컷 중앙(B4 '빠르면 반려'), 마지막 블록 컷 ≥1.2초·끝 컷 ≥1.5초.
  · 장면 판독(누가·제품·글자 자리·주피사체 가로 위치)은 무료 제미나이 1회(원본 프레임 + 벤치 주인공 참고 1장).
narr = {"N1": [a,b], "N2": [a,b]} TTS 실측 말 구간(⑤ make 가 넘김) — 없으면 8.4자/초 추정.
"""
from __future__ import annotations

import io
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from tools.calcopy.yanshot.common import GEM_MODELS, ROOT, StageError, jload, jsave, norm, run, vtt_words

CPS = 8.4
NARR_PAD = {"N1": 0.12, "N2": 0.45}        # 정본 장윤정: N1 끝 쉼 · N2 끝 여유(끝 컷 ≥1.5초)
CROP = 870                                 # 정본 크롭 한 변(1080 원본 위쪽, 아래 자막 띠 y≥865 밖) — 확대 1.24배
CROP_MIN = 700                             # 글자를 피하려 줄일 때 하한(확대 ≤1.55배, A4 ≤2.3)
REUSE_GAP = 3.0                            # B13
SCENE_T = 0.30
FRAME = ROOT / "channel/mantem/frame_얜샷템.json"
LAST_MIN, END_MIN = 1.2, 1.5               # B4: 마지막 묶음 컷 ≥1.2초, 끝 컷 ≥1.5초
MAX_CANDS = 44
SAME_SETUP_S = 20.0                        # 이웃 B롤 원본 시각 최소 간격(같은 촬영 자리 = 안 보이는 컷)
ZOOM_ALT = 0.78                            # 이웃 본인 컷 확대 크롭 비율(1.28배)
VERIFY_ROUNDS = 8                          # 크롭 검사 → 걸린 장면 빼고 다시 고르기 최대 횟수(자막 많은 원본 = 정재형 편 4회로 모자람)
SHORT_S = 0.6                              # 이보다 짧은 원음 조각은 앞 컷 화면을 이어 쓴다(0.3초 깜빡 컷 금지)


# ── 원본 장면(컷) 경계 ─────────────────────────────────────────────
def scene_cuts(mp4, a: float, b: float) -> list[float]:
    e = run(["ffmpeg", "-hide_banner", "-ss", f"{max(0, a):.2f}", "-t", f"{b - max(0, a):.2f}", "-i", str(mp4), "-an", "-vf",
             f"scale=320:-2,select='gt(scene,{SCENE_T})',showinfo", "-f", "null", "-"], check=False).stderr
    return sorted(round(max(0, a) + float(x), 3) for x in re.findall(r"pts_time:([\d.]+)", e))


def windows(T: dict, B: dict, src_dur: float) -> list[tuple[float, float]]:
    """B롤 찾을 원본 창 — 원음 블록 ±60초 + 제품 낱말이 나온 자리 ±15초(합쳐서)."""
    ws = [(o["spans"][0][0] - 60, o["spans"][-1][1] + 60) for o in T["orig"]]
    kws = [norm(k) for k in (B.get("keywords") or []) + [B.get("product") or ""] if norm(k)]
    for t, w in vtt_words(T["source"]["vtt"]):
        if any(k in norm(w) for k in kws):
            ws.append((t - 15, t + 15))
    ws = sorted((max(0, a), min(src_dur, b)) for a, b in ws)
    out = []
    for a, b in ws:
        if out and a <= out[-1][1] + 2:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def shots_in(mp4, wins) -> list[tuple[float, float]]:
    out = []
    for a, b in wins:
        c = [a] + scene_cuts(mp4, a, b) + [b]
        out += [(round(x, 3), round(y, 3)) for x, y in zip(c, c[1:]) if y - x >= 0.3]
    return out


# ── 장면 판독(제미나이 1회) ─────────────────────────────────────────
def frame_jpg(mp4, t: float, w: int = 384, crop=None) -> bytes:
    vf = (f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}," if crop else "") + f"scale={w}:-2"
    return subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", vf,
                           "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True).stdout


LOOK_PROMPT = """R1~R4 는 이 원본을 다시 편집한 경쟁 쇼츠 화면이다 — 그중 가장 자주·크게 나오는 사람이 주인공 연예인({person})이다(옷·머리·얼굴로 알아봐라, 이하 R). P 는 경쟁 쇼츠에 나온 제품({product}) 예시다.
그 뒤 #번호 그림들은 같은 원본 영상의 프레임이다. 그림마다 판독해라:
- who: 화면의 주 인물 — "main"(R 과 같은 사람) · "other"(R 이 아닌 사람만) · "both"(R 과 다른 사람 함께) · "none"(사람 없음)
- product: P 와 같은 제품({product})이 또렷이 보일 때만 true. 다른 물건(음식·병·옷·가방 등)은 false
- other_body_close: 얼굴 없이 R 이 아닌 사람의 손·팔·다리 같은 신체 일부만 화면 1/4 이상 크게 잡혔을 때만 true(두 사람이 함께 서 있는 화면은 false)
- cx: R 이 보이면 R 얼굴의 가로 위치, R 이 없으면 제품, 둘 다 없으면 주피사체의 가로 위치(0~1)
- text: 영상 위에 덧씌운 글자·자막·로고·워터마크마다 [x0,y0,x1,y1](0~1, 왼쪽 위 기준). 없으면 []
- ok: 흐림·전환 중·검정이면 false
- desc: 한국어 10자 안팎 설명(예 '돋보기 걸어 보임')
JSON만: {{"items":[{{"i":0,"who":"main","product":false,"other_body_close":false,"cx":0.5,"text":[],"ok":true,"desc":""}}]}}"""


def look(mp4, ref_jpg: list, frames: list[tuple[int, float]], B: dict, ask=None, prod_jpg: bytes | None = None) -> dict:
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as ask_
        ask = ask_
    parts = [x for k, r in enumerate(ref_jpg) for x in (f"R{k + 1}:", r)] + (["P:", prod_jpg] if prod_jpg else [])
    for i, t in frames:
        parts += [f"#{i}", frame_jpg(mp4, t)]
    d, why = ask(parts, LOOK_PROMPT.format(person=B.get("person"), product=B.get("product")), tag="yanshot_plan_look", models=GEM_MODELS)
    if d is None:
        raise StageError(f"장면 판독 실패: {why}")
    out = {"_model": d.get("_model")}
    for r in d.get("items") or []:
        try:
            out[int(str(r.get("i")).lstrip("#"))] = r
        except (ValueError, TypeError, AttributeError):
            continue                      # 참고 그림 R 등
    miss = [i for i, _ in frames if i not in out]
    if len(miss) > len(frames) // 3:
        raise StageError(f"장면 판독이 {len(miss)}/{len(frames)}장 빠짐")
    return out


def cut_out(shots, holes) -> list[tuple[float, float]]:
    """장면들에서 원음 싱크 구간을 도려낸 나머지(앞뒤 조각 — '이렇게 보는 거야'처럼 원음 바로 뒤 제품 장면을 살린다)."""
    out = []
    for a, b in shots:
        segs = [(a, b)]
        for x, y in holes:
            nxt = []
            for p, q in segs:
                if y <= p or x >= q:
                    nxt.append((p, q)); continue
                if x > p:
                    nxt.append((p, x))
                if y < q:
                    nxt.append((y, q))
            segs = nxt
        out += [(round(p, 3), round(q, 3)) for p, q in segs]
    return out


def bench_gaps(T: dict, dur: float) -> list[tuple[float, float]]:
    """벤치에서 지문이 안 맞은 구간(= 벤치 채널 나레 자리)."""
    segs = sorted((g["b0"], g["b1"]) for g in T["fingerprint"])
    out, t = [], 0.0
    for a, b in segs:
        if a - t > 0.3:
            out.append((t, a))
        t = max(t, b)
    if dur - t > 0.3:
        out.append((t, dur))
    return out


CROP_CAP = {"s": CROP}      # 이 편 크롭 한 변 상한 — plan() 이 원본 아래 자막 띠 위쪽으로 정한다(subtitle_cap)


def subtitle_cap(info: dict, H: int = 1080) -> int:
    """(판단 주인) 원본 아래 자막 띠 맨 위 → 크롭 한 변 상한. 판독 글자 상자 중 화면 아래쪽(y0≥0.6) 것들의 하위 10% y0 − 14px.
    10-17 정재형 원본: 큰 자막이 y0 0.72~0.78 — 870 크롭이면 '후기다되니까' 윗부분이 크롭 아래 끝에 걸렸다."""
    ys = sorted(b[1] for v in info.values() if isinstance(v, dict) for b in (v.get("text") or [])
                if isinstance(b, (list, tuple)) and len(b) == 4 and b[1] >= 0.6)
    if len(ys) < 3:
        return CROP
    return int(max(CROP_MIN, min(CROP, ys[len(ys) // 10] * H - 14)))


def crop_for(info: dict, W: int = 1920, H: int = 1080) -> list[int] | None:
    """(판단 주인) 판독 → 정사각 크롭 [x,y,s,s] — 위쪽에 붙이고(y=0) 주피사체 가운데, 덧씌운 글자는 피한다. 못 피하면 None."""
    boxes = [b for b in (info.get("text") or []) if isinstance(b, (list, tuple)) and len(b) == 4]
    cx = float(info.get("cx") if isinstance(info.get("cx"), (int, float)) else 0.5) * W
    top = CROP_CAP["s"]
    for s in list(range(top, CROP_MIN - 1, -34)):
        for dx in (0, -120, 120, -240, 240, -360, 360):
            x = int(min(max(0, cx - s / 2 + dx), W - s))
            hit = False
            for x0, y0, x1, y1 in boxes:
                bx0, by0, bx1, by1 = x0 * W - 12, y0 * H - 12, x1 * W + 12, y1 * H + 12
                if bx1 > x and bx0 < x + s and by1 > 0 and by0 < s:
                    hit = True; break
            if not hit:
                return [x, 0, s, s]
    # 판독 글자 상자가 크롭을 못 피하면(상자 좌표가 틀릴 때도 있다) 기본 크롭 — 실제 잘린 화면은 verify_crops 가 다시 본다
    return [int(min(max(0, cx - top / 2), W - top)), 0, top, top]


# ── 블록·컷 ──────────────────────────────────────────────────────
def blocks_of(T: dict, S: dict, narr: dict | None) -> tuple[list[dict], float]:
    O = T["orig"]
    order = [O[0]["id"], "N1"] + [o["id"] for o in O[1:]] + ["N2"]
    L = {l["id"]: l for l in S["lines"]}
    out, t = [], 0.0
    for bid in order:
        if bid.startswith("O"):
            o = next(x for x in O if x["id"] == bid)
            d = round(sum(b - a for a, b in o["spans"]), 3)
            out.append({"id": bid, "kind": "원음", "t": [round(t, 3), round(t + d, 3)], "spans": o["spans"], "orig": o})
        else:
            talk = (narr[bid][1] - narr[bid][0]) if narr else L[bid]["chars"] / CPS
            d = round(talk + NARR_PAD[bid], 3)
            out.append({"id": bid, "kind": "나레", "t": [round(t, 3), round(t + d, 3)], "talk": round(talk, 3), "line": L[bid]})
        t += d
    return out, round(t, 3)


def orig_at(spans, rel: float) -> float:
    acc = 0.0
    for s, e in spans:
        if rel < acc + (e - s) - 1e-6:
            return round(s + rel - acc, 3)
        acc += e - s
    return round(spans[-1][1], 3)


def _overlap(a, b, gap=REUSE_GAP):
    return a[0] < b[1] + gap and b[0] < a[1] + gap


def _score(x: dict) -> float:
    """B롤 점수 — 본인+제품 4 · 제품 3 · 본인 2 · 그 밖 0(다른 사람만 = 쓰지 않음)."""
    main = x.get("who") in ("main", "both")
    if x.get("product") and main:
        return 4
    if x.get("product"):
        return 3
    return 2 if main else 0


def _assign(blocks, sync, cands, info, Lc, banned: set) -> list[dict]:
    """(판단 주인) 블록 → 컷. banned = 크롭 검사에서 걸린 원본 장면 시작 초(다시 안 고른다)."""
    used: list[tuple[float, float]] = [(x, y) for x, y, _ in sync]     # 원음 싱크 자리는 처음부터 잡아 둔다(B13 — 나레 B롤이 먼저 와도)
    cuts: list[dict] = []

    def ok_sync(k):
        x = info.get(str(k)) or {}
        if round(sync[k][0], 2) in banned:
            return None, "크롭 검사에서 걸림(A5)"
        if not x.get("ok", True) or x.get("other_body_close") or x.get("who") == "none":
            return None, "판독: " + ("흐림" if not x.get("ok", True) else "남의 신체 근접(A13)" if x.get("other_body_close") else "사람 없음")
        return crop_for(x), ""

    def pick(need: float, cont_from, prev_ss=None):
        """같은 촬영 자리 피하기로 못 고르면 그 조건만 풀고 한 번 더(확대 번갈이 vary_zoom 이 컷을 보이게 한다)."""
        return pick1(need, cont_from, prev_ss) or (pick1(need, cont_from, None) if prev_ss is not None else None)

    def pick1(need: float, cont_from, prev_ss=None):
        """B롤 한 컷 — 점수 높은 순. 같은 원본 ±3초 재사용 0, 단 바로 앞 컷 끝에서 앞으로 3.5초 안 이어짐은 허용(정본 B13 '앞으로 이어짐')."""
        best = None
        for i, sc_ in enumerate(cands):
            x = info.get(str(100 + i)) or {}
            if round(sc_[0], 2) in banned or not x.get("ok", True) or x.get("other_body_close") or _score(x) == 0:
                continue
            cont = cont_from is not None and cont_from - 0.05 <= sc_[0] <= cont_from + 3.5
            lo0 = (max(sc_[0], cont_from) + 0.05) if cont else sc_[0] + 0.15
            seg = None
            lo = lo0
            while sc_[1] - lo >= need + 0.1:     # 긴 장면은 앞에서부터 1초씩 밀며 빈 자리를 찾는다(장면 하나에서 ±3초 떨어진 컷 여럿)
                cand = (round(lo, 3), round(lo + need, 3))
                clash = [u for u in used if _overlap(cand, u)]
                if not clash or (cont and lo == lo0 and all(u[1] <= cand[0] + 0.05 and abs(u[1] - cont_from) < 0.05 for u in clash)):
                    seg = cand
                    break
                if cont:
                    break
                lo += 1.0
            if seg is None:
                continue
            if prev_ss is not None and not cont and abs(seg[0] - prev_ss) < SAME_SETUP_S:
                continue                     # 바로 앞 B롤과 같은 촬영 자리(20초 안) — 화면이 거의 같아 컷으로 안 보인다(정재형 편 B4 1.54배 실측)
            sc = _score(x) * 10 + (6 if cont else 0) - (min(5, abs(lo - cont_from) / 30) if cont_from is not None else 0)
            if best is None or sc > best[0]:
                best = (sc, i, seg, x)
        if not best:
            return None
        _, i, seg, x = best
        used.append(seg)
        return {"ss": seg[0], "crop": crop_for(x), "desc": x.get("desc", ""), "who": x.get("who"), "product": bool(x.get("product")),
                "scene0": cands[i][0], "scene1": cands[i][1]}

    nb = len(blocks)
    for bi, b in enumerate(blocks):
        a0, a1 = b["t"]
        last = bi == nb - 1
        if b["kind"] == "원음":
            for k, (s0, s1, bid) in enumerate(sync):
                if bid != b["id"]:
                    continue
                d = round(s1 - s0, 3)
                c, why = ok_sync(k)
                x = info.get(str(k)) or {}
                prev = cuts[-1] if cuts else None
                near = [q for q in cuts if q.get("sync") and q["block"] != b["id"] and abs(q["ss"] - s0) < SAME_SETUP_S]
                if c and near:                   # 다른 원음 블록의 본인 화면과 같은 촬영 자리(20초 안) — B13 재사용·안 보이는 컷 → B롤로
                    c, why = None, f"다른 원음 블록 화면(원본 {near[0]['ss']:.1f})과 같은 자리(B13)"
                if prev is not None and prev["block"] == b["id"] and (d < SHORT_S or (d < 0.8 and k > 0 and sync[k - 1][1] < s0 - 0.05))                         and prev["ss"] + prev["dur"] + d <= prev.get("scene1", 1e9) + 0.01 and (c or not prev.get("sync")):
                    # 쉼을 잘라 낸 자리 뒤 짧은 조각 — 화면은 앞 컷을 그대로 이어 보인다(컷 안 생김), 소리만 원음 다음 조각
                    cuts.append({"block": b["id"], "dur": d, "ss": round(prev["ss"] + prev["dur"], 3), "audio_ss": s0, "crop": prev["crop"],
                                 "desc": prev["desc"], "who": prev["who"], "why": "쉼 잘린 뒤 짧은 원음 조각 — 화면은 앞 컷 그대로 이어짐", "sync": prev.get("sync"),
                                 "scene0": prev["scene0"], "scene1": prev.get("scene1"), "join": True})
                    used.append((prev["ss"] + prev["dur"], prev["ss"] + prev["dur"] + d))
                    used.append((s0, s1))
                    continue
                if c:
                    cuts.append({"block": b["id"], "dur": d, "ss": s0, "audio_ss": s0, "crop": c, "desc": x.get("desc", ""), "who": x.get("who"),
                                 "why": "원음 싱크(본인 화면)", "sync": True, "scene0": s0, "scene1": s1 if k + 1 < len(sync) and sync[k + 1][0] != s1 else s1 + 1.0})
                    used.append((s0, s1))
                else:
                    n = max(1, int(round(d / Lc)))          # 긴 대체는 컷 길이만큼 나눠 B롤 여러 장(4초 한 컷 금지 — B4)
                    ds = [round(d / n, 3)] * n
                    ds[-1] = round(d - sum(ds[:-1]), 3)
                    off = 0.0
                    for dd in ds:
                        pv = cuts[-1] if cuts else None
                        br = pick(dd, None, pv["ss"] if pv else None)
                        if not br:
                            raise StageError(f"{b['id']} 원음 {s0}~{s1} 화면을 못 씀({why}) + 대신할 B롤 없음")
                        cuts.append({"block": b["id"], "dur": dd, "ss": br["ss"], "audio_ss": round(s0 + off, 3), "crop": br["crop"], "desc": br["desc"],
                                     "who": br["who"], "why": f"원음 화면 대체 — {why}(소리는 원음)", "scene0": br["scene0"], "scene1": br["scene1"]})
                        off += dd
        else:
            dur = a1 - a0
            lc = max(Lc, LAST_MIN) if last else Lc
            n = max(1, int(round(dur / lc)))
            if last and n > 1 and dur / n < END_MIN:
                n = max(1, int((dur - END_MIN) // lc) + 1)
            ds = [round(dur / n, 3)] * n
            ds[-1] = round(dur - sum(ds[:-1]), 3)
            for d in ds:
                prev = cuts[-1] if cuts else None
                # 앞으로 이어짐은 원음 컷 바로 뒤에서만(B롤끼리 이어 붙이면 같은 촬영 자리라 컷이 안 보인다 — 정재형 편 B4 1.75배 실측)
                br = pick(d, (prev["ss"] + prev["dur"]) if prev and not prev.get("mute") else None, prev["ss"] if prev else None)
                if not br:
                    raise StageError(f"{b['id']} 나레 B롤 후보가 모자람(필요 {d:.2f}초)")
                kind = "본인+제품" if br["product"] and br["who"] in ("main", "both") else "제품" if br["product"] else "본인"
                cuts.append({"block": b["id"], "dur": d, "ss": br["ss"], "crop": br["crop"], "desc": br["desc"], "who": br["who"],
                             "why": f"나레 '{b['line']['text'][:16]}…' — {kind} B롤", "mute": True, "scene0": br["scene0"]})
    vary_zoom(cuts)
    t = 0.0
    for i, c in enumerate(cuts):
        c["i"] = i
        c["t_final"] = [round(t, 3), round(t + c["dur"], 3)]
        t += c["dur"]
    return cuts


def vary_zoom(cuts: list[dict]):
    """(판단 주인) 이웃 컷이 둘 다 본인 화면이고 원본에서 이어지지 않으면 하나 걸러 확대(×ZOOM_ALT) — 같은 촬영 자리(앉아서 말하는 원본)는
    장면이 바뀌어도 그림이 거의 같아 컷으로 안 보인다(정재형 편 B4 1.8 vs 벤치 0.93, 만템도 확대 1.32~1.60 실측). 이어지는 컷·join 은 안 건드린다."""
    flip = False
    for a, b in zip(cuts, cuts[1:]):
        if b.get("join") or abs(a["ss"] + a["dur"] - b["ss"]) < 0.05:
            continue
        if a.get("who") in ("main", "both") and b.get("who") in ("main", "both") and abs(a["crop"][2] - b["crop"][2]) < 0.1 * a["crop"][2]:
            flip = not flip
            if flip:
                x, y, s, _ = b["crop"]
                s2 = int(s * ZOOM_ALT)
                b["crop"] = [int(x + (s - s2) / 2), 0, s2, s2]
                b["why"] = b.get("why", "") + f" · 확대 {s / s2:.2f}배(이웃 컷과 같은 자리)"
        else:
            flip = False


VERIFY_PROMPT = """R1~R4 는 경쟁 쇼츠 화면이다 — 가장 자주 나오는 사람이 주인공({person}, 이하 R). P 는 제품({product}) 예시다.
아래 #번호 그림은 우리 쇼츠에 그대로 쓸 화면(정사각 크롭)이다. 그림마다:
- text: 영상 위에 덧씌운 글자·자막·로고·워터마크·말풍선·스티커·이모지·불꽃 같은 편집 그래픽이 조금이라도 보이면 true(옷·물건에 원래 인쇄된 글자는 false)
- main: R 의 얼굴 또는 몸이 화면에 또렷이 보이면 true
- product: P 와 같은 제품이 보이면 true
- desc: 한국어 10자 안팎
JSON만: {{"items":[{{"i":0,"text":false,"main":true,"product":false,"desc":""}}]}}"""


def _vkey(c: dict) -> str:
    return f"{c['ss']:.2f}|{c['dur']:.2f}|{c['crop']}"


def verify_crops(mp4, cuts: list[dict], B: dict, refs: list, prod: bytes | None, ask=None, cache: dict | None = None) -> dict:
    """(판단 주인) 고른 크롭을 실제로 잘라 덧씌운 글자(A5)를 다시 본다 — 컷마다 시작·끝 2장, 제미나이 1회."""
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as ask_
        ask = ask_
    parts, idx = [x for k, r in enumerate(refs) for x in (f"R{k + 1}:", r)] + (["P:", prod] if prod else []), []
    cache = {} if cache is None else cache
    bad = {c["i"]: cache[_vkey(c)] for c in cuts if not c.get("join") and cache.get(_vkey(c))}
    for c in cuts:
        if c.get("join") or _vkey(c) in cache:          # 이미 본 컷(같은 원본 시각·크롭)은 다시 안 묻는다
            continue
        for t in (c["ss"] + 0.08, c["ss"] + c["dur"] / 2, c["ss"] + c["dur"] - 0.08):    # 시작·가운데·끝(자막은 컷 안에서도 바뀐다)
            parts += [f"#{len(idx)}", frame_jpg(mp4, t, w=256, crop=c["crop"])]
            idx.append(c["i"])
    if not idx:
        return {"bad": bad, "model": "cache"}
    d, why = ask(parts, VERIFY_PROMPT.format(person=B.get("person"), product=B.get("product")), tag="yanshot_plan_verify", models=GEM_MODELS)
    if d is None:
        raise StageError(f"크롭 검사 실패: {why}")
    for c in cuts:
        if c["i"] in idx:
            cache[_vkey(c)] = ""
    for r in d.get("items") or []:
        try:
            n = int(str(r.get("i")).lstrip("#"))
        except (ValueError, TypeError):
            continue
        if 0 <= n < len(idx) and (r.get("text") or not (r.get("main") or r.get("product"))):
            bad[idx[n]] = ("덧씌운 글자 " if r.get("text") else "주인공·제품 안 보임 ") + r.get("desc", "")
            cache[_vkey(cuts[idx[n]])] = bad[idx[n]]
    return {"bad": bad, "model": d.get("_model")}


def visual_cuts(cuts: list[dict]) -> list[float]:
    """화면이 이어지는 조각(join)은 한 컷으로 센 컷 길이들."""
    out = []
    for c in cuts:
        if c.get("join") and out:
            out[-1] += c["dur"]
        else:
            out.append(c["dur"])
    return out


def plan(B: dict, T: dict, S: dict, W: Path, narr: dict | None = None, ask=None, log=print, sheet_out=True) -> dict:
    """(판단 주인) 컷 계획 → W/plan.json + 대본.json·재료.json·frame.json·계획.md·계획_시트.jpg (W/doc)."""
    W = Path(W)
    doc = W / "doc"
    (doc / "plan").mkdir(parents=True, exist_ok=True)
    mp4 = T["source"]["mp4"]
    from tools.calcopy.yanshot.common import dur_of
    src_dur = dur_of(mp4)
    blocks, total = blocks_of(T, S, narr)
    Lc = max(1.0, min(1.9, ((B.get("measure") or {}).get("shot_median") or 1.2) * 1.05))   # 목표 컷 길이(벤치 중앙보다 약간 느리게)
    cache = W / "look.json"
    if cache.exists():
        LK = jload(cache)
    else:
        sync = []
        for b in blocks:
            if b["kind"] != "원음":
                continue
            for a_, e_ in b["spans"]:
                c = [a_] + [x for x in scene_cuts(mp4, a_, e_) if a_ + 0.15 < x < e_ - 0.15] + [e_]
                sync += [[round(x, 3), round(y, 3), b["id"]] for x, y in zip(c, c[1:])]
        cands = [s for s in cut_out(shots_in(mp4, windows(T, B, src_dur)), [(x, y) for x, y, _ in sync]) if s[1] - s[0] >= 1.0]
        kt = [t for t, w in vtt_words(T["source"]["vtt"]) if any(norm(k) in norm(w) for k in (B.get("keywords") or []) if norm(k))]
        cands.sort(key=lambda s: min([abs((s[0] + s[1]) / 2 - t) for t in kt] or [0]))
        cands = sorted(cands[:MAX_CANDS])
        fr = [(i, (s[0] + s[1]) / 2) for i, s in enumerate(sync)] + [(100 + i, (s[0] + s[1]) / 2) for i, s in enumerate(cands)]
        fp = max(T["fingerprint"], key=lambda g: g["b1"] - g["b0"])
        win = (B.get("measure") or {}).get("window") or [0, 420, 1080, 1080]
        ref = [frame_jpg(B["mp4"], B["dur"] * f, crop=win) for f in (0.25, 0.42, 0.6, 0.85)]     # 주인공 = 벤치에 가장 자주 나오는 사람
        nar = [g for g in bench_gaps(T, B["dur"]) if g[1] - g[0] >= 0.8] or [(0.0, 1.0)]
        prod = frame_jpg(B["mp4"], (nar[0][0] + nar[0][1]) / 2, crop=win)     # 벤치 나레 구간 = 대개 제품 화면
        info = look(mp4, ref, fr, B, ask=ask, prod_jpg=prod)
        LK = {"sync": sync, "cands": cands, "info": {str(k): v for k, v in info.items()}, "Lc": Lc}
        jsave(cache, LK)
    info = {k: v for k, v in LK["info"].items() if k != "_model"}
    sync, cands = LK["sync"], LK["cands"]
    CROP_CAP["s"] = subtitle_cap(info)
    log(f"[plan] 크롭 한 변 상한 {CROP_CAP['s']}px(원본 아래 자막 띠 위)")
    win = (B.get("measure") or {}).get("window") or [0, 420, 1080, 1080]
    refs = [frame_jpg(B["mp4"], B["dur"] * f, w=320, crop=win) for f in (0.25, 0.42, 0.6, 0.85)]
    nar = [g for g in bench_gaps(T, B["dur"]) if g[1] - g[0] >= 0.8] or [(0.0, 1.0)]
    prod = frame_jpg(B["mp4"], (nar[0][0] + nar[0][1]) / 2, w=320, crop=win)
    banned: set = set()
    checks_log = []
    vcache = jload(W / "verify_cache.json") if (W / "verify_cache.json").exists() else {}
    for rnd in range(VERIFY_ROUNDS):
        cuts = _assign(blocks, sync, cands, info, Lc, banned)
        vc = verify_crops(mp4, cuts, B, refs, prod, ask=ask, cache=vcache)
        jsave(W / "verify_cache.json", vcache)
        checks_log.append({"round": rnd, "bad": {str(k): v for k, v in vc["bad"].items()}, "model": vc["model"]})
        if not vc["bad"]:
            break
        for i in vc["bad"]:
            banned.add(round(cuts[i]["scene0"], 2))
        log(f"[plan] 크롭 검사 {rnd + 1}회: 글자 걸린 컷 {sorted(vc['bad'])} → 그 장면 빼고 다시")
    else:
        raise StageError(f"크롭 검사 {VERIFY_ROUNDS}회 모두 걸림: {checks_log[-1]['bad']}")
    if abs(cuts[-1]["t_final"][1] - total) > 0.02:
        raise StageError(f"컷 합 {cuts[-1]['t_final'][1]:.3f} ≠ 블록 합 {total:.3f}")
    viol = rule_check(cuts, Lc)
    caps = captions(blocks, total)
    vis = visual_cuts(cuts)
    P = {"blocks": blocks, "cuts": cuts, "dur": total, "Lc": round(Lc, 3), "captions": caps, "violations": viol, "narr_measured": bool(narr),
         "look_model": LK["info"].get("_model"), "crop_checks": checks_log, "visual_cut_median": round(median(vis), 3)}
    jsave(W / "plan.json", P)
    write_docs(B, T, S, P, doc)
    if sheet_out:
        plan_sheet(mp4, P, doc / "plan" / "계획_시트.jpg")
    log(f"[plan] 블록 {[b['id'] for b in blocks]} · {total:.2f}초(벤치 {B['dur']}) · 보이는 컷 {len(vis)} · 중앙 {median(vis):.2f}"
        f"(벤치 {(B.get('measure') or {}).get('shot_median')}) · 위반 {viol or '없음'}")
    return P


def median(x):
    x = sorted(x)
    return (x[len(x) // 2] + x[(len(x) - 1) // 2]) / 2 if x else 0.0


def rule_check(cuts: list[dict], Lc: float) -> list[str]:
    """(판단 주인) 계획 단계 규칙 — B13 재사용 ±3초 · 되감김(같은 장면 뒤 컷이 앞 시각) · A-B-A 한 컷 끼움 · 끝 컷 ≥1.5초."""
    v = []
    for i, a in enumerate(cuts):
        for j, b in enumerate(cuts[i + 1:], start=i + 1):
            ra0, rb0 = a["ss"] + a["dur"], b["ss"]
            if j == i + 1 and ra0 - 0.05 <= rb0 <= ra0 + 3.5:
                continue                     # 바로 다음 컷이 원본에서 앞으로 이어짐(정본 B13 허용: 225.98→226.4)
            ra, rb = (a["ss"], a["ss"] + a["dur"]), (b["ss"], b["ss"] + b["dur"])
            if _overlap(ra, rb):
                v.append(f"B13 컷{a['i']}·컷{b['i']} 원본 {ra[0]:.1f}/{rb[0]:.1f} ±3초")
    for a, b in zip(cuts, cuts[1:]):
        if abs(a["ss"] - b["ss"]) < 6 and b["ss"] < a["ss"] + a["dur"] - 0.05 and b["ss"] >= a["ss"] - 6:
            v.append(f"되감김 컷{a['i']}→컷{b['i']} ({a['ss']:.2f}→{b['ss']:.2f})")
    for a, b, c in zip(cuts, cuts[1:], cuts[2:]):
        if a.get("who") in ("main", "both") and c.get("who") in ("main", "both") and b.get("who") not in ("main", "both") \
                and abs(a["ss"] + a["dur"] - c["ss"]) < 4 and a.get("sync") and c.get("sync"):
            v.append(f"A-B-A 컷{a['i']}-{b['i']}-{c['i']}")
    if cuts and cuts[-1]["dur"] < END_MIN - 1e-3:
        v.append(f"끝 컷 {cuts[-1]['dur']:.2f}초 < {END_MIN}")
    return v


def fix_words(words: list, heard: str) -> list:
    """(판단 주인) 원음 자막 글 바로잡기 — 자동자막 낱말(시각 있음)을 확정 받아쓰기 낱말로 1:1 바꾼다(같은 수로 어긋난 자리만).
    10-17 정재형: 자동자막 '얄서 화라당' → 받아쓰기 '얇아서 후라당'. 받아쓰기가 클립을 합쳐 답했으면(덮음 낮음) 그대로 둔다."""
    from difflib import SequenceMatcher
    hw = heard.split()
    if not hw or not words:
        return words
    a = [norm(w) for _, w in words]
    b = [norm(w) for w in hw]
    if SequenceMatcher(None, "".join(a), "".join(b), autojunk=False).ratio() < 0.6:   # 글자로 재서 딴 말이면 그대로
        return words
    m = SequenceMatcher(None, a, b, autojunk=False)
    out = list(words)
    for op, i1, i2, j1, j2 in m.get_opcodes():
        if op == "replace" and i2 - i1 == j2 - j1:
            for k in range(i2 - i1):
                out[i1 + k] = (words[i1 + k][0], hw[j1 + k])
    return out


def captions(blocks: list[dict], total: float) -> list[dict]:
    """(판단 주인) 자막 계획 — 나레 = 조각 글자 비례(노랑), 원음 = 원본 낱말 시각으로 ≤13자 조각(흰)."""
    caps = []
    for b in blocks:
        a0, a1 = b["t"]
        if b["kind"] == "나레":
            cs = b["line"]["caps"]
            n = sum(len(c.replace(" ", "")) for c in cs)
            x = a0
            for k, c in enumerate(cs):
                d = b["talk"] * len(c.replace(" ", "")) / n + (a1 - a0 - b["talk"] if k == len(cs) - 1 else 0)
                caps.append({"t0": round(x, 3), "t1": round(x + d, 3), "text": c, "kind": "나레"}); x += d
            continue
        spans = b["spans"]
        words = fix_words([(t, w) for t, w in b["orig"]["words"]], ((b["orig"].get("asr") or {}).get("text") or ""))
        groups, cur, ct = [], [], None
        for t, w in words:
            w2 = w.rstrip(".?!,")
            if cur and len(("".join(cur) + w2).replace(" ", "")) > 13:
                groups.append((ct, " ".join(cur))); cur, ct = [], None
            if ct is None:
                ct = t
            cur.append(w2)
            if re.search(r"[.?!]$", w) and len("".join(cur)) >= 4:
                groups.append((ct, " ".join(cur))); cur, ct = [], None
        if cur:
            groups.append((ct, " ".join(cur)))

        def rel(src_t):
            acc = 0.0
            for s, e in spans:
                if s - 0.3 <= src_t <= e:
                    return acc + max(0.0, src_t - s)
                acc += e - s
            return acc
        ts = [a0 + (0.0 if k == 0 else rel(st)) for k, (st, _) in enumerate(groups)] + [a1]
        for k, (_, c) in enumerate(groups):
            if ts[k + 1] - ts[k] > 0.05:
                caps.append({"t0": round(ts[k], 3), "t1": round(ts[k + 1], 3), "text": c, "kind": "원음"})
    return caps


def write_docs(B, T, S, P, doc: Path):
    """정본 꼴 파일 — 대본.json · 재료.json · frame.json · 계획.md (렌더는 이 파일들만 읽는다)."""
    src = T["source"]
    url = src["url"]
    sdate = f"{src['channel']} 유튜브 {str(src.get('upload') or '')[:4]}.{str(src.get('upload') or '')[4:6]}.{str(src.get('upload') or '')[6:8]}"
    srcname = Path(src["mp4"]).name
    lines = []
    for b in P["blocks"]:
        if b["kind"] == "나레":
            L = b["line"]
            lines.append({"fn": "훅" if b["id"] == "N1" else "마무리", "text": L["text"], "tts": L["tts"], "facts": L["facts"], "sources": [url],
                          "block": b["id"], "t_final": b["t"], "est_sec": b["talk"], "slice": b.get("slice"),
                          "cps": round(L["chars"] / b["talk"], 2) if b["talk"] else None})
    orig = [{"id": b["id"], "spans": b["spans"], "dur": round(b["t"][1] - b["t"][0], 3), "said": b["orig"]["said"], "t_final": b["t"],
             "asr_sim": b["orig"]["asr_sim"]} for b in P["blocks"] if b["kind"] == "원음"]
    Sd = {"topic": f"{B.get('person')} {B.get('product')}", "bench": {"id": B["id"], "channel": B.get("channel"), "title": B.get("title"), "dur": B["dur"],
                                                                     "screen_title": B.get("screen_title")},
          "source": {"id": src["id"], "channel": src["channel"], "title": src["title"], "upload": src.get("upload"), "url": url, "res": src.get("res")},
          "titles": {"hook": "\n".join(S["title"])}, "facts": S["facts"],
          "final": {"lines": lines, "orig_audio": orig, "order": [b["id"] for b in P["blocks"]],
                    "model": f"yanshot 파이프라인 — 제미나이 {S.get('model')} {S.get('calls')}회", "check": {"dur_est": P["dur"]}},
          "captions_plan": P["captions"]}
    jsave(doc / "대본.json", Sd)
    shots = []
    for c in P["cuts"]:
        sh = {"i": c["i"], "line": c["block"], "src": srcname, "url": url, "src_date": sdate, "ss": c["ss"], "dur": c["dur"],
              "src_span": [c["ss"], round(c["ss"] + c["dur"], 3)], "t_final": c["t_final"], "kind": "원본재편집", "full": True,
              "src_crop": c["crop"], "res": src.get("res"), "scale": round(1080 / c["crop"][2], 2), "ours": c["desc"], "why": c["why"], "who": c.get("who")}
        if c.get("audio_ss") is not None:
            sh["audio_src"], sh["audio_ss"] = srcname, c["audio_ss"]
        else:
            sh["mute"] = True
        shots.append(sh)
    jsave(doc / "재료.json", {"_note": "yanshot plan.py 가 씀(손으로 고치지 않는다)", "cand_dir": str(Path(src["mp4"]).parent).replace("\\", "/"),
                             "blocks": {b["id"]: b["t"] for b in P["blocks"]}, "dur_est": P["dur"], "shots": shots})
    fr = jload(FRAME)
    for l in fr["layers"]:
        if l.get("role") == "title":
            l["text"] = "\n".join(S["title"])
        if l.get("role") == "label":
            l["text"] = f"출처 : {re.sub(r'[(（].*$', '', src['channel']).strip()}"
    fr.setdefault("made_from", {})["note"] = "channel/mantem/frame_얜샷템.json 에서 제목·출처 글만 바꿈(yanshot plan.py)"
    jsave(doc / "frame.json", fr)
    md = [f"# 계획 — 얜샷템 {B.get('person')} {B.get('product')} (벤치 {B['id']} {B['dur']}초 · 원본 {src['id']})", "",
          f"길이 {P['dur']:.2f}초 · 컷 {len(P['cuts'])} · 컷 중앙 {median([c['dur'] for c in P['cuts']]):.2f}(벤치 {(B.get('measure') or {}).get('shot_median')}) · "
          f"위반 {P['violations'] or '없음'}", "", "| # | 블록 | 시각 | 길이 | 원본 ss | 소리 | 크롭 | 화면 | 왜 |", "|---|---|---|---|---|---|---|---|---|"]
    for c in P["cuts"]:
        md.append(f"| {c['i']} | {c['block']} | {c['t_final'][0]:.2f} | {c['dur']:.2f} | {c['ss']:.2f} | {'원음 ' + str(c['audio_ss']) if c.get('audio_ss') is not None else '나레'} | "
                  f"{c['crop']} | {c['desc']} | {c['why']} |")
    md += ["", "## 자막", ""] + [f"- {c['t0']:.2f}~{c['t1']:.2f} [{c['kind']}] {c['text']} ({len(c['text'].replace(' ', ''))}자)" for c in P["captions"]]
    (doc / "plan" / "계획.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def _font(sz):
    for f in ("C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/gulim.ttc"):
        if Path(f).exists():
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def plan_sheet(mp4, P: dict, out: Path, cw: int = 200):
    """계획 시트 — 컷마다 크롭한 시작·가운데·끝 3프레임 + 블록·시각·자막(A3 눈 대조용)."""
    rows = []
    f = _font(15)
    for c in P["cuts"]:
        ims = []
        for t in (c["ss"] + 0.05, c["ss"] + c["dur"] / 2, c["ss"] + c["dur"] - 0.05):
            b = frame_jpg(mp4, t, w=cw, crop=c["crop"])
            ims.append(Image.open(io.BytesIO(b)).convert("RGB") if b else Image.new("RGB", (cw, cw)))
        cap = " / ".join(x["text"] for x in P["captions"] if x["t0"] < c["t_final"][1] and x["t1"] > c["t_final"][0])
        row = Image.new("RGB", (cw * 3 + 520, cw), "white")
        for k, im in enumerate(ims):
            row.paste(im.resize((cw, cw)), (k * cw, 0))
        d = ImageDraw.Draw(row)
        d.text((cw * 3 + 8, 6), f"#{c['i']} {c['block']} {c['t_final'][0]:.2f}~{c['t_final'][1]:.2f} ({c['dur']:.2f}s) 원본 {c['ss']:.2f}", fill=(200, 0, 0), font=f)
        d.text((cw * 3 + 8, 30), ("원음 " + str(c.get('audio_ss')) if c.get("audio_ss") is not None else "나레(무음 화면)"), fill=(0, 0, 160), font=f)
        d.text((cw * 3 + 8, 54), (c["desc"] or "")[:30], fill=(0, 0, 0), font=f)
        d.text((cw * 3 + 8, 78), (c["why"] or "")[:32], fill=(80, 80, 80), font=f)
        d.text((cw * 3 + 8, 102), cap[:32], fill=(0, 120, 0), font=f)
        rows.append(row)
    sh = Image.new("RGB", (rows[0].width, sum(r.height + 4 for r in rows)), (230, 230, 230))
    y = 0
    for r in rows:
        sh.paste(r, (0, y)); y += r.height + 4
    out.parent.mkdir(parents=True, exist_ok=True)
    sh.save(out, quality=82)
    return out


def retime(B: dict, T: dict, S: dict, W: Path, P: dict, slices: dict, log=print) -> dict:
    """(판단 주인) TTS 실측 줄 길이로 시각만 다시 — 나레 블록 컷은 길이 비례로 늘이고/줄이고(원본 장면 안에서), 원음 블록은 그대로.
    컷 고르기는 다시 하지 않는다(판독·크롭 검사 결과 유지)."""
    W = Path(W)
    blocks, total = blocks_of(T, S, slices)
    old = {b["id"]: b for b in P["blocks"]}
    cuts, t = [], 0.0
    for b in blocks:
        mine = [dict(c) for c in P["cuts"] if c["block"] == b["id"]]
        k = (b["t"][1] - b["t"][0]) / (old[b["id"]]["t"][1] - old[b["id"]]["t"][0])
        if b["kind"] == "나레":
            for c in mine:
                c["dur"] = round(c["dur"] * k, 3)
            mine[-1]["dur"] = round((b["t"][1] - b["t"][0]) - sum(c["dur"] for c in mine[:-1]), 3)
            for c in mine:
                if c.get("scene1") and c["ss"] + c["dur"] > c["scene1"] - 0.03:
                    c["ss"] = round(max(c.get("scene0", c["ss"]), c["scene1"] - 0.03 - c["dur"]), 3)
        b["slice"] = slices.get(b["id"])
        for c in mine:
            c["t_final"] = [round(t, 3), round(t + c["dur"], 3)]
            t += c["dur"]
            cuts.append(c)
    for i, c in enumerate(cuts):
        c["i"] = i
    P2 = dict(P, blocks=blocks, cuts=cuts, dur=total, captions=captions(blocks, total), violations=rule_check(cuts, P["Lc"]), narr_measured=True,
              visual_cut_median=round(median(visual_cuts(cuts)), 3))
    jsave(W / "plan.json", P2)
    write_docs(B, T, S, P2, W / "doc")
    log(f"[plan] TTS 실측으로 다시 맞춤 {P['dur']:.2f} → {total:.2f}초 · 위반 {P2['violations'] or '없음'}")
    return P2
