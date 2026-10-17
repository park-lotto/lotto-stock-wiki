# -*- coding: utf-8 -*-
"""② 출처 추적 — 판단 주인: trace(B, W) (관제 097, 2026-10-17).

방식(channel/itemhome/칼카피_조사_2026-10-17.md §3): 출처 표기(설명란·화면 '출처 : ○○') + 인물·제품 → 검색(≤6 검색어)
→ 후보 자동자막만 받아(영상 X) **벤치 자동자막과 글자 지문 대조**(fingerprint) → 원본 확정 + 원음 구간.
원음 구간 = 지문이 맞은 원본 낱말 → 문장 끝까지 넓힘(화자 바뀜 '>>' 은 넘지 않음) → 길이 예산까지 다음 문장 더함
→ 원본 소리 무음 경계로 다듬고(앞뒤) 안쪽 긴 쉼은 잘라 낸다(정본 장윤정 O1 225.98~226.40 처럼)
→ −35 LUFS 이하 웅얼 구간 제외(B17) → 확정 받아쓰기 1회(제미나이, 구간 전부 한 번에) — 반복 받아쓰기 없음.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import time
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from tools.calcopy.yanshot.common import (GEM_MODELS, StageError, YT_FMT, dur_of, jload, jsave, lufs_of, norm, run, vtt_words)

K = 5                 # 지문 글자 조각 길이
MIN_RUN = 7           # 이보다 짧게 맞은 줄기는 버린다(우연 일치)
ANCHOR_RUN = 12       # 이 이상 긴 줄기 = 닻(원본 자리 확실)
ANCHOR_S = 150.0      # 짧은 줄기는 닻 가운데 시각 ±이 안만
MERGE_GAP_CH = 6      # 벤치 쪽 줄기 사이 글자 틈 ≤ 이것 + 원본 쪽 대각선 차 ≤ DIAG_TOL 이면 한 구간
DIAG_TOL = 8
CONFIRM_CHARS = 20    # 원본 확정 하한(맞은 글자 수)
SENT_END = re.compile(r"[.?!]$")
EXT_BACK_S = 0.0      # 문장 머리로 뒤로 넓히지 않는다 — 벤치 편집자가 고른 시작이 정본과 맞다(한고은 763.30·장윤정 224.80, 10-17 대조)
EXT_FWD_S = 3.5       # 문장 끝까지 앞으로
ADD_SENT_MAX_S = 4.0  # 길이 예산 채우기로 더하는 문장 하나 최대 초
QUIET_LUFS = -35.0    # B17: 원본에서 이보다 작은 말은 쓰지 않는다
PAUSE_CUT = 0.35      # 구간 안 쉼이 이보다 길면 잘라 낸다(앞뒤 0.06초 남김)
EDGE_PAD = 0.06
SIL_DB, SIL_D = -30.0, 0.08
SIL_REL = 8.0        # 무음 문턱 = 말소리 LUFS − 이것
SIL_MERGE = 0.15     # 쉼 사이 이보다 짧은 소리는 쉼으로 본다
NARR_EST_S = 7.6      # 나레 2줄 예상 상한(26자 ×2 ÷ 8.4 + 쉼) — 원음 길이 예산 = 벤치 길이 − narr_est(dur)
MAX_QUERIES = 6
PER_QUERY = 20
MAX_CANDS = 6


# ── 지문 대조 ─────────────────────────────────────────────────────
def char_seq(words: list[tuple[float, str]]) -> tuple[str, list[float], list[int]]:
    """낱말 → (정규화 글자열, 글자별 시각, 글자별 낱말 번호). 글자 시각 = 낱말 시작 ~ 다음 낱말 시작 사이 균등."""
    s, ts, wi = [], [], []
    for k, (t, w) in enumerate(words):
        n = norm(w)
        if not n:
            continue
        nxt = next((words[j][0] for j in range(k + 1, len(words)) if words[j][0] > t), t + 0.5)
        span = min(nxt - t, 0.18 * len(n) + 0.3)
        for c_i, c in enumerate(n):
            s.append(c); ts.append(t + span * c_i / len(n)); wi.append(k)
    return "".join(s), ts, wi


def fingerprint(bench_words, src_words) -> list[dict]:
    """벤치 낱말·원본 낱말 → 맞은 구간 목록 [{b0,b1(벤치 초), w0,w1(원본 낱말 번호), chars, text}] — 벤치 시각 순."""
    bs, bt, _ = char_seq(bench_words)
    ss, st, sw = char_seq(src_words)
    idx = defaultdict(list)
    for j in range(len(ss) - K + 1):
        idx[ss[j:j + K]].append(j)
    hits = defaultdict(list)          # 대각선 d=j-i → 벤치 위치들
    for i in range(len(bs) - K + 1):
        for j in idx.get(bs[i:i + K], ()):
            hits[j - i].append(i)
    runs = []
    for d, ii in hits.items():
        ii.sort()
        a = p = ii[0]
        for i in ii[1:] + [None]:
            if i is not None and i - p <= 2:
                p = i
                continue
            ln = p + K - a
            if ln >= MIN_RUN:
                runs.append((ln, a, p + K, d))
            if i is not None:
                a = p = i
    long_ = [st[min(len(st) - 1, a + d)] for ln, a, b, d in runs if ln >= ANCHOR_RUN]
    if long_:                                   # 짧은 줄기는 긴 줄기들 근처(원본 시각)만 — '너무 신선해요'가 원본 앞쪽 다른 자리에 또 나온 오탐(한고은 23초)
        long_.sort()
        anchor = long_[len(long_) // 2]
        runs = [r for r in runs if r[0] >= ANCHOR_RUN or abs(st[min(len(st) - 1, r[1] + r[3])] - anchor) <= ANCHOR_S]
    runs.sort(key=lambda r: -r[0])
    taken = [False] * len(bs)
    keep = []
    for ln, a, b, d in runs:            # 벤치 글자는 한 번만 — 긴 줄기부터
        free = [i for i in range(a, b) if not taken[i]]
        if len(free) < MIN_RUN:
            continue
        a2, b2 = free[0], free[-1] + 1
        for i in range(a2, b2):
            taken[i] = True
        keep.append((a2, b2, d))
    keep.sort()
    segs = []
    for a, b, d in keep:
        if segs and a - segs[-1]["_b"] <= MERGE_GAP_CH and abs(d - segs[-1]["_d"]) <= DIAG_TOL:
            segs[-1].update(_b=b, _d=d, chars=segs[-1]["chars"] + (b - a))
            continue
        segs.append({"_a": a, "_b": b, "_d": d, "chars": b - a})
    out = []
    for g in segs:
        a, b, d = g["_a"], g["_b"], g["_d"]
        j0, j1 = max(0, a + d), min(len(ss) - 1, b - 1 + d)
        out.append({"b0": round(bt[a], 2), "b1": round(bt[b - 1], 2), "w0": sw[j0], "w1": sw[j1], "chars": g["chars"], "text": bs[a:b]})
    return out


def narr_est(bench_dur: float) -> float:
    """나레 2줄 예상 초 — 벤치의 0.3배, 5.0~7.6초(짧은 벤치는 나레도 짧게). script 의 줄 글자 목표도 이것으로 정한다."""
    return max(5.0, min(NARR_EST_S, bench_dur * 0.3))


def score(segs: list[dict]) -> int:
    return sum(s["chars"] for s in segs)


# ── 원음 구간: 낱말 → 문장 → 예산 ───────────────────────────────────
def _sentence_bounds(words, w0: int, w1: int) -> tuple[int, int]:
    """[w0,w1] 을 문장 머리·끝까지 넓힌다 — 그 안에 문장 경계가 있을 때만(없으면 맞은 낱말 그대로). 화자 바뀜('>>')은 넘지 않는다."""
    t0, t1 = words[w0][0], words[w1][0]
    a = w0
    while a - 1 >= 0 and words[a - 1][1] != ">>" and not SENT_END.search(words[a - 1][1]) and t0 - words[a - 1][0] <= EXT_BACK_S:
        a -= 1
    if not (a == 0 or words[a - 1][1] == ">>" or SENT_END.search(words[a - 1][1])):
        a = w0                                   # 문장 머리를 못 찾음 → 넓히지 않는다
    b = w1
    while not SENT_END.search(words[b][1]) and b + 1 < len(words) and words[b + 1][1] != ">>" and words[b + 1][0] - t1 <= EXT_FWD_S:
        b += 1
    if not SENT_END.search(words[b][1]):
        b = w1
    return a, b


def _next_sentence(words, b: int) -> int | None:
    """b 다음 문장의 끝 낱말 번호(화자 바뀜이면 None)."""
    k = b + 1
    if k >= len(words) or words[k][1] == ">>":
        return None
    t0 = words[k][0]
    while k < len(words) and not SENT_END.search(words[k][1]):
        if k + 1 >= len(words) or words[k + 1][1] == ">>" or words[k + 1][0] - t0 > ADD_SENT_MAX_S:
            return None
        k += 1
    return k if k < len(words) else None


def _w_end(words, b: int) -> float:
    """낱말 b 끝 추정 — 다음 낱말 시작(쉼이 길면 글자 수로)."""
    t, w = words[b]
    nxt = next((words[j][0] for j in range(b + 1, len(words)) if words[j][0] > t), t + 1.0)
    return min(nxt, t + 0.16 * len(norm(w)) + 0.35)


HOOK_S = 3.0          # 벤치 이 초 안에서 시작하는 원음 = 훅
FIRST_MAX_S = 5.0     # 첫 원음 블록이 이보다 길면 문장 경계에서 나눈다
FIRST_TARGET_S = 2.5  # 그때 첫 조각 목표 길이
MIN_PART_S = 2.5      # 문장 끝이 아닌 블록은 이보다 짧으면 버린다


def _turn_piece(words, w0: int, w1: int) -> tuple[int, int]:
    """[w0,w1] 안에 화자 바뀜('>>')이 있으면 글자가 가장 많은 한 사람 몫만 — 원음 = 그 연예인 말만(10-17 엄정화 편: 지문이
    '…레스토랑 가잖아. >> 왜 이렇게 매니폰이 작은 거야?'로 김나영 말까지 걸쳤다)."""
    pieces, a = [], w0
    for k in range(w0, w1 + 1):
        if words[k][1] == ">>":
            if k > a:
                pieces.append((a, k - 1))
            a = k + 1
    if w1 >= a:
        pieces.append((a, w1))
    return max(pieces, key=lambda p: sum(len(norm(words[k][1])) for k in range(p[0], p[1] + 1))) if pieces else (w0, w1)


def _bench_lead(g: dict, segs: list[dict], bench_words) -> float:
    """벤치에서 이 지문 바로 앞, 안 맞은 낱말이 원음으로 이어진 초 — 앞 지문 끝·화자 바뀜('>>')·벤치 시작 중 늦은 것부터."""
    if not bench_words:
        return 0.0
    prev = max([x["b1"] for x in segs if x["b1"] <= g["b0"] - 0.05] + [t for t, w in bench_words if w == ">>" and t <= g["b0"]] + [0.0])
    words = [t for t, w in bench_words if w != ">>" and prev < t < g["b0"] - 0.05]
    return round(g["b0"] - words[0], 2) if words else 0.0


def _back_sentences(words, a: int, lead: float) -> int:
    """a 앞 문장을 하나씩 붙여 길이가 lead 에 가장 가깝게(넘침 ≤ +1초, 화자 바뀜 넘지 않음)."""
    t_a = words[a][0]
    best = a
    k = a
    while k > 0 and words[k - 1][1] != ">>":
        j = k - 1
        while j > 0 and words[j - 1][1] != ">>" and not SENT_END.search(words[j - 1][1]):
            j -= 1
        ext = t_a - words[j][0]
        if ext > lead + 1.0:
            break
        best, k = j, j
        if ext >= lead - 0.5:
            break
    return best


def _sent_ends(words, a: int, b: int) -> list[int]:
    return [k for k in range(a, b) if SENT_END.search(words[k][1])]


def word_spans(words, segs: list[dict], budget: float, keywords: list[str] = (), bench_words=None) -> list[dict]:
    """맞은 구간 → 원음 블록 후보(문장 단위, 한 사람 말). 같은 원본 문장을 두 번 쓰지 않는다.
    예산(벤치 길이 − 나레 예상)에 맞춘다: 모자라면 블록마다 다음 문장(제품 낱말 든 것만 — '화장품을 한번 보고 싶었어요'처럼
    다음 이야기로 넘어가지 않게) 더하고, 넘치면 지문이 짧은 블록부터 빼고 그래도 넘치면 지문 밖 문장부터 덜어 낸다.
    블록이 하나만 남고 문장이 둘 이상이면 문장 경계에서 둘로 나눈다(원음 → 나레 → 원음 → 나레 짜임)."""
    kws = [norm(k) for k in keywords if norm(k)]
    blocks, used = [], set()
    for g in segs:
        c0, c1 = _turn_piece(words, g["w0"], g["w1"])
        a, b = _sentence_bounds(words, c0, c1)
        lead = _bench_lead(g, segs, bench_words)
        if lead > 0.6 and c0 == g["w0"]:      # 벤치가 지문 앞에 원음을 더 썼는데(자동자막이 달라 안 맞음) → 그만큼 원본 문장을 앞으로
            a = _back_sentences(words, a, lead)
        if any(k in used for k in range(a, b + 1)):
            continue
        whole = bool(SENT_END.search(words[b][1]))       # 끝이 문장 끝인가(머리는 자동자막에 문장부호가 드물어 재지 않는다)
        if not whole and _w_end(words, b) - words[a][0] < MIN_PART_S:
            continue
        used.update(range(a, b + 1))
        blocks.append({"w0": a, "w1": b, "bench": [g["b0"], g["b1"]], "core": [c0, c1], "chars": g["chars"], "whole": whole})
    if sum(x["whole"] for x in blocks) >= 2:          # 문장 중간에서 끊기는 원음은 쓰지 않는다(온전한 블록이 2개 이상일 때)
        blocks = [x for x in blocks if x["whole"]]

    def dur(x):
        return _w_end(words, x["w1"]) - words[x["w0"]][0]

    def tot():
        return sum(dur(x) for x in blocks)
    changed = True
    while changed and tot() < budget - 1.0:
        changed = False
        for x in blocks:
            nb = _next_sentence(words, x["w1"])
            if nb is None or any(k in used for k in range(x["w1"] + 1, nb + 1)):
                continue
            add = _w_end(words, nb) - words[x["w1"] + 1][0]
            sent = norm("".join(w for _, w in words[x["w1"] + 1:nb + 1]))
            if tot() + add > budget + 1.0 or not any(k in sent for k in kws):
                continue
            used.update(range(x["w1"] + 1, nb + 1)); x["w1"] = nb; x["added"] = x.get("added", 0) + 1; changed = True
    heads = [x for x in blocks if x["bench"][0] < HOOK_S]
    hook = max(heads, key=lambda x: x["chars"]) if heads else None     # 벤치 첫 3초 원음 = 훅 — 지켜서 맨 앞에(정본 한고은 H·장윤정 O1)
    if hook:
        blocks.remove(hook); blocks.insert(0, hook)
    while blocks and tot() > budget + 2.0 and len(blocks) > 2:   # 넘치면 지문이 짧은(덜 확실한) 블록부터 뺀다(훅 빼고)
        drop = min([x for x in blocks if x is not hook], key=lambda x: (x["chars"], -blocks.index(x)))
        blocks.remove(drop)
    trimmed = True
    while blocks and tot() > budget + 1.0 and trimmed:          # 그래도 넘치면 가장 긴 블록의 앞 문장(지문 밖 먼저)부터 덜어 낸다
        trimmed = False
        for x in sorted(blocks, key=dur, reverse=True):
            ends = _sent_ends(words, x["w0"], x["w1"])
            if not ends:
                continue
            k = ends[0]
            if _w_end(words, x["w1"]) - words[k + 1][0] < 2.0:
                continue
            x["w0"] = k + 1; x["trimmed"] = x.get("trimmed", 0) + 1; trimmed = True
            break
    if blocks and (dur(blocks[0]) > FIRST_MAX_S or len(blocks) == 1):   # 첫 원음은 짧게(만템: 원음 한 마디 → 첫 나레 2초쯤)
        x = blocks[0]
        t0 = words[x["w0"]][0]
        ends = [e for e in _sent_ends(words, x["w0"], x["w1"]) if _w_end(words, e) - t0 >= 1.2 and _w_end(words, x["w1"]) - words[e + 1][0] >= 1.5]
        if ends:
            k = min(ends, key=lambda e: abs(_w_end(words, e) - t0 - FIRST_TARGET_S))
            y = dict(x, w0=k + 1, split=True)
            x["w1"] = k; x["split"] = True
            blocks.insert(1, y)
    for x in blocks:
        x["t0"], x["t1"] = round(words[x["w0"]][0], 3), round(_w_end(words, x["w1"]), 3)
        x["said"] = " ".join(w for _, w in words[x["w0"]:x["w1"] + 1] if w != ">>")
    return blocks


# ── 무음 경계 ─────────────────────────────────────────────────────
def silences(wav, a: float, b: float, noise_db: float = SIL_DB, d: float = SIL_D) -> list[tuple[float, float]]:
    """원본 소리 [a,b] 안 무음 구간(원본 초)."""
    e = run(["ffmpeg", "-hide_banner", "-ss", f"{max(0, a):.3f}", "-t", f"{b - max(0, a):.3f}", "-i", str(wav), "-af",
             f"silencedetect=noise={noise_db}dB:d={d}", "-f", "null", "-"], check=False).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", e)]
    off = max(0, a)
    out = []
    for k, s in enumerate(st):
        e_ = en[k] if k < len(en) else b - off
        s_, e2 = round(off + max(0.0, s), 3), round(off + e_, 3)
        if out and s_ - out[-1][1] <= SIL_MERGE:      # 쉼 사이 짧은 소리(숨·잡음)는 쉼으로 이어 붙인다
            out[-1] = (out[-1][0], e2)
        else:
            out.append((s_, e2))
    return out


def snap_spans(wav, t0: float, t1: float) -> list[list[float]]:
    """[t0,t1](낱말 시각) → 무음 경계에 맞춘 조각들. 시작 = t0 앞 0.6초 안 마지막 무음 끝(없으면 t0−0.12),
    끝 = t1 앞뒤 무음 시작(말이 끝난 자리), 안쪽 쉼 > PAUSE_CUT 은 잘라 낸다.
    무음 문턱 = 그 구간 말소리 LUFS − SIL_REL (원본마다 배경 크기가 달라 고정 −30dB 는 쉼을 못 찾았다 — 장윤정 원본 말 −12·배경 −25, 10-17 실측)."""
    L = lufs_of(wav, t0, t1)["I"]
    noise = SIL_DB if L is None else max(-35.0, min(-18.0, L - SIL_REL))
    sil = silences(wav, t0 - 0.8, t1 + 0.8, noise)
    before = [e for s, e in sil if e <= t0 + 0.15 and e >= t0 - 0.6]
    a = (max(before) - 0.02) if before else t0 - 0.12
    after = [s for s, e in sil if s >= t1 - 0.45 and s <= t1 + 0.5 and s > a + 0.3]
    b = (min(after) + EDGE_PAD) if after else t1
    spans, cur = [], a
    for s, e in sil:
        if s > a + 0.2 and e < b - 0.2 and e - s > PAUSE_CUT:
            spans.append([round(cur, 2), round(s + EDGE_PAD, 2)])
            cur = e - EDGE_PAD
    spans.append([round(cur, 2), round(b, 2)])
    return [s for s in spans if s[1] - s[0] > 0.25]


# ── 검색·후보 ─────────────────────────────────────────────────────
def queries(B: dict) -> list[str]:
    who, prod, brand, ch = B.get("person") or "", B.get("product") or "", B.get("brand") or "", (B.get("source_label") or {}).get("channel") or ""
    q = [f"{ch} {who} {prod}", f"{ch} {prod}", f"{who} {brand} {prod}", f"{who} {prod}", f"{ch} {who}", f"{who} {brand}"]
    out = []
    for x in q:
        x = " ".join(x.split())
        if x and len(x) > 2 and x not in out:
            out.append(x)
    return out[:MAX_QUERIES]


def search(q: str, n: int = PER_QUERY) -> list[dict]:
    r = run(["yt-dlp", "--no-update", "--encoding", "utf-8", "--socket-timeout", "15", "--flat-playlist", "-J", f"ytsearch{n}:{q}"],
            timeout=120, check=False)
    try:
        d = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return []
    out = []
    for e in d.get("entries") or []:
        out.append({"id": e.get("id"), "title": e.get("title") or "", "channel": e.get("channel") or e.get("uploader") or "",
                    "duration": e.get("duration") or 0, "q": q})
    return out


def _date_of(label: dict) -> str | None:
    m = re.search(r"(20\d{2})[.\-/ ]\s*(\d{1,2})[.\-/ ]\s*(\d{1,2})", label.get("raw") or "")
    return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}" if m else None


def rank(cands: list[dict], B: dict) -> list[dict]:
    lab = (B.get("source_label") or {})
    ch = norm(lab.get("channel") or "")
    who = norm(B.get("person") or "")
    seen, out = set(), []
    for c in cands:
        if not c["id"] or c["id"] in seen or c["id"] == B["id"]:
            continue
        seen.add(c["id"])
        if c["duration"] and c["duration"] < 70:        # 쇼츠(남의 재편집본) 제외
            continue
        if norm(c["channel"]) == norm(B.get("channel") or ""):
            continue
        s = 0
        cn = norm(c["channel"])
        if ch and cn and (ch in cn or cn in ch):
            s += 3
        if who and who in norm(c["title"] + c["channel"]):
            s += 1
        c["meta_score"] = s
        out.append(c)
    out.sort(key=lambda c: (-c["meta_score"], cands.index(next(x for x in cands if x["id"] == c["id"]))))
    return out


def fetch_subs(vid: str, d: Path) -> tuple[Path | None, dict]:
    d.mkdir(parents=True, exist_ok=True)
    info = d / f"{vid}.info.json"
    vtts = sorted(d.glob(f"{vid}*.vtt"))
    if not vtts or not info.exists():
        run(["yt-dlp", "--no-update", "--encoding", "utf-8", "--socket-timeout", "15", "--skip-download", "--write-auto-subs", "--write-subs",
             "--sub-langs", "ko-orig,ko", "--sub-format", "vtt", "--write-info-json", "--sleep-requests", "1",
             "-o", str(d / f"{vid}.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"], timeout=180, check=False)
        vtts = sorted(d.glob(f"{vid}*.vtt"))
    pick = next((v for v in vtts if ".ko-orig." in v.name), None) or next((v for v in vtts if ".ko." in v.name), None)
    meta = jload(info) if info.exists() else {}
    return pick, meta


def download_source(vid: str, out: Path) -> Path:
    if out.exists() and out.stat().st_size > 1_000_000:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["yt-dlp", "--no-update", "--socket-timeout", "20", "-f", YT_FMT, "--merge-output-format", "mp4", "-o", str(out),
         f"https://www.youtube.com/watch?v={vid}"], timeout=1800)
    return out


def confirm_asr(wav: Path, blocks: list[dict], work: Path, ask=None) -> list[dict]:
    """확정 받아쓰기 1회 — 블록마다 조각을 이어 붙인 mp3 를 한 요청에. 반환 = 블록별 {text, speakers}."""
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as ask_
        ask = ask_
    parts = []
    for k, x in enumerate(blocks):
        mp3 = work / f"orig_{k}.mp3"
        fc = "".join(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=N/SR/TB[p{i}];" for i, (a, b) in enumerate(x["spans"]))
        fc += "".join(f"[p{i}]" for i in range(len(x["spans"]))) + f"concat=n={len(x['spans'])}:v=0:a=1[a]"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-filter_complex", fc, "-map", "[a]", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(mp3)])
        parts += [f"클립 {k}:", (mp3.read_bytes(), "audio/mp3")]
    prompt = ('위 클립마다 한국어 말소리를 들리는 그대로 받아써라(배경음악·효과음 빼고). 말하는 사람이 몇 명인지도 세라.\n'
              'JSON만: {"clips":[{"i":0,"text":"","speakers":1}]}')
    d, why = ask(parts, prompt, tag="yanshot_trace_confirm", models=GEM_MODELS)
    if d is None:
        raise StageError(f"확정 받아쓰기 실패: {why}")
    rows = {int(c.get("i", k)): c for k, c in enumerate(d.get("clips") or d.get("items") or [])}
    return [{"text": (rows.get(k) or {}).get("text", ""), "speakers": int((rows.get(k) or {}).get("speakers") or 0), "model": d.get("_model")}
            for k in range(len(blocks))]


def similar(a: str, b: str) -> float:
    return round(SequenceMatcher(None, norm(a), norm(b)).ratio(), 2)


ASR_COVER = 0.55      # 원본 자막(said) 글자 중 확정 받아쓰기에 같은 차례로 든 비율 하한


def coverage(said: str, heard: str) -> float:
    """said 글자 중 heard 에 같은 차례로 나온 비율(받아쓰기가 클립을 나눴든 합쳤든 같은 값)."""
    a, b = norm(said), norm(heard)
    if not a:
        return 0.0
    m = SequenceMatcher(None, a, b, autojunk=False)
    return round(sum(x.size for x in m.get_matching_blocks()) / len(a), 2)


# ── 단계 함수 ─────────────────────────────────────────────────────
def trace(B: dict, W: Path, ask=None, log=print) -> dict:
    """(판단 주인) 벤치 → 원본 확정 + 원음 블록. 반환은 W/trace.json 으로도 남긴다."""
    W = Path(W)
    sd = W / "trace"
    bench_words = vtt_words(B["vtt"])
    if not bench_words:
        raise StageError("벤치 자동자막이 없다 — 지문 대조 불가(음성 받아쓰기 경로는 아직 없음)")
    tried, cands = [], []
    qs = queries(B)
    cache = sd / "search.json"
    if cache.exists() and jload(cache).get("queries") == qs:      # 같은 검색어면 다시 검색하지 않는다(재실행)
        cands = jload(cache)["cands"]
    else:
        for q in qs:
            cands += search(q)
            time.sleep(1.0)
        jsave(cache, {"queries": qs, "cands": cands})
    ranked = rank(cands, B)
    log(f"[trace] 검색어 {len(qs)}개 → 후보 {len(ranked)}편(쇼츠·벤치 채널 제외)")
    best = None
    want_date = _date_of(B.get("source_label") or {})
    for c in ranked[:MAX_CANDS]:
        vtt, meta = fetch_subs(c["id"], sd)
        if not vtt:
            tried.append({**c, "score": None, "why": "자동자막 없음"})
            continue
        segs = fingerprint(bench_words, vtt_words(vtt))
        sc = score(segs)
        date_ok = bool(want_date) and meta.get("upload_date") == want_date
        tried.append({**{k: c[k] for k in ("id", "title", "channel", "duration", "q", "meta_score")}, "score": sc, "upload_date": meta.get("upload_date"),
                      "date_ok": date_ok, "segs": len(segs)})
        log(f"[trace]   {c['id']} {c['channel'][:14]} 맞은 글자 {sc} 구간 {len(segs)} {'날짜맞음' if date_ok else ''}")
        if best is None or sc > best["score"]:
            best = {"id": c["id"], "vtt": str(vtt), "meta": meta, "score": sc, "segs": segs}
        if sc >= 40 and (c["meta_score"] >= 3 or date_ok):
            break
    if not best or best["score"] < CONFIRM_CHARS:
        jsave(W / "trace_fail.json", {"queries": qs, "tried": tried})
        raise StageError(f"원본 확정 실패 — 최고 맞은 글자 {best and best['score']} < {CONFIRM_CHARS} (후보 {len(tried)}편, trace_fail.json)")
    meta = best["meta"]
    src_words = vtt_words(best["vtt"])
    bench_dur = B["dur"]
    budget = max(8.0, bench_dur - narr_est(bench_dur))
    blocks = word_spans(src_words, best["segs"], budget, B.get("keywords") or [], bench_words)
    # 원본 받기 + 소리 → 무음 경계
    mp4 = download_source(best["id"], W / "src" / f"src_{best['id']}.mp4")
    wav = W / "src" / "src_16k.wav"
    if not wav.exists():
        run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    keep, dropped = [], []
    for x in blocks:
        x["spans"] = snap_spans(wav, x["t0"], x["t1"])
        L = lufs_of(wav, x["spans"][0][0], x["spans"][-1][1])["I"]
        x["lufs"] = L
        if L is None or L < QUIET_LUFS:
            dropped.append({**x, "why": f"웅얼(원본 {L} LUFS < {QUIET_LUFS})"}); continue
        keep.append(x)
    if not keep:
        raise StageError("원음 블록이 하나도 안 남았다(전부 웅얼/없음)")
    asr = confirm_asr(wav, keep, sd, ask=ask)
    final = []
    whole_txt = " ".join(a["text"] for a in asr)      # 모델이 클립을 한 덩이로 답할 때가 있다(lite, 10-17 실측) → 전체 받아쓰기에서 덮는 비율로 잰다
    for x, a in zip(keep, asr):
        x["asr"] = a
        x["asr_sim"] = coverage(x["said"], whole_txt)
        if x["asr_sim"] < ASR_COVER:
            dropped.append({**x, "why": f"받아쓰기 불일치(원본 자막 글자 중 받아쓰기에 든 비율 {x['asr_sim']} < {ASR_COVER})"}); continue
        final.append(x)
    if not final:
        jsave(W / "trace_fail.json", {"dropped": dropped, "asr": asr})
        raise StageError("확정 받아쓰기에서 원음 블록이 전부 빠졌다: " + " / ".join(f"{d['said'][:20]}…{d['why']}" for d in dropped))
    for k, x in enumerate(final):
        x["id"] = f"O{k + 1}"
        x["dur"] = round(sum(b - a for a, b in x["spans"]), 3)
        x["words"] = [[t, w] for t, w in src_words[x["w0"]:x["w1"] + 1] if w != ">>"]
    T = {"source": {"id": best["id"], "url": f"https://www.youtube.com/watch?v={best['id']}", "channel": meta.get("channel") or meta.get("uploader"),
                    "title": meta.get("title"), "upload": meta.get("upload_date"), "dur": meta.get("duration"),
                    "description": (meta.get("description") or "")[:1500], "mp4": str(mp4), "wav": str(wav), "vtt": best["vtt"],
                    "res": f"{meta.get('width')}x{meta.get('height')}"},
         "score": best["score"], "fingerprint": best["segs"], "queries": qs, "tried": tried, "budget": round(budget, 2),
         "orig": final, "dropped": dropped, "orig_total": round(sum(x["dur"] for x in final), 2)}
    jsave(W / "trace.json", T)
    log(f"[trace] 원본 {best['id']} ({T['source']['channel']}) 맞은 글자 {best['score']} · 원음 블록 {len(final)}개 {T['orig_total']}초 (예산 {budget:.1f}) · 뺌 {len(dropped)}")
    return T
