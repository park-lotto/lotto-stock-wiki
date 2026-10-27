# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 — **벤치 판 공용 렌더러**(키치잇판·꿀템노트판·스타픽룸판 …). 판 설정(styles/<판>.json)만 보고 그린다 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/render_bench.py <판> <doc_dir> <work_dir> [--plan]
    (보통은 run.py <연예인> render --version <판>)

편 전용 렌더 3벌(channel/kitchit/…/render_kitchit.py · channel/kkultemnote/…/render_kkt.py · channel/starpickroom/hybrid/render_spr.py)의 공통을 뽑았다.
같은 판단 두 벌 금지:
  · 시각 = timeline() 한 곳(줄 이어 붙이기·자막 덩어리 시각·컷)            · 나레 = render_itssum.tts_once/make_sentences(Typecast·미나 서버 합성 캐시)
  · 자막·효과 배치 = placement.place() 한 곳(벤치 줄판독 빈도)              · 자막 그리기 = scene_style.compose(자막팩 길) — PNG 자막 없음
  · 자막표 → 비트 = tools/caption_pack/check_bench_packs.rows_to_timeline(자막팩 쪽 견본 그대로)
  · 틀 그림 = frame_png() 한 곳(판 설정 frame 칸) · 마스터 = −14 LUFS 2단 loudnorm(판 설정 loudness)

대본.json: slug · title_lines [[[글, 'hi'|null|'#hex'], …], …] · source_label · (comment{text,likes,from,to}) ·
  lines[{id, kind:'tts', tts, caps[{text, key?, key_color?, object_src?} | 글]} | {id, kind:'orig', src, spans[[a,b]…] | span, caps_rel[[글, s0, s1, key?]…]}
        | {id, kind:'sub', dur, caps[{text, s0?, …} | 글]}]   ← sub = 나레 없는 자막 줄(TTS 없이 dur 초 동안 자막만 — 신박·썰풀다A·숏비타민 꼴, 관제 263 02 2차)
재료.json: cand_dir · cuts{줄 id: [{src, ss?, crop[x,y,w,h] | 'face', w?, at?, max?, move?, see}]} · blur{src: [[x,y,w,h(,a,b)]…]}(원본에 박힌 글 흐림 — 잘라서 피하지 말고)
  tts 줄 = w(무게) 비례로 줄 칸 [시작, 다음 줄 시작) 을 나눔 · orig 줄 = at(줄 시작부터 초), ss 를 안 적으면 원음 구간에 입을 맞춘 초 · 비어 있으면 구간마다 얼굴 크롭 한 컷
출력(work/render/): final.mp4 · timeline.json · 자막표.json(배치 결과) · render_info.json · (doc) final_sheet_1s.jpg
"""
from __future__ import annotations

import json
import math
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import FACE_MODEL, FPS, ROOT, SR, StageError, dur_of, jload, jsave, lufs, nchar, probe, run  # noqa: E402
from tools.calcopy.engine.encoder import venc  # noqa: E402 — 인코더 주인(GPU 있으면 NVENC, 화질 같게, 98 #79)

W, H = 1080, 1920
FONTS = ROOT / "shopping_shorts/static/fonts"
SFX_DIR = ROOT / "shopping_shorts/assets/sfx_packs"
BGM_DIR = ROOT / "shopping_shorts/assets/bgm_lib"
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
CAP_EXTRA = ("key", "key_color", "object_src", "aside", "append", "sound", "small", "likes", "ago")   # likes·ago = 댓글카드 글 칸(card_plan)   # 대본 caps 덩어리 칸 → 배치(placement)가 읽는다


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(c, str) else tuple(c)


def _font(name, px):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), int(px))


def caps_of(L: dict) -> list[dict]:
    """줄 자막 덩어리 → [{text, key?, …}] (글만 적은 꼴도 받는다)."""
    if L["kind"] == "orig":
        out = []
        for c in L.get("caps_rel") or []:
            d = {"text": c[0], "s0": float(c[1]), "s1": float(c[2])}
            if len(c) > 3 and c[3]:
                d["key"] = c[3]
            out.append(d)
        return out
    return [c if isinstance(c, dict) else {"text": c} for c in L.get("caps") or []]


def spans_of(L: dict) -> list[list[float]]:
    return [list(s) for s in (L.get("spans") or [L["span"]])]


# ── 시간표(판단 주인) ───────────────────────────────────────────────────
LINE_KINDS = ("tts", "orig", "sub")      # sub = 나레 없는 자막 줄(dur 초) — 시각·컷은 나레 줄과 같은 길(소리만 없다)


def gap_between(st: dict, prev: str | None, cur: str) -> float:
    T = st.get("timing") or {}
    if prev is None:
        return 0.0
    if prev == "orig" and cur == "orig" and "gap_oo" in T:
        return T["gap_oo"]
    key = "gap_after_tts" if prev in ("tts", "sub") else "gap_after_orig"
    return T.get(key, T.get("gap", 0.1))


def sub_cap_starts(L: dict, dur: float) -> list[float]:
    """나레 없는 자막 줄(kind sub) 덩어리 시작(줄 시작부터 초): 덩어리에 s0 가 있으면 그것(자막 시간표 그대로), 없으면 글자 수 비례."""
    caps = caps_of(L)
    if caps and all(c.get("s0") is not None for c in caps):
        return [round(float(c["s0"]), 3) for c in caps]
    w = [max(1, nchar(c["text"])) for c in caps]
    acc, out = 0, []
    for x in w:
        out.append(round(dur * acc / sum(w), 3)); acc += x
    return out


def narr_cap_starts(L: dict, sent: dict | None, align: dict | None, tts_char0: int) -> list[float]:
    """나레 덩어리 시작(줄 시작부터 초). 글자 시각(align)이 있으면 그 덩어리 첫 글자의 소리 시각(배속·앞자르기 갚음),
    없으면 글자 수 비례. 자막 글(숫자 표기)과 tts 글(한글 읽기)이 다르면 덩어리 비율로 tts 글자 자리를 잡는다."""
    caps = caps_of(L)
    w = [max(1, nchar(c["text"])) for c in caps]
    dur = sent["dur"] if sent else sum(w) / 7.0
    if not (sent and align):
        acc, out = 0, []
        for x in w:
            out.append(round(dur * acc / sum(w), 3)); acc += x
        return out
    ch, st = align["characters"], align["character_start_times_seconds"]
    idx = [i for i, c in enumerate(ch) if re.match(r"[가-힣A-Za-z0-9]", c)]
    n_line = nchar(L["tts"])
    out, acc = [], 0
    for j, x in enumerate(w):
        if j == 0:
            out.append(0.0)
        else:
            k = tts_char0 + round(acc / sum(w) * n_line)
            k = min(k, len(idx) - 1)
            t_raw = float(st[idx[k]])
            x0 = max(0.0, sent["raw"][0] - 0.02)
            t_out = (t_raw - x0) / sent["tempo"]
            if sent.get("tmap"):          # fit_voice 가 앞뒤 무음·문장부호 쉼을 고친 줄 — 고치기 전 시각 → 고친 뒤 시각
                xs, ys = zip(*sent["tmap"])
                t_out = float(__import__("numpy").interp(t_out, xs, ys))
            out.append(round(max(0.0, min(dur - 0.15, t_out)), 3))
        acc += x
    return out


def real_cut_bounds(cuts: list[dict], src_dir: Path | None) -> list[float]:
    """(판단 주인 — 계획 컷 중 '진짜 컷' 경계) 이웃 컷이 다른 파일이거나, 그림이거나, 같은 파일이라도 원본 장면(shot_starts)이 다르면 진짜 컷.
    같은 원본 같은 샷을 이어 붙인 조각·같은 샷 안 건너뛰기는 컷 감지(kal_analyze.media_of)가 경계로 못 본다(10-25 박정수 v2 실측: 칸 당김 조각
    22경계 → 완성본 컷 11, check_seams 는 점프줌 12 로 잡음) — 그래서 판 리듬 판정은 이 경계만 센다."""
    out = []
    for a, b in zip(cuts, cuts[1:]):
        if a["src"] != b["src"] or Path(str(a["src"])).suffix.lower() in IMG_EXT or a.get("ss") is None or b.get("ss") is None or not src_dir:
            out.append(float(b["t0"]))
            continue
        st = shot_starts(Path(src_dir) / a["src"])
        sa = max([t for t in st if t <= float(a["ss"]) + 1e-3] or [0.0])
        sb = max([t for t in st if t <= float(b["ss"]) + 1e-3] or [0.0])
        if sa != sb or _jump_cut(Path(src_dir) / a["src"], float(a["ss"]) + cut_speed(a) * float(a.get("dur") or (float(b["t0"]) - float(a["t0"]))), float(b["ss"])):
            out.append(float(b["t0"]))
    return out


def _jump_cut(src: Path, t_end: float, t_next: float) -> bool:
    """같은 원본·같은 샷 안 건너뛰기가 화면에서 컷으로 보이나 — 앞 컷 마지막 프레임 ↔ 다음 컷 첫 프레임 회색 상관 < CUT_CORR_MAX(샷 경계와 같은 문턱·같은 자,
    오류기록 85 '같은 배경 점프컷 0.6~0.85 = 진짜 편집점'). 10-26 두유노판: 끊김 없는 44초 한 샷(e-LfR) 안 12초 건너뛰기(마개 근접 → 손에 든 제품)를
    옛 판정이 '같은 샷'이라 컷으로 안 세서 rhythm_gate 가 컷 중앙 1.46초로 멈췄다. 1초 안 건너뛰기(칸 당김 조각)는 그대로 컷 아님. 못 재면 컷 아님(옛 동작)."""
    import subprocess
    import numpy as np
    if abs(t_next - t_end) < 1.0:
        return False
    fr = []
    for t in (max(0.0, t_end - 1 / FPS), t_next):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", str(src), "-vf", "scale=90:-2,format=gray", "-frames:v", "1", "-f", "rawvideo", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL).stdout
        fr.append(np.frombuffer(raw, np.uint8).astype(float))
    if not all(len(f) for f in fr) or len(fr[0]) != len(fr[1]) or fr[0].std() < 1e-6 or fr[1].std() < 1e-6:
        return False
    return float(np.corrcoef(fr[0], fr[1])[0, 1]) < CUT_CORR_MAX


def rhythm_gate(T: dict, st: dict, src_dir: Path | None) -> list[str]:
    """(판단 주인 — 판 rhythm.cut_median·hook_cuts_3s 를 계획에 적용, 관제263 10-25 페이블 E1·E2) 렌더 전 관문: 진짜 컷(real_cut_bounds) 길이 중앙이
    판 cut_median×1.3(재현 cut.median 과 같은 ±30%)을 넘거나 0.1~3초 안 진짜 컷 경계가 hook_cuts_3s.min 보다 적으면 멈춘다.
    렌더러가 같은 샷을 잘게 나눠 흉내 내지 않는다(그건 컷으로 안 잡히고 점프줌이 된다 — 10-25 실측) — 재료.json 에 다른 장면 컷을 더해야 한다."""
    import statistics
    from tools.calcopy.hybrid import styles as _STY
    R = _STY.rhythm(st)
    if not (R.get("cut_median") or R.get("hook_cuts_3s")):
        return []
    b = real_cut_bounds(T["cuts"], src_dir)
    spans = list(zip([0.0] + b, b + [float(T["end"])]))
    bad = []
    if R.get("cut_median"):
        v, med = float(R["cut_median"]["v"]), statistics.median([y - x for x, y in spans])
        hi = _STY.rhythm_bounds(st)["cut_median"][1]          # 합격 범위 주인 styles.rhythm_bounds(×1.3 또는 벤치 가장 느린 편)
        if med > hi + 1e-6:
            line_at = lambda x: next((c["line"] for c in T["cuts"] if abs(float(c["t0"]) - x) < 1e-3), "?")  # noqa: E731
            long = sorted(spans, key=lambda s: s[0] - s[1])[:5]
            bad.append(f"진짜 컷 중앙 {med:.2f}초 > 판 cut_median {v} 상한 {hi} — 긴 화면 {[(line_at(x), round(x, 2), round(y - x, 2)) for x, y in long]} "
                       f"에 다른 장면 컷을 더할 것(재료.json — 같은 샷 이어 붙이기는 컷이 아니다)")
    if R.get("hook_cuts_3s"):
        h = [t for t in b if 0.1 < t <= 3.0]
        hm = _STY.rhythm_bounds(st)["hook_min"]
        if len(h) < hm:
            bad.append(f"훅 0.1~3초 진짜 컷 경계 {len(h)} < 판 {hm} — 첫 줄 재료에 다른 장면 컷을 더할 것")
    return bad


def photo_share(cuts: list[dict], end: float) -> float:
    """(판단 주인 — 쿠팡·상품 그림 컷 비중) 그림(jpg·png·webp) 컷 초 합 ÷ 길이 — 연예인 본인 사진(파일 앞머리 own_, deco.is_own_photo)은 뺀다
    (사장님 10-25 "사진 비중 상한은 쿠팡 사진에만" — 본인 사진은 판 deco.photo 가 따로 센다). 렌더 전 관문(photo_gate)·품질 관문 rhythm 행이 같이 부른다."""
    from tools.calcopy.hybrid.deco import is_own_photo
    if not end:
        return 0.0
    s = sum((c.get("t1", end) - c["t0"]) for c in cuts if Path(str(c.get("src") or "")).suffix.lower() in IMG_EXT and not is_own_photo(c.get("src")))
    return round(s / end, 3)


def photo_gate(T: dict, st: dict) -> list[str]:
    """렌더 전 관문: 그림 컷 비중이 판 rhythm.photo_share_max 를 넘으면 멈춘다(벤치 정지 화면 = 연예인 화보, 쇼핑몰 사진 0/8)."""
    from tools.calcopy.hybrid import styles as _STY
    R = _STY.rhythm(st).get("photo_share_max")
    if not R:
        return []
    sh = photo_share(T["cuts"], T["end"])
    return [f"그림 컷 비중 {sh} > 판 photo_share_max {R['v']} — 쿠팡·상품 사진을 줄이고 원본·재료 영상으로(재료.json)"] if sh > float(R["v"]) + 1e-9 else []


def timeline(S: dict, M: dict, st: dict, sent: dict | None, align: dict | None) -> dict:
    """sent = {줄 id: {dur, raw, tempo}} (None 이면 글자÷cps 어림). 반환 = lines(줄 시각)·rows(자막 덩어리)·cuts(화면)·opos(원음 조각)·end."""
    from tools.calcopy.hybrid.material_fit import action_order       # 대사 동작 ↔ 컷 동작(페이블 E3) — 동작 컷 우선 + 없으면 경고
    action_order(S, M, log=lambda m: sys.stderr.write(m + "\n"))
    t, prev, lines, rows, opos, char0 = 0.0, None, {}, [], [], 0
    orig_trim = {}           # 원음 줄 앞 무음을 뺀 초 — 재료.json 의 그 줄 컷 at·ss 를 같이 옮긴다(입 맞춤 그대로)
    est = st.get("cps_target", 7.0)
    for L in S["lines"]:
        if L["kind"] not in LINE_KINDS:
            raise StageError(f"줄 {L.get('id')} kind '{L['kind']}' 모름 — {LINE_KINDS}")
        t += gap_between(st, prev, L["kind"])
        if L["kind"] == "sub":          # 나레 없는 자막 줄 — 자막 시간표(dur·s0)만, 소리 없음
            d = round(float(L["dur"]), 3)
            lines[L["id"]] = [round(t, 3), round(t + d, 3)]
            starts = sub_cap_starts(L, d)
            caps = caps_of(L)
            for j, c in enumerate(caps):
                a = t + starts[j]
                b = t + (starts[j + 1] if j + 1 < len(caps) else d)
                rows.append({"line": L["id"], "j": j, "speaker": "narr", "text": c["text"], "t0": round(a, 3), "t1": round(b, 3),
                             **{k: c[k] for k in CAP_EXTRA if c.get(k)}})
            t += d
        elif L["kind"] == "orig":
            t0 = t
            sp = spans_of(L)
            h, tl = orig_edges(Path(M["cand_dir"]) / L["src"], sp) if M.get("cand_dir") else (0.0, 0.0)
            if h or tl:            # 줄 사이 '소리 쉼' = 판 timing — 원음 조각 앞뒤 무음은 빼고 붙인다(관제263 B18: 잘라 온 구간 끝 무음 0.59초가 쉼에 얹혔다)
                sp[0][0] = round(sp[0][0] + h, 3)
                sp[-1][1] = round(sp[-1][1] - tl, 3)
                orig_trim[L["id"]] = h
            for k, (a, b) in enumerate(sp):
                opos.append({"line": L["id"], "k": k, "src": L["src"], "span": [a, b], "t0": round(t, 3), "t1": round(t + b - a, 3)})
                t += b - a
            lines[L["id"]] = [round(t0, 3), round(t, 3)]
            for j, c in enumerate(caps_of(L)):
                c0, c1 = max(0.0, c["s0"] - h), min(t - t0, max(0.0, c["s1"] - h))
                rows.append({"line": L["id"], "j": j, "speaker": "orig", "text": c["text"], "t0": round(t0 + c0, 3), "t1": round(t0 + c1, 3),
                             **{k: c[k] for k in CAP_EXTRA if c.get(k)}})
        else:
            s = (sent or {}).get(L["id"])
            d = s["dur"] if s else round(nchar(L["tts"]) / est, 3)
            lines[L["id"]] = [round(t, 3), round(t + d, 3)]
            starts = narr_cap_starts(L, s, align, char0)
            caps = caps_of(L)
            for j, c in enumerate(caps):
                a = t + starts[j]
                b = t + (starts[j + 1] if j + 1 < len(caps) else d)
                rows.append({"line": L["id"], "j": j, "speaker": "narr", "text": c["text"], "t0": round(a, 3), "t1": round(b, 3),
                             **{k: c[k] for k in CAP_EXTRA if c.get(k)}})
            char0 += nchar(L["tts"])
            t += d
        prev = L["kind"]
    end = round(t + (st.get("timing") or {}).get("tail", 0.35), 3)
    end = round(round(end * FPS) / FPS, 4)
    order = [L["id"] for L in S["lines"]]
    Lm = {L["id"]: L for L in S["lines"]}
    cuts, log_drop = [], []
    for i, lid in enumerate(order):
        a = lines[lid][0]
        nxt = lines[order[i + 1]][0] if i + 1 < len(order) else end
        L = Lm[lid]
        cs = (M.get("cuts") or {}).get(lid)
        if L["kind"] == "orig":
            if not cs:
                cs = [{"at": round(p["t0"] - a, 3), "src": p["src"], "ss": p["span"][0], "crop": "face", "see": "원음 구간(자동 얼굴 크롭)"}
                      for p in opos if p["line"] == lid]
            h = orig_trim.get(lid, 0.0)
            if h and (M.get("cuts") or {}).get(lid):      # 손 컷(at 은 잘라 오기 전 줄 시작 기준) → 앞 무음 뺀 만큼 당기고, 0 밑으로 가면 ss 를 그만큼 뒤로(입 맞춤)
                L_len = lines[lid][1] - a
                moved = []
                for c in cs:
                    if "at" not in c:
                        moved.append(c); continue
                    at = float(c["at"]) - h
                    c = {**c, "at": round(max(0.0, at), 3)}
                    if at < 0 and c.get("ss") is not None:
                        c["ss"] = round(float(c["ss"]) - at, 3)
                    if at >= L_len - 1 / FPS:                 # 뺀 끝 무음 안에서만 보이던 컷 — 빼고 기록
                        log_drop.append((lid, c.get("src"), c.get("ss"), round(at, 3)))
                        continue
                    moved.append(c)
                head = [c for c in moved if "at" in c and c["at"] <= 0.0]
                cs = ([head[-1]] if head else []) + [c for c in moved if not ("at" in c and c["at"] <= 0.0)]
            for c in cs:
                if "at" not in c and c.get("ss") is not None:   # ss 만 적은 컷 = 원음 초 → 그 초가 들리는 줄 안 시각(입 맞춤 그대로, 10-23 꿀템노트 재료)
                    p = next((p for p in opos if p["line"] == lid and p["span"][0] - 1e-3 <= float(c["ss"]) < p["span"][1]), None)
                    c = {**c, "at": round(p["t0"] - a + float(c["ss"]) - p["span"][0], 3) if p else 0.0}
                c0 = a + float(c.get("at", 0.0))
                ss = c.get("ss")
                if ss is None:      # 입 맞춤: 그 시각에 들리는 원음 조각의 원본 초
                    p = next((p for p in opos if p["line"] == lid and p["t0"] - 1e-3 <= c0 < p["t1"]), None)
                    if not p:
                        raise StageError(f"{lid} 컷 at {c.get('at')} 가 원음 조각 밖")
                    ss = round(p["span"][0] + (c0 - p["t0"]), 3)
                cuts.append({**c, "line": lid, "ss": ss, "src": c.get("src", L["src"]), "t0": round(c0, 3), "kind": "orig"})
        else:
            if not cs:
                raise StageError(f"재료.json cuts 에 나레 줄 {lid} 컷이 없다")
            ws = [float(c.get("w", 1)) for c in cs]
            acc = 0.0
            for c, w in zip(cs, ws):
                if "cap" in c:        # 자막 덩어리 j 가 뜨는 순간에 컷(자막 한 덩어리 = 컷 하나 — 두유노 벤치 cut_eq_sub 94%, 10-26 material_bank)
                    hit = [r["t0"] for r in rows if r["line"] == lid and r["j"] == int(c["cap"])]
                    if not hit:
                        raise StageError(f"{lid} 컷 cap {c['cap']} — 그 줄에 자막 덩어리 {c['cap']} 이 없다")
                    c0 = hit[0]
                else:
                    c0 = a + float(c["at"]) if "at" in c else a + (nxt - a) * acc / sum(ws)
                cuts.append({**c, "line": lid, "t0": round(c0, 3), "kind": "tts"})
                acc += w
    cuts[0]["t0"] = 0.0
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    if src_dir:
        fit_lip_edges(cuts, src_dir, end, {k: v.get("src") for k, v in Lm.items()})
    line_src = {k: v.get("src") for k, v in Lm.items()}

    def fit_all(reach: float = 0.4):
        for i, c in enumerate(cuts):
            c["t1"] = cuts[i + 1]["t0"] if i + 1 < len(cuts) else end
            c["dur"] = round(c["t1"] - c["t0"], 3)
            lip = c["kind"] == "orig" and c["src"] == Lm[c["line"]].get("src")      # 입 맞춤 = 원음 줄의 그 원본 화면 — 원음 줄 안에 끼운 다른 원본 컷(소리와 무관)은 나레 컷처럼 맞춘다(10-26 회원 마스크편 L7)
            if src_dir and not lip and c.get("ss") is not None and not c.get("no_snap"):
                if c.get("max") is None and "ss_planned" not in c:
                    shot_cap(c, src_dir / c["src"])
                base = float(c.get("ss_planned", c["ss"]))                         # 다시 맞출 때도 재료에 적힌 ss·max 기준(옮긴 ss 에 max 를 다시 붙이면 샷 끝을 넘는다)
                s2, k = fit_cut(src_dir / c["src"], base, round(c["t1"] * FPS) - round(c["t0"] * FPS), c.get("max"), reach)   # 실제 뽑을 프레임 수로 — 옮기기·샷 안 늦추기 주인      # 원음 컷은 입 맞춤이라 옮기지도 늦추지도 않는다(검사만)
                c.pop("speed", None)
                if s2 != base:
                    c["ss_planned"], c["ss"] = base, s2
                if k < 1.0:
                    c["speed"] = k
    fit_all()
    if src_dir:              # 그래도 남은 짧은 조각 = 계획이 스스로 끝낸다(관문 ③에 보내 Claude 가 초를 고치게 하지 않는다 — 10-26 까르보 '경계 맞추는 중' 22번)
        settle_edges(cuts, src_dir, end, line_src, fit_all)
    for i, c in enumerate(cuts):
        lip = c["kind"] == "orig" and c["src"] == Lm[c["line"]].get("src")
        sd = round(src_frames(c) / FPS, 3)                        # 원본에서 쓰는 초 = 뽑을 프레임 × 속도(늦춘 컷은 짧다) — fit_cut·관문 ③과 같은 프레임 셈
        cap = None if (c.get("max") is None or lip) else float(c["max"]) - (float(c["ss"]) - float(c.get("ss_planned", c["ss"])))   # max = 재료에 적힌 ss 기준 — 옮긴 만큼 뺀다
        # 원음(입 맞춤) 컷은 원본 사람이 말하는 구간 그대로 — 그 안에 원본 자체 카메라 전환이 드는 건 원본 편집이 흐르는 것(샷 한도 아님).
        # 번쩍임(짧은 조각)은 관문 ③(edge_fault)·원본 끝은 src_left 가 따로 본다(10-27 립글로스 회원편 O1 2.76초 vs 샷 0.53초 반려 — 맞출 수 없는 반려)
        c["over"] = round(sd - cap, 3) if cap is not None and sd > cap + 1e-3 else 0.0
        if c["over"] and c.get("max_auto") and src_dir:      # 샷이 모자란 재료 컷 — 고칠 자리(이 길이가 들어가는 샷)를 같이 싣는다
            c["room"] = shot_room(src_dir / c["src"], round(sd / _max_slowmo(), 2))
        if src_dir:
            left = src_left(src_dir / c["src"], float(c.get("ss") or 0.0))
            if left is not None and sd > left + 1e-3:
                c["src_left"] = left
                c["over"] = max(c["over"], round(sd - left, 3))
    if src_dir:              # B13(같은 원본 가까운 구간) — 계획이 처음부터 피한다(주인 material_fit.respace_reuse, 판정 = quality_gate.reuse_violations_bench)
        from tools.calcopy.hybrid.material_fit import respace_reuse
        respace_reuse(cuts, src_dir, log=lambda m: sys.stderr.write(m + "\n"), adjacent_run=bool((st.get("reuse") or {}).get("adjacent_run")))   # 판 칸 reuse.adjacent_run(두유노판 — 사장님 10-26 '가')
    for i, r in enumerate(rows):      # 자막은 다음 덩어리 시작까지(줄 사이 틈도 앞 자막이 덮는다 — 벤치: 자막 없는 틈 거의 없음)
        r["show"] = [r["t0"], round(rows[i + 1]["t0"] if i + 1 < len(rows) else end, 3)]
    out = {"lines": lines, "rows": rows, "cuts": cuts, "opos": opos, "end": end}
    if orig_trim or log_drop:
        out["orig_trim"] = {"head": orig_trim, "dropped_cuts": log_drop}
    return out


# ── 줄 사이 쉼·문장부호 쉼(판단 주인 — 판 timing·speech 를 소리에 맞춘다, 관제263 B18/B18a) ─────────────
EDGE_NOISE, EDGE_MIN = "-35dB", 0.02      # 무음 판정 = 품질 관문 B18 과 같은 문턱(-35dB) · 앞뒤 무음은 0.02초부터 본다
EDGE_KEEP = 0.015                         # 말 앞뒤에 남기는 숨(초) — 0이면 자음 첫소리가 깎인다. 줄 사이 실측 쉼 = 판 gap + 2×이 값
_EDGE_CACHE: dict = {}


def pause_targets(st: dict) -> dict:
    """한 줄 안 문장부호 쉼 목표(초) — 판 speech.pause_comma/period, 없으면 표준 §11 ①ⓑ 0.22/0.30. 렌더(fit_voice)·관문(B18a)이 같이 부른다."""
    sp = st.get("speech") or {}
    return {"comma": float(sp.get("pause_comma", 0.22)), "period": float(sp.get("pause_period", 0.30))}


EDGE_BLIP = 0.05      # 줄 조각 맨 앞·뒤 이 안의 짧은 소리(앞 줄 꼬리·자르기 딸깍)는 무음 판정에서 무음으로 친다(10-25 박정수 N7: 0.02초 소리 뒤 무음 0.18초 ·
                      # 10-27 TV 스탠드 L2: 앞 줄 꼬리 0.044초 뒤 무음 0.18초가 안 깎여 B18 L1→L2 0.11초(계획 0.04) — 0.03 → 0.05. 다른 줄 첫 무음은 0.08초 뒤라 영향 없음)


def _edge_sil(sil: list, total: float) -> tuple[float, float]:
    head = next((e for a, e in sil if a <= EDGE_BLIP), 0.0)
    tail = next((total - a for a, e in reversed(sil) if e >= total - EDGE_BLIP), 0.0)
    return max(0.0, head - EDGE_KEEP), max(0.0, tail - EDGE_KEEP)


def orig_edges(src: Path, spans: list) -> tuple[float, float]:
    """원음 줄(조각들)의 맨 앞 무음·맨 뒤 무음 중 뺄 초(EDGE_KEEP 남김). 원본이 없거나 소리가 늘 깔려 무음이 안 잡히면 0(안 자른다)."""
    import subprocess
    from tools.calcopy.hybrid.common import silences
    if not Path(src).exists() or not spans:
        return 0.0, 0.0
    out = []
    for (a, b), which in ((spans[0], 0), (spans[-1], 1)):
        key = (str(src), round(a, 3), round(b, 3), Path(src).stat().st_mtime)
        if key not in _EDGE_CACHE:
            tmp = Path(src).parent / f"_edge_{Path(src).stem}_{int(a * 1000)}_{int(b * 1000)}.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src), "-vn", "-ac", "1", "-ar", str(SR),
                            "-af", "highpass=f=90", str(tmp)], capture_output=True, stdin=subprocess.DEVNULL)
            if not tmp.exists():
                _EDGE_CACHE[key] = (0.0, 0.0)
            else:
                _EDGE_CACHE[key] = _edge_sil(silences(tmp, EDGE_NOISE, EDGE_MIN), b - a)
                tmp.unlink(missing_ok=True)
        out.append(_EDGE_CACHE[key][which])
    h, tl = out
    if spans[0][1] - spans[0][0] - h < 0.2 or spans[-1][1] - spans[-1][0] - tl < 0.2:     # 남는 소리가 너무 짧으면 무음 판정을 믿지 않는다
        return 0.0, 0.0
    return round(h, 3), round(tl, 3)


def fit_voice(S: dict, st: dict, sent: list, align: dict | None, log=print) -> list:
    """나레 줄 소리(s_<줄>.wav)를 판에 맞춘다 — ① 앞뒤 무음을 EDGE_KEEP 만 남기고 뺀다(줄 사이 '소리 쉼' = 판 timing.gap 이 되게 — 판 gap 은 벤치 소리 쉼 실측)
    ② 줄 안 쉼표·마침표 자리 무음을 pause_targets(판 speech) 길이로(길면 가운데를 자르고, 짧으면 그 무음 가운데를 이어 늘린다 — 디지털 무음 금지).
    자리 = 글자 시각(align) → 줄 소리 시각(make_sentences 와 같은 x0·배속). 손 쉼(tts_pauses)·대체 소리(tts_override) 줄은 ②를 건너뛴다.
    반환 sent(dur·tmap 갱신) — tmap = [(고치기 전 시각, 고친 뒤 시각)] → narr_cap_starts 가 자막 시작을 옮긴다."""
    import subprocess
    import wave
    import numpy as np
    from tools.calcopy.hybrid.common import silences
    th = pause_targets(st)
    L = {l["id"]: l for l in S["lines"] if l["kind"] == "tts"}
    order = [l["id"] for l in S["lines"] if l["kind"] == "tts"]
    char0, pos = {}, 0
    for i in order:
        char0[i] = pos
        pos += len(L[i]["tts"]) + 1
    P = S.get("tts_pauses") or {}
    xf = int(0.005 * SR)
    logs = []
    for s in sent:
        p = Path(s["wav"])
        x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True,
                                         stdin=subprocess.DEVNULL).stdout, np.float32).copy()
        total = len(x) / SR
        sil = silences(p, EDGE_NOISE, EDGE_MIN)
        hc, tc = _edge_sil(sil, total)
        regs = []                                   # (시작초, 끝초, 새 길이초, 종류)
        if hc > 0:
            regs.append((0.0, hc, 0.0, "head"))
        inner_log = []
        l = L.get(s["id"])
        if l and align and not P.get(s["id"]) and not s.get("override"):
            ch, a0, e0 = align["characters"], align["character_start_times_seconds"], align["character_end_times_seconds"]
            body = l["tts"].rstrip(" .,?!~…")
            x0 = max(0.0, s["raw"][0] - 0.02)
            inner = [(a, b) for a, b in sil if a > EDGE_BLIP and b < total - EDGE_BLIP]
            for i, c in enumerate(body):
                if c not in ",.?!":
                    continue
                kind = "comma" if c == "," else "period"
                g = char0[s["id"]] + i
                j, k = g - 1, g + 1
                while j >= 0 and (ch[j].isspace() or ch[j] in ",.?!"):
                    j -= 1
                while k < len(ch) and (ch[k].isspace() or ch[k] in ",.?!"):
                    k += 1
                if j < 0 or k >= len(ch):
                    continue
                m = ((float(e0[j]) + float(a0[k])) / 2 - x0) / s["tempo"]
                near = min(inner, key=lambda r: abs((r[0] + r[1]) / 2 - m), default=None)
                if not near or abs((near[0] + near[1]) / 2 - m) > 0.15:      # 그 자리에 무음이 없다(쉼 없이 읽음) — 글자 사이 가장 조용한 10ms 에 쉼을 넣는다(engine/tts_pause 와 같은 규칙)
                    w = int(0.01 * SR)
                    c0 = max(w, int((m - 0.06) * SR)); c1 = min(len(x) - w, int((m + 0.06) * SR))
                    if c1 <= c0:
                        continue
                    e = [float(np.mean(x[i:i + w] ** 2)) for i in range(c0, c1, w // 2)]
                    at = (c0 + int(np.argmin(e)) * (w // 2) + w // 2) / SR
                    regs.append((at, at, th[kind] + 0.005, kind))
                    inner_log.append({"kind": kind, "at": round(m, 3), "was": 0.0, "now": th[kind], "insert": round(at, 3)})
                    continue
                regs.append((near[0], near[1], th[kind] + 0.005, kind))
                inner_log.append({"kind": kind, "at": round(m, 3), "was": round(near[1] - near[0], 3), "now": th[kind]})
        if tc > 0:
            regs.append((total - tc, total, 0.0, "tail"))
        regs = sorted(regs)
        if not regs:
            logs.append({"id": s["id"], "head": 0.0, "tail": 0.0, "inner": inner_log, "dur": [s["dur"], s["dur"]]})
            continue
        out, tmap, last, tn = [], [(0.0, 0.0)], 0, 0.0
        for a, b, want, kind in regs:
            i0, i1 = int(round(a * SR)), int(round(b * SR))
            if i0 < last:
                continue
            out.append(x[last:i0]); tn += (i0 - last) / SR
            tmap.append((a, tn))
            gap = x[i0:i1]
            n = int(round(want * SR))
            if kind in ("head", "tail"):
                ng = gap[:0]
            elif n <= len(gap):
                h = n // 2
                ng = np.concatenate([gap[:h], gap[len(gap) - (n - h):]]) if n else gap[:0]
                if h > xf and len(gap) - (n - h) - xf >= h:            # 이음매 5ms 겹침(딸깍 소리 방지)
                    r = np.linspace(0, 1, xf, dtype=np.float32)
                    ng[h - xf:h] = ng[h - xf:h] * (1 - r) + gap[len(gap) - (n - h) - xf:len(gap) - (n - h)] * r
            else:
                core = gap[len(gap) // 4: 3 * len(gap) // 4]
                if len(core) < int(0.02 * SR) or (len(core) and float(np.max(np.abs(core))) > 0.01):     # 틈이 없거나 말 꼬리가 섞임 → 방 잡음(가장 조용한 40ms, 디지털 무음 금지)
                    rw = int(0.04 * SR)
                    en = [float(np.mean(x[i:i + rw] ** 2)) for i in range(0, max(1, len(x) - rw), rw // 4)]
                    i_q = int(np.argmin(en)) * (rw // 4)
                    core = x[i_q:i_q + rw] if len(x) >= rw else np.zeros(rw, np.float32)
                fill = np.tile(core, int(np.ceil((n - len(gap)) / max(1, len(core)))) + 1)[:n - len(gap)]
                h = len(gap) // 2
                ng = np.concatenate([gap[:h], fill, gap[h:]])
            out.append(ng); tn += len(ng) / SR
            tmap.append((b, tn))
            last = i1
        out.append(x[last:]); tn += (len(x) - last) / SR
        tmap.append((total, tn))
        y = np.concatenate(out)
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
        s["dur_before_fit"], s["dur"] = s["dur"], round(len(y) / SR, 3)
        s["tmap"] = [(round(a, 4), round(b, 4)) for a, b in tmap]
        logs.append({"id": s["id"], "head": round(hc, 3), "tail": round(tc, 3), "inner": inner_log, "dur": [s["dur_before_fit"], s["dur"]]})
    log("[쉼 맞춤] " + " ".join(f"{g['id']}:앞{g['head']}·뒤{g['tail']}" + "".join(f"·{'.' if q['kind'] == 'period' else ','}{q['was']}→{q['now']}" for q in g["inner"]) for g in logs))
    return sent


# ── 틀 그림(판단 주인: 판 설정 frame) ─────────────────────────────────────
FRAME_KINDS = ("window", "post", "full")      # 표준 §3-3 B1 — frame.kind 하나로 갈린다(채널 이름 분기 없음)


def frame_kind(F: dict) -> str:
    k = F.get("kind") or "window"
    if k not in FRAME_KINDS:
        raise StageError(f"frame.kind '{k}' 모름 — {FRAME_KINDS}")
    return k


def frame_window(F: dict) -> list[int]:
    """영상 창 [x,y,w,h] 한 곳 — full = 화면 전체(창 칸을 안 적어도 된다), 그 밖 = frame.window."""
    from tools.calcopy.hybrid import styles as _STY
    frame_kind(F)                                   # 모르는 kind 는 여기서 멈춘다
    return _STY.frame_window(F)


def _glow(lay, G: dict):
    """글자 층 둘레 번짐(네온·글로우) — G{px(번짐 반지름), color, strength(진하기 배수, 기본 1)}. 층 크기 그대로(여백은 부른 쪽이 둔다).
    머리띠 채널 글·로고가 쓴다(관제 263 02 2차 ⑦ — 손 스크립트 make_썰템홈샷 민트 네온·make_맛템썰템 크림골드 네온 자리)."""
    from PIL import Image, ImageFilter
    a = lay.getchannel("A").filter(ImageFilter.GaussianBlur(float(G["px"])))
    k = float(G.get("strength", 1.0))
    if k != 1.0:
        a = a.point(lambda v: min(255, int(v * k)))
    g = Image.new("RGBA", lay.size, _rgb(G["color"]) + (255,))
    g.putalpha(a)
    return Image.alpha_composite(g, lay)


def _spaced(dl, xy, text, f, ls: float, **kw) -> float:
    """글을 그린다 — ls(자간 px, 글자 사이 더 띄우기)가 0 이면 한 번에(옛 그림 그대로), 아니면 글자마다. 반환 = 그린 폭(끝 자간 뺌)."""
    if not ls:
        dl.text(xy, text, font=f, **kw)
        return f.getlength(text)
    x = xy[0]
    for ch in text:
        dl.text((x, xy[1]), ch, font=f, **kw)
        x += f.getlength(ch) + ls
    return x - xy[0] - (ls if text else 0)


def _text_w(f, text: str, ls: float) -> float:
    return f.getlength(text) + (ls * (len(text) - 1) if ls and text else 0)


def _draw_text(im, T: dict, text: str):
    """한 줄 글(게시글 작성자·조회수·본문·머리띠 채널 글): font·px·color · x(왼쪽 x) 또는 cx(가운데 x) · cy(잉크 가운데 y) 또는 ink_top ·
    word_spacing(어절 사이 더 띄우기 px) · letter_spacing(글자 사이 px, 음수 = 좁힘) · max_w(넘치면 px 줄임) ·
    선택 stroke{px,color}(외곽선) · glow{px,color,strength}(번짐). 자리(x·cx·cy·ink_top)는 글자 잉크 기준 — 번짐은 밖으로 붙는다."""
    from PIL import Image, ImageDraw
    if not text:
        return
    px = float(T["px"])
    ws = float(T.get("word_spacing", 0))
    ls = float(T.get("letter_spacing", 0))
    words = text.split(" ")
    while True:
        f = _font(T["font"], px)
        sp = f.getlength(" ") + ws + (2 * ls if ls else 0)
        tw = sum(_text_w(f, w_, ls) for w_ in words) + sp * (len(words) - 1)
        if tw <= T.get("max_w", W) or px <= 20:
            break
        px -= 2
    asc, desc = f.getmetrics()
    SK, G = T.get("stroke") or {}, T.get("glow")
    sw = int(SK.get("px", 0))
    pad = 4 + sw + (int(math.ceil(3 * float(G["px"]))) if G else 0)       # 칸 없으면 4 = 옛 그림 그대로
    lay = Image.new("RGBA", (int(tw) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    xx = pad
    col = _rgb(T.get("color", "#000000")) + (255,)
    kw = {"fill": col, **({"stroke_width": sw, "stroke_fill": _rgb(SK.get("color", "#000000")) + (255,)} if sw else {})}
    for w_ in words:
        _spaced(dl, (xx, pad), w_, f, ls, **kw)
        xx += _text_w(f, w_, ls) + sp
    bb = lay.getbbox()
    if not bb:
        return
    if G:
        lay = _glow(lay, G)
        gb = lay.getbbox()
        lay = lay.crop(gb)
        off = (gb[0] - bb[0], gb[1] - bb[1])          # 자리는 잉크 기준 — 번짐만큼 비켜 붙인다
        iw, ih = bb[2] - bb[0], bb[3] - bb[1]
    else:
        lay = lay.crop(bb)
        off = (0, 0)
        iw, ih = lay.size
    left = int(T["x"]) if "cx" not in T else int(T["cx"]) - iw // 2
    top = int(T["ink_top"]) if "ink_top" in T else int(T["cy"]) - ih // 2
    im.alpha_composite(lay, (left + off[0], top + off[1]))


def _draw_rect(im, box, color, fade=None, radius=0):
    """[x0,y0,x1,y1](끝 제외) 채움 — fade [위 px, 아래 px] = 그 폭만큼 위·아래 끝이 투명→불투명(게시글 본문 상자 번짐) · radius 둥근 모서리."""
    from PIL import Image, ImageDraw
    import numpy as np
    x0, y0, x1, y1 = (int(v) for v in box)
    lay = Image.new("RGBA", (x1 - x0, y1 - y0), _rgb(color) + (255,))
    a = np.full((y1 - y0, x1 - x0), 255, np.uint8)
    if fade:
        col = np.full((y1 - y0,), 255.0)
        ft, fb = int(fade[0]), int(fade[1])
        if ft:
            col[:ft] = np.linspace(0, 255, ft, endpoint=False)
        if fb:
            col[-fb:] = np.linspace(255, 0, fb, endpoint=False)
        a = np.repeat(col.astype(np.uint8)[:, None], x1 - x0, axis=1)
    if radius:
        m = Image.new("L", lay.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, lay.size[0] - 1, lay.size[1] - 1], radius=int(radius), fill=255)
        a = (a.astype(np.uint16) * np.asarray(m, np.uint16) // 255).astype(np.uint8)
    lay.putalpha(Image.fromarray(a, "L"))
    im.alpha_composite(lay, (x0, y0))


def _paste_image(im, src, x, y, w, h):
    """그림 한 장(PNG 투명 그대로)을 [x,y,w,h] 에 늘려 붙인다 — 머리띠 그림 아이콘(관제 263 02 2차 ⑦). src = 저장소 상대 또는 절대 경로."""
    from PIL import Image
    p = Path(src)
    p = p if p.is_absolute() else ROOT / p
    if not p.exists():
        raise StageError(f"그림 아이콘 파일 없음: {p}")
    m = Image.open(p).convert("RGBA").resize((int(w), int(h)), Image.LANCZOS)
    im.alpha_composite(m, (int(x), int(y)))


def _draw_post(im, P: dict, S: dict):
    """게시글형 틀(B1): head_bar{box,color,icons[bars|search|text]} · rules[{box,color}](가는 줄) · author_line ·
    body_box{box,color,fade,radius,rules,text} · views_line · meme_slot{box[x,y,w,h]}.
    글은 대본 post{brand,author,body,views,meme} 가 있으면 그것, 없으면 판 칸 text."""
    from PIL import Image, ImageDraw
    SP = S.get("post") or {}
    HB = P.get("head_bar")
    if HB:
        _draw_rect(im, HB["box"], HB["color"])
        d = ImageDraw.Draw(im)
        for ic in HB.get("icons") or []:
            col = _rgb(ic.get("color", "#000000"))
            if ic["kind"] == "bars":        # 메뉴(가로 막대 여러 개)
                for yy in ic["ys"]:
                    d.rectangle([ic["x"], yy, ic["x"] + ic["w"] - 1, yy + ic["h"] - 1], fill=col)
            elif ic["kind"] == "search":    # 돋보기(고리 + 손잡이) — 84px 기준 꼴(설명서 frame.json 아이콘과 같은 비율)
                k = ic["size"] / 84.0
                sw = max(1, int(round(ic.get("stroke", 7) * k)))
                cx, cy, r = ic["x"] + 34 * k, ic["y"] + 34 * k, 28 * k
                d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=sw)
                d.line([ic["x"] + 54 * k, ic["y"] + 54 * k, ic["x"] + 80 * k, ic["y"] + 80 * k], fill=col, width=sw)
            elif ic["kind"] == "text":      # 머리띠 안 채널 글(브랜드) — stroke·glow 칸이면 외곽선·네온
                _draw_text(im, ic, SP.get(ic.get("from", "brand")) or ic.get("text"))
            elif ic["kind"] == "image":     # 그림 아이콘(화살표·포크 접시 등 글꼴에 없는 꼴) — src 를 [x,y,w,h] 에 붙인다
                _paste_image(im, ic["src"], ic["x"], ic["y"], ic["w"], ic["h"])
            else:
                raise StageError(f"머리띠 아이콘 kind '{ic['kind']}' 모름 — bars·search·text·image")
    for r in P.get("rules") or []:
        _draw_rect(im, r["box"], r["color"])
    BB = P.get("body_box")
    if BB:
        _draw_rect(im, BB["box"], BB["color"], BB.get("fade"), BB.get("radius", 0))
        for r in BB.get("rules") or []:
            _draw_rect(im, r["box"], r["color"])
        if BB.get("text"):
            _draw_text(im, BB["text"], SP.get("body") or BB["text"].get("text"))
    for key, sk in (("author_line", "author"), ("views_line", "views")):
        if P.get(key):
            _draw_text(im, P[key], SP.get(sk) or P[key].get("text"))
    MS = P.get("meme_slot")
    if MS and SP.get("meme") and Path(SP["meme"]).exists():      # 반응 짤 자리(채워 자르기)
        x, y, w, h = MS["box"]
        m = Image.open(SP["meme"]).convert("RGBA")
        s = max(w / m.size[0], h / m.size[1])
        m = m.resize((max(1, round(m.size[0] * s)), max(1, round(m.size[1] * s))), Image.LANCZOS)
        l, t = (m.size[0] - w) // 2, (m.size[1] - h) // 2
        im.alpha_composite(m.crop((l, t, l + w, t + h)), (x, y))


def _draw_full(im, FL: dict | None):
    """전체화면 틀(B1): 창 = 화면 전체, 위에 얹는 것은 가운데 자막 띠(선택) — band{cy,h,rgba}."""
    from PIL import Image
    B = (FL or {}).get("band")
    if B:
        im.alpha_composite(Image.new("RGBA", (W, int(B["h"])), tuple(B["rgba"])), (0, int(B["cy"]) - int(B["h"]) // 2))


TITLE_ALIGNS = ("center", "left", "right")


def _title_line(im, spec: dict, segs):
    """제목 한 줄(낱말 색·기울임·박스) 한 곳 — 선택 칸 stroke{px,color}·shadow{dx,dy,color}(게시글형 제목 외곽선·그림자) ·
    align(center 기본|left|right) + x(left = 왼쪽 끝 x · right = 오른쪽 끝 x · center = 가운데 x, 기본 화면 가운데) · letter_spacing(글자 사이 px).
    칸이 없으면 외곽선 0·그림자 없음·가운데·자간 0 = 옛 그림과 같은 픽셀(회귀 검사 대상)."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(im)
    segs = [(s, None) if isinstance(s, str) else (s[0], s[1] if len(s) > 1 else None) for s in segs]
    col = lambda c: _rgb(spec["hi"]) if c == "hi" else (_rgb(c) if c else _rgb(spec["color"]))
    al = spec.get("align", "center")
    if al not in TITLE_ALIGNS:
        raise StageError(f"제목 align '{al}' 모름 — {TITLE_ALIGNS}")
    ls = float(spec.get("letter_spacing", 0))
    px = spec["px"]
    while True:
        f = _font(spec["font"], px)
        tw = sum(f.getlength(t) for t, _ in segs) + (ls * (sum(len(t) for t, _ in segs) - 1) if ls else 0)
        if tw <= spec.get("max_w", 1000) or px <= 50:
            break
        px -= 2
    asc, desc = f.getmetrics()
    SK, SH = spec.get("stroke") or {}, spec.get("shadow")
    sw = int(SK.get("px", 0))
    pad = int(px * 0.5) + sw + (max(abs(SH["dx"]), abs(SH["dy"])) if SH else 0)
    sh = float(spec.get("shear") or 0)
    lay = Image.new("RGBA", (int(tw) + 2 * pad + int((asc + desc) * sh), asc + desc + 2 * pad), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    x0 = pad + int((asc + desc) * sh * 0.5)
    if SH:
        xx = x0
        for t, c in segs:
            xx += _spaced(dl, (xx + SH["dx"], pad + SH["dy"]), t, f, ls, fill=_rgb(SH["color"]) + (255,), stroke_width=sw,
                          stroke_fill=_rgb(SH["color"]) + (255,)) + (ls if ls and t else 0)
    xx = x0
    for t, c in segs:
        xx += _spaced(dl, (xx, pad), t, f, ls, fill=col(c) + (255,), stroke_width=sw,
                      stroke_fill=_rgb(SK.get("color", "#000000")) + (255,)) + (ls if ls and t else 0)
    if sh:
        lay = lay.transform(lay.size, Image.AFFINE, (1, sh, -sh * lay.size[1] * 0.5, 0, 1, 0), resample=Image.BICUBIC)
    lay = lay.crop(lay.getbbox())
    if spec.get("box"):
        bx = spec["box"]
        d.rectangle(bx, fill=_rgb(spec["box_color"]) + (255,))
        top = (bx[1] + bx[3]) // 2 - lay.size[1] // 2
    elif "center" in spec:
        top = spec["center"] - lay.size[1] // 2
    else:
        top = spec["ink_top"]
    if al == "left":
        left = int(spec["x"])
    elif al == "right":
        left = int(spec["x"]) - lay.size[0]
    else:
        left = int(spec.get("x", W // 2)) - lay.size[0] // 2
    im.alpha_composite(lay, (left, int(top)))


def _seg_time(v, S: dict, T: dict) -> float:
    """구간 끝 시각: 숫자(초) · '<줄 id>.start|end' · '#<k>.start|end'(k번째 줄, 1부터)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = re.fullmatch(r"(#?)([^.]+)\.(start|end)", str(v))
    if not m:
        raise StageError(f"frame.segments 시각 '{v}' 모름 — 초 · '<줄id>.start|end' · '#k.start|end'")
    ids = [L["id"] for L in S["lines"]]
    lid = ids[int(m.group(2)) - 1] if m.group(1) else m.group(2)
    if lid not in T["lines"]:
        raise StageError(f"frame.segments 줄 '{lid}' 이 대본에 없다")
    a, b = T["lines"][lid]
    return a if m.group(3) == "start" else b


SEG_CAPTIONS = ("show", "hide")


def frame_segments(S: dict, T: dict, st: dict) -> list[dict]:
    """시간 구간별 틀(관제 263 02 2차 ①) — 판 칸 frame.segments[{t0, t1, frame{…덮을 칸}, captions show|hide, body_text lines|null, why}].
    구간 밖은 판 frame 그대로, 구간 안은 frame 에 구간 frame 을 깊게 덮은 틀(kind·window·title… 전부 바꿀 수 있다 — 훅 카드 → 본문 틀, A/B 하이브리드).
    body_text=lines = 그 구간에서 시작하는 나레·자막 줄 글을 게시글 본문(post.body) 자리에 — 훅 카드 가운데 흰 띠 나레 문장.
    captions=hide = 그 구간 자막팩 자막을 그리지 않는다(훅 카드 띠가 자막을 대신). 시각은 프레임 격자에 맞춘다. 겹치면 멈춘다.
    판단 주인 = 이 함수 하나(render_base·caption_rows·devices 가 이것만 읽는다)."""
    F = st.get("frame") or {}
    segs = F.get("segments") or []
    if not segs:
        return []
    from tools.calcopy.hybrid import styles as ST
    base = {k: v for k, v in F.items() if k != "segments"}
    end = T["end"]
    out = []
    for i, sg in enumerate(segs):
        t0 = _seg_time(sg.get("t0", 0.0), S, T)
        t1 = _seg_time(sg["t1"], S, T)
        t0 = round(round(max(0.0, t0) * FPS) / FPS, 4)
        t1 = round(round(min(end, t1) * FPS) / FPS, 4)
        if t1 <= t0:
            raise StageError(f"frame.segments[{i}] 길이 0 이하({t0}~{t1})")
        Fi = ST._merge(base, sg.get("frame") or {})
        frame_kind(Fi)
        cap = sg.get("captions", "show")
        if cap not in SEG_CAPTIONS:
            raise StageError(f"frame.segments[{i}].captions '{cap}' 모름 — {SEG_CAPTIONS}")
        bt = sg.get("body_text")
        text = None
        if bt == "lines":
            text = " ".join((L.get("tts") or " ".join(c["text"] for c in caps_of(L))).strip() for L in S["lines"]
                            if L["kind"] != "orig" and t0 - 1e-3 <= T["lines"][L["id"]][0] < t1 - 1e-3)
        elif bt is not None:
            raise StageError(f"frame.segments[{i}].body_text '{bt}' 모름 — lines 또는 비움")
        out.append({"i": i, "t0": t0, "t1": t1, "frame": Fi, "kind": frame_kind(Fi), "window": frame_window(Fi), "captions": cap,
                    "body_text": text, "why": sg.get("why")})
    out.sort(key=lambda g: g["t0"])
    for a, b in zip(out, out[1:]):
        if b["t0"] < a["t1"]:
            raise StageError(f"frame.segments 겹침: {a['t0']}~{a['t1']} · {b['t0']}~{b['t1']}")
    return out


def seg_frame_png(S: dict, st: dict, sg: dict, out: Path) -> Path:
    """구간 틀 한 장 — 구간 frame + (body_text 가 있으면) 대본 post.body 를 그 글로."""
    S2 = S if sg.get("body_text") is None else {**S, "post": {**(S.get("post") or {}), "body": sg["body_text"]}}
    return frame_png(S2, {**st, "frame": sg["frame"]}, out)


def title_segs(F: dict, S: dict) -> list:
    """틀 제목 줄 칸(frame.title[i]) ↔ 대본 title_lines 짝 한 곳. 칸에 join(이을 글, 예 " ")이 있으면 그 칸이 대본의 남은 줄을 전부 이어 한 줄로 그린다
    (게시글 본문 제목 = 훅 2줄을 한 줄로 — 07 2차 썰템홈샷판: 칸 1개라 1줄째만 나오던 것). join 없으면 옛 짝(i번째 칸 = i번째 줄) 그대로."""
    TL = S.get("title_lines") or []
    out = []
    for i, spec in enumerate(F.get("title") or []):
        if i >= len(TL):
            break
        if spec.get("join") is None:
            out.append(TL[i])
            continue
        segs = []
        for k, ln in enumerate(TL[i:]):
            if k:
                segs.append(str(spec["join"]))
            segs += list(ln)
        out.append(segs)
        break
    return out


def frame_png(S: dict, st: dict, out: Path) -> Path:
    """틀 한 장(창 자리는 투명). frame.kind = window(바탕 + 제목 줄들 + 로고 + 출처 + 워터마크, 기본) ·
    post(게시글형: 머리띠·작성자 줄·본문 상자·조회수 줄·짤 자리 + 같은 제목 줄·출처·로고) · full(전체화면 — 창 = 화면 전체, 가운데 자막 띠·제목·로고만)."""
    from PIL import Image, ImageDraw
    F = st["frame"]
    kind = frame_kind(F)
    im = Image.new("RGBA", (W, H), _rgb(F.get("bg", [0, 0, 0])) + (255,))
    x, y, w, h = frame_window(F)
    rad = int(F.get("window_radius") or 0) if kind != "full" else 0
    if rad:      # 둥근 창(관제 263 02 2차 ⑤) — 모서리는 틀 바탕이 덮는다. 4배로 그려 줄여 가장자리 부드럽게
        m = Image.new("L", (w * 4, h * 4), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=rad * 4, fill=255)
        im.paste(Image.new("RGBA", (w, h), (0, 0, 0, 0)), (x, y), m.resize((w, h), Image.LANCZOS))
    else:
        im.paste((0, 0, 0, 0), (x, y, x + w, y + h))
    if kind == "post":
        _draw_post(im, F.get("post") or {}, S)
    elif kind == "full":
        _draw_full(im, F.get("full"))
    d = ImageDraw.Draw(im)
    for spec, segs in zip(F.get("title") or [], title_segs(F, S)):
        _title_line(im, spec, segs)
    BD = F.get("band")                 # 맨 위 그림 띠(별헤는쏭 0~235 그림 — 로고 자리) {src, box[x,y,w,h]}
    if BD:
        p = Path(BD["src"]) if Path(BD["src"]).is_absolute() else ROOT / BD["src"]
        bx, by, bw, bh = BD["box"]
        im.alpha_composite(Image.open(p).convert("RGBA").resize((bw, bh), Image.LANCZOS), (bx, by))
    C = F.get("credit")
    if C and S.get("source_label") and not C.get("in_window"):
        f = _font(C["font"], C["px"])
        bb = d.textbbox((0, 0), S["source_label"], font=f)
        top = C["ink_top"] - bb[1] if "ink_top" in C else C["center"] - (bb[1] + bb[3]) // 2
        d.text((W // 2 - (bb[2] - bb[0]) // 2 - bb[0], top), S["source_label"], font=f, fill=_rgb(C["color"]))
    WM = F.get("watermark")
    if WM:
        f = _font(WM["font"], WM["px"])
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        bb = f.getbbox(WM["text"])
        dl.text((WM["x1"] - f.getlength(WM["text"]), WM["cy"] - (bb[1] + bb[3]) // 2), WM["text"], font=f, fill=(255, 255, 255, WM["alpha"]))
        im.alpha_composite(lay)
    LG = F.get("logo")
    if LG and LG.get("kind") == "spr_gold":
        sys.path.insert(0, str(ROOT / "channel/starpickroom/_tools"))
        import spr_overlay
        spr_overlay.logo_layer(im, LG["text"])
    elif LG:
        f = _font(LG["font"], LG["px"])
        G = LG.get("glow")              # 로고 번짐(네온) — {px,color,strength} · 외곽선 = stroke(px)·stroke_rgba
        mg = int(math.ceil(3 * float(G["px"]))) if G else 0
        lay = Image.new("RGBA", (W, 160 + 2 * mg), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((LG["x"], 10 + mg), LG["text"], font=f, fill=tuple(LG["rgba"]), stroke_width=LG.get("stroke", 0), stroke_fill=tuple(LG.get("stroke_rgba", [0, 0, 0, 255])))
        if G:
            lay = _glow(lay, G)
        im.alpha_composite(lay, (0, LG["y"] - 10 - mg))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def comment_png(C: dict, px: int, out: Path) -> tuple[int, int]:
    """유튜브 댓글 카드(꿀템노트 벤치 m0Ex·KCx 실측: 흰 상자, 글 검정, 아래 줄 엄지·숫자·'답글')."""
    from PIL import Image, ImageDraw
    f, fs = _font("Pretendard-Regular.otf", px), _font("Pretendard-Regular.otf", 28)
    try:
        from PIL import ImageFont
        sym = ImageFont.truetype("C:/Windows/Fonts/segmdl2.ttf", 32)
    except OSError:
        sym = fs
    w = int(min(980, f.getlength(C["text"]) + 44)); h = 142
    im = Image.new("RGBA", (w, h), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    d.text((20, 14), C["text"], font=f, fill=(15, 15, 15))
    d.text((20, 86), "\ue8e1", font=sym, fill=(30, 30, 30))
    d.text((66, 88), str(C.get("likes", "")), font=fs, fill=(96, 96, 96))
    d.text((130, 86), "\ue8e0", font=sym, fill=(30, 30, 30))
    d.text((210, 88), "답글", font=fs, fill=(30, 30, 30))
    im.save(out)
    return w, h


def comment_track(F: dict) -> dict | None:
    """frame.comment.track == 'lines' = 댓글카드가 본문 자막(별헤는쏭 벤치 5편 실측 10-27): 자막 줄(kind sub)마다 그 줄 시간 동안 카드 한 장.
    없으면 None(옛 꿀템노트 꼴 — 한 구간 흰 카드 한 장, plan_rows 의 placed['comment'])."""
    C = F.get("comment") or {}
    return C if C.get("track") == "lines" else None


def card_plan(S: dict, T: dict, st: dict) -> list[dict]:
    """(판단 주인: 어느 줄이 댓글카드인가·카드 시각·프로필 색) — 대본 sub 줄의 덩어리마다 카드 한 장, 시각 = 시간표 덩어리 시각.
    카드 글 칸(likes·ago)은 대본 caps 덩어리에 적는다. 색 = 판 avatar.colors 를 차례로(편 안에서 겹치지 않게)."""
    CT = comment_track(st["frame"])
    if not CT:
        return []
    sub = {L["id"] for L in S["lines"] if L["kind"] == "sub"}
    cols = (CT.get("avatar") or {}).get("colors") or ["#6A35CB"]
    k0 = sum(map(ord, S.get("slug") or "x")) % len(cols)
    out = []
    for i, r in enumerate(r for r in T["rows"] if r["line"] in sub):
        out.append({"line": r["line"], "t0": r["t0"], "t1": r["t1"], "text": r["text"], "likes": r.get("likes", ""), "ago": r.get("ago", ""),
                    "color": cols[(k0 + i) % len(cols)]})
    return out


def comment_card_png(c: dict, CT: dict, out: Path) -> tuple[int, int]:
    """다크 댓글카드 한 장(유튜브 다크 모드 꼴, 별헤는쏭 실측 — 판 frame.comment 칸이 숫자 주인). 반환 (w, h) — 아래 끝 = CT.bottom."""
    from PIL import Image, ImageDraw, ImageFilter
    B, A, TX, MT = CT["box"], CT["avatar"], CT["text"], CT["meta"]
    lines = str(c["text"]).split("\n")
    w = B["x1"] - B["x0"]
    h = B["h1"] + B["line_add"] * (len(lines) - 1)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=B["radius"], fill=_rgb(B["rgb"]) + (int(round(255 * B["alpha"])),))
    ax, ay, ad = A["cx"] - B["x0"], A["cy_rel"], A["d"]
    d.ellipse([ax - ad // 2, ay - ad // 2, ax + ad // 2, ay + ad // 2], fill=_rgb(c["color"]) + (255,))
    hr = ad * 0.16                                         # 흰 사람 모양(머리·어깨) — 벤치 프로필 원 안 꼴
    d.ellipse([ax - hr, ay - ad * 0.28, ax + hr, ay - ad * 0.28 + 2 * hr], fill=(255, 255, 255, 235))
    d.pieslice([ax - ad * 0.3, ay + ad * 0.02, ax + ad * 0.3, ay + ad * 0.62], 180, 360, fill=(255, 255, 255, 235))
    fm = _font(MT["font"], MT["px"])
    tx = TX["x"] - B["x0"]
    nick = Image.new("RGBA", (int(MT["nick_w"]), MT["px"] + 8), (0, 0, 0, 0))   # 가린 닉네임 = 흐린 회색 글자 덩어리
    ImageDraw.Draw(nick).text((0, 2), "●" * max(4, int(MT["nick_w"]) // MT["px"]), font=fm, fill=_rgb(MT["color"]) + (200,))
    im.alpha_composite(nick.filter(ImageFilter.GaussianBlur(3)), (tx, MT["y_rel"]))
    if c.get("ago"):
        d.text((tx + int(MT["nick_w"]) + 14, MT["y_rel"]), c["ago"], font=fm, fill=_rgb(MT["color"]))
    ft = _font(TX["font"], TX["px"])
    for j, ln in enumerate(lines):
        d.text((tx, TX["y_rel"] + j * B["line_add"]), ln, font=ft, fill=_rgb(TX["color"]))
    fy = h - (B["h1"] - MT["foot_rel"])                    # 아래 줄 = 상자 아래 끝 기준(2줄이면 같이 내려간다)
    try:
        from PIL import ImageFont
        sym = ImageFont.truetype("C:/Windows/Fonts/segmdl2.ttf", MT["px"] + 4)
    except OSError:
        sym = fm
    d.text((tx, fy), "\ue8e1", font=sym, fill=_rgb(MT["color"]))
    d.text((tx + 44, fy), str(c.get("likes", "")), font=fm, fill=_rgb(MT["color"]))
    lw = int(fm.getlength(str(c.get("likes", ""))))
    d.text((tx + 44 + lw + 30, fy), "\ue8e0", font=sym, fill=_rgb(MT["color"]))
    d.text((tx + 44 + lw + 100, fy), "답글", font=fm, fill=_rgb(MT["color"]))
    im.save(out)
    return w, h


def lyric_plan(S: dict, st: dict, end: float) -> list[dict]:
    """(판단 주인: 가사 화면 시각) — 곡 옆 가사표 bgm_lib/<id>.lyrics.json [{t0,t1,jp,ko}](곡 기준 초) − 대본 bgm.ss(곡 몇 초부터 쓰나).
    판 frame.lyrics 가 없거나 가사표가 없으면 []."""
    if not st["frame"].get("lyrics"):
        return []
    bid = (S.get("bgm") or {}).get("id") or st["bgm"].get("id")
    p = BGM_DIR / f"{bid}.lyrics.json"
    if not bid or not p.exists():
        raise StageError(f"판 frame.lyrics 가 켜졌는데 가사표 없음: {p}")
    ss = float((S.get("bgm") or {}).get("ss", 0.0))
    out = []
    for x in jload(p)["lyrics"]:
        a, b = x["t0"] - ss, x["t1"] - ss
        if b <= 0 or a >= end:
            continue
        out.append({"t0": round(max(0.0, a), 3), "t1": round(min(end, b), 3), "jp": x["jp"], "ko": x["ko"]})
    return out


def bgm_ss_for(st: dict, length: float, bgm_id: str | None = None) -> float | None:
    """(판단 주인: 노래 시작 지점 bgm.ss) 가사가 영상 길이의 판 bgm.vocal_at 비율 자리에서 처음 뜨게 — 곡 첫 가사 t0 − 비율×길이(0 아래면 0).
    판 bgm.vocal_at 이나 가사표가 없으면 None(대본 bgm.ss 를 그대로 쓴다). 흐름(flow 자막노래형)·손 대본이 같이 부른다."""
    va = (st.get("bgm") or {}).get("vocal_at")
    bid = bgm_id or (st.get("bgm") or {}).get("id")
    p = BGM_DIR / f"{bid}.lyrics.json" if bid else None
    if not isinstance(va, dict) or not isinstance(va.get("v"), (int, float)) or not p or not p.exists():
        return None
    t0 = min(float(x["t0"]) for x in jload(p)["lyrics"])
    return round(max(0.0, t0 - float(va["v"]) * float(length)), 2)


def lyric_png(x: dict, LY: dict, out: Path):
    """가사 2줄(위 일본어·아래 한국어, 가운데 정렬, 고정 자리) 한 장 = 화면 전체 크기 투명 PNG."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in ("jp", "ko"):
        sp = LY[k]
        f = _font(sp["font"], sp["px"])
        bb = d.textbbox((0, 0), x[k], font=f, stroke_width=LY["stroke"]["px"])
        d.text((W // 2 - (bb[2] - bb[0]) // 2 - bb[0], sp["cy"] - (bb[1] + bb[3]) // 2), x[k], font=f, fill=_rgb(sp["color"]),
               stroke_width=LY["stroke"]["px"], stroke_fill=_rgb(LY["stroke"]["color"]))
    im.save(out)


# ── 화면 ────────────────────────────────────────────────────────────────
_det = None


def face_crop(src: Path, t: float, ar: float) -> list[int]:
    """그 프레임의 가장 큰 얼굴을 가운데로 둔 ar(가로/세로) 크롭 — 높이는 원본 전체."""
    import cv2
    global _det
    sw, sh, _ = probe(src)
    ch = sh; cw = int(round(ch * ar)); cw = min(cw, sw)
    if cw == sw:
        ch = int(round(sw / ar))
    cap = cv2.VideoCapture(str(src)); cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read(); cap.release()
    cx = sw / 2
    if ok:
        if _det is None:
            _det = cv2.FaceDetectorYN.create(FACE_MODEL, "", (320, 320), 0.6, 0.3, 50)
        _det.setInputSize((f.shape[1], f.shape[0]))
        _, faces = _det.detect(f)
        if faces is not None and len(faces):
            fx, fy, fw, fh = max(faces, key=lambda z: z[2] * z[3])[:4]
            cx = fx + fw / 2
    x = int(min(max(cx - cw / 2, 0), sw - cw))
    return [x, 0, cw, ch]


BLUR_SIGMA = 25.0     # 가림 흐림 세기 = 제품 가림막 흐림의 최저값(deco_frame.blur_sigma 25~80)과 같은 gblur


def blur_vf(regs, ss: float, dur: float, sigma: float = BLUR_SIGMA) -> str:
    """원본에 박힌 자막·글 자리를 흐린다(원본 픽셀 좌표, 잘라 내기 전). regs = [[x, y, w, h(, a, b)], …], a~b = 원본 초(없으면 늘).
    10-22 사장님 "자막을 가리려고 확대를 많이 해서 너무 커지거나 가운데로 안 간다 → 가림막 흐림으로": 잘라서 피하던 걸 흐림으로 바꾼다.
    흐림은 제품 렌더(video_assemble)와 같은 gblur — 다만 여기는 원본 좌표라 마스크 그림 대신 사각 영역(crop→gblur→overlay)."""
    out = []
    for r in regs or []:
        x, y, w, h = (int(v) for v in r[:4])
        a, b = (float(r[4]), float(r[5])) if len(r) >= 6 else (None, None)
        if a is not None and (b <= ss or a >= ss + dur):
            continue                                           # 이 컷 구간과 안 겹침
        en = f":enable='between(t,{max(0.0, a - ss):.3f},{b - ss:.3f})'" if a is not None else ""
        out.append(f"split[bo][bi];[bi]crop={w}:{h}:{x}:{y},gblur=sigma={sigma}[bb];[bo][bb]overlay={x}:{y}{en}")
    return ",".join(out)


_src_len: dict[str, float] = {}


def src_left(src: Path, ss: float) -> float | None:
    """원본 영상에서 ss 뒤로 남은 화면 초(마지막 프레임 하나 뺌). 사진은 None(얼마든 늘린다).
    10-23 사장님 "뒤에 멈추거나 중간중간 튄다": 컷이 원본 끝을 넘으면 clip 이 n프레임보다 적게 뽑고, 뒤 컷이 전부 앞당겨져
    (09 딸기라떼 27프레임 = 0.9초 어긋남) 끝 화면이 멈췄다. 그때까지 아무 검사도 안 걸렸다(05·08·09·11 네 편)."""
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return None
    k = str(src)
    if k not in _src_len:
        out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration:format=duration", "-of", "json", src]).stdout
        j = json.loads(out)
        d = (j.get("streams") or [{}])[0].get("duration") or (j.get("format") or {}).get("duration")
        _src_len[k] = float(d)
    return round(_src_len[k] - ss - 1 / FPS, 3)


_src_rate: dict[str, tuple[float, float]] = {}


def src_start(src: Path, ss: float) -> float:
    """(판단 주인 — 컷 첫 화면이 원본 몇 초인가) `-ss ss -i src` 는 ss 이상인 첫 원본 프레임부터 낸다 → 그 프레임 초(원본 fps 격자).
    30fps 원본이면 ss 그대로. 10-26 식기세척기 50.433(23.976fps): 실제 첫 화면 50.467 → 29프레임 컷 끝이 다음 샷(51.4) 1프레임을 끌고 왔는데
    경계 판정은 ss 부터 쟀다(눈 확인 — 마지막 1프레임이 다음 장면). 경계로 조각 재기(snap_ss·cut_boundary_gate·check_shot_cross)는 이 초부터 잰다."""
    src = Path(src)
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return ss
    k = str(src)
    if k not in _src_rate:
        try:
            out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate,start_time", "-of", "json", src]).stdout
        except StageError:      # 못 읽는 파일(시험용 빈 파일 등) — 읽기·렌더 단계가 따로 크게 멈춘다. 여기선 ss 그대로(옛 판과 같음)
            out = "{}"
        s0 = (json.loads(out).get("streams") or [{}])[0]
        num, _, den = str(s0.get("r_frame_rate") or "0/1").partition("/")
        fr = float(num) / float(den or 1) if float(den or 1) else 0.0
        _src_rate[k] = (fr, float(s0.get("start_time") or 0.0))
    fr, t0 = _src_rate[k]
    if fr <= 0:
        return ss
    f = t0 + math.ceil((ss - t0 - 1e-3) * fr) / fr
    return ss if f - ss < 1e-3 else round(f, 4)


MIN_PIECE_SEC = 0.4   # 컷을 원본 장면 경계로 나눈 조각이 이보다 짧으면 번쩍임(오류기록 55·84) — 계획(snap_ss)·관문·품질 검사가 이 한 상수를 쓴다
SLIVER_SEC = MIN_PIECE_SEC      # 컷 처음·끝 이 안에 장면 경계가 있으면 '번쩍임'(앞뒤 샷이 몇 프레임 끼어 튀어 보인다)


def shot_starts(video: Path) -> list[float]:
    """영상의 장면 경계(새 샷이 시작하는 초, 30fps 격자) — '경계가 어디냐'의 주인 한 곳(오류기록 84).
    후보 = readline_tools.cutdet(상대 문턱 max(12, 3.5×이웃 중앙값) 또는 히스토그램차), 확정 = 경계 앞뒤 프레임 상관 < CUT_CORR_MAX(_real_cut, 오류기록 85).
    snap_ss(계획)·cut_boundary_gate(관문)·quality_gate.part_slivers(완성본 검사) 모두 이걸 부른다. 파일 옆 json 캐시.
    (옛 판은 절대 문턱 max(25, 4×중앙값)이라 차 22~31 인 진짜 편집점을 놓쳤다 — 10-25 잇템로그 05·09 번쩍임.)"""
    w, h = probe(Path(video))[:2]
    return _src_cuts(Path(video), 0, int(h), int(w))


def inner_bounds(starts: list[float], a: float, b: float) -> list[float]:
    """구간 [a,b) 화면 안에 보이는 장면 경계 — 첫 프레임부터 새 샷이면(t ≤ a+반 프레임) 경계 아님, 마지막 프레임까지 옛 샷이면(t > b−1프레임) 경계 아님.
    10-25 ep12 N7 ayB: 옛 판은 첫 1.5프레임 안을 빼서 ss 8.367·경계 8.4(= 둘째 프레임부터 새 샷)를 못 봐, snap_ss 가 앞 샷 1프레임 번쩍임 자리로 옮겼다(눈 확인)."""
    return [t for t in starts if a + 0.5 / FPS < t <= b - 1 / FPS + 1e-3]


def shot_cap(c: dict, src: Path) -> None:
    """(판단 주인 — 나레 컷의 샷 한도) 재료에 max 가 없는 영상 컷(쇼핑형 재료 영상처럼 서버 샷 표가 없는 파일)에 '그 샷 끝까지' 한도를 붙인다.
    경계 = shot_starts(관문·완성본 검사·source_rule_scan 이 잡는 전환과 같은 자리 — 10-27 TV 편 재료 실측: 반려 컷 10/10 이 이 경계를 넘었고, 샷 23개 안쪽만 쓰면 0개).
    ss 가 샷 끝 MIN_PIECE_SEC 안이면(다음 샷이 바로 이어지는 자리) 다음 샷 처음으로 옮긴다. 이 한도로 fit_cut 이 샷 안에서 옮기고 늦춘다.
    10-27 TV 스탠드 편: 한도가 없어 재료 컷이 장면 전환을 넘었고, 계획 반려 → Claude 가 초를 눈대중으로 고치기를 17번."""
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return
    starts = shot_starts(src)
    ss = float(c["ss"])
    nxt = [t for t in starts if t > ss + 0.5 / FPS]
    if nxt and nxt[0] - ss < MIN_PIECE_SEC:
        ss = round(nxt[0], 3)
        c["ss"] = c["ss_planned"] = ss
        nxt = nxt[1:]
    c["max"] = round(nxt[0] - ss, 3) if nxt else None
    c["max_auto"] = True


def shot_room(src: Path, need: float, k: int = 6) -> list[tuple[float, float]]:
    """그 파일에서 need 초 이상 이어지는 샷 [(시작, 끝)] 긴 순 k 개 — 재료 고치기 질문에 싣는다(눈대중 대신 고를 자리)."""
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return []
    st = [0.0] + shot_starts(src)
    end = src_left(src, 0.0)
    pts = st + ([end] if end else [])
    return sorted([(round(a, 2), round(b, 2)) for a, b in zip(pts, pts[1:]) if b - a >= need], key=lambda x: x[0] - x[1])[:k]


def short_pieces(starts: list[float], a: float, b: float) -> list[float]:
    """구간 [a,b) 를 경계(inner_bounds)로 쪼갠 조각 중 MIN_PIECE_SEC 보다 짧은 것의 길이."""
    pts = [a] + inner_bounds(starts, a, b) + [b]
    if len(pts) == 2:
        return []
    return [round(y - x, 2) for x, y in zip(pts, pts[1:]) if y - x < MIN_PIECE_SEC - 1e-3]


def slivers(starts: list[float], a: float, b: float, edge: float = SLIVER_SEC) -> list[float]:
    """구간 [a,b) 안 경계 중 처음·끝 edge 안에 있는 것 — 경계 = inner_bounds(계획 snap_ss·fit_cut·fit_lip_edges 와 같은 자).
    10-26: 여기만 a+1ms 부터 세어 첫 반 프레임 안(0.003초 — 첫 프레임부터 새 샷, 화면엔 안 보임)도 번쩍임으로 쳐서 계획이 통과시킨 컷을 완성본 검사가 잡았다(자 두 벌)."""
    return [s for s in inner_bounds(starts, a, b) if s - a < edge - 1e-3 or b - s < edge - 1e-3]      # 딱 0.2초(6프레임)는 통과


def snap_ss(src: Path, ss: float, dur: float, reach: float = 0.4) -> float:
    """나레 컷 시작 초를 ±reach 안에서 가장 덜 움직여 번쩍임 없는 자리로(원본 끝도 넘지 않게). 못 찾으면 그대로(검사가 잡는다)."""
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return ss
    st = shot_starts(src)

    def bad(s):          # 실제 첫 화면(src_start)부터 잰다 — 24fps 원본은 ss 보다 최대 1원본프레임 늦게 시작한다
        e = src_start(src, s)
        return short_pieces(st, e, e + dur)
    if not bad(ss):
        return ss
    for k in range(1, int(reach * FPS) + 1):
        for s in (ss + k / FPS, ss - k / FPS):
            left = src_left(src, s)
            if s >= 0 and (left is None or dur <= left) and not bad(s):
                return round(s, 3)
    return ss


def _max_slowmo() -> float:
    """늦춤 상한(배) — 정본은 shopping_shorts.config.MAX_SLOWMO 한 곳(숏템메이커 video_assemble._speed_and_freeze 와 같은 값, 관제 020 ·
    10-01 사장님 '제일 심플하게': 경쟁사 완성본 실측 약 0.84배 감속 = 1.19배 늦춤). 여기서 숫자를 적지 않는다."""
    from shopping_shorts.config import MAX_SLOWMO
    return float(MAX_SLOWMO)


def fit_cut(src: Path, ss: float, n: int, cap: float | None = None, reach: float = 0.4) -> tuple[float, float]:
    """(판단 주인 — 나레 컷을 원본 샷 안에 맞추는 시작 초·속도, 사장님 10-26 "조각이 짧거나 길면 숏템메이커처럼 늘리기")
    n = 컷 프레임 수 · cap = 재료 max(ss 에서 그 샷 끝까지 초 — rules.fill_shot_max) · 반환 (ss, speed) — speed = 원본 초 ÷ 화면 초(≤1, 1 = 제 속도).
    ① snap_ss 그대로(±reach 안 옮기기, 옛 동작) → 제 속도로 샷 안·원본 끝 안·짧은 조각 없음이면 끝
    ② 아니면 같은 자리부터 ±reach 안 가까운 순으로, 원본 프레임 수를 n → n÷MAX_SLOWMO 까지 줄여(= 늦춰) 처음 맞는 자리
       (덜 늦추는 쪽 먼저 — 숏템메이커처럼 컷 안에서 고르게 늦춰 채움, 멈춤 프레임 없음) ③ 그래도 안 되면 그대로(관문이 잡는다).
    cap 은 ss 를 옮긴 만큼 줄어든다(뒤로 δ 옮기면 샷 끝까지 cap−δ). 경계·조각 판정 = shot_starts·short_pieces·src_start(관문 ③과 같은 자)."""
    src = Path(src)
    if src.suffix.lower() in IMG_EXT or not src.exists() or n <= 0:
        return ss, 1.0
    starts = shot_starts(src)

    def ok(s: float, m: int) -> bool:
        sec = m / FPS
        if s < 0 or (cap is not None and sec > float(cap) - (s - ss) + 1e-3):
            return False
        left = src_left(src, s)
        if left is not None and sec > left + 1e-3:
            return False
        e = src_start(src, s)
        return not short_pieces(starts, e, e + sec)
    s1 = snap_ss(src, ss, n / FPS, reach)
    if ok(s1, n):
        return s1, 1.0
    lo = math.ceil(n / _max_slowmo() - 1e-6)
    shifts = [0] + [d for k in range(1, int(reach * FPS) + 1) for d in (k, -k)]
    for d in shifts:
        s = round(ss + d / FPS, 3)
        for m in range(n - 1, lo - 1, -1):
            if ok(s, m):
                return s, round(m / n, 4)
    return s1, 1.0


def cut_speed(c: dict) -> float:
    """컷 속도(원본 초 ÷ 화면 초) — fit_cut 이 정한 c["speed"] 를 읽기만. 없으면 1."""
    return float(c.get("speed") or 1.0)


def fit_lip_edges(cuts: list, src_dir: Path, end: float, line_src: dict) -> list:
    """(판단 주인 — 원음(입 맞춤) 컷 가장자리 초 조절, 사장님 10-26 "0.13·0.001 때문에 늦어지는 건 말이 안 된다 — 숏템메이커처럼 초 조절")
    원음 컷은 입 맞춤이라 늦추거나 옮길 수 없다 — 대신 **이웃 컷과의 경계 시각**을 옮긴다:
      · 끝 조각(원본 장면 경계 뒤 MIN_PIECE_SEC 미만)·샷 max 를 조금 넘는 끝 → 이 컷을 그만큼 일찍 끝내고 다음 컷이 일찍 시작(다음이 나레 컷이면 fit_cut 이 늘려 채운다)
      · 첫 조각(경계 앞 MIN_PIECE_SEC 미만) → 이 컷을 그만큼 늦게 시작(ss 도 같이 — 입 맞춤 유지)하고 앞 컷이 그만큼 길어진다
    옮기는 양은 MIN_PIECE_SEC 미만만(그보다 크면 계획을 고쳐야 할 일 — 관문이 그대로 잡는다). 반환 = 옮긴 기록."""
    moved = []
    lip = lambda c: c.get("kind") == "orig" and c.get("src") == line_src.get(c.get("line")) and c.get("ss") is not None
    k = 0
    while k + 1 < len(cuts):          # ① 같은 원음 줄에서 원본을 이어 트는 컷은 한 컷으로 — 원본의 제 컷은 그대로 흐르고, 우리가 나눈 자리에서 생기던 1프레임 끼임이 없다(10-26 까르보 L2)
        a, b = cuts[k], cuts[k + 1]
        if lip(a) and lip(b) and a["line"] == b["line"] and a["src"] == b["src"] \
                and abs(float(b["ss"]) - (float(a["ss"]) + float(b["t0"]) - float(a["t0"]))) < 0.15:
            moved.append((a["line"], "합침", round(float(b["ss"]), 3)))
            a["max"] = None              # 샷 끝 max 는 쪼갠 첫 컷 것 — 합친 컷은 원본 제 컷을 그대로 흘려 보내므로 샷 끝 한도 대신 원본 남은 길이(src_left)만 본다
            a["lip_run"] = True
            del cuts[k + 1]
            continue
        k += 1
    for i, c in enumerate(cuts):
        if not lip(c):
            continue
        src = src_dir / c["src"]
        if not src.exists() or src.suffix.lower() in IMG_EXT:
            continue
        t1 = cuts[i + 1]["t0"] if i + 1 < len(cuts) else end
        ss, dur = float(c["ss"]), float(t1) - float(c["t0"])
        if dur <= MIN_PIECE_SEC:
            continue
        e0 = src_start(src, ss)
        bs = inner_bounds(shot_starts(src), e0, e0 + dur)
        head = (bs[0] - e0) if bs else None
        if head is not None and head < MIN_PIECE_SEC - 1e-3 and i > 0 and dur - head > MIN_PIECE_SEC:
            k = round(head, 3)
            c["t0"], c["ss"] = round(float(c["t0"]) + k, 3), round(ss + k, 3)
            ss, dur, e0 = ss + k, dur - k, e0 + k
            moved.append((c.get("line"), "앞", k))
            bs = inner_bounds(shot_starts(src), e0, e0 + dur)
        if i + 1 >= len(cuts):
            continue
        cap = c.get("max")
        k = 0.0
        for _ in range(4):           # 당긴 끝 바로 앞에 또 원본 경계가 있으면(0.09초 조각, 10-26 까르보 L2) 조각이 없어질 때까지 다시 당긴다
            d_now = dur - k
            bs_k = inner_bounds(shot_starts(src), e0, e0 + d_now)
            tail = (e0 + d_now - bs_k[-1]) if bs_k else 0.0
            sd = (round((float(t1) - k) * FPS) - round(float(c["t0"]) * FPS)) / FPS      # 실제 뽑는 프레임 수로(관문과 같은 셈 — 화면 0.75초가 23프레임 0.767초가 돼 샷 0.751초를 넘었다)
            over = (sd - float(cap)) if cap is not None and sd > float(cap) + 1e-3 else 0.0
            cut_back = max(tail if 0 < tail < MIN_PIECE_SEC - 1e-3 else 0.0, over if over < MIN_PIECE_SEC else 0.0)
            if cut_back <= 0 or d_now - cut_back <= MIN_PIECE_SEC:
                break
            k += math.ceil(cut_back * FPS - 1e-6) / FPS           # 프레임 격자로 올림(0.001 넘침도 한 프레임 당겨 끝낸다)
        if k > 0:
            nx = cuts[i + 1]
            nx["t0"] = round(float(nx["t0"]) - k, 3)
            if nx.get("kind") == "orig" and nx.get("ss") is not None and nx.get("src") == line_src.get(nx.get("line")) and nx.get("line") == c.get("line"):
                nx["ss"] = round(float(nx["ss"]) - k, 3)             # 같은 원음 줄 다음 컷 — 입 맞춤 그대로(원본 초도 같이 당긴다)
            moved.append((c.get("line"), "끝", round(k, 3)))
    if moved:
        sys.stderr.write(f"[fit_lip_edges] 원음 컷 가장자리 초 조절 {moved}\n")
    return moved


def edge_fault(c: dict, src_dir: Path) -> dict | None:
    """(판단 주인 — 컷 하나가 원본 장면 경계로 짧은 조각을 만드나) 원본에서 실제로 쓰는 [첫 화면, +src_frames] 안 경계(inner_bounds)로 나눈 조각 중
    MIN_PIECE_SEC 미만이 있으면 {e, end, hit, pieces}. 계획(settle_edges)과 렌더 전 관문 ③(cut_boundary_gate)이 같이 부른다 — 자 하나."""
    src = Path(src_dir) / c["src"]
    if c.get("ss") is None or src.suffix.lower() in IMG_EXT or not src.exists():
        return None
    e = src_start(src, float(c["ss"]))
    end = e + src_frames(c) / FPS
    hit = inner_bounds(shot_starts(src), e, end)
    if not hit or not short_pieces(hit, e, end):
        return None
    pts = [e] + hit + [end]
    return {"e": e, "end": end, "hit": hit, "pieces": [y - x for x, y in zip(pts, pts[1:])]}


def settle_edges(cuts: list, src_dir: Path, end: float, line_src: dict, refit, passes: int = 4) -> list:
    """(판단 주인 — 계획이 짧은 조각을 스스로 없앤다, 사장님 10-27 '걸림이 생기는 걸 없애라') fit_lip_edges·fit_cut(±0.4초 옮기기·늘리기) 뒤에도
    edge_fault 가 남은 컷을 이렇게 푼다 — 관문 ③에 넘겨 Claude 가 초를 손으로 고치게 하지 않는다:
      ① 나레 컷: 옮기는 범위를 ±1.2초로 넓혀 다시 맞춘다(refit) — 샷 안에 들어가면 끝
      ② 그래도 끝 조각이 짧으면 이 컷을 그 조각만큼 일찍 끝내고 다음 컷이 일찍 시작(다음이 나레 컷이면 refit 이 늘려 채운다)
      ③ 첫 조각이 짧으면 이 컷을 그만큼 늦게 시작(원본 초도 같이 — 원음 컷 입 맞춤 유지)하고 앞 컷이 길어진다
    옮기는 양은 MIN_PIECE_SEC 미만·옮긴 뒤 컷이 MIN_PIECE_SEC 넘게 남을 때만. 컷 0 의 시작(0초)은 안 옮긴다. 반환 = 옮긴 기록."""
    moved = []
    lip = lambda c: c.get("kind") == "orig" and c.get("src") == line_src.get(c.get("line")) and c.get("ss") is not None
    for p in range(passes):
        bad = [i for i, c in enumerate(cuts) if edge_fault(c, src_dir)]
        if not bad:
            break
        if p == 0 and any(not lip(cuts[i]) for i in bad):
            refit(1.2)
            moved.append(("넓혀 다시 맞춤", len(bad)))
            continue
        changed = False
        for i in bad:
            f = edge_fault(cuts[i], src_dir)
            if not f:
                continue
            c = cuts[i]
            sp = float(c.get("speed") or 1.0)
            dur = float(c["t1"]) - float(c["t0"])
            head, tail = f["pieces"][0], f["pieces"][-1]
            if tail < MIN_PIECE_SEC - 1e-3 and i + 1 < len(cuts):
                k = math.ceil(tail / sp * FPS - 1e-6) / FPS         # 화면 초(늘린 컷은 원본 1초 = 화면 1/speed 초)
                if dur - k > MIN_PIECE_SEC:
                    nx = cuts[i + 1]
                    nx["t0"] = round(float(nx["t0"]) - k, 3)
                    if lip(nx) and nx.get("line") == c.get("line"):
                        nx["ss"] = round(float(nx["ss"]) - k, 3)
                    moved.append((c.get("line"), "끝", round(k, 3)))
                    changed = True
                    continue
            if head < MIN_PIECE_SEC - 1e-3 and i > 0:
                k = math.ceil(head / sp * FPS - 1e-6) / FPS
                if dur - k > MIN_PIECE_SEC:
                    c["t0"] = round(float(c["t0"]) + k, 3)
                    c["ss"] = round(float(c["ss"]) + k * sp, 3)
                    if "ss_planned" in c:
                        c["ss_planned"] = round(float(c["ss_planned"]) + k * sp, 3)
                    if c.get("max") is not None:
                        c["max"] = round(float(c["max"]) - k * sp, 3)          # max = 재료 ss 에서 샷 끝까지 — 시작을 늦춘 만큼 준다
                    moved.append((c.get("line"), "앞", round(k, 3)))
                    changed = True
        if not changed:
            break
        refit(1.2)
    left = [cuts[i].get("line") for i, c in enumerate(cuts) if edge_fault(c, src_dir)]
    if moved or left:
        sys.stderr.write(f"[settle_edges] 짧은 조각 스스로 풀기 {moved} · 남음 {left}\n")
    return moved


def src_frames(c: dict) -> int:
    """컷이 원본에서 쓰는 프레임 수(30fps 격자) = 화면 프레임 × 속도 — 관문 ③·④·접촉 시트·VMake 구간이 같이 읽는다(늘린 컷이 다음 샷을 재지 않게)."""
    return max(1, round(cut_frames_n(c) * cut_speed(c)))


CUT_CORR_MAX = 0.86   # 경계 앞뒤 프레임 회색 상관이 이보다 낮으면 진짜 편집점(오류기록 85: 146개 오푸스 눈 판정 P 0.94·R 0.97, 0.6 이면 R 0.43)
CUTBOUNDS_VER = 2     # 경계 판정(문턱·읽는 법)이 바뀌면 올린다 — 파일 옆 캐시 이름에 들어가 옛 판정 캐시를 안 쓴다


def _cut_corr(src: Path, t: float, y0: int, y1: int, w: int) -> float | None:
    """cutdet 후보 t(새 샷 첫 프레임) 앞뒤 이웃 프레임 쌍 3개(t-2→t-1, t-1→t, t→t+1) 회색 상관 중 최솟값. 못 재면 None.
    ±1프레임을 보는 건 -ss 찾기가 한두 프레임 어긋나도 경계를 놓치지 않게(ep09 j2B 14.97 이 같은 프레임 두 장으로 1.00 이 나왔다).
    영상 첫 3프레임 안 후보는 읽기 시작을 0 으로 당기고 쌍 위치를 그만큼 옮긴다(옛 판은 경계 뒤 프레임끼리 재서 0.95~0.99 로 놓쳤다)."""
    import numpy as np
    import subprocess
    H = max(16, y1 - y0)
    k = round(t * FPS)
    s0 = max(0, k - 3)
    c = k - s0                       # 읽은 프레임 중 t 의 자리
    K = c + 2
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s0 / FPS:.4f}", "-i", str(src), "-vf",
                          f"fps={FPS},crop={w}:{H}:0:{y0},scale=90:-2,format=gray", "-frames:v", str(K), "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    n = len(raw) // K
    if n < 2 or len(raw) % K:
        return None
    F = [np.frombuffer(raw[q * n:(q + 1) * n], np.uint8).astype(float) for q in range(K)]
    cs = [float(np.corrcoef(F[q], F[q + 1])[0, 1]) for q in range(max(0, c - 2), c + 1) if F[q].std() > 1e-6 and F[q + 1].std() > 1e-6]
    return min(cs) if cs else None


def _real_cut(src: Path, t: float, y0: int, y1: int, w: int) -> bool:
    """cutdet 후보가 진짜 편집점(다른 샷·각도·점프컷)인지 — 판정 주인 한 곳. 상관 < CUT_CORR_MAX.
    10-25 오푸스 눈 판정 146개(잇템로그 05·09·13 + 키칫·꿀템노트·스타픽룸·성시경 가로 원본): 같은 배경 점프컷이 0.6~0.85 에 몰려 있어
    옛 0.6 은 진짜 편집점 절반 이상을 놓쳤다. 같은 샷(걷기·손·자막만 바뀜·번쩍 효과)은 대부분 0.86 이상. 표본: readline_tools/fixtures/cut_corr_labels.json.
    못 재면 진짜로 본다(놓치는 쪽이 번쩍임을 통과시키므로)."""
    r = _cut_corr(src, t, y0, y1, w)
    return True if r is None else r < CUT_CORR_MAX


def _src_cuts(src: Path, y0: int, y1: int, w: int) -> list[float]:
    """원본 한 파일의 장면 경계 초(주인 = readline_tools.cutdet.cutdet — 상대 문턱 max(12, 3.5×이웃 중앙값) 또는 히스토그램차, 불러 쓴다). 파일 옆 json 캐시."""
    cp = src.parent / f"_cutbounds_{src.stem}_{y0}_{y1}_v{CUTBOUNDS_VER}.json"
    try:
        if cp.exists() and cp.stat().st_mtime >= src.stat().st_mtime:
            return jload(cp)
    except Exception:
        pass
    from tools.calcopy.engine.readline_tools.cutdet import cutdet
    ts = [t for t in (float(r["t"]) for r in cutdet(str(src), y0, y1, float(FPS), w, shots=False)["cuts"]) if _real_cut(src, t, y0, y1, w)]   # shots=False = 프레임을 쌓지 않음(1592초 원본 23GiB MemoryError, 98 #101)
    try:
        jsave(cp, ts)
    except Exception:
        pass
    return ts



def cut_frames_n(c: dict) -> int:
    """컷이 실제로 뽑히는 프레임 수(render_window 와 같은 셈) — 렌더 전 관문이 같이 쓴다."""
    return int(c.get("frames") or (round(c["t1"] * FPS) - round(c["t0"] * FPS)))


def cut_length_gate(T: dict, st: dict | None = None) -> list[str]:
    """렌더 전 관문 ⑤ 조각 규격(10-25): 컷 하나가 통째로 MIN_PIECE_SEC(0.4초)보다 짧으면 멈춘다 — 화면에 이어 보이는 조각이 0.4초 미만이면 번쩍임이라는
    판정(오류기록 55·84·85, 관문 ③ short_pieces)과 같은 상수·같은 판단. 관문 ③은 컷 '안' 경계만 보므로 컷 자체가 짧은 것(잇템로그 13 N5 0.275초 —
    재료 w 0.12 로 나눈 조각, snap_ss 가 옆 장면으로 밀어 다음 컷 N6 과 같은 통 화면을 0.3초 되감아 보임)은 아무 관문에도 안 걸렸다.
    벤치 원본 실측(18판 2072샷, render_bench._src_cuts): 0.4초 미만 샷 9% — 대부분 맨 앞 썸네일 카드 2프레임·같은 인물 펀치 줌 몰아치기(J7GxfaVdwSU 4.2~5.1초)로,
    우리 계획은 그런 몰아치기를 짜지 않는다(계획 511컷 중 0.4 미만 5컷 = 전부 줄 나누기 끝자락·원음 자투리). 문턱을 판마다 바꾸지 않는다 — 관문 ③과 한 상수."""
    lo = MIN_PIECE_SEC
    bad = []
    for k, c in enumerate(T["cuts"]):
        sec = cut_frames_n(c) / FPS
        if sec < lo - 1e-3:
            bad.append(f"컷 길이 {k} {c['line']} {c['src']}@{c.get('ss')}: {sec:.2f}초(<{lo}) — 화면이 번쩍 지나간다. 재료.json 그 줄 컷 수를 줄이거나 w 를 고르게(한 컷 ≥{lo}초)")
    return bad


def clip_args(c: dict, src: Path, st: dict, M: dict) -> dict:
    """(판단 주인) 컷 하나를 clip_cmd 에 넘길 인자 — 시작 초·프레임 수·칸·판 밀기(cuts.push_tts/push_orig)·움직임·흐림·그림 칸.
    render_window(조각 굽기)·cut_gray(관문 ⑦)·plan_frames_gray(완성본 = 계획 프레임 대조)가 같이 부른다 — 셋이 다른 그림을 상상하지 않게(관제263 10-25:
    대조가 판 push 를 모르고 안 민 원본과 비교해 0.946 으로 떨어졌다)."""
    _, _, ww, wh = frame_window(st["frame"])
    push = (st.get("cuts") or {}).get("push_orig" if c["kind"] == "orig" else "push_tts", 0.0)
    return {"ss": float(c.get("ss") or 0.0), "n": cut_frames_n(c), "crop": cut_crop(c, src, (ww, wh)), "win": (ww, wh),
            "push": float(c.get("push", push)), "move": c.get("move"), "blur": (M.get("blur") or {}).get(c["src"]),
            "pic": pic_box(c, (ww, wh)), "pic_bg": c.get("pic_bg") or st["frame"].get("bg"), "speed": cut_speed(c)}


def plan_frames_gray(c: dict, src: Path, st: dict, M: dict, idx: list[int]) -> dict:
    """계획 프레임 = 조각이 될 그림(clip_cmd, 판 밀기·사진 움직임·흐림 포함)의 컷 안 프레임 번호 idx 를 창 크기 회색으로 {i: 배열}."""
    import numpy as np
    import subprocess
    a = clip_args(c, src, st, M)
    ww, wh = a["win"]
    inp, vf, extra = clip_cmd(src, a["ss"], a["n"], a["crop"], a["win"], a["push"], a["move"], a["blur"], a["pic"], a["pic_bg"], speed=a["speed"])
    fs = sorted({int(i) for i in idx if 0 <= int(i) < a["n"]})
    if not fs:
        return {}
    sel = "+".join(f"eq(n\\,{i})" for i in fs)
    raw = subprocess.run(["ffmpeg", "-v", "error", *map(str, inp), "-vf", f"{vf},select={sel},format=gray", "-frames:v", str(len(fs)), "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout      # extra(사진 -r)는 뺀다 — 고른 프레임만 그대로(passthrough)
    arr = np.frombuffer(raw[:len(raw) - len(raw) % (ww * wh)], np.uint8).reshape(-1, wh, ww)
    return dict(zip(fs, arr))


def cut_gray(c: dict, src: Path, st: dict, M: dict):
    """컷 조각이 될 그림을 렌더 없이 회색 108폭 프레임으로 — clip_cmd(조각 굽기와 같은 필터·크롭·움직임·흐림) 그대로 ffmpeg 로 읽기만."""
    import numpy as np
    import subprocess
    a = clip_args(c, src, st, M)
    (ww, wh), n = a["win"], a["n"]
    inp, vf, extra = clip_cmd(src, a["ss"], n, a["crop"], a["win"], a["push"], a["move"], a["blur"], a["pic"], a["pic_bg"], speed=a["speed"])
    sh = max(8, round(108 * wh / ww / 2) * 2)
    raw = subprocess.run(["ffmpeg", "-v", "error", *map(str, inp), "-vf", f"{vf},scale=108:{sh},format=gray", "-frames:v", str(n), *map(str, extra),
                          "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw[:len(raw) - len(raw) % (108 * sh)], np.uint8).reshape(-1, sh, 108).astype(np.int16)


def cut_still_gate(T: dict, M: dict, st: dict, ks: list | None = None) -> list[str]:
    """렌더 전 관문 ⑦ 멈춤·거의 멈춤(10-25): 컷마다 조각이 될 그림(cut_gray)에서 정지 구간을 quality_gate.still_spans(완성본 '화면 멈춤 없음'과 같은 판정)로 잰다.
    감사 눈7 정지 47건(확정 18: 골든카레 흑백 트럭 2.2초·S&B 로고·카레 캔·거즈 잠옷 등)은 원본 자체가 멈춘 그림인 컷이었고 렌더 전에는 아무 관문도 안 봤다.
    원본 끝을 넘어 마지막 프레임이 굳는 멈춤은 계획의 src_left('컷이 원본 샷보다 길다')가 이미 멈춘다(98 #61) — 여기서 다시 적지 않는다.
    사진 컷은 clip_cmd 가 still_move(확대·흐름)를 넣은 그대로 재므로 '움직임 없는 사진'만 걸린다(벤치 판에 의도된 정지 사진 칸 없음 — 사장님 10-18 '이미지를 쓰려면 계속 움직이게').
    ks = 문구에 적을 컷 번호(T 컷 순서와 같은 길이 — preset_gates 가 preset_make 컷 번호로). 없으면 T 안 순번."""
    from tools.calcopy.hybrid import quality_gate as QG
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    if not src_dir:
        return []
    items = [(k, c, src_dir / c["src"]) for k, c in enumerate(T["cuts"]) if (src_dir / c["src"]).exists()]
    if len(items) > 1:      # 컷마다 ffmpeg 회색 읽기를 동시 FRAME_JOBS 개까지 — 판정(still_spans)·문구 순서는 컷 순서 그대로
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(min(FRAME_JOBS, len(items))) as ex:
            grays = list(ex.map(lambda x: cut_gray(x[1], x[2], st, M), items))
    else:
        grays = [cut_gray(c, src, st, M) for _, c, src in items]
    bad = []
    for (k, c, src), g in zip(items, grays):
        if ks is not None:
            k = ks[k]
        sp = QG.still_spans(g)
        if sp:
            bad.append(f"컷 멈춤 {k} {c['line']} {c['src']}@{c.get('ss')}: 컷 안 {[(round(a, 2), round(b, 2)) for a, b in sp]}초가 멈춘 그림 — 움직이는 장면으로 바꾸거나(ss·원본) 사진이면 move 를 준다")
    return bad


def cut_boundary_gate(T: dict, M: dict, st: dict | None = None) -> list[str]:
    """렌더 전 관문 ③(10-25 잇템로그 05·09 번쩍임): 계획된 컷마다 원본 [ss, ss+길이] 안(가장자리 포함, 맨 앞 1프레임 제외)에
    장면 경계로 나눈 조각 중 MIN_PIECE_SEC(0.4초)보다 짧은 것이 있으면 막는다. 옛 shot_starts(절대 문턱 25)는 차 22~31 인 진짜 편집점을 놓쳤고 slivers 는 가장자리 0.2초만 봤다.
    경계는 shot_starts(원본 전체 화면) — 크롭 밖 편집점도 센다. 계획(snap_ss)이 같은 경계로 먼저 피하고 이 관문은 확인만 한다."""
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    if not src_dir:
        return []
    bad = []
    for c in T["cuts"]:
        f = edge_fault(c, src_dir)         # 계획 settle_edges 와 같은 자(원본에서 쓰는 프레임·실제 첫 화면 초·inner_bounds)
        if f:                  # 양쪽이 긴 조각이면 원본 자체의 이어진 편집이라 통과 — 짧은 조각(번쩍임)만 막는다(오류기록 55: 0.3초 꼬리도 결함)
            short = [round(x, 2) for x in f["pieces"] if x < MIN_PIECE_SEC - 1e-3]
            bad.append(f"컷 경계 {c['line']} {c['src']} ss={float(c['ss']):.2f}~{f['end']:.2f} 안 원본 장면 경계 {[round(t, 2) for t in f['hit']]}초 → 짧은 조각 {short}초(<{MIN_PIECE_SEC})")
    return bad


# ── 렌더 전 관문 ④ — 컷 안 남의 글자·남의 얼굴(10-25 감사: 남의 글자 확정 33 · 남 얼굴 확정 15 — 전부 완성본 눈 검사에서야 보였다) ──
# 판정 주인 = cut_content_gate 한 곳. 프레임은 렌더 조각과 같은 자리(cut_crop)·같은 흐림(blur_vf)으로 thumb.card_scene_frame 이 원본에서 뽑는다.
# 자 = channelkit.vision(PP-OCRv5 det 글자 상자 · YuNet 얼굴 · SFace 동일성). 문턱 표본 = shopping_shorts/tests/fixtures/cut_content_labels.json.
CONTENT_PAIR = 2 / FPS            # 글자 '붙박이' 재기 짝 프레임 간격 — 박힌 글은 2프레임 동안 그대로, 장면 속 글(포장·간판)은 화면과 같이 움직인다
CONTENT_VER = 4                   # 판정(자·문턱)이 바뀌면 올린다 — 캐시 열쇠
# 글자 문턱 — 표본 762컷(10-25 494컷 + 10-25 오검출 수리 268컷: 원본 무작위 구간·잇템로그 ep12·박정수·샤크탱크 원편) 오푸스 눈 라벨.
#   pos 132(원본 쇼츠 가격·자막·제목 띠·방송사 자막·로고·광고 글) / neg 630(제품 포장·상자·라벨·간판·화면 속 글).
#   id crc32 짝수로 정하고 홀수로 잰 값(정직한 값): 옛 판정 P 0.857·R 0.677 → 지금 P 0.900·R 0.726. 옛 494컷만: P 0.808→0.863 · R 0.94 그대로.
#   ★재현율이 0.9 아래인 까닭 = 새로 넣은 틱톡형 작은 자막(창 높이 2.5~3.5%·흰 글 얇은 테) 29컷 — 옛 판정도 0.554(그대로 못 잡던 것). 남는 오검출 = 손에 든 포장 글(ep10 컷 5)·멈춘 화면 큰 제품 글(트럭·캔).
#   10-25 획 붙박이(d_gl, 98 #99): 틱톡형 작은 자막은 얇은 글씨라 상자 넓이 대부분이 글자 사이 배경 — 상자 평균(d_in)이 배경을 따라 움직여 붙박이로 안 잡혔다.
#     획 픽셀(오츠 적은 쪽)만 재면 박힌 글은 0 근처. 짝수 반으로 정하고 홀수 반으로 잰 값: P 0.900→0.917 · R 0.726→0.887(오검출 그대로 5) · 옛 494컷 P 0.863·R 0.94 그대로 · 전체 오검출 13 그대로.
TEXT_SCORE_MIN = 0.9              # 상자 점수(윤곽 안 확률 평균)
TEXT_FILL_MIN = 0.8               # 윤곽 넓이/사각형 넓이(얼굴·유리 질감을 따라 번진 가짜 윤곽 거르기 — 박힌 글은 0.85~0.95)
TEXT_ASPECT_MIN = 1.6             # 가로/세로 — 글줄 모양
TEXT_H_RANGE = (0.035, 0.25)      # 상자 높이 / 창 높이 — 진열대 가격표(0.01~0.03)는 밖
TEXT_BLUR_MAX = 0.3               # 흐림 칸이 이만큼 넘게 덮으면 이미 가린 글
TEXT_STILL_RATIO = 0.5            # 상자 안 변화 / 둘레 변화 < 이 값이면 붙박이(박힌 글) — 움직이는 화면 위 자막
TEXT_RING_MIN = 1.0               # 둘레 변화가 이보다 작으면(멈춘 화면) 붙박이를 잴 수 없다 → 크기로만(TEXT_STATIC_H)
TEXT_STATIC_H = 0.05              # 멈춘 화면에서는 높이 ≥ 창 5% 글줄만(제목 띠·큰 자막)
TEXT_FAR_RING = 5.0               # 긴 간격(같은 컷 다른 잴 프레임) 둘레 변화가 이 이상이어야 그 짝을 쓴다(화면이 실제로 바뀐 짝만)
TEXT_SCENE_RATIO = (0.6, 1.3)     # 멈춘 화면 글: 긴 간격 짝에서 안/둘레 가 이 범위 = 글이 주변과 같이 변함 = 장면 속 글(카레 상자 팬·전구 무늬·성시경 간판). 표본 0.5~0.7 / 1.2~1.5 어디서나 같은 결과
TEXT_SMALL_H = 0.03               # 창 3~3.5% 작은 글줄은 긴 간격 짝 전부에서 안/둘레 < TEXT_SMALL_STILL 일 때만(배경이 바뀌는 동안 그대로 = 박힌 자막 — 진열대 가격표는 같이 움직인다)
TEXT_SMALL_STILL = 0.6
TEXT_GLYPH_STILL = 0.3            # 획 픽셀 변화(d_gl) / 둘레 변화 < 이 값 = 획이 그대로인 박힌 글(자막 줄). 짝수 반 0.3~0.5 같은 결과(0.2 는 R 0.91), 홀수 반 오검출 +0
TEXT_GLYPH_FILL = 0.65            # 획 판정 상자 채움 하한 — 작은 자막 줄은 낱말 사이 틈 때문에 0.70~0.79(TEXT_FILL_MIN 0.8 밖). 0.6~0.7 같은 결과
TEXT_GLYPH_ASPECT = 3.0           # 획 판정은 글줄(가로/세로 ≥ 3)만 — 1.6 이면 짝수 반 오검출 +4
TEXT_GLYPH_RING = 2.0             # 둘레 변화가 이 이상(배경이 실제로 움직인 짝)일 때만 획 판정
FACE_OTHER_COS = 0.25             # 기준 얼굴(카드 통과 얼굴들) 중 가장 닮은 것과 SFace 코사인이 이 아래면 다른 사람(표본 286얼굴: 0.25 P 0.96·R 0.90, 0.20 P 0.98·R 0.83)
FACE_MIN_H = 0.12                 # 잴 얼굴 높이 / 창 높이 하한 — 표본에서 0.12~0.2 연예인 얼굴도 코사인 0.65~0.97 로 맞았다(vision.JUDGE_H 0.2 는 자라 모델·콜라주 얼굴을 놓친다)
TEXT_MIN_HITS = 1                 # 컷 3장 중 글자 걸린 장 수 — 1(2로 올리면 표본 R 0.78: 짧게 지나가는 자막을 놓친다)
FACE_NEST = 0.7                   # 더 큰 얼굴 상자 안에 넓이 70%+ 들어간 얼굴 = 같은 얼굴 겹친 검출(표본: 옛 5개 전부 바깥 얼굴과 같은 사람 · 박정수 컷 8)
FACE_YAW_MAX = 1.0                # |코−눈가운데|/눈사이 > 1 = 코가 눈 폭 밖(손 가림·고개 돌림) — 관문 창 표본 연예인 3·남 0, 옛 표본 둘 다 0(남 최대 0.97)
FACE_MIN_HITS = 2                 # 컷 3장 중 남 얼굴 걸린 장 수 — 한 장 오검출로 렌더를 막지 않게


def look_times(n: int) -> list[float]:
    """컷 안 재는 시각(컷 시작부터 초) — 처음·가운데·끝 근처 3장."""
    d = n / FPS
    return [round(x, 3) for x in (min(0.2, d / 4), d / 2, max(d - 0.2, 3 * d / 4))]


# ── 컷 프레임 뽑기 주인(10-26 관문 속도, 98 #?) — 접촉 시트·관문 ④·plan_canvas 가 같은 함수로 같은 프레임을 한 번만 뽑는다 ──
# 그림 주인은 그대로 thumb.card_scene_frame(file 자리 · -ss 를 -i 앞에 둔 빠른 찾기 + ffmpeg 정확 찾기 · 흐림 → crop → scale). 여기는 그 결과를
#   ① 프로세스 안 기억(열쇠 = 원본 경로·크기·mtime · t · crop · 창 · 흐림 칸 — 같은 열쇠 = 같은 ffmpeg 명령 = 같은 픽셀)
#   ② 서로 상관없는 프레임을 동시에 FRAME_JOBS 개까지(ffmpeg 프로세스 — 판정 계산은 그대로 한 줄로)
# 로 나눠 쓸 뿐이다. 10-26 회원 마스크편 실측: 접촉 시트 57장 45초 + 관문 ④ 114장(시트와 같은 57장 다시) — 프레임 한 장 0.7초.
FRAME_JOBS = 6                   # 동시 ffmpeg 상한(프레임 뽑기·⑦ 회색 읽기)
FRAME_MEMO_MAX = 1_200_000_000   # 기억 상한(바이트) — 넘으면 오래된 것부터 버린다(다시 뽑으면 같은 그림)
_FRAME_MEMO: dict = {}
_FRAME_MEMO_N = [0]
_FRAME_LOCK = None


def src_ident(src: Path) -> list:
    """원본 정체 = [경로, 크기, mtime_ns] — 같은 이름으로 다시 받은 원본을 옛 기억·캐시로 보지 않게."""
    p = Path(src)
    try:
        s = p.stat()
        return [str(p), int(s.st_size), int(s.st_mtime_ns)]
    except OSError:
        return [str(p), -1, -1]


def _frame_key(src: Path, t: float, crop, win, blur) -> str:
    return json.dumps([src_ident(src), repr(float(t)), list(crop) if crop else None, list(win), blur])


def _lock():
    global _FRAME_LOCK
    if _FRAME_LOCK is None:
        import threading
        _FRAME_LOCK = threading.Lock()
    return _FRAME_LOCK


def _frame_get(k: str):
    with _lock():
        if k in _FRAME_MEMO:
            v = _FRAME_MEMO.pop(k)
            _FRAME_MEMO[k] = v          # 최근 쓴 것을 뒤로(오래된 것부터 버린다)
            return True, v
    return False, None


def _frame_put(k: str, im):
    with _lock():
        if k in _FRAME_MEMO:
            return
        _FRAME_MEMO[k] = im
        _FRAME_MEMO_N[0] += im.nbytes if im is not None else 0
        while _FRAME_MEMO_N[0] > FRAME_MEMO_MAX and len(_FRAME_MEMO) > 1:
            old = _FRAME_MEMO.pop(next(iter(_FRAME_MEMO)))
            _FRAME_MEMO_N[0] -= old.nbytes if old is not None else 0


def _frame_read(src: Path, t: float, crop, win, blur):
    from tools.calcopy.hybrid import thumb as TH
    im = TH.card_scene_frame({"file": str(src), "ss": t, "crop": crop}, {}, Path("."), win, blur=blur)[0]
    return im                           # 나눠 쓰는 그림 — 고치려면 .copy()(지금 부르는 쪽은 읽기만: 접촉 시트·글자·얼굴 자·plan_canvas)


def cut_frames(reqs: list, jobs: int | None = None) -> list:
    """(판단 주인 — 컷 프레임 뽑기) reqs = [(src, t, crop, win, blur)…] → 같은 순서의 그림(창 크기 BGR, 나눠 쓰니 고치지 말 것) 또는 None.
    기억에 없는 것만 ffmpeg 로 — 서로 다른 프레임은 동시에 jobs(기본 FRAME_JOBS)개까지."""
    keys = [_frame_key(*r) for r in reqs]
    out: dict = {}
    todo = {}
    for k, r in zip(keys, reqs):
        hit, v = _frame_get(k)
        if hit:
            out[k] = v
        elif k not in todo:
            todo[k] = r
    if todo:
        n = max(1, min(jobs or FRAME_JOBS, len(todo)))
        if n == 1:
            got = [_frame_read(*r) for r in todo.values()]
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(n) as ex:
                got = list(ex.map(lambda r: _frame_read(*r), todo.values()))
        for k, im in zip(todo, got):
            _frame_put(k, im)
            out[k] = im
    return [out[k] for k in keys]


def cut_frame(src: Path, t: float, crop, win: tuple[int, int], blur=None):
    """렌더 조각과 같은 그림(창 크기 BGR, 나눠 쓰니 고치지 말 것) — 주인 thumb.card_scene_frame(file 자리) + 같은 흐림. 뽑기·기억 = cut_frames."""
    return cut_frames([(src, t, crop, win, blur)], jobs=1)[0]


def blur_cover(regs, crop, win: tuple[int, int], box, t: float) -> float:
    """창 좌표 상자 넓이 중 그 시각(원본 초 t) 켜진 흐림 칸이 덮는 비율. 흐린 글도 글자 검출기는 글로 본다(표본 08 blurtest 점수 0.99) — 그래서 덮인 상자는 뺀다."""
    import numpy as np
    if not regs:
        return 0.0
    cx, cy, cw, ch = crop
    sx, sy = win[0] / cw, win[1] / ch
    x0, y0, x1, y1 = box
    m = np.zeros((max(1, y1 - y0), max(1, x1 - x0)), bool)
    for r in regs:
        if len(r) >= 6 and not (float(r[4]) <= t <= float(r[5])):
            continue
        bx0, by0 = (r[0] - cx) * sx, (r[1] - cy) * sy
        a0, b0 = int(max(0, bx0 - x0)), int(max(0, by0 - y0))
        a1, b1 = int(min(x1 - x0, bx0 + r[2] * sx - x0)), int(min(y1 - y0, by0 + r[3] * sy - y0))
        if a1 > a0 and b1 > b0:
            m[b0:b1, a0:a1] = True
    return round(float(m.mean()), 3)


def _in_ring(diff, box) -> list[float]:
    """상자 안 평균 변화 · 둘레(상자 높이만큼 넓힌 테) 평균 변화."""
    H, W = diff.shape
    x0, y0, x1, y1 = box
    bh = max(1, y1 - y0)
    ring = diff[max(0, y0 - bh):min(H, y1 + bh), max(0, x0 - bh):min(W, x1 + bh)]
    inner = diff[y0:y1, x0:x1]
    return [round(float(inner.mean()), 2) if inner.size else 0.0, round(float((ring.sum() - inner.sum()) / max(1, ring.size - inner.size)), 2)]


def _glyph_diff(g, diffs, box) -> list[float]:
    """상자 안 '획 픽셀'(오츠 두 무리 중 적은 쪽 = 글자 획) 위 평균 변화 — diffs 마다 하나.
    얇은 글씨(틱톡형 작은 자막·흰 글 얇은 테)는 상자 넓이 대부분이 글자 사이 배경이라 상자 평균(d_in)이 배경 움직임을 따라간다 — 획만 보면 박힌 글은 0 근처."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = box
    p = g[y0:y1, x0:x1]
    if p.size < 16:
        return [0.0 for _ in diffs]
    u = p.astype(np.uint8)
    _, m = cv2.threshold(u, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    m = m.astype(bool)
    if m.mean() > 0.5:
        m = ~m
    if not m.any():
        return [0.0 for _ in diffs]
    return [round(float(d[y0:y1, x0:x1][m].mean()), 2) for d in diffs]


def text_feats(a, b, regs=None, crop=None, win=None, t: float = 0.0, far=(), boxes=None) -> list[dict]:
    """한 프레임(a)의 글자 상자마다 잰 값 — 판정은 foreign_text. b = CONTENT_PAIR 뒤(또는 앞) 프레임(붙박이 재기).
    far = 같은 컷의 다른 잴 프레임들(긴 간격 0.4초+ — 천천히 훑는 화면·멈춘 듯한 화면에서도 글이 주변과 같이 변하는지 본다) → fi = [[안, 둘레]…].
    boxes = 이 프레임(a)의 vision.text_boxes_scored 결과(같은 프레임 열쇠로 캐시해 둔 것 — cut_content_feats). 없으면 여기서 잰다."""
    import cv2
    import numpy as np
    from shopping_shorts.channelkit import vision as V
    gray = lambda im: cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    ga = gray(a)
    gb = gray(b) if b is not None else ga
    diff = np.abs(ga - gb)
    dfar = [np.abs(ga - gray(x)) for x in far if x is not None and x.shape == a.shape]
    H, W = ga.shape
    out = []
    for q in (V.text_boxes_scored(a) if boxes is None else boxes):
        x0, y0, x1, y1 = q["box"]
        bw, bh = max(1, x1 - x0), max(1, y1 - y0)
        d_in, d_ring = _in_ring(diff, (x0, y0, x1, y1))
        gl = _glyph_diff(ga, [diff] + dfar, (x0, y0, x1, y1))
        out.append({"box": [x0, y0, x1, y1], "score": q["score"], "fill": q["fill"], "aspect": round(bw / bh, 2), "h": round(bh / H, 4),
                    "cx": round((x0 + x1) / 2 / W, 3), "cy": round((y0 + y1) / 2 / H, 3),
                    "d_in": d_in, "d_ring": d_ring, "d_gl": gl[0], "fg": gl[1:],
                    "fi": [_in_ring(d, (x0, y0, x1, y1)) for d in dfar],
                    "blur": blur_cover(regs, crop, win, (x0, y0, x1, y1), t) if regs else 0.0})
    return out


def content_times(ss: float, n: int) -> tuple[list[float], list[float]]:
    """관문 ④가 컷 하나에서 읽는 시각(원본 초) — 잴 프레임 3장(look_times)과 그 짝(CONTENT_PAIR 뒤, 컷 끝이면 앞)."""
    ss = float(ss)
    d = n / FPS
    ts = [ss + dt for dt in look_times(n)]
    return ts, [t + CONTENT_PAIR if (t - ss) + CONTENT_PAIR < d else t - CONTENT_PAIR for t in ts]


def cut_content_feats(src: Path, ss: float, n: int, crop, win: tuple[int, int], regs=None, anchors=(), ocr: dict | None = None) -> dict:
    """관문 ④가 재는 값(판정 전) — 컷 하나의 잴 프레임 3장(look_times)마다 글자 상자 값(text_feats)·얼굴 값(face_feats).
    표본 수집(test_cut_content_labels 표본)도 이 함수를 그대로 부른다 — 관문과 표본이 같은 자.
    프레임 = cut_frames(접촉 시트와 같은 열쇠 — 이미 뽑은 그림은 다시 안 뽑는다). ocr = {프레임 열쇠: text_boxes_scored 결과} 캐시(주면 읽고 채운다)."""
    ss = float(ss)
    ts, t2s = content_times(ss, n)
    fr = cut_frames([(src, t, crop, win, regs) for t in ts + t2s])
    A, B = fr[:len(ts)], fr[len(ts):]
    r = {"text": [], "face": []}
    for i, (t, a) in enumerate(zip(ts, A)):
        if a is None:
            continue
        boxes = None
        if ocr is not None:
            ok = ocr_key(src, t, crop, win, regs)
            boxes = ocr.get(ok)
            if boxes is None:
                from shopping_shorts.channelkit import vision as V
                boxes = ocr[ok] = [{"box": list(q["box"]), "score": q["score"], "fill": q["fill"]} for q in V.text_boxes_scored(a)]
        r["text"].append(text_feats(a, B[i], regs, crop, win, t, far=[x for j, x in enumerate(A) if j != i], boxes=boxes))
        if anchors:
            r["face"].append(face_feats(a, anchors))
    return r


def ocr_key(src: Path, t: float, crop, win, regs) -> str:
    """글자 상자 캐시 열쇠 = 프레임 열쇠(원본 정체·t·crop·창·흐림) + CONTENT_VER."""
    import hashlib
    return hashlib.md5((_frame_key(src, t, crop, win, regs) + f"|v{CONTENT_VER}").encode()).hexdigest()[:20]


CACHE_KEEP = 3000          # cut_content.json·cut_ocr.json 에 남기는 항목 수(옛 계획 컷도 남긴다 — 대본↔장면을 오가면 같은 컷이 돌아온다)


def _cache_load(p: Path | None) -> dict:
    try:
        return jload(p) if (p and p.exists()) else {}
    except Exception:  # noqa: BLE001 — 깨진 캐시 = 빈 캐시(다시 잰다)
        return {}


def _cache_save(p: Path | None, old: dict, now: dict):
    """옛 항목 뒤에 이번 항목(최근 것이 뒤) — CACHE_KEEP 넘으면 앞(오래된 것)부터 버린다."""
    if not p:
        return
    allk = {k: v for k, v in old.items() if k not in now}
    allk.update(now)
    keep = dict(list(allk.items())[-CACHE_KEEP:])
    jsave(p, keep)


def foreign_text(f: dict) -> bool:
    """글자 상자 하나가 '남의 박힌 글자(자막·워터마크·로고 글)'인가 — 판정 주인. 표본(오푸스 눈) 정밀도·재현율은 test_cut_content_labels.
    fi(긴 간격 짝)·d_gl(획 변화) 가 없는 옛 값은 그 판정을 건너뛴다(옛 판정 그대로)."""
    if f["blur"] > TEXT_BLUR_MAX:
        return False
    if (f.get("d_gl") is not None and f["score"] >= TEXT_SCORE_MIN and f["fill"] >= TEXT_GLYPH_FILL and f["aspect"] >= TEXT_GLYPH_ASPECT
            and TEXT_SMALL_H <= f["h"] <= TEXT_H_RANGE[1] and f["d_ring"] >= TEXT_GLYPH_RING and f["d_gl"] < TEXT_GLYPH_STILL * f["d_ring"]):
        return True               # 획 붙박이 — 움직이는 배경 위 획이 그대로인 글줄(틱톡형 작은 자막 포함). d_gl 없는 옛 값은 건너뜀
    if f["score"] < TEXT_SCORE_MIN or f["fill"] < TEXT_FILL_MIN or f["aspect"] < TEXT_ASPECT_MIN:
        return False
    if not (TEXT_SMALL_H <= f["h"] <= TEXT_H_RANGE[1]):
        return False
    far = [i / r for i, r in (f.get("fi") or []) if r >= TEXT_FAR_RING]
    small = f["h"] < TEXT_H_RANGE[0]
    if small and not (far and max(far) < TEXT_SMALL_STILL):
        return False
    if f["d_ring"] < TEXT_RING_MIN:
        if any(TEXT_SCENE_RATIO[0] <= q <= TEXT_SCENE_RATIO[1] for q in far):
            return False          # 2프레임 사이엔 멈췄지만 같은 컷 안 긴 간격에서 주변과 같이 변한 글 = 장면 속 글
        return f["h"] >= TEXT_STATIC_H or small
    return f["d_in"] < TEXT_STILL_RATIO * f["d_ring"]


def other_face(f: dict) -> bool:
    """얼굴 하나가 연예인(기준 얼굴)이 아닌 다른 사람인가 — 판정 주인. f = {h(창 높이 비), cos(기준 얼굴 중 최댓값) | None}.
    표본 = 감사 결함 완성본 8편(함익병 도브·박세리 라프레리 2·안유진·함익병 비누·강민경·최은경) + 얼지마트롯 원본 4편, 오푸스 눈 라벨."""
    if f.get("nest") or (f.get("yaw") is not None and abs(f["yaw"]) > FACE_YAW_MAX):
        return False      # 겹친 검출·정렬 깨진 얼굴은 동일성을 잴 수 없다(표본 face 행 nest·yaw — 없으면 옛 판정 그대로)
    return f["h"] >= FACE_MIN_H and f.get("cos") is not None and f["cos"] < FACE_OTHER_COS


def face_feats(im, anchors: list) -> list[dict]:
    """잴 얼굴(높이 ≥ FACE_MIN_H)마다 {h, box, cos = 기준 얼굴 중 최댓값, nest, yaw}.
    nest = 더 큰 얼굴 상자 안에 넓이 FACE_NEST 이상 들어간 얼굴(같은 얼굴의 겹친 검출 — 10-25 박정수 컷 8 근접 크롭 코 둘레 상자 cos 0.18)
    yaw  = (코 x − 두 눈 가운데 x) / 눈 사이 — 임베딩 정렬(alignCrop)에 쓰는 YuNet 랜드마크 그대로. |yaw| > FACE_YAW_MAX 면 코가 눈 폭 밖 = 손에 가림·옆얼굴로 정렬이 깨진 얼굴."""
    from shopping_shorts.channelkit import vision as V
    fs = V.faces_all(im, min_h=FACE_MIN_H)
    raw = V._raw_rows(im) if fs else None
    Hh, Ww = im.shape[:2]
    out = []
    for f, e in fs:
        yaw = None
        if raw is not None and len(raw):
            fx, fy = (f["x"] + f["w"] / 2) * Ww, (f["y"] + f["h"] / 2) * Hh
            row = min(raw, key=lambda r: (r[0] + r[2] / 2 - fx) ** 2 + (r[1] + r[3] / 2 - fy) ** 2)      # vision.embedding 과 같은 행 고르기
            yaw = round(float((row[8] - (row[4] + row[6]) / 2) / (abs(row[6] - row[4]) + 1e-6)), 3)
        a = f["w"] * f["h"]
        nest = any(g is not f and g["w"] * g["h"] > a and
                   max(0, min(f["x"] + f["w"], g["x"] + g["w"]) - max(f["x"], g["x"])) * max(0, min(f["y"] + f["h"], g["y"] + g["h"]) - max(f["y"], g["y"])) >= FACE_NEST * a
                   for g, _ in fs)
        out.append({"h": round(f["h"], 3), "box": [f["x"], f["y"], f["w"], f["h"]],
                    "cos": round(max(V.cos(a_, e) for a_ in anchors), 3) if (e is not None and anchors) else None, "nest": nest, "yaw": yaw})
    return out


def face_anchors(st: dict, doc: Path, T: dict, cand_dir: Path) -> list:
    """연예인 기준 얼굴 = 썸네일 카드 3안 장면 중 thumb.card_faces 를 통과한 안의 가장 큰 얼굴 SFace 임베딩(카드 얼굴 관문 ⑥과 같은 장면)."""
    from shopping_shorts.channelkit import vision as V
    from tools.calcopy.hybrid import thumb as TH
    sp = Path(doc) / "썸네일.json"
    if not sp.exists():
        return []
    ok = {r["id"] for r in TH.card_faces(st, doc, T, cand_dir) if r["ok"]}
    _, _, ww, wh = frame_window(st["frame"])
    out = []
    for o in jload(sp).get("options") or []:
        if o.get("id") not in ok:
            continue
        im, _ = TH.card_scene_frame(o, T, cand_dir, (ww, wh))
        fs = V.faces_all(im) if im is not None else []
        if fs:
            f, e = max(fs, key=lambda z: z[0]["h"])
            if e is not None:
                out.append(e)
    return out


def blur_entry(boxes: list, crop: list, win: tuple, ss: float, sec: float, pad: int = 8) -> list:
    """(판단 주인 — 창 좌표 글자 상자 → 재료.blur 한 칸) 창 [x0,y0,x1,y1] 들을 합친 칸을 원본 픽셀 [x, y, w, h, 시작초, 끝초]로.
    10-26 까르보: 반려 문구가 창 좌표만 줘서 고치는 쪽이 원본 좌표로 바꾸다 세 번 다 어긋났다(같은 'NOOO!' 자막 3번 반려)."""
    ww, wh = win
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes); x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    sx, sy = crop[2] / ww, crop[3] / wh
    ax, ay = crop[0] + x0 * sx - pad, crop[1] + y0 * sy - pad
    bx, by = crop[0] + x1 * sx + pad, crop[1] + y1 * sy + pad
    ax, ay = max(crop[0], int(ax)), max(crop[1], int(ay))
    bx, by = min(crop[0] + crop[2], int(bx + 0.5)), min(crop[1] + crop[3], int(by + 0.5))
    return [ax, ay, bx - ax, by - ay, round(ss, 3), round(ss + sec, 3)]


def cut_content_gate(T: dict, M: dict, st: dict, doc: Path | None = None, R: Path | None = None, log=print, erase: list | None = None) -> list[str]:
    """렌더 전 관문 ④(10-25 감사 남의 글자 33·남 얼굴 15): 계획의 컷마다 렌더 조각과 같은 프레임 3장(cut_crop·blur)을 원본에서 뽑아
      ① 글자: 흐림 밖에 남의 박힌 글자(자막·워터마크·로고 글)가 TEXT_MIN_HITS 장 이상이면 멈춤(foreign_text)
      ② 얼굴(연예인 판 thumb_card_face=true): 기준 얼굴(카드 통과 얼굴)과 다른 사람의 큰 얼굴이 FACE_MIN_HITS 장 이상이면 멈춤(other_face)
    문제 목록(빈 목록 = 통과). 잰 값은 R/cut_content.json 캐시(열쇠 = 원본 정체(경로·크기·mtime)·ss·프레임 수·crop·blur·기준 얼굴·CONTENT_VER),
    프레임마다 글자 상자는 R/cut_ocr.json(ocr_key) — 둘 다 옛 계획 컷을 남긴다(대본↔장면을 오가도 같은 컷·같은 프레임은 다시 안 잰다).
    캐시 없는 컷의 프레임은 FRAME_JOBS 개씩 미리 뽑아 두고(cut_frames) 판정 계산은 컷 순서대로 한 줄로(결과·문구 순서 그대로).
    다른 제품(감사 눈3 24건)은 기계로 잴 자가 없어 이 관문 밖 — 접촉 시트 눈 검사 몫.
    erase = 목록을 주면(박힌 글자를 VMake 로 지우는 판의 계획 — render 가 vmake_clean.will_erase 로 정한다) 글자 컷은 멈추지 않고 그 컷 번호를 erase 에 담는다(사장님 10-26).
    얼굴은 지울 수 없으니 그대로 멈춘다."""
    import hashlib
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    if not src_dir:
        return []
    _, _, ww, wh = frame_window(st["frame"])
    anchors = face_anchors(st, doc, T, src_dir) if (st.get("thumb_card_face") and doc) else []
    if st.get("thumb_card_face") and not anchors:
        log("[관문④] 연예인 판인데 기준 얼굴 없음(썸네일.json 없음 또는 카드 얼굴 통과 0) — 얼굴 판정 건너뜀, 글자만 잰다")
    ak = hashlib.md5(b"".join(a.tobytes() for a in anchors)).hexdigest()[:8] if anchors else "-"
    cp = (R / "cut_content.json") if R else None
    op = (R / "cut_ocr.json") if R else None
    cache, ocr0 = _cache_load(cp), _cache_load(op)
    ocr = dict(ocr0)
    jobs = []
    for k, c in enumerate(T["cuts"]):
        src = src_dir / c["src"]
        if c.get("ss") is None or src.suffix.lower() in IMG_EXT or not src.exists():
            continue
        n = src_frames(c)                  # 원본에서 쓰는 프레임 — 재는 시각 = 렌더 조각이 실제로 보여 주는 원본 초(늦춘 컷이 다음 샷을 재지 않게)
        crop = cut_crop(c, src, (ww, wh))
        regs = (M.get("blur") or {}).get(c["src"])
        key = hashlib.md5(json.dumps([c["src"], src_ident(src)[1:], round(float(c["ss"]), 3), n, crop, regs, ak, CONTENT_VER, ww, wh]).encode()).hexdigest()[:16]
        jobs.append((k, c, src, n, crop, regs, key))
    todo = [j for j in jobs if j[6] not in cache]
    pre = {}
    if todo:
        from concurrent.futures import ThreadPoolExecutor
        ex = ThreadPoolExecutor(min(FRAME_JOBS, len(todo)))
        for (k, c, src, n, crop, regs, key) in todo:      # 프레임만 미리(ffmpeg 동시) — 판정 계산은 아래 순서대로
            ts, t2s = content_times(c["ss"], n)
            pre[key] = ex.submit(cut_frames, [(src, t, crop, (ww, wh), regs) for t in ts + t2s], 1)
    bad, rows = [], {}
    try:
        for (k, c, src, n, crop, regs, key) in jobs:
            r = cache.get(key)
            if r is None:
                pre[key].result()
                m = cut_content_feats(src, c["ss"], n, crop, (ww, wh), regs, anchors, ocr=ocr)
                r = {"text": [[f for f in fr if foreign_text(f)] for fr in m["text"]], "face": [[f for f in fr if other_face(f)] for fr in m["face"]]}
            rows[key] = r
            nt = sum(1 for x in r["text"] if x)
            nf = sum(1 for x in r["face"] if x)
            where = f"{c['line']} {c['src']}@{float(c['ss']):.2f}"
            if nt >= TEXT_MIN_HITS and erase is not None:
                erase.append(k)
            elif nt >= TEXT_MIN_HITS:
                boxes = [f["box"] for x in r["text"] for f in x][:3]
                bad.append(f"컷 {k} {where}: 흐림 밖 남의 박힌 글자 {nt}/{len(r['text'])}장(창 좌표 {boxes}) — 재료.json blur[{c['src']}] 에 "
                           f"이 칸을 그대로 넣거나(원본 픽셀·원본 초로 바꿔 둠) crop·ss 를 옮긴다: {blur_entry(boxes, crop, (ww, wh), float(c['ss']), n / FPS)}")
            if nf >= FACE_MIN_HITS:
                cs = [f["cos"] for x in r["face"] for f in x][:3]
                bad.append(f"컷 {k} {where}: 연예인 아닌 얼굴 {nf}/{len(r['face'])}장(기준 얼굴 코사인 {cs} < {FACE_OTHER_COS}) — 연예인이 나오는 장면으로 바꾼다")
    finally:
        if todo:
            ex.shutdown(wait=True, cancel_futures=True)
    _cache_save(cp, cache, rows)
    if len(ocr) != len(ocr0):
        _cache_save(op, ocr0, {k: v for k, v in ocr.items() if k not in ocr0})
    return bad


SHEET_W = 360      # 접촉 시트 한 장 폭(px) — 98 #63 "0.5초 시트(220px)로는 컵·워터마크가 안 보였다"


def contact_sheet(T: dict, M: dict, st: dict, out: Path, S: dict | None = None) -> Path | None:
    """G-10 렌더 없는 눈 검사 — 계획 컷마다 처음·가운데·끝 3장(look_times)을 렌더 조각과 같은 그림(cut_frame·cut_crop·재료 blur = 관문 ④와 같은 프레임)으로
    원본에서 뽑아 한 줄씩. 칸 머리 = 컷 번호·줄·시각·원본@ss + 그 줄 글. 남의 글자·얼굴·다른 제품·술·같은 장면 반복을 렌더 전에 눈으로 본다.
    반환 = 쓴 jpg(컷 없으면 None)."""
    import numpy as np
    from PIL import Image, ImageDraw
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    if not src_dir or not T.get("cuts"):
        return None
    _, _, ww, wh = frame_window(st["frame"])
    th = round(SHEET_W * wh / ww)
    head = 44
    text = {L["id"]: L.get("tts") or " ".join(c["text"] for c in caps_of(L)) for L in (S or {}).get("lines", [])}
    f1, f2 = _font("Pretendard-Regular.otf", 20), _font("Pretendard-Regular.otf", 17)
    reqs = []          # 칸 그림을 먼저 한꺼번에(cut_frames — 동시 FRAME_JOBS 개, 관문 ④가 같은 열쇠로 다시 쓴다)
    for c in T["cuts"]:
        src = src_dir / c["src"]
        if src.exists():
            img = src.suffix.lower() in IMG_EXT
            n = src_frames(c)              # 관문 ④·아래 칸과 같은 원본 프레임(늦춘 컷)
            crop = cut_crop(c, src, (ww, wh))
            regs = (M.get("blur") or {}).get(c["src"])
            reqs += [(src, 0.0 if img else float(c.get("ss") or 0) + dt, crop, (ww, wh), regs) for dt in ([0.0] if img else look_times(n))]
    cut_frames(reqs)
    rows = []
    for k, c in enumerate(T["cuts"]):
        src = src_dir / c["src"]
        row = Image.new("RGB", (SHEET_W * 3, head + th), (20, 20, 20))
        dr = ImageDraw.Draw(row)
        dr.text((6, 2), f"#{k} {c['line']} {c['t0']:.2f}~{c['t1']:.2f}s  {c['src']}@{c.get('ss')}", font=f1, fill=(255, 220, 0))
        dr.text((6, 24), str(text.get(c["line"], ""))[:60], font=f2, fill=(230, 230, 230))
        if src.exists():
            img = src.suffix.lower() in IMG_EXT
            n = src_frames(c)              # 관문 ④와 같은 원본 프레임(늦춘 컷)
            crop = cut_crop(c, src, (ww, wh))
            regs = (M.get("blur") or {}).get(c["src"])
            for j, dt in enumerate([0.0] if img else look_times(n)):
                a = cut_frame(src, 0.0 if img else float(c.get("ss") or 0) + dt, crop, (ww, wh), regs)
                if a is None:
                    continue
                row.paste(Image.fromarray(np.ascontiguousarray(a[:, :, ::-1])).resize((SHEET_W, th)), (j * SHEET_W, head))
        rows.append(row)
    sheet = Image.new("RGB", (SHEET_W * 3, sum(r.height for r in rows)), (0, 0, 0))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y)); y += r.height
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


def count_frames(p: Path) -> int:
    return int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                    "-of", "csv=p=0", p]).stdout.strip().split(",")[0] or 0)   # ICC side_data 면 '78,' (98 #73)


def pic_box(c: dict, win: tuple[int, int]) -> list[int] | None:
    """컷 그림 칸(관제 263 02 2차 ⑥) — 재료.json 컷 pic[x,y,w,h](창 안 px). 없으면 None(창 가득, 옛 그림). 창 밖이면 멈춘다."""
    pb = c.get("pic")
    if not pb:
        return None
    x, y, w, h = (int(v) for v in pb)
    if x < 0 or y < 0 or w < 16 or h < 16 or x + w > win[0] or y + h > win[1]:
        raise StageError(f"컷 pic {pb} 가 창 {list(win)} 밖")
    return [x, y, w - (w & 1), h - (h & 1)]          # yuv420 = 짝수 크기


def clip(src: Path, ss: float, n: int, crop, win: tuple[int, int], out: Path, push: float = 0.0, move=None, blur=None, pic=None, pic_bg=None, speed: float = 1.0):
    """컷 조각 하나 — 창 크기(win) 영상. pic[x,y,w,h] 를 주면 그 칸 크기로 그리고 창 나머지는 pic_bg 색(틀 바탕)으로 채운다(컷마다 그림 칸 크기)."""
    inp, vf, extra = clip_cmd(src, ss, n, crop, win, push, move, blur, pic, pic_bg, speed)
    run(["ffmpeg", "-y", "-v", "error", *inp, "-vf", vf, "-frames:v", n, *extra, *venc(16), "-pix_fmt", "yuv420p", *(["-color_range", "tv", "-colorspace", "bt709"] if src.suffix.lower() in IMG_EXT else []), out])


def clip_cmd(src: Path, ss: float, n: int, crop, win: tuple[int, int], push: float = 0.0, move=None, blur=None, pic=None, pic_bg=None,
             speed: float = 1.0) -> tuple[list, str, list]:
    """(판단 주인) 컷 조각이 어떤 그림이 되나 — (입력 인자, 필터, 출력 인자). clip(조각 굽기)·cut_still_gate(관문 ⑦ 멈춤 재기)가 같이 부른다.
    speed<1 = fit_cut 이 정한 샷 안 늦춤 — 원본 n×speed 프레임을 n 프레임으로 고르게 늘린다(setpts, 숏템메이커 video_assemble.cut_setpts 와 같은 꼴, 멈춤 프레임 없음)."""
    ww, wh = win
    tw, th = (pic[2], pic[3]) if pic else (ww, wh)
    pad = f",pad={ww}:{wh}:{pic[0]}:{pic[1]}:color=0x{''.join(f'{v:02X}' for v in _rgb(pic_bg or [0, 0, 0]))}" if pic else ""
    if src.suffix.lower() in IMG_EXT:
        from tools.calcopy import narr_video as nv
        x, y, cw, ch = crop
        mv = nv.still_move(src, crop, tw / th, n / FPS, move or "in")
        # 사진(JPG)은 yuvj420p·pc·bt470bg 로 나온다 → 영상 조각(yuv420p·tv·bt709)과 이어 붙이면 render_base 가 그 경계에서
        # 필터를 다시 세우며 틀(제목·로고·출처 줄)을 2~4프레임 빠뜨린다(10-21 장윤주 실측: 쿠팡 사진 컷 앞뒤 2+4프레임 → 고친 뒤 0.
        # 최화정_피부 완성본에도 제목 빠짐 2+2프레임이 있었다 — 원인 대조는 안 함). 영상 조각과 같은 꼴로 맞춘다.
        vf = (f"crop={cw}:{ch}:{x}:{y},{mv}scale={tw}:{th}:flags=lanczos:out_range=tv:out_color_matrix=bt709{pad},"
              f"format=yuv420p,setsar=1")
        return ["-loop", "1", "-i", src], vf, ["-r", FPS]
    x, y, cw, ch = crop
    sp = float(speed or 1.0)
    bl = blur_vf(blur, ss, n * sp / FPS)                     # 흐림 시각 = 원본 초(늦추기 전 — setpts 는 흐림 뒤)
    pre = bl + "," if bl else ""
    slow = f"setpts=(PTS-STARTPTS)/{sp:.6f}," if sp < 1.0 - 1e-6 else ""
    vf = f"{pre}crop={cw}:{ch}:{x}:{y},scale={tw}:{th}:flags=lanczos,setsar=1{pad},{slow}fps={FPS}"
    if push:
        vf = (f"{pre}crop={cw}:{ch}:{x}:{y},scale={tw * 2}:{th * 2}:flags=lanczos,{slow}fps={FPS},"
              f"zoompan=z='1+{push}*on/{max(1, n)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={tw}x{th}:fps={FPS},setsar=1{pad}")
    return ["-ss", f"{ss:.3f}", "-i", src, "-an"], vf, []


# ── 장면 전환(A1) — 종류·자리 결정 = placement.place(placed["transitions"]), 여기는 읽기·그리기만 ──────────────
TRANSITION_KINDS = ("cut", "flash", "zoomblur", "black", "edge_glow")
TRANSITION_MS = {"flash": 100, "zoomblur": 200, "black": 33, "edge_glow": 450}     # 판 칸 cuts.transition.ms 가 0/없을 때 종류별 기본 길이 · edge_glow 450 = shark rules flash.dur(사건 길이, α 는 dur 칸)
ZOOMBLUR_ZOOM, ZOOMBLUR_SIGMA = 0.12, 14.0                         # 줌블러: 경계에서 최대 12% 확대 + gblur(가림 흐림 BLUR_SIGMA 와 별개 — 움직임 번짐)


def transitions_of(T: dict, st: dict, placed: dict, log=None) -> list[dict]:
    """전환 목록 [{t, kind, ms, sec?, why}] 한 곳 — render_window(줌블러·검은 프레임, 창 안)·render_base(흰 번쩍, 화면 전체)가 이것만 읽는다.
    종류·자리 판단 주인 = placement.place → placed["transitions"](지시서 03, 판 칸 cuts.transition.kinds 비율도 거기서 읽는다).
    여기는 **읽기·정리만**: 모르는 종류는 막고, ms 가 비면 판 cuts.transition.ms → 종류별 기본(TRANSITION_MS). cut 은 그릴 것 없음.
    placed 에 transitions 칸이 없는 옛 배치 결과(03 전)는 옛 키 flashes 를 kind=flash 로 읽는다(변환만 — 흰 번쩍 그림 그대로)."""
    F = st.get("frame") or {}
    ms_set = (st.get("cuts") or {}).get("transition", {}).get("ms") or 0
    ncf: dict = {}

    def norm(e):
        k = e.get("kind", "cut")
        if k not in TRANSITION_KINDS:
            raise StageError(f"전환 종류 '{k}' 모름 — {TRANSITION_KINDS}")
        m = e.get("ms") or (ms_set.get(k) if isinstance(ms_set, dict) else ms_set) or TRANSITION_MS.get(k, 0)
        out = {"t": round(float(e["t"]), 3), "kind": k, "ms": float(m)}
        if k in ("flash", "edge_glow"):
            out.update(flash_color_of(e, st, ncf.setdefault(k, [0])))
        if k == "zoomblur":           # 세기 = 판 cuts.transition.zoomblur{zoom, sigma}(벤치 drop 에 맞춘 값 — 관제263 10-25) · 없으면 옛 상수
            Z = ((st.get("cuts") or {}).get("transition") or {}).get("zoomblur") or {}
            out["zoom"] = float(e.get("zoom", Z.get("zoom", ZOOMBLUR_ZOOM)))
            out["sigma"] = float(e.get("sigma", Z.get("sigma", ZOOMBLUR_SIGMA)))
        if e.get("sec") is not None:
            out["sec"] = float(e["sec"])
        if e.get("why"):
            out["why"] = e["why"]
        return out
    if placed.get("transitions") is not None:
        return sorted((norm(e) for e in placed["transitions"] if e.get("kind", "cut") != "cut"), key=lambda e: e["t"])
    fsec = F.get("flash_sec", 0.1)
    if log and any(k != "cut" for k in ((st.get("cuts") or {}).get("transition", {}).get("kinds") or {})):
        log("[전환] 배치 결과에 transitions 칸이 없다(옛 placement) — 판 cuts.transition.kinds 는 placement.place 가 자리를 정해야 그려진다")
    return [{"t": t, "kind": "flash", "ms": round(fsec * 1000), "sec": fsec, "why": "placement flashes(옛 키)"} for t in placed.get("flashes") or []]


def flash_color_of(e: dict, st: dict, cnt: list) -> dict:
    """번쩍 두 종류의 색·세기(표준 §11-6 ㉝ — 그리기 정본 = render_bench).
    flash = 창 전체 색 덮기(벤치 실측: 경계 프레임 α → ms 뒤 0, 선형). 색 = 사건 칸 rgb(자리·색 = placement 03) > 판 cuts.transition.flash.colors(사건 차례 돌림),
      α = 사건 alpha > 판 flash.alpha. 둘 다 색이 없으면 {} = 옛 흰 번쩍(화면 전체 밝히기, 그림 그대로 — 흰 번쩍은 이 경우).
    edge_glow = 가장자리 빛(사장님 R4 — shark/fx.py 에서 옮김) · 업그레이드 판 전용(판에 base 가 없으면 멈춘다). 칸 = 판 cuts.transition.edge_glow
      {alpha0, dur, clear, soft, tint, bright{luma,alpha_gain}, colors} · 색 = 사건 rgb > colors 돌림. 빠진 칸은 멈춘다(숨은 기본 금지)."""
    k = e.get("kind")
    C = ((st.get("cuts") or {}).get("transition") or {}).get(k) or {}
    cols = C.get("colors")
    rgb = e.get("rgb") or (cols[cnt[0] % len(cols)] if cols else None)
    if rgb is not None and not e.get("rgb"):
        cnt[0] += 1
    if k == "flash":
        if rgb is None:
            return {}
        alpha = e.get("alpha", C.get("alpha"))
        if alpha is None:
            raise StageError(f"flash {e.get('t')} 색 {rgb} 에 alpha 가 없다 — 사건 칸 또는 판 cuts.transition.flash.alpha")
        return {"rgb": [int(v) for v in rgb], "alpha": float(alpha)}
    if not st.get("base"):
        raise StageError(f"edge_glow({e.get('t')}) 는 업그레이드 판 전용(표준 §11-6 ㉝, 벤치에 없음) — 판 '{st.get('name')}' 은 1차 판(base 없음)")
    miss = [x for x in ("alpha0", "dur", "clear", "soft", "tint") if C.get(x) is None]
    if rgb is None or miss:
        raise StageError(f"edge_glow({e.get('t')}) 칸 모자람 {miss + ([] if rgb is not None else ['rgb/colors'])} — 판 cuts.transition.edge_glow")
    return {"rgb": [int(v) for v in rgb], "edge": {x: C[x] for x in ("alpha0", "dur", "clear", "soft", "tint", "bright") if C.get(x) is not None}}


# ── 가장자리 빛(edge_glow) — tools/calcopy/shark/fx.py(_edge_mask·flash_look·flash_image·pose flash edge)를 인자 그대로 옮김(㉝) ──
def edge_mask(w: int, h: int, clear: float, soft: float):
    """번쩍 가장자리 빛 모양(0~1) — 타원 거리 clear 안쪽 0, 가장자리 1(부드럽게). = shark fx._edge_mask(rules flash.clear·soft)."""
    import numpy as np
    ys, xs = np.mgrid[0:h, 0:w]
    dd = np.sqrt(((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2) / math.sqrt(2)   # 모서리 = 1, 변 가운데 = 0.71
    c0 = clear * 0.7071
    u = np.clip((dd - c0) / max(1e-6, (0.7071 - c0) * (1 + soft)), 0, 1)
    return (u * u * (3 - 2 * u)).astype(np.float32)


def edge_look(luma, tint: float, bright: dict | None) -> tuple[float, float]:
    """장면 밝기 luma(0~255, 없으면 None) → (tint, α 배율) = shark fx.flash_look(rules flash.bright)."""
    if luma is None or not bright:
        return tint, 1.0
    u = min(1.0, max(0.0, (luma - bright["luma"][0]) / (bright["luma"][1] - bright["luma"][0])))
    return tint * (1 - u), 1.0 + bright["alpha_gain"] * u


def edge_glow_image(rgb, alpha: float, w: int, h: int, clear: float, soft: float, tint: float):
    """가장자리 빛 한 장(PIL RGBA, 곧은 알파) = shark fx.flash_image(style edge)."""
    import numpy as np
    from PIL import Image
    col = np.array(rgb, float)
    col = col + (255 - col) * tint
    a = (edge_mask(w, h, clear, soft) * alpha * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([np.broadcast_to(col.astype(np.uint8), (h, w, 3)), a]), "RGBA")


def edge_glow_alpha(dt: float, alpha0: float, dur: float) -> float:
    """사건 시작에서 dt 초 뒤 α = alpha0·(1−u)², u = dt/dur(감속으로 사라짐) = shark fx.pose(flash edge)."""
    u = min(1.0, dt / dur)
    return max(0.0, alpha0 * (1 - u) ** 2)


def edge_scene_luma(video: Path, t: float, w: int, h: int, clear: float, soft: float) -> float | None:
    """번쩍 얹기 전 창 영상의 그 시각(+0.02초) 가장자리(mask>0.5) 평균 밝기 = shark fx.flash_scene_luma."""
    import numpy as np
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t + 0.02:.3f}", "-i", str(video), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    if len(raw) != w * h * 3:
        return None
    f = np.frombuffer(raw, np.uint8).reshape(h, w, 3)[edge_mask(w, h, clear, soft) > 0.5].astype(float)
    return round(float((f @ np.array([0.299, 0.587, 0.114])).mean()), 1)


def flash_layers(trans: list[dict], rect, R: Path, ins: list, last: str, n: int, win_video: Path | None) -> tuple[str, str]:
    """창 자리에 색 번쩍(flash+rgb)·가장자리 빛(edge_glow)을 얹는 식 조각(render_base — 꾸밈 스티커 위·자막 아래, shark rules flash.order 와 같음).
    반환 (덧붙일 filter_complex 조각, 끝 이름). 색 없는 flash(옛 흰 번쩍)는 여기서 안 그린다(render_base 옛 길)."""
    x, y, ww, wh = rect
    fc = ""
    for j, e in enumerate(e for e in trans if e["kind"] == "flash" and e.get("rgb")):
        n0 = round(e["t"] * FPS)
        k = max(1, round(e["ms"] / 1000 * FPS))
        hexc = "".join(f"{v:02X}" for v in e["rgb"])
        fc += (f";color=c=0x{hexc}:s={ww}x{wh}:r={FPS}:d={k / FPS:.4f},format=rgba,"
               f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='255*{e['alpha']:.3f}*(1-N/{k})',setpts=PTS-STARTPTS+{n0}/({FPS}*TB)[cf{j}];"
               f"[{last}][cf{j}]overlay={x}:{y}:eof_action=pass:enable='between(n,{n0},{n0 + k - 1})'[cfo{j}]")
        last = f"cfo{j}"
    eg = [e for e in trans if e["kind"] == "edge_glow"]
    if eg:
        import subprocess
        spans = [(round(e["t"] * FPS), min(n, round(e["t"] * FPS) + max(1, round(e["ms"] / 1000 * FPS)))) for e in eg]
        f0, f1 = min(a for a, _ in spans), max(b for _, b in spans)
        for e in eg:
            E = e["edge"]
            e["scene_luma"] = edge_scene_luma(win_video, e["t"], ww, wh, E["clear"], E["soft"]) if win_video else None
        out = R / "edge_glow.mov"
        pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{ww}x{wh}", "-r", str(FPS), "-i", "-",
                               "-c:v", "qtrle", str(out)], stdin=subprocess.PIPE)
        from PIL import Image
        for f in range(f0, f1):
            cv = Image.new("RGBA", (ww, wh), (0, 0, 0, 0))
            for e, (a, b) in zip(eg, spans):
                if a <= f < b:
                    E = e["edge"]
                    tint, gain = edge_look(e["scene_luma"], E["tint"], E.get("bright"))
                    al = edge_glow_alpha((f - a) / FPS, E["alpha0"], E["dur"])
                    cv.alpha_composite(edge_glow_image(e["rgb"], round(min(1.0, al * gain), 3), ww, wh, E["clear"], E["soft"], round(tint, 3)))
            pr.stdin.write(cv.tobytes())
        pr.stdin.close()
        if pr.wait() != 0:
            raise StageError("가장자리 빛 층 인코딩 실패")
        k = len([a for a in ins if a == "-i"])
        ins += ["-i", out]
        fc += (f";[{k}:v]setpts=PTS-STARTPTS+{f0}/({FPS}*TB)[egl];"
               f"[{last}][egl]overlay={x}:{y}:eof_action=pass:enable='between(n,{f0},{f1 - 1})'[ego]")
        last = "ego"
    return fc, last


def window_fx(trans: list[dict], ww: int, wh: int) -> str:
    """창 안 전환 필터(filter_complex, 입력 [0:v] → [v]). 줌블러 = 경계 ±ms/2 동안 확대 사다리꼴 + gblur 덮기 · 검은 = 경계 프레임부터 ms 만큼 검정.
    그릴 것이 없으면 '' (창 영상을 다시 굽지 않는다 — 장치 끈 판은 그림이 그대로)."""
    zb = [e for e in trans if e["kind"] == "zoomblur"]
    bk = [e for e in trans if e["kind"] == "black"]
    if not (zb or bk):
        return ""
    fc, last = [], "0:v"
    if zb:
        zoom = zb[0].get("zoom", ZOOMBLUR_ZOOM)        # 한 편 안 줌블러 세기는 판 한 값(transitions_of)
        sigma = zb[0].get("sigma", ZOOMBLUR_SIGMA)
        terms = "+".join(f"max(0,1-abs(in/{FPS}-{e['t']:.3f})/{e['ms'] / 2000:.3f})" for e in zb)
        en = "+".join(f"between(t,{max(0.0, e['t'] - e['ms'] / 2000):.3f},{e['t'] + e['ms'] / 2000:.3f})" for e in zb)
        fc.append(f"[0:v]split[zm][zc];[zc]zoompan=z='1+{zoom}*({terms})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
                  f"s={ww}x{wh}:fps={FPS},gblur=sigma={sigma}[zb];[zm][zb]overlay=0:0:enable='{en}'[z]")
        last = "z"
    if bk:
        rng = []
        for e in bk:
            n0 = round(e["t"] * FPS)
            k = max(1, round(e["ms"] / 1000 * FPS))
            rng.append(f"between(n,{n0},{n0 + k - 1})")
        fc.append(f"[{last}]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='{'+'.join(rng)}'[k]")
        last = "k"
    fc.append(f"[{last}]format=yuv420p[v]")
    return ";".join(fc)


# ── 전환 세기 자(표준 §11-2 ⑯) — 우리 완성본과 벤치를 **같은 함수·같은 마스크 규칙**으로 잰다 ──────────────
TD_BAND_S = 0.1                 # 경계 띠 = 경계 ±0.05초(0.1초 띠)
TD_AROUND = (0.2, 0.4)          # 비교 바탕 = 경계 앞뒤 0.2~0.4초
TD_LOW = 0.7                    # 바탕 대비 분산이 이 비율 밑인 연속 프레임 = 전환이 보이는 길이(ms 실측)
TD_PAD = 8                      # 자막·스티커 상자 테두리(px)


def _gray_seg(video: Path, t0: float, t1: float, crop) -> tuple:
    """[t0,t1) 프레임(회색, crop=[x,y,w,h]) 배열과 그 프레임들의 시각."""
    import subprocess
    import numpy as np
    x, y, w, h = crop
    t0 = max(0.0, t0)
    # 시각 → 프레임은 trim(start_frame) 으로(입력 -ss 는 파일마다 시작 pts 가 달라 한 프레임씩 어긋났다 — 완성본(광고 표시 다시 굽기)↔captioned 마스크가 1프레임 밀림, 10-25 실측)
    f0, f1 = round(t0 * FPS), round(t1 * FPS)
    # 회색으로 바꾼 뒤 자른다 — yuv420p 에서 먼저 자르면 ffmpeg 가 홀수 높이·위치를 짝수로 내려 1501 줄 창이 1500 줄로 나와 reshape 가 깨졌다
    # (키치잇 벤치 vSEaZ-BCELY 창 [0,418,1080,1501], 관제263). 짝수 창은 결과가 같다.
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf",
                          f"trim=start_frame={f0}:end_frame={f1},setpts=PTS-STARTPTS,format=gray,crop={w}:{h}:{x}:{y}", "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
    return fr, [round((f0 + k) / FPS, 4) for k in range(len(fr))]


def _masked_lapvar(fr, mask) -> float:
    import cv2
    import numpy as np
    lap = cv2.Laplacian(fr, cv2.CV_64F)
    keep = ~mask if mask is not None else np.ones(fr.shape, bool)
    return float(lap[keep].var()) if keep.sum() > 1000 else float("nan")


def transition_drop(video: Path, ts: list[float], crop, mask_of=None) -> list[dict]:
    """경계마다 drop = 1 − (경계 ±0.05초 띠 라플라시안 분산 평균)/(앞뒤 0.2~0.4초 바탕 평균) · ms = 바탕의 TD_LOW 밑으로 떨어진 연속 프레임 길이.
    crop = 창 [x,y,w,h](화면 픽셀) · mask_of(t, shape) → bool 배열(True = 빼는 픽셀: 자막 띠·스티커, 테두리 8px 포함) | None.
    우리 완성본·벤치 원본 둘 다 이 함수(⑯ '같은 자'). 품질 관문(04)은 이 함수를 부르면 된다."""
    import numpy as np
    out = []
    for t in ts:
        a0, a1 = TD_AROUND
        fr, tt = _gray_seg(video, t - a1, t + a1, crop)
        if not len(fr):
            continue
        lv = np.array([_masked_lapvar(f, mask_of(ti, f.shape) if mask_of else None) for f, ti in zip(fr, tt)])
        rel = np.array(tt) - t
        band = np.abs(rel) <= TD_BAND_S / 2 + 1e-3
        around = (np.abs(rel) >= a0 - 1e-3) & (np.abs(rel) <= a1 + 1e-3)
        base = float(np.nanmean(lv[around])) if around.any() else float("nan")
        drop = 1 - float(np.nanmean(lv[band])) / base if band.any() and base > 0 else float("nan")
        k0 = int(np.argmin(np.abs(rel)))
        low = lv < TD_LOW * base
        a = b = k0
        if low[k0]:
            while a > 0 and low[a - 1]:
                a -= 1
            while b + 1 < len(low) and low[b + 1]:
                b += 1
            ms = round((b - a + 1) * 1000 / FPS)
        else:
            ms = 0
        out.append({"t": round(t, 3), "drop": round(drop, 3), "ms": ms, "band_var": round(float(np.nanmean(lv[band])), 1), "around_var": round(base, 1)})
    return out


def overlay_mask_of(base: Path, over: Path, crop, pad: int = TD_PAD, th: int = 12):
    """우리 완성본 마스크: 바탕(base.mp4, 자막 없음)과 자막 입힌 영상(captioned.mp4)이 다른 픽셀 = 자막·스티커 → 테두리 pad px 넓혀 뺀다."""
    import cv2
    import numpy as np
    cache = {}
    k = np.ones((2 * pad + 1, 2 * pad + 1), np.uint8)

    def mask_of(t, shape):
        key = round(t * FPS)
        if key not in cache:          # 1초 덩어리로 한 번에 읽어 둔다(프레임마다 영상 열기 금지)
            a, ta = _gray_seg(base, t, t + 1.0, crop)
            b, _ = _gray_seg(over, t, t + 1.0, crop)
            for fa, fb, ti in zip(a, b, ta):
                m = (np.abs(fa.astype(np.int16) - fb.astype(np.int16)) > th).astype(np.uint8)
                cache[round(ti * FPS)] = cv2.dilate(m, k) > 0
        return cache.get(key)
    return mask_of


def rect_mask_of(rects, crop, pad: int = TD_PAD):
    """벤치 마스크: 줄판독 자막 띠·스티커 상자 [x0,y0,x1,y1,t0,t1](화면 픽셀·초) → 그 시각에 걸린 상자를 pad px 넓혀 뺀다."""
    import numpy as np
    cx, cy, cw, ch = crop

    def mask_of(t, shape):
        m = np.zeros(shape, bool)
        for x0, y0, x1, y1, a, b in rects:
            if a - 1e-3 <= t < b + 1e-3:
                m[max(0, int(y0) - pad - cy):max(0, int(y1) + pad - cy), max(0, int(x0) - pad - cx):max(0, int(x1) + pad - cx)] = True
        return m
    return mask_of


def bench_transition_drop(line_read: Path, video: Path, kind: str = "zoomblur") -> dict:
    """벤치 한 편: 줄판독 lines[].transition==kind 인 줄 시작 근처(±0.2초) 장면 경계(shot_starts, 없으면 줄 시작)에서 transition_drop.
    마스크 = 줄판독 자막 띠(y)·스티커 상자 · 창 = layout.window(화면 밖은 잘라 냄)."""
    import json as _j
    d = _j.loads(Path(line_read).read_text(encoding="utf-8"))
    x, y, w, h = d["layout"]["window"]
    h = min(h, H - y)
    crop = [x, y, w, h]
    rects = []
    for l in d["lines"]:
        yy = l.get("y")
        if isinstance(yy, list) and len(yy) == 2:
            rects.append([0, yy[0], W, yy[1], l["t0"], l["t1"]])
        for s in l.get("sticker") or []:
            b = s.get("bbox") if isinstance(s, dict) else None
            if isinstance(b, list) and len(b) == 4:
                rects.append([*b, l["t0"], l["t1"]])
    st = shot_starts(Path(video))
    ts = []
    for l in d["lines"]:
        if l.get("transition") == kind:
            near = [s for s in st if abs(s - l["t0"]) <= 0.2]
            ts.append(min(near, key=lambda s: abs(s - l["t0"])) if near else l["t0"])
    return {"id": d.get("id"), "kind": kind, "window": crop, "boundaries": transition_drop(Path(video), ts, crop, rect_mask_of(rects, crop))}


def render_transition_drop(R: Path, style_name: str, kinds=("zoomblur",)) -> dict:
    """우리 완성본 한 편: render/자막표.json transitions(kind) 경계에서 transition_drop — 완성본(final.mp4) 창 영역,
    마스크 = base.mp4(자막 없음) ↔ captioned.mp4 가 다른 픽셀(자막·스티커) + 8px. 벤치(bench_transition_drop)와 같은 함수."""
    from tools.calcopy.hybrid import styles as ST
    R = Path(R)
    st = ST.load(style_name)
    crop = frame_window(st["frame"])
    crop = [crop[0], crop[1], crop[2], min(crop[3], H - crop[1])]
    tab = jload(R / "자막표.json")
    ts = [e["t"] for e in tab.get("transitions") or [] if e["kind"] in kinds]
    return {"style": style_name, "window": crop, "boundaries": transition_drop(R / "final.mp4", ts, crop, overlay_mask_of(R / "base.mp4", R / "captioned.mp4", crop))}


def cut_crop(c: dict, src: Path, win: tuple[int, int]) -> list[int]:
    """컷 하나의 원본 자르기 칸 [x, y, w, h] — 판단 주인 한 곳(render_window 조각 뽑기 · cut_content_gate 관문 프레임이 같이 부른다).
    재료 crop 이 4칸이면 그대로 · 사진 재료에 crop 이 없으면 창(또는 그림 칸) 비율로 가운데 · 'face'(또는 없음)면 face_crop. 정한 값은 c["crop_used"]."""
    crop = c.get("crop", "face")
    pb = pic_box(c, win)
    aw, ah = (pb[2], pb[3]) if pb else win
    if src.suffix.lower() in IMG_EXT and not (isinstance(crop, list) and len(crop) == 4):
        # 사진 재료(쿠팡 상품 사진)는 얼굴 크롭·시작 초가 없다 — 창 비율로 가운데를 자른다(10-22 강주은: 사진 컷에 ss·crop 없음 → KeyError 'ss' 로 렌더 멈춤)
        iw, ih = probe(src)[:2]
        cw = min(iw, round(ih * aw / ah)); chh = min(ih, round(cw * ah / aw))
        crop = [(iw - cw) // 2, (ih - chh) // 2, cw, chh]
        c["crop_used"] = crop
    elif crop == "face":
        crop = c.get("crop_used") or face_crop(src, float(c.get("ss") or 0.0) + min(0.5, c["dur"] / 2), aw / ah)
        c["crop_used"] = crop
    return crop


def render_window(T: dict, M: dict, st: dict, R: Path, trans: list[dict] | None = None) -> Path:
    src_dir = Path(M["cand_dir"])
    x, y, ww, wh = frame_window(st["frame"])
    parts = R / "parts"; shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst = []
    for k, c in enumerate(T["cuts"]):
        n = round(c["t1"] * FPS) - round(c["t0"] * FPS)
        c["frames"] = n
        src = src_dir / c["src"]
        a = clip_args(c, src, st, M)       # 칸·밀기·그림 칸·흐림 = 주인 한 곳(계획 프레임 대조·관문 ⑦과 같은 인자)
        p = parts / f"c{k:02d}.mp4"
        clip(src, a["ss"], n, a["crop"], a["win"], p, push=a["push"], move=a["move"], blur=a["blur"], pic=a["pic"], pic_bg=a["pic_bg"], speed=a["speed"])
        got = count_frames(p)
        if got != n:      # 모자라면 뒤 컷이 전부 앞당겨지고 끝이 멈춘다 — 조용히 넘기지 않는다
            raise StageError(f"컷 조각 프레임 모자람: {c['line']} {c['src']}@{c.get('ss')} 계획 {n} · 실제 {got}")
        lst.append(f"file '{p.as_posix()}'")
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    win = R / "window.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", win])
    return window_transitions(win, T, st, R, trans)


def window_transitions(win: Path, T: dict, st: dict, R: Path, trans: list[dict] | None) -> Path:
    """창 영상에 전환(줌블러·검은 프레임)을 입힌다 — 그릴 것이 없으면 창 그대로(다시 굽지 않는다)."""
    x, y, ww, wh = frame_window(st["frame"])
    fx = window_fx(trans or [], ww, wh)
    if fx:
        n_all = sum(c["frames"] for c in T["cuts"])
        out = R / "window_tr.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", win, "-filter_complex", fx, "-map", "[v]", "-frames:v", n_all, "-r", FPS,
             *venc(16), "-pix_fmt", "yuv420p", out])
        got = count_frames(out)
        if got != n_all:
            raise StageError(f"전환 입힌 창 프레임 {got} ≠ 계획 {n_all}")
        return out
    return win


FX_STICKERS = ("red_circle", "dashed_circle", "arrow_green_down", "arrow_pink_up", "arrow_curve_red", "money_emoji")   # = tools/calcopy/shark/fx.py KINDS(번쩍·emoji 빼고)


def fx_effects(placed: dict) -> list[dict]:
    """배치가 자리를 받은 꾸밈 스티커(종류·자리 = placement + fx_target, 03) → 샤크 fx 사건 {kind, at:[x,y] 완성본 px, T:[t0,t1], radius?/size?/stroke?}.
    모양·움직임·크기 기본값의 주인 = tools/calcopy/shark/fx.py(sprite·pose·place, 값 rules.json — 샤크탱크 벤치 실측). 자리 못 받은(pending) 것은 안 그림."""
    out = []
    for r in placed.get("rows") or []:
        for s in r.get("stickers") or []:
            if s.get("kind") not in FX_STICKERS or s.get("site") not in ("detected", "fixed") or s.get("x") is None:
                continue
            e = {"kind": s["kind"], "at": [round(float(s["x"]) / 100 * W), round(float(s["y"]) / 100 * H)],
                 "T": [round(float(r["t0"]), 3), round(float(r["t0"]) + float(s.get("len_s", 1.0)), 3)]}
            for k in ("radius", "size", "stroke", "w", "h"):
                if isinstance(s.get(k), (int, float)):
                    e[k] = s[k]
            out.append(e)
    return out


def fx_layer(effects: list[dict], R: Path, n: int) -> tuple[Path, int, int] | None:
    """꾸밈 사건 → 투명 층 mov(1080×1920, 사건이 있는 프레임 구간만) + (첫 프레임, 끝 프레임). 그리기 = shark fx.pose·place·_sprite_im(그 채널 렌더러와 같은 함수)."""
    if not effects:
        return None
    from PIL import Image
    from tools.calcopy.shark import fx as FXS
    f0 = max(0, min(round(e["T"][0] * FPS) for e in effects))
    f1 = min(n, max(round(e["T"][1] * FPS) for e in effects))
    if f1 <= f0:
        return None
    out = R / "fx_layer.mov"
    pr = __import__("subprocess").Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                         "-c:v", "qtrle", str(out)], stdin=__import__("subprocess").PIPE)
    for f in range(f0, f1):
        t = f / FPS
        cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for e in effects:
            p = FXS.pose(e, t)
            if p is None:
                continue
            im = FXS._sprite_im(e["kind"], FXS._key(e), round(p["scale"], 2), round(p["deg"] / 3) * 3.0, round(p["alpha"], 2), round(p["rot"], 1), round(p["sweep"], 3))
            pl = FXS.place(e, p)
            x0, y0 = int(round(pl["cx"] - im.size[0] / 2)), int(round(pl["cy"] - im.size[1] / 2))
            cv.alpha_composite(im, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))
        pr.stdin.write(cv.tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise StageError(f"꾸밈 층 인코딩 실패 {out}")
    return out, f0, f1


def meme_overlays(placed: dict) -> list[dict]:
    """배치가 자리를 받은 짤(placement meme_step → site detected|fixed) → [{src, t0, len, box[x0,y0,w,h]}]. 자리 못 받은 짤(pending)은 안 그린다."""
    out = []
    for r in placed.get("rows") or []:
        for s in r.get("stickers") or []:
            if s.get("kind") != "meme" or s.get("site") not in ("detected", "fixed") or not s.get("src"):
                continue
            w, h = int(s.get("w") or 420), int(s.get("h") or 420)
            cx, cy = float(s["x"]) / 100 * W, float(s["y"]) / 100 * H
            out.append({"src": s["src"], "t0": float(r["t0"]), "len": float(s.get("len_s", 1.0)), "box": [round(cx - w / 2), round(cy - h / 2), w, h]})
    return out


def _seg_on(g: dict) -> str:
    """구간 켜짐 식 — [t0, t1) 반 프레임 앞당긴 경계(경계 프레임은 뒤 구간 것)."""
    e = 0.5 / FPS
    return f"gte(t,{g['t0'] - e:.4f})*lt(t,{g['t1'] - e:.4f})"


def seg_layers(S: dict, st: dict, segs: list[dict], R: Path, ins: list, base_win, end: float) -> str:
    """구간 틀 합성 식(입력 0 = 검정 바탕 · 1 = 창 영상 · 2 = 판 틀) → 끝 이름 [b]. 구간 밖 = 판 창 자리·판 틀,
    구간 안 = 구간 창 자리(크기가 다르면 창 영상을 채워 자른다 — 창 하나를 다시 굽지 않는다)·구간 틀. ins 에 구간 틀 PNG 입력을 덧붙인다."""
    x, y, ww, wh = base_win
    off = "not(" + "+".join(_seg_on(g) for g in segs) + ")"
    fc = [f"[1:v]split={len(segs) + 1}" + "".join(f"[w{i}]" for i in range(len(segs) + 1)),
          f"[0:v][w0]overlay={x}:{y}:shortest=0:enable='{off}'[a0]"]
    last = "a0"
    for i, g in enumerate(segs, 1):
        sx, sy, sw, sh = g["window"]
        src = f"w{i}"
        if (sw, sh) != (ww, wh):
            fc.append(f"[w{i}]scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,crop={sw}:{sh},setsar=1[ws{i}]")
            src = f"ws{i}"
        fc.append(f"[{last}][{src}]overlay={sx}:{sy}:enable='{_seg_on(g)}'[a{i}]")
        last = f"a{i}"
    fc.append(f"[{last}][2:v]overlay=0:0:enable='{off}'[f0]")
    last = "f0"
    for i, g in enumerate(segs, 1):
        p = seg_frame_png(S, st, g, R / f"frame_seg{i}.png")
        k = len([a for a in ins if a == "-i"])
        ins += ["-loop", "1", "-t", f"{end:.3f}", "-i", p]
        fc.append(f"[{last}][{k}:v]overlay=0:0:enable='{_seg_on(g)}'[f{i}]")
        last = f"f{i}"
    fc.append(f"[{last}]null[b]")
    return ";".join(fc)


def render_base(S: dict, T: dict, st: dict, placed: dict, R: Path, win: Path, trans: list[dict] | None = None, name: str = "base.mp4",
                color: str | None = None, look: bool = False) -> Path:
    """틀 + 창 + 댓글 카드 + 짤 + 흰 번쩍임(자막 없는 바탕). 번쩍임 = 전환 목록(transitions_of) kind=flash — 화면 전체.
    짤 = 배치가 검출로 자리를 받은 meme 스티커(자막팩은 짤을 안 그린다 — 여기 한 곳).
    look=True(회원 꾸민 모양, 관제 266): 판 틀 그림·구간 틀을 안 그리고 창 자리만 잘라 낸 영상(창 크기)을 돌려준다 — 틀은 compose 가
    회원 스냅샷(web.look)으로 그리고 이 영상을 그 스냅샷의 영상 칸에 앉힌다. 짤·꾸밈·번쩍임은 창 안 그대로 따라간다."""
    F = st["frame"]
    x, y, ww, wh = frame_window(F)
    if look:
        from PIL import Image
        png = R / "frame_look_blank.png"
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(png)
    else:
        png = frame_png(S, st, R / "frame.png")
    n = sum(c["frames"] for c in T["cuts"])
    end = n / FPS
    ins = ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={end:.3f}", "-i", win, "-loop", "1", "-t", f"{end:.3f}", "-i", png]
    segs = [] if look else frame_segments(S, T, st)
    if not segs:
        fc = f"[0:v][1:v]overlay={x}:{y}:shortest=0[a];[a][2:v]overlay=0:0[b]"
    else:
        fc = seg_layers(S, st, segs, R, ins, (x, y, ww, wh), end)
    last = "b"
    C = placed.get("comment")
    if C:
        cw, ch = comment_png(C, F["comment"]["px"], R / "comment.png")
        k = len([a for a in ins if a == "-i"])
        ins += ["-loop", "1", "-t", f"{end:.3f}", "-i", R / "comment.png"]
        fc += f";[b][{k}:v]overlay={(W - cw) // 2}:{F['comment']['bottom'] - ch}:enable='between(t,{C['t0']:.3f},{C['t1']:.3f})'[c]"
        last = "c"
    CT = comment_track(F)
    for i, c in enumerate(placed.get("cards") or []):      # 댓글카드 자막(track lines) — 등장 = 페이드 + 아래에서 dy 위로(ms), 퇴장 = 그 프레임에 사라짐
        cw, ch = comment_card_png(c, CT, R / f"card_{i}.png")
        k = len([a for a in ins if a == "-i"])
        ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{end:.3f}", "-i", R / f"card_{i}.png"]
        ms, dy = CT["enter"]["ms"] / 1000, CT["enter"]["dy"]
        y0 = CT["box"]["bottom"] - ch
        fc += (f";[{k}:v]format=rgba,fade=t=in:st={c['t0']:.3f}:d={ms:.3f}:alpha=1[cd{i}];"
               f"[{last}][cd{i}]overlay={CT['box']['x0']}:'{y0}+{dy}*max(0,1-(t-{c['t0']:.3f})/{ms:.3f})':enable='between(t,{c['t0']:.3f},{c['t1'] - 1 / FPS:.3f})'[cc{i}]")
        last = f"cc{i}"
    CR = F.get("credit") or {}
    if CR.get("in_window") and S.get("source_label"):     # 창 위 출처 줄(📍핀 + 원본 계정, 왼쪽 정렬) — on 초부터
        from PIL import Image, ImageDraw
        cim = Image.new("RGBA", (W, H), (0, 0, 0, 0)); cd = ImageDraw.Draw(cim)
        f = _font(CR["font"], CR["px"])
        bb = cd.textbbox((0, 0), S["source_label"], font=f, stroke_width=CR.get("stroke", 0))
        px_ = CR["x"]
        if CR.get("pin"):
            P = CR["pin"]
            cd.ellipse([px_, CR["cy"] - P["r"] - 6, px_ + 2 * P["r"], CR["cy"] + P["r"] - 6], fill=_rgb(P["color"]), outline=(0, 0, 0), width=2)
            cd.line([px_ + P["r"], CR["cy"] + P["r"] - 6, px_ + P["r"], CR["cy"] + P["r"] + 8], fill=_rgb(P["color"]), width=4)
            px_ += 2 * P["r"] + 8
        cd.text((px_ - bb[0], CR["cy"] - (bb[1] + bb[3]) // 2), S["source_label"], font=f, fill=_rgb(CR["color"]),
                stroke_width=CR.get("stroke", 0), stroke_fill=_rgb(CR.get("stroke_color", "#000000")))
        cim.save(R / "credit.png")
        k = len([a for a in ins if a == "-i"])
        ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{end:.3f}", "-i", R / "credit.png"]
        fc += f";[{last}][{k}:v]overlay=0:0:enable='gte(t,{float(CR.get('on', 0.0)):.3f})'[cr]"
        last = "cr"
    for i, x in enumerate(placed.get("lyrics") or []):     # 가사 2줄(즉시 뜨고 즉시 바뀜, 고정 자리)
        lyric_png(x, F["lyrics"], R / f"lyric_{i}.png")
        k = len([a for a in ins if a == "-i"])
        ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{end:.3f}", "-i", R / f"lyric_{i}.png"]
        fc += f";[{last}][{k}:v]overlay=0:0:enable='between(t,{x['t0']:.3f},{x['t1'] - 1 / FPS:.3f})'[ly{i}]"
        last = f"ly{i}"
    for j, m in enumerate(meme_overlays(placed)):
        k = len([a for a in ins if a == "-i"])
        mx, my, mw, mh = m["box"]
        ins += ["-i", m["src"]]
        fc += (f";[{k}:v]trim=duration={m['len']:.3f},setpts=PTS-STARTPTS+{m['t0']:.3f}/TB,fps={FPS},"
               f"scale={mw}:{mh}:force_original_aspect_ratio=decrease[mm{j}];"
               f"[{last}][mm{j}]overlay={mx}+({mw}-w)/2:{my}+({mh}-h)/2:eof_action=pass:enable='between(t,{m['t0']:.3f},{m['t0'] + m['len']:.3f})'[m{j}]")
        last = f"m{j}"
    FL = fx_layer(fx_effects(placed), R, n)          # 꾸밈 스티커(빨간 원·점선 원·화살표) — 창·짤 위, 자막 아래(샤크 fx 겹침 순서와 같다)
    if FL:
        k = len([a for a in ins if a == "-i"])
        ins += ["-i", FL[0]]
        fc += (f";[{k}:v]setpts=PTS-STARTPTS+{FL[1]}/({FPS}*TB)[fxl];"
               f"[{last}][fxl]overlay=0:0:eof_action=pass:enable='between(n,{FL[1]},{FL[2] - 1})'[fxo]")
        last = "fxo"
    trs = trans if trans is not None else transitions_of(T, st, placed)
    add, last = flash_layers(trs, (x, y, ww, wh), R, ins, last, n, win)
    fc += add
    fl = [(e["t"], e["sec"] if "sec" in e else e["ms"] / 1000) for e in trs if e["kind"] == "flash" and not e.get("rgb")]     # 옛 흰 번쩍(색 없는 flash)
    if fl:
        e = "+".join(f"between(T,{t:.3f},{t + dsec:.3f})*(1-(T-{t:.3f})/{dsec})" for t, dsec in fl)
        fc += f";[{last}]geq=lum='min(255,lum(X,Y)+255*({e}))':cb='cb(X,Y)':cr='cr(X,Y)'[f]"
        last = "f"
    out = R / name
    cf = f"{color.strip()}," if color and color.strip() else ""          # 모션그래픽팩 색감(자막 전 — 고객 엔진 video_assemble 과 같은 순서)
    if look:
        cf = f"crop={ww}:{wh}:{x}:{y}," + cf                             # 회원 꾸민 모양: 창 자리만(틀은 compose 가)
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc + f";[{last}]{cf}format=yuv420p[v]", "-map", "[v]", "-frames:v", n, "-r", FPS,
         *venc(16), out])
    return out


def member_look(pack: Path | str | None) -> dict | None:
    """회원 팩 파일(~/.shortem/packs/<pid>.json = {"1": 합친 팩, "web": {"look": 스냅샷|null}}, 주인 shortem_client local_settings.packFile)의
    꾸민 모양(web.look — 설정 화면 장면꾸미기에서 '이 영상에 적용'한 것, 저장 주인 claude_studio.save_look). 없으면 None(판 틀 그대로).
    검사 = 렌더러와 같은 scene_style.validate_snapshot — 틀리면 멈춘다(조용히 판 틀로 되돌아가지 않는다)."""
    if not pack:
        return None
    look = ((jload(Path(pack)).get("web") or {}).get("look"))
    if not look:
        return None
    from shopping_shorts import scene_style
    try:
        return scene_style.validate_snapshot(look)
    except Exception as e:  # noqa: BLE001 — 검사 실패 사유를 그대로 올린다
        raise StageError(f"회원 꾸민 모양(web.look) 검사 실패: {e}") from None


def look_snapshot(st: dict, look: dict) -> dict:
    """회원 꾸민 모양 + 판 자막팩 — 틀·글·색·자리는 회원 것, 자막팩·움직임팩은 회원이 안 정했으면(없음·'off') 판 것(snapshot(st) 의 칸)."""
    from shopping_shorts import scene_style
    base = snapshot(st)
    snap = dict(look)
    for k in ("captionPack", "motionPack"):
        if (not snap.get(k) or snap.get(k) == "off") and base.get(k):
            snap[k] = base[k]
    return scene_style.validate_snapshot(snap)


# ── 자막(자막팩 길) ──────────────────────────────────────────────────────
PACK_XY_KINDS = ("circle_arrow", "object_pop", "hearts", "sound_word", "small_text")   # 자막팩 그리기(out/precision20-ui.js renderStickers)가 s.x·s.y 를 읽는 종류(10-25 코드 실측) — 나머지(gem·spark_lines·kk_doodle·comic_burst·aside_line·append_text·comment_card)는 자막·낱말 기준 고정 자리
STACK_BREAKS = ("full", "line")


def stack_rows(rows: list[dict], st: dict) -> list[dict]:
    """자막 쌓기(관제 263 02 2차 ③ — 누적형 방구석·맛템·썰템쇼): 판 칸 caption.stack{lines(2~3), break full|line}.
    덩어리마다 앞 덩어리 밑에 한 줄씩 덧붙여(글 = '앞줄\n새줄') lines 줄이 차면 다음 덩어리에서 페이지를 지우고 새로 시작.
    break=line 이면 대본 줄(문장)이 바뀔 때도 지운다(맛템: 문장 단위 누적). 칸 없으면 그대로(한 줄 교체, 옛 그림).
    y(첫 줄 가운데 px)·pitch(줄 간격 px)를 적으면 첫 줄이 제자리에 서고 새 줄이 밑으로 붙는다 — 자막팩은 여러 줄 덩어리를 가운데 기준으로
    세우므로(10-25 실측: clean 팩 place y = 덩어리 가운데) 쌓인 줄 수 k 마다 place y = y + (k−1)·pitch/2. 안 적으면 팩 자리(덩어리 가운데 기준).
    쌓인 줄의 타이핑 글자 시각은 버린다(새 줄만 치는 표현은 자막팩 몫 — 벤치 셋 다 typing 0)."""
    SK = (st.get("caption") or {}).get("stack")
    if not SK:
        return rows
    n = int(SK.get("lines", 1))
    brk = SK.get("break", "full")
    if brk not in STACK_BREAKS or not 2 <= n <= 4 or (SK.get("y") is None) != (SK.get("pitch") is None):
        raise StageError(f"caption.stack {SK} — lines 2~4 · break {STACK_BREAKS} · y·pitch 는 짝")
    page, prev = [], None
    for r in rows:
        if len(page) >= n or (brk == "line" and prev is not None and r["line"] != prev):
            page = []
        page.append(r["text"])
        r["text"] = "\n".join(page)
        r["stack"] = len(page)
        if SK.get("y") is not None:
            r["place"] = {"x": 50, "y": round((float(SK["y"]) + (len(page) - 1) * float(SK["pitch"]) / 2) / H * 100, 3)}
        if len(page) > 1:
            r.pop("chars", None)
        prev = r["line"]
    return rows


def caption_hidden(rows: list[dict], segs: list[dict]) -> list[dict]:
    """구간 틀 captions=hide 구간의 자막을 뺀다(frame_segments 가 주인) — 구간 안에서 **시작한** 덩어리는 통째로 뺀다(그 말은 훅 카드 띠가 대신했다.
    끝만 잘라 남기면 구간 끝에 몇 프레임 번쩍 뜬다 — 10-25 _test_hook 실측 3.533~3.607초 2프레임) · 구간 앞에서 시작해 걸치면 구간 시작에서 내린다."""
    hide = [(g["t0"], g["t1"]) for g in segs if g["captions"] == "hide"]
    if not hide:
        return rows
    out = []
    for r in rows:
        a, b = r["t0"], r["t1"]
        if any(h0 - 1e-3 <= a < h1 - 1e-3 for h0, h1 in hide):
            continue
        for h0, h1 in hide:
            if a < h0 < b:
                b = h0
        if b - a < 1 / FPS:
            continue
        r = {**r, "t1": round(b, 3)}
        if r.get("chars"):
            r["chars"] = [c for c in r["chars"] if c < b]
        out.append(r)
    return out


def caption_rows(placed: dict, st: dict, segs: list[dict] | None = None) -> list[dict]:
    """배치 결과 → 자막팩 견본(check_bench_packs.rows_to_timeline) 공통 줄 꼴. 타이핑 덩어리는 글자 시각(판 caption.typing_cps).
    segs(frame_segments) 의 captions=hide 구간은 빼고, 판 caption.stack 이면 쌓는다."""
    cps = float(st["caption"].get("typing_cps", 10.0))
    out = []
    carded = {c["line"] for c in placed.get("cards") or []}      # 댓글카드가 그 줄 자막(render_base) — 자막팩으로 두 번 그리지 않는다
    for r in placed["rows"]:
        if r["line"] in carded:
            continue
        a, b = r["show"]
        row = {"line": r["line"], "t0": a, "t1": b, "text": r["text"], "speaker": r["speaker"], "variant": r.get("variant") or "",
               "emph": r.get("emph") or [], "sticker": "", "stickers": [], "enter": r.get("enter") or "instant"}   # enter = 검증 자(kal_analyze)가 등장을 잰다
        for s in r.get("stickers") or []:
            if s["kind"] == "heart":
                row["sticker"] = "heart"
            elif s["kind"] not in ("comment_card", "meme") + FX_STICKERS and s.get("site") != "pending":   # 짤·꾸밈 스티커 = render_base · 자리 못 받은 것 = 안 그림(눈대중 금지, 03)
                if s.get("site") in ("detected", "fixed") and s["kind"] not in PACK_XY_KINDS:
                    # 배치가 자리(x·y)를 정했는데 자막팩 그리기(편집기 renderStickers)가 이 종류는 x·y 를 안 읽고 자막 옆 고정 자리에 그린다 →
                    # 엉뚱한 곳에 그리느니 안 그린다(10-25 15 ep13: kk_doodle 자리 91.5%·60.7% 인데 화면 x240~555). 편집기 쪽 수리 = 그 파일 주인.
                    placed.setdefault("log", []).append(f"스티커 {s['kind']} 자리 {s.get('x')}%·{s.get('y')}% — 자막팩이 이 종류는 자리(x·y)를 안 읽어 안 그림({r['line']})")
                    continue
                row["stickers"].append({k: v for k, v in s.items() if k != "follow"})
        if r["enter"] == "typing":
            n = len(r["text"].replace(" ", ""))
            step = min(1.0 / cps, (b - a) * 0.85 / max(1, n))
            row["chars"] = [round(a + k * step, 3) for k in range(n)]
        out.append(row)
    return pack_place_x(stack_rows(caption_hidden(out, segs or []), st), st)


def caption_packs() -> dict:
    """자막팩 계약 파일(shopping_shorts/static/caption-motions.js /*PACKS*/ 사이 json) — 자막 모양의 주인(표준 ㉑)."""
    t = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
    return json.loads(t.split("/*PACKS*/")[1])


def pack_place_x(rows: list[dict], st: dict, packs: dict | None = None) -> list[dict]:
    """자막팩 가로 자리 place.x(화면 %, 자막 가운데)를 줄마다 place 표식으로 싣는다 — 편집기 renderCaption 은 가로 자리를 장면 place.x 에서만 읽어
    팩 place.x 가 렌더에 안 먹었다(10-25 자막팩 작업자 보고). 우선 = 줄 변형(variants) > 화자(speakers) > 팩. 팩에 x 가 없으면 아무것도 안 바꾼다
    (장면 자리 표식은 y 가 함께여야 받아지므로 y = 쌓기(stack)가 정한 y, 없으면 팩 place.y — 팩 세로 자리와 같다)."""
    P = (packs if packs is not None else caption_packs()).get((st.get("caption") or {}).get("pack")) or {}

    def get(r, k):
        for sec, key in (("variants", r.get("variant")), ("speakers", r.get("speaker"))):
            pl = (((P.get(sec) or {}).get(key) or {}) if key else {}).get("place") or {}
            if isinstance(pl.get(k), (int, float)):
                return float(pl[k])
        pl = P.get("place") or {}
        return float(pl[k]) if isinstance(pl.get(k), (int, float)) else None
    for r in rows:
        x = get(r, "x")
        if x is None:
            continue
        y = (r.get("place") or {}).get("y")
        y = y if isinstance(y, (int, float)) else get(r, "y")
        if y is None:      # 장면 자리 표식은 y 가 있어야 받아진다(scene_style 줄 자리 칸) — x 만 있는 팩은 그릴 수 없다
            raise StageError(f"자막팩 '{st['caption'].get('pack')}' place.x 만 있고 y 가 없다 — 팩에 place.y 를 같이 적는다")
        r["place"] = {**(r.get("place") or {}), "x": x, "y": y}
    return rows


def snapshot(st: dict) -> dict:
    """자막 스냅샷 — 팩 칸(captionPack·motionPack)의 주인 = pack_map.snapshot_fields(st)(판 packs, 지시서 11).
    모션그래픽팩(packs.motion.graphics)은 스냅샷 칸이 아니라 motion_graphics() 가 그린다 — snapshot_fields 의 'graphics≠off 거절'은
    render_bench 에 그리는 길이 없던 때의 막이라, 여기서는 graphics 를 뺀 판으로 팩 칸만 받는다(그리는 길 = motion_graphics, 02 2차)."""
    from shopping_shorts import scene_style
    from tools.calcopy.hybrid import pack_map as PM
    P = st.get("packs") or {}
    st2 = {**st, "packs": {**P, "motion": {**(P.get("motion") or {}), "graphics": "off"}}} if P else st
    fields = PM.snapshot_fields(st2)
    return scene_style.validate_snapshot({"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0, "frameKind": "body",
                                          "frameRule": "body_all", "text": {"channel": "", "hook1": "", "hook2": "", "bodyTitle": ""},
                                          "captionPack": fields["captionPack"], "motionPack": fields["motionPack"],
                                          "wordFx": {"style": "mark", "color": "", "grow": ""}})


def motion_graphics(st: dict, T: dict) -> dict | None:
    """모션그래픽팩(packs.motion.graphics — 전환 swipe·sparkle 겹·색감) 그리기 재료. 판단 주인은 고객 엔진과 같은 함수들:
    motion_packs.build_plan(팩 + 비트 시간표 → 레이어·색감) · motion_assets.resolve_layers(자산 실경로) · 그리기 = video_assemble._motion_layer_filters.
    비트 = 대본 줄(나레·원음·자막 줄 시작~끝 — mix_pipeline 의 비트와 같은 '말 덩어리'). off 면 None(옛 그림 그대로).
    자막 효과(caption.effect)·헤드카피 노출은 mix 의 drawtext 자막 칸이라 bench(자막팩)에는 해당 없음 → 로그 칸에 남긴다."""
    g = ((st.get("packs") or {}).get("motion") or {}).get("graphics", "off")
    if not g or g == "off":
        return None
    from shopping_shorts.motion_assets import resolve_layers
    from shopping_shorts.motion_packs import build_plan, load_packs
    pk = load_packs().get(g)
    if not pk:
        raise StageError(f"모션그래픽팩 '{g}' 없음 — shopping_shorts/assets/motion/packs.json")
    beats = [{"t0": a, "dur": round(b - a, 3)} for a, b in sorted(T["lines"].values())]
    plan = build_plan(pk, beats)
    layers = resolve_layers(plan["layers"])
    if len(layers) != len(plan["layers"]):        # resolve_layers 는 자산 없으면 조용히 건너뛴다 — 여기서는 멈춘다(조용한 빠짐 금지)
        raise StageError(f"모션그래픽팩 '{g}' 자산 {len(plan['layers']) - len(layers)}개 파일 없음 — assets/motion/manifest.json")
    return {"id": g, "layers": layers, "color_filter": plan["color_filter"],
            "not_drawn": {k: plan[k] for k in ("caption_effect", "headcopy_enable") if plan.get(k)}}


def draw_motion_layers(video: Path, MG: dict | None, R: Path) -> Path:
    """자막 입힌 영상 위에 모션그래픽 레이어(전환·스티커) — 고객 엔진과 같은 순서(자막 다음, video_assemble 의 has_motion 자리)·같은 함수."""
    if not MG or not MG["layers"]:
        return video
    from shopping_shorts.video_assemble import _motion_layer_filters
    m_in, m_fc, vcur, _ = _motion_layer_filters(MG["layers"], 1, "0:v")
    out = R / "captioned_mg.mp4"
    n = count_frames(video)
    run(["ffmpeg", "-y", "-v", "error", "-i", video, *m_in, "-filter_complex", ";".join(m_fc) + f";[{vcur}]format=yuv420p[v]", "-map", "[v]",
         "-frames:v", n, "-r", FPS, *venc(16), out])
    got = count_frames(out)
    if got != n:
        raise StageError(f"모션그래픽 입힌 영상 프레임 {got} ≠ {n}")
    return out


def burn_captions(base: Path, rows: list[dict], st: dict, R: Path, end: float, snap: dict | None = None) -> Path:
    from shopping_shorts import scene_style
    from tools.caption_pack.check_bench_packs import rows_to_timeline
    if not rows and not snap:      # 자막팩이 그릴 줄 0(댓글카드가 모든 줄 자막 — frame.comment.track lines) → 바탕 그대로(compose 는 빈 시간표를 거절한다)
        return base
    tts = R / "silence.wav"
    if not tts.exists():
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", "1", tts])
    tl = rows_to_timeline(rows, tts, end)
    jsave(R / "caption_timeline.json", tl)
    out = R / "captioned.mp4"
    shutil.rmtree(R / "cw", ignore_errors=True)
    scene_style.compose(str(base), tl, snap or snapshot(st), str(out), R / "cw", {"text": ""})
    return out


# ── 소리 ────────────────────────────────────────────────────────────────
def audio(S: dict, M: dict, st: dict, T: dict, sent: list[dict], placed: dict, R: Path) -> tuple[Path, dict]:
    src_dir = Path(M["cand_dir"])
    end = T["end"]
    pieces = []
    for s in sent:
        pieces.append((s["wav"], T["lines"][s["id"]][0], "narr"))
    for k, p in enumerate(T["opos"]):
        a, b = p["span"]
        w = R / f"o_{k}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src_dir / p["src"], "-vn", "-ac", "1", "-ar", SR,
             "-af", f"highpass=f=90,afade=t=in:d=0.015,afade=t=out:st={max(0, b - a - 0.02):.3f}:d=0.02", w])
        pieces.append((str(w), p["t0"], "orig"))

    def cat(kind):
        ps = [p for p in pieces if p[2] == kind]
        if not ps:
            return None, float("nan")
        o = R / f"cat_{kind}.wav"
        run(["ffmpeg", "-y", "-v", "error", *[x for p in ps for x in ("-i", p[0])], "-filter_complex",
             "".join(f"[{i}:a]" for i in range(len(ps))) + f"concat=n={len(ps)}:v=0:a=1[o]", "-map", "[o]", "-ar", SR, o])
        return o, lufs(o)[0]
    _, nI = cat("narr")
    _, oI = cat("orig")
    og = round(nI - oI, 2) if not math.isnan(oI) and not math.isnan(nI) else 0.0      # 원음 = 나레와 같은 크기
    voice = R / "voice.wav"
    if pieces:
        ins, fc = [], []
        for k, (p, t, kind) in enumerate(pieces):
            ins += ["-i", p]
            fc.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,volume={og if kind == 'orig' else 0}dB,adelay={int(round(t * 1000))}[p{k}]")
        fc.append("".join(f"[p{k}]" for k in range(len(pieces))) + f"amix=inputs={len(pieces)}:normalize=0,apad,atrim=0:{end:.3f}[n]")
        run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[n]", "-ar", SR, voice])
    else:          # 나레도 원음도 없는 편(자막 줄만) — 목소리 자리는 무음, 소리는 배경음·효과음뿐
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{end:.3f}", voice])
    B = st["bgm"]
    bid = S.get('bgm', {}).get('id') or B.get('id')
    SF = st.get("sfx_files") or {}
    check_sfx(st, placed)
    narr_spans = [T["lines"][s["id"]] for s in sent]
    if not bid:        # 배경음 없는 판(판 bgm.id null — 두유노판 10-26 사장님 귀 확인 '배경음·효과음 없음') — 목소리(+효과음)만, 배경음 층·덕킹 없음
        ins2, fc2, mix_in = ["-i", voice], [], "[0:a]"
        for j, e in enumerate(placed.get("sfx") or []):
            ins2 += ["-i", SFX_DIR / SF[e["kind"]]]
            fc2.append(f"[{j + 1}:a]aresample={SR},aformat=channel_layouts=mono,volume={SF.get('gain_db', -8)}dB,adelay={int(round(e['t'] * 1000))}[s{j}]")
            mix_in += f"[s{j}]"
        raw = R / "mix_raw.wav"
        if fc2:
            fc2.append(f"{mix_in}amix=inputs={1 + len(placed.get('sfx') or [])}:normalize=0:duration=first[o]")
            run(["ffmpeg", "-y", "-v", "error", *ins2, "-filter_complex", ";".join(fc2), "-map", "[o]", "-ar", SR, raw])
        else:
            run(["ffmpeg", "-y", "-v", "error", "-i", voice, "-ar", SR, raw])
        mix = R / "mix.wav"
        loud(raw, mix, st["loudness"])
        return mix, {"narr_lufs": nI, "orig_lufs": oI, "orig_gain": og, "bgm_gain": None, "bgm_ref": "없음(판 bgm.id null)", "mix": lufs(mix),
                     "duck_narr_db": 0.0, "bed": None}
    bgm = BGM_DIR / f"{bid}.mp3"
    bI = lufs(bgm)[0]
    # 배경음 크기 기준 = 나레 크기(옛 그대로). 나레 없는 편(관제 263 02 2차 ②)은 원음 크기, 원음도 없으면 판 목표 음량(마스터가 어차피 맞춘다)
    ref = nI if not math.isnan(nI) else (oI if not math.isnan(oI) else float(st["loudness"]["lufs"]))
    g = round((ref - B["db_below_voice"]) - bI, 2)
    k = 10 ** (float(B.get("duck_orig_db", 0.0)) / 20)
    duck = "+".join(f"between(t,{p['t0']:.3f},{p['t1']:.3f})" for p in T["opos"]) or "0"
    vol = f"if({duck},{k:.4f},1)"
    dn = float(B.get("duck_narr_db") or 0.0)          # 나레 덕킹(A4) — 말할 때 BGM 을 더 줄인다. 0 = 없음(식이 예전과 같다)
    narr_spans = [T["lines"][s["id"]] for s in sent]
    if dn:
        nduck = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in narr_spans) or "0"
        vol = f"if({duck},{k:.4f},if({nduck},{10 ** (dn / 20):.4f},1))"
    ss = float((S.get("bgm") or {}).get("ss", 0.0))      # 곡 몇 초부터 쓰나(편마다 — 보컬 드롭 자리를 맞춘다, 가사 시각 lyric_plan 과 같은 값)
    bed_chain = (f"aresample={SR},aformat=channel_layouts=mono,atrim={ss:.3f}:{ss + end:.3f},asetpts=PTS-STARTPTS,volume={g}dB,"
                 f"volume='{vol}':eval=frame,afade=t=out:st={end - B.get('fade_out', 0.4):.3f}:d={B.get('fade_out', 0.4)}")
    bed = R / "bgm_bed.wav"       # BGM 만(나레·원음·효과음 없이) — 덕킹 실측·품질 관문이 읽는다
    run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", bgm, "-filter_complex", f"[0:a]{bed_chain}[b]", "-map", "[b]", "-ar", SR, bed])
    ins2 = ["-i", voice, "-stream_loop", "-1", "-i", bgm]
    fc2 = [f"[1:a]{bed_chain}[b]"]
    mix_in = "[0:a][b]"
    SF = st.get("sfx_files") or {}
    check_sfx(st, placed)
    for j, e in enumerate(placed.get("sfx") or []):
        f = SFX_DIR / SF[e["kind"]]
        ins2 += ["-i", f]
        fc2.append(f"[{j + 2}:a]aresample={SR},aformat=channel_layouts=mono,volume={SF.get('gain_db', -8)}dB,adelay={int(round(e['t'] * 1000))}[s{j}]")
        mix_in += f"[s{j}]"
    n_in = 2 + len(placed.get("sfx") or [])
    fc2.append(f"{mix_in}amix=inputs={n_in}:normalize=0:duration=first[o]")
    raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", "-v", "error", *ins2, "-filter_complex", ";".join(fc2), "-map", "[o]", "-ar", SR, raw])
    mix = R / "mix.wav"
    loud(raw, mix, st["loudness"])
    return mix, {"narr_lufs": nI, "orig_lufs": oI, "orig_gain": og, "bgm_gain": g, "bgm_ref": "narr" if not math.isnan(nI) else ("orig" if not math.isnan(oI) else "target"), "mix": lufs(mix),
                 "duck_narr_db": dn, "bed": bed_contrast(bed, narr_spans, [[p["t0"], p["t1"]] for p in T["opos"]], end)}


def check_sfx(st: dict, placed: dict):
    """배치가 고른 효과음 종류가 판 sfx_files(= packs.sfx, 지시서 11)에 다 있고 파일도 있나 — 없으면 멈춘다.
    옛 코드는 없는 종류를 '팩01/<종류>.wav' 로 조용히 대신 넣었다(판이 고른 팩이 아닌 소리가 나간다 — 0순위 조용한 되돌아가기)."""
    SF = st.get("sfx_files") or {}
    kinds = sorted({e["kind"] for e in placed.get("sfx") or []})
    miss = [k for k in kinds if k not in SF]
    if miss:
        raise StageError(f"효과음 종류 {miss} 가 판 sfx_files 에 없다(있는 것 {sorted(k for k in SF if k not in ('gain_db', 'why'))}) — "
                         f"packs.sfx 에 종류→파일을 적는다(pack_map, 지시서 11). 옛 '팩01/<종류>.wav' 대신 넣기는 없앴다")
    nofile = [k for k in kinds if not (SFX_DIR / SF[k]).exists()]
    if nofile:
        raise StageError(f"효과음 파일 없음: {[(k, SF[k]) for k in nofile]}")


def bed_contrast(bed: Path, narr: list, orig: list, end: float) -> dict:
    """BGM 만 뽑은 트랙의 구간별 크기(RMS dBFS) — 나레 구간 · 원음 구간 · 빈 구간(둘 다 아님). 끝 페이드 0.5초는 뺀다."""
    import subprocess
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(bed), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True,
                         stdin=subprocess.DEVNULL).stdout
    x = np.frombuffer(raw, np.float32)
    t = np.arange(len(x)) / 16000.0
    def mask(spans):
        m = np.zeros(len(x), bool)
        for a, b in spans:
            m |= (t >= a) & (t < b)
        return m
    mn, mo = mask(narr), mask(orig)
    live = t < end - 0.5
    def db(m):
        m = m & live
        return round(float(10 * np.log10(np.mean(x[m] ** 2) + 1e-12)), 2) if m.sum() > 1600 else None
    out = {"narr_db": db(mn), "orig_db": db(mo), "gap_db": db(~mn & ~mo)}
    out["narr_vs_gap"] = round(out["narr_db"] - out["gap_db"], 2) if out["narr_db"] is not None and out["gap_db"] is not None else None
    return out


def loud(src: Path, dst: Path, L: dict):
    """2단 loudnorm(측정 → 선형 맞춤) — 판 설정 loudness(−14 LUFS · TP).
    올릴 양만큼 최고점이 TP 를 넘으면 ffmpeg 가 선형을 버리고 동적으로 가 목표에 못 미친다(김나영 꿀템노트판 −21.6/−0.8 → −15.2).
    그때는 먼저 올리고 리미터로 최고점을 눌러 둔 뒤 선형 맞춤."""
    import json as _j
    I, TP = L["lufs"], L["tp"]
    pi, ptp = lufs(src)
    if ptp + (I - pi) > TP:
        pre = Path(dst).with_name(Path(dst).stem + "_lim.wav")
        run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af",
             f"volume={I - pi:.2f}dB,alimiter=limit={10 ** ((TP - 1.0) / 20):.4f}:attack=2:release=50:level=disabled", "-ar", SR, pre])
        src = pre
    m = run(["ffmpeg", "-hide_banner", "-i", src, "-af", f"loudnorm=I={I}:TP={TP}:LRA=11:print_format=json", "-f", "null", "-"], check=False).stderr
    j = _j.loads(m[m.rindex("{"):m.rindex("}") + 1])
    af = (f"loudnorm=I={I}:TP={TP}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample={SR}")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", af, "-ar", SR, dst])


# ── 전체 ────────────────────────────────────────────────────────────────
def needs_locate(st: dict) -> bool:
    """판 배치 규칙에 검출 자리(target = face|object|caption_side)를 받는 스티커·짤이 있나 — 없으면 검출 영상을 안 만든다."""
    Rl = (st.get("placement") or {}).get("rules") or {}
    if any(isinstance(r, dict) and isinstance(r.get("target"), str) for r in (Rl.get("stickers") or {}).values()):
        return True
    Mm = Rl.get("meme")
    return bool(Mm and float(Mm.get("rate", 0)) > 0 and not isinstance(Mm.get("target"), dict))


def plan_canvas(T: dict, M: dict, st: dict):
    """렌더 없이 시각 t 의 화면(1080×1920, 창 자리에 렌더 조각과 같은 그림 cut_frame — contact_sheet·관문 ④와 같은 프레임)을 돌려주는 함수.
    --plan --locate 에서 자리 검출(fx_target.locator/aim)이 detect_base.mp4 대신 쓴다(10-25 원·화살표 대상 좌표 — 렌더 금지 중 확인 길)."""
    import numpy as np
    src_dir = Path(M["cand_dir"])
    x, y, ww, wh = frame_window(st["frame"])

    def at(t):
        t = float(t or 0)
        c = next((c for c in T["cuts"] if c["t0"] <= t < c["t1"]), T["cuts"][-1])
        src = src_dir / c["src"]
        img = src.suffix.lower() in IMG_EXT
        a = cut_frame(src, 0.0 if img else float(c.get("ss") or 0) + (t - c["t0"]), cut_crop(c, src, (ww, wh)), (ww, wh), (M.get("blur") or {}).get(c["src"]))
        cv = np.zeros((H, W, 3), np.uint8)
        if a is not None:
            cv[y:y + wh, x:x + ww] = a[:, :, ::-1]
        return cv
    return at


def make_locate(S: dict, T: dict, st: dict, R: Path, win: Path, log=print, det=None):
    """placement.place(locate=…) 에 꽂을 자리 검출기(주인 = fx_target.locator/find). 검출 화면 = 틀+창(자막·전환 없이) detect_base.mp4.
    caption_side 는 판 칸 caption.band(y0,y1 — 자막 띠)가 있어야 한다. 크기 = 판 규칙 size([w,h]) · 없으면 스티커 160 · 짤 420."""
    if not needs_locate(st):
        return None
    from tools.calcopy.hybrid import fx_target as FX
    det = det if det is not None else render_base(S, T, st, {}, R, win, [], name="detect_base.mp4")      # det = plan_canvas(--plan --locate) 면 렌더 없이
    Rl = st["placement"].get("rules") or {}
    band = (st.get("caption") or {}).get("band")

    def size_of(s):
        rule = Rl.get("meme") if s.get("kind") == "meme" else (Rl.get("stickers") or {}).get(s.get("kind")) or {}
        return tuple((rule or {}).get("size") or ((420, 420) if s.get("kind") == "meme" else (160, 160)))
    lines: dict = {}            # 줄 글 전체·줄 key — 원·화살표 대상 질문 재료(fx_target.aim, 10-25)
    for r in T["rows"]:
        L = lines.setdefault(r["line"], {"text": "", "keys": []})
        L["text"] = (L["text"] + " " + r["text"]).strip()
        if r.get("key"):
            L["keys"].append(r["key"])
    loc = FX.locator(det, win=frame_window(st["frame"]), caption_band=tuple(band) if band else None, size_of=size_of,
                     cuts=T["cuts"], lines=lines, channel=(st.get("bench") or {}).get("channel"))

    def locate(target, row, s):
        try:
            return loc(target, row, s)
        except ValueError as e:        # caption_side 인데 caption.band 없음·object 인데 무엇(what) 없음 → 안 붙인다(조용히 넘기지 않고 로그)
            log(f"[자리] {s.get('kind')} {target.get('kind')} 검출 못 함: {e}")
            return None
    return locate


def deco_apply(placed: dict, doc: Path, st: dict, log=print) -> None:
    """꾸밈 답(doc/deco_answers.json — 편마다 정해진 질문 deco.questions 의 답)을 배치 rows 에 얹는다. 주인 = deco.apply(여기선 부르기만)."""
    from tools.calcopy.hybrid import deco as DC
    ans = DC.load_answers(doc)
    try:
        DC.apply(placed["rows"], ans, st, log)
    except DC.DecoError as e:
        raise StageError(str(e))
    placed.setdefault("log", []).append(f"꾸밈 답 {len((ans or {}).get('items') or [])}개" if ans else "꾸밈 답 없음(deco_answers.json)")


def deco_gate(placed: dict, doc: Path, st: dict, log=print) -> list[str]:
    """렌더 전 관문: 꾸밈 결과(배치 rows + 계획 컷)가 판 deco 범위 안인가. 판정 주인 = deco.check(부르기만). 판에 deco 칸이 없으면 안 본다."""
    from tools.calcopy.hybrid import deco as DC
    if not st.get("deco") or DC.load_answers(doc) is None:      # WIP(10-26): 답 파일이 있는 편만 멈춘다 — 새 편 연달아 만들기를 막지 않게(사장님 '새 편 우선')
        return []
    T = placed.get("_timeline") or {}
    v = DC.check(doc, st, rows=placed["rows"], cuts=T.get("cuts") or [], end=T.get("end") or 0)
    log(f"[꾸밈 관문] {'통과' if v['ok'] else '멈춤'} 포인트 {v.get('accents')} · {v['bad']}")
    return [f"꾸밈 {x}" for x in v["bad"]]


def plan_rows(S: dict, T: dict, st: dict, locate=None) -> dict:
    """배치(placement.place) — 씨앗 = 편 slug(같은 편은 늘 같은 배치). locate = make_locate(스티커·짤 자리 검출, 없으면 자리는 pending)."""
    from tools.calcopy.hybrid import placement as PL
    placed = PL.place(T["rows"], st, S.get("slug") or "x", cuts=T["cuts"], locate=locate)      # 전환·효과음 자리 = 화면 컷 경계(03)
    for r, t in zip(placed["rows"], T["rows"]):
        r["show"] = t["show"]
    placed["_timeline"] = {"cuts": T["cuts"], "end": T["end"]}      # 꾸밈 관문(deco_gate)이 본인 사진 컷·길이를 센다
    # 댓글 카드 = 배치가 고르고(벤치 편 비율) 대본에 원본 댓글이 있을 때만
    C = S.get("comment")
    rule = (st["placement"]["rules"].get("stickers") or {}).get("comment_card")
    cnt = (st["placement"].get("counted") or {}).get("stickers", {}).get("comment_card", {})
    share = cnt if isinstance(cnt, (int, float)) else cnt.get("videos", rule.get("share", 0.6) if isinstance(rule, dict) else 0.6)
    if C and rule and PL._chance(S.get("slug") or "x", "sticker:comment_card") < float(share):   # counted 는 비율 숫자로 올 때도 있다(꿀템노트판 10-23)
        t0 = T["lines"][C["from"]][0] if C.get("from") in T["lines"] else T["end"] / 2
        t1 = T["end"] if C.get("to", "end") == "end" else T["lines"][C["to"]][0]
        placed["comment"] = {**C, "t0": t0, "t1": t1}
        placed["log"].append(f"댓글 카드 {t0:.2f}~{t1:.2f}")
    placed["cards"] = card_plan(S, T, st)               # 댓글카드 자막(판 frame.comment.track lines) — 그 줄은 자막팩이 안 그린다(caption_rows)
    placed["lyrics"] = lyric_plan(S, st, T["end"])
    if placed["cards"]:
        placed["log"].append(f"댓글카드 {len(placed['cards'])}장")
    if placed["lyrics"]:
        placed["log"].append(f"가사 {len(placed['lyrics'])}줄 {placed['lyrics'][0]['t0']:.2f}초부터")
    return placed


# ── 나레 합성 줄 캐시(결정 ㉗ '바뀐 줄만 재합성') — 합성 주인은 그대로 engine/narr_align.synth_cached(돈 드는 곳 한 곳) ──────────────
TTS_LINE_GAP = 0.25        # 줄 합성본을 이어 붙일 때 줄 사이 무음(초) — 전체 한 번 합성의 문장 끝 쉼 자리. 뒤 make_sentences 가 줄 경계를 글자 시각으로 다시 자른다


def tts_by_line(S: dict, R: Path, log=print) -> tuple[Path, dict | None]:
    """나레 합성(narr_full.mp3 + 글자 시각)을 줄 캐시로. 반환은 RI.tts_once 와 같은 꼴(그 뒤 make_sentences 는 그대로).
      ① 전체 캐시(narr_full.mp3 사이드카 열쇠 = 전체 글·목소리·배속)가 맞으면 그대로 쓴다(옛 렌더와 같은 소리 — 회귀 0) + 줄 캐시로 쪼개 저장.
      ② 안 맞는데 줄 캐시가 하나도 없으면(새 대본) 옛처럼 전체 1회 합성(RI.tts_once) + 줄 캐시로 쪼개 저장.
      ③ 줄 캐시가 하나라도 있으면 바뀐 줄만 합성(synth_cached, 열쇠 = 목소리·줄 글·배속·모델)하고 줄들을 이어 narr_full 을 다시 만든다(사이드카 열쇠 = 새 전체 글).
    줄 캐시 = R/tts_lines/<열쇠>.mp3(+ .tts.json, align = 그 줄 글자 시각)."""
    from tools.calcopy.engine import narr_align as NA
    from tools.calcopy.hybrid import render_itssum as RI
    voice, tempo = S["voice"]["voice_id"], S["voice"].get("tempo")
    full = R / "narr_full.mp3"
    LD = R / "tts_lines"
    lines = [l for l in S["lines"] if l["kind"] == "tts"]
    VA = RI.voice_args(S)                                          # 회원 팩 provider·감정(관제 266) — 옛 길이면 열쇠·합성 모두 옛 그대로(NA.old_path)
    key_full = NA.voice_key(RI.tts_text(S), voice, tempo, **VA)
    meta = json.loads(NA.sidecar_of(full).read_text(encoding="utf-8")) if NA.sidecar_of(full).exists() else {}
    lkey = {l["id"]: NA.voice_key(l["tts"], voice, tempo, **VA) for l in lines}
    have = {i for i, k in lkey.items() if (LD / f"{k}.mp3").exists() and NA.sidecar_of(LD / f"{k}.mp3").exists()}
    if (full.exists() and meta.get("key") == key_full) or not have:
        full, align = RI.tts_once(S, R, log)                      # ①(캐시 적중) 또는 ②(새 대본 = 전체 1회)
        tts_split_lines(S, full, align, LD, log)
        return full, align
    # ③ 바뀐 줄만 합성
    LD.mkdir(parents=True, exist_ok=True)
    made = []
    for l in lines:
        f = LD / f"{lkey[l['id']]}.mp3"
        if l["id"] not in have:
            NA.synth_cached(l["tts"], voice, tempo, f, log=log, **VA)
            made.append(l["id"])
    log(f"[tts] 줄 캐시: 재사용 {len(lines) - len(made)}줄 · 새로 합성 {made}")
    import subprocess
    import numpy as np
    pcm, chars, st0, en0, t = [], [], [], [], 0.0
    gap = np.zeros(int(round(TTS_LINE_GAP * 44100)), np.float32)
    for k, l in enumerate(lines):
        f = LD / f"{lkey[l['id']]}.mp3"
        x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-ac", "1", "-ar", "44100", "-f", "f32le", "-"], capture_output=True,
                                         stdin=subprocess.DEVNULL).stdout, np.float32)
        a = NA.load_align(f)
        if not a or len(a["characters"]) != len(l["tts"]):
            raise StageError(f"줄 캐시 {f.name} 글자 시각이 줄 글({len(l['tts'])}자)과 안 맞는다 — 줄 캐시를 지우고 다시")
        if k:
            pcm.append(gap); chars.append(" "); st0.append(round(t - TTS_LINE_GAP / 2, 3)); en0.append(round(t - TTS_LINE_GAP / 2, 3))
        chars += list(a["characters"])
        st0 += [round(t + v, 3) for v in a["character_start_times_seconds"]]
        en0 += [round(t + v, 3) for v in a["character_end_times_seconds"]]
        pcm.append(x)
        t += len(x) / 44100 + TTS_LINE_GAP
    wav = R / "narr_full_lines.wav"
    import wave
    y = np.concatenate(pcm)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    if full.exists():
        full.replace(full.with_name(f"narr_full_old_{str(meta.get('key', 'x'))[:8]}.mp3"))
    run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "1", full])
    align = {"characters": chars, "character_start_times_seconds": st0, "character_end_times_seconds": en0}
    if "".join(chars) != RI.tts_text(S):
        raise StageError("줄 캐시로 이은 글자 시각이 전체 글과 다르다")
    NA.sidecar_of(full).write_text(json.dumps({"key": key_full, "text": RI.tts_text(S), "voice": voice, "tempo": tempo, "model": NA.TTS_MODEL,
                                               "align": align, "legacy": False, "from_lines": {l["id"]: lkey[l["id"]] for l in lines}, "made": made,
                                               "at": __import__("time").strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False), encoding="utf-8")
    return full, align


def tts_split_lines(S: dict, full: Path, align: dict | None, LD: Path, log=print) -> int:
    """전체 합성본을 줄 캐시로 쪼개 저장(글자 시각이 있을 때만 — 줄 경계 = RI.split_by_align 과 같은 자리). 이미 있는 줄은 건너뜀. 반환 = 새로 쓴 줄 수."""
    from tools.calcopy.engine import narr_align as NA
    from tools.calcopy.hybrid import render_itssum as RI
    if not align:
        return 0
    voice, tempo = S["voice"]["voice_id"], S["voice"].get("tempo")
    VA = RI.voice_args(S)
    lines = [l for l in S["lines"] if l["kind"] == "tts"]
    try:
        spans = RI.split_by_align(S, align)
    except StageError as e:
        log(f"[tts] 줄 캐시 쪼개기 건너뜀: {e}")
        return 0
    LD.mkdir(parents=True, exist_ok=True)
    pos, n = 0, 0
    for l, (a, b) in zip(lines, spans):
        i0, i1 = pos, pos + len(l["tts"])
        pos = i1 + 1
        f = LD / f"{NA.voice_key(l['tts'], voice, tempo, **VA)}.mp3"
        if f.exists() and NA.sidecar_of(f).exists():
            continue
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", full, "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "1", f])
        la = {k: [round(v - a, 3) for v in align[k][i0:i1]] for k in ("character_start_times_seconds", "character_end_times_seconds")}
        la["characters"] = align["characters"][i0:i1]
        NA.sidecar_of(f).write_text(json.dumps({"key": NA.voice_key(l["tts"], voice, tempo, **VA), "text": l["tts"], "voice": voice, "tempo": tempo, **VA,
                                                "model": NA.TTS_MODEL, "align": la, "legacy": False, "split_from": full.name}, ensure_ascii=False), encoding="utf-8")
        n += 1
    return n


def devices(st: dict, trans: list[dict], A: dict | None = None, segs: list[dict] | None = None, T: dict | None = None,
            n_narr: int | None = None) -> dict:
    """render_info.devices 표식(지시서 02 → 04 품질 관문이 읽는다): 전환 종류별 개수 · 나레 덕킹 dB·실측 · 틀 종류 ·
    (2차) 구간 틀 · 자막 쌓기 · 컷 그림 칸 수 · 나레 줄 수(0 = 나레 없는 편). 2차 칸은 값이 있을 때만 붙는다(장치 안 켠 판 표식 그대로)."""
    from collections import Counter
    TR = (st.get("cuts") or {}).get("transition") or {}
    d = {"transition": {"kinds_set": TR.get("kinds") or {"cut": 1.0}, "drawn": dict(Counter(e["kind"] for e in trans)), "n": len(trans)},
         "duck_narr": {"db": float((st.get("bgm") or {}).get("duck_narr_db") or 0.0), "bed": (A or {}).get("bed")},
         "frame_kind": frame_kind(st["frame"])}
    if segs:
        d["segments"] = [{"t0": g["t0"], "t1": g["t1"], "kind": g["kind"], "window": g["window"], "captions": g["captions"]} for g in segs]
    if (st.get("caption") or {}).get("stack"):
        d["caption_stack"] = st["caption"]["stack"]
    if T and any(c.get("pic") for c in T["cuts"]):
        d["pic_cuts"] = sum(1 for c in T["cuts"] if c.get("pic"))
    if n_narr == 0:
        d["narration"] = 0
    return d


def render_marks(style_name: str, renderer_file: str | Path) -> dict:
    """render_info 표식 한 곳(0순위-C, 표준 §11 ⑤ — 04 품질 관문 marker_verdict 가 읽는다): render_bench·render_itssum·render_jaemi 가 같이 부른다.
    style_sha = 판 파일 바이트 sha256(관문이 지금 파일과 앞자리 대조) · style_sha_effective = _common·base 합친 설정 sha256 앞 12자리 ·
    renderer_sig = '<렌더러 파일 이름>@<그 파일 sha256 앞 12자리>'."""
    import hashlib
    from tools.calcopy.hybrid import styles as ST
    rf = Path(renderer_file)
    eff = json.dumps(ST.load(style_name), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {"style_sha": hashlib.sha256(ST.path_of(style_name).read_bytes()).hexdigest(),
            "style_sha_effective": hashlib.sha256(eff).hexdigest()[:12],
            "renderer_sig": f"{rf.stem}@{hashlib.sha256(rf.read_bytes()).hexdigest()[:12]}"}


def _voice_gate_text(S: dict) -> None:
    """렌더 전 관문 ② 앞 — tts 글에 영문이 있으면 TTS 돈 쓰기 전에 멈춘다(주인 engine/narr_verify.latin_lines)."""
    from tools.calcopy.engine import narr_verify as NV
    bad = NV.latin_lines(S)
    if bad:
        raise StageError(f"tts 글에 영문 {bad} — 타입캐스트가 건너뛴다(감사 'AI'·'LED' 7곳). 한글 읽기로 바꿔 보낸다(AI → 에이아이)")


def _voice_bad_audio(S: dict, sent: list, R: Path, log=print) -> list[str]:
    """렌더 전 관문 ② — 합성 직후 줄별 받아쓰기 ↔ 그 줄 글(주인 engine/narr_verify.gate_sent). 확정 결함 글 목록(빈 목록 = 통과, 멈춤은 voice_plan 이 모아서)."""
    from tools.calcopy.engine import narr_verify as NV
    bad = NV.gate_sent(S, sent, R, log)
    return ["나레 줄별 받아쓰기 확정 결함: " + " / ".join(bad) + " — 그 줄 문장을 바꿔 다시 합성(줄 캐시라 바뀐 줄만). 상세 render/narr_verify.json"] if bad else []


def _voice_gate_audio(S: dict, sent: list, R: Path, log=print) -> None:
    """(옛 이름 — 바로 멈추는 꼴) _voice_bad_audio 를 부르고 걸리면 GateError."""
    gate_stop([("② 받아쓰기", _voice_bad_audio(S, sent, R, log))])


# ── 렌더 전 관문 순서·모으기(10-26 사장님 '품질관문이나 고칠 것부터' — 회원 마스크편 장면 맞추기 8바퀴 = 바퀴마다 첫 실패 하나만 알려 줌) ──
# 판정 함수·문턱은 그대로. 여기는 부르는 순서와 모으기만 정한다. 계획(--plan·회원 c_plan)과 렌더가 같은 timeline_gates 를 부른다(두 벌 금지).
GATE_DEPENDS = {
    # 관문(또는 묶음) : 기대는 것 — 앞이 걸리면 뒤는 그 결과가 바뀐 뒤 다시 재야 하니 이번엔 돌리지 않는다
    "G-1 대본 글(영문)": "없음 — TTS(돈) 전에 멈춘다",
    "이름 끊김 · ② 받아쓰기": "합성한 소리(같은 소리를 재는 두 관문이라 모아 한 번)",
    "시간표 관문(넘침·⑧ 길이·⑥ 카드·③ 경계·④ 글자·얼굴·⑤ 컷 길이·⑦ 멈춤·사진·리듬)":
        "소리 → 시간표(timeline). 전부 같은 시간표 T 를 읽기만 하고 서로의 결과를 안 읽는다 → 모두 돌려 모은다"
        "(하나를 고치면 ss·컷이 바뀌어 다른 칸 값도 바뀔 수 있다 — 다음 계획이 전부 다시 잰다)",
    "꾸밈(deco)": "계획 = 배치(plan_rows) 뒤 · 렌더 = 굽은 창의 자리 검출(make_locate) 뒤 — 렌더에서는 시간표 관문 통과 뒤에 돈다",
}


class GateError(StageError):
    """렌더 전 관문 멈춤 — problems = [(관문 이름, 문제 글)…] 전부(한 번에 고치게). str = 문제 글을 ' / ' 로 이은 것(옛 StageError 글 꼴 그대로)."""

    def __init__(self, problems: list[tuple[str, str]]):
        self.problems = list(problems)
        super().__init__(" / ".join(m for _, m in self.problems))


def gate_stop(groups: list[tuple[str, list[str]]]) -> None:
    """[(관문 이름, 문제 글 목록)…] — 하나라도 있으면 전부 실은 GateError."""
    probs = [(g, m) for g, ms in groups for m in ms]
    if probs:
        raise GateError(probs)


def over_text(over: list[dict], plan: bool, measured: bool = True) -> list[str]:
    """'컷이 원본 샷보다 길다' 글(옛 글 그대로 — flow _plan_causes·ph_render_got 가 이 글로 찾는다)."""
    if not over:
        return []
    rows = str([(c["line"], c["src"], c.get("ss"), c["dur"], c.get("max"), {"원본 남음": c["src_left"]} if "src_left" in c else None) for c in over])
    room = [f"{c['line']} {c['src']} 에서 {c['dur']}초가 들어가는 샷(시작~끝): {c['room'] or '없음 — 이 줄 컷을 둘로 나눠라'}" for c in over if "room" in c]
    if room:
        rows += " — 고칠 자리: " + " / ".join(room)
    return [("계획에서 컷이 원본 샷보다 길다" + ("" if measured else "(어림)") + ": " if plan else "컷이 원본 샷보다 길다: ") + rows]


GATE_STAMP = "plan_gates_ok.json"      # 계획 관문이 전부 통과한 입력 지문 — 렌더가 같은 지문이면 시간표 관문을 다시 안 잰다(검수단축 ⑤, 10-26)


def gate_stamp(T: dict, M: dict, st: dict, doc: Path) -> str:
    """(판단 주인 — 시간표 관문 입력 지문) 관문이 읽는 것 전부: 컷(시각·원본·ss·crop·속도…)·길이·흐림·원본 파일 정체(크기·mtime — VMake 로 지우면 바뀐다)·
    판 설정·썸네일.json(카드 관문)·이 파일(관문 코드). 하나라도 다르면 다른 지문 = 다시 잰다."""
    import hashlib
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    srcs = sorted({str(c.get("src")) for c in T["cuts"]})
    tp = Path(doc) / "썸네일.json"
    body = [T["cuts"], T.get("end"), M.get("blur"), str(src_dir), st, [src_ident(src_dir / s)[1:] if src_dir else None for s in srcs],
            tp.read_text(encoding="utf-8") if tp.exists() else None, hashlib.sha256(Path(__file__).read_bytes()).hexdigest()]
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def timeline_gates(T: dict, M: dict, st: dict, doc: Path, R: Path, log=print, *, plan: bool, measured: bool = True,
                   erase: list | None = None, placed: dict | None = None) -> list[tuple[str, list[str]]]:
    """(판단 주인 — 렌더 전 시간표 관문 목록·순서) 같은 시간표 T 를 읽는 관문을 전부 돌려 [(관문 이름, 문제 글 목록)…] 로(빈 목록 = 통과).
    계획과 렌더가 이 함수 하나를 부른다. placed 를 주면(계획) 꾸밈 관문도. 기대는 관계 = GATE_DEPENDS."""
    from tools.calcopy.hybrid import thumb_rule as TR
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    out = [("넘침", over_text([c for c in T["cuts"] if c["over"] > 0], plan, measured)),
           ("⑧ 길이", plan_length_gate(T, st, measured)),
           ("⑥ 카드 글", TR.card_text_gate(doc)),
           ("⑥ 카드 얼굴", TR.card_face_gate(st, doc, T, M["cand_dir"])),
           ("③ 경계", cut_boundary_gate(T, M, st)),
           ("④ 글자·얼굴", cut_content_gate(T, M, st, doc, R, log, erase=erase)),
           ("⑤ 컷 길이", cut_length_gate(T, st)),
           ("⑦ 멈춤", cut_still_gate(T, M, st)),
           ("사진", photo_gate(T, st)),
           ("리듬", rhythm_gate(T, st, src_dir))]
    if placed is not None:
        out.append(("꾸밈", deco_gate(placed, doc, st, log)))
    n = sum(len(b) for _, b in out)
    if n:
        log(f"[렌더 전 관문] 걸린 것 {n}개 — " + " · ".join(f"{g} {len(b)}" for g, b in out if b) + " (한 번에 모아 알린다)")
    return out


def voice_plan(S: dict, st: dict, R: Path, log=print) -> tuple[list, dict | None, dict | None]:
    """나레 목소리 길이 주인(관문 ⑧ · G-3) — 계획(--plan)과 렌더가 같이 부른다(10-25 전엔 두 벌).
    영문 관문 → 줄 캐시 합성(tts_by_line, 바뀐 줄만 돈) → 줄 자르기(make_sentences) → 받아쓰기 관문 → 쉼 맞춤(fit_voice).
    반환 (sent, tempo, align) · tts 줄이 없으면 ([], None, None)."""
    from tools.calcopy.hybrid import render_itssum as RI
    tts_S = {**S, "lines": [l for l in S["lines"] if l["kind"] == "tts"]}
    if not tts_S["lines"]:
        return [], None, None
    _voice_gate_text(S)
    full, align = tts_by_line(tts_S, R, log)
    from tools.calcopy.engine import narr_verify as NV
    nb = NV.name_breaks(S, align)      # 관문(이름 끊김, 관제 266) — 합성 글자 시각으로 인물 이름 안 쉼 > 0.15초면 영상 굽기 전에 멈춘다
    if not align:
        log("[이름 끊김] 글자 시각 없음 — 판정 못 함(받아쓰기 관문 ②만)")
    sent, tempo, _ = RI.make_sentences(tts_S, full, R, log, align=align, spread=RI.spread_of(st))
    asr = _voice_bad_audio(S, sent, R, log)   # 판 targets.speech 목표가 있으면 타입캐스트 줄별 ±8% 미세(미나 그대로, 지시서 15)
    gate_stop([("이름 끊김", nb), ("② 받아쓰기", asr)])      # 같은 소리를 재는 두 관문 — 모아 한 번(GATE_DEPENDS: 시간표 관문은 이 소리에 기댄다)
    sent = fit_voice(S, st, sent, align, log)   # 줄 사이·문장부호 쉼 = 판(B18 timing.gap · B18a speech) — 관제263
    return sent, tempo, align


LENGTH_TOL = 0.5      # 판 length 허용 폭(초) — bench_check '길이'·계획 length.ok 와 같은 범위


def plan_length_gate(T: dict, st: dict, measured: bool) -> list[str]:
    """렌더 전 관문 ⑧ — 완성본 길이가 판 length(±LENGTH_TOL) 밖이면 영상 굽기 전에 멈춘다. 진짜 목소리 길이일 때만 본다:
    어림(글자÷cps)은 이미 만든 12편 실측 0.13~3.40초 짧아 5편을 거짓으로 '짧다' 했다(fixtures/plan_voice_len.json)."""
    if not measured:
        return []
    LD = st["length"]
    if LD["min"] - LENGTH_TOL <= T["end"] <= LD["max"] + LENGTH_TOL:
        return []
    return [f"길이 {T['end']:.2f}초 — 판 '{st.get('name')}' {LD['min']}~{LD['max']}초(±{LENGTH_TOL}) 밖. 대본 줄을 "
            + ("줄이거나 쉼을 덜어" if T["end"] > LD["max"] else "늘려") + " 다시(렌더 전에 멈춤)"]


def render(style_name: str, doc: Path, work: Path, plan_only: bool = False, log=print, tts: bool = True, report: bool = False, locate: bool = False,
           pack: Path | str | None = None) -> dict:
    """plan_only: 계획만(조각·영상 안 만듦). tts=True(기본) = 진짜 목소리 길이로 계획(합성은 줄 캐시 — 렌더가 그대로 쓴다), False = 어림(--guess, 관문 ⑧ 안 봄).
    report=True: 계획에서 컷 넘침·길이를 멈추지 않고 돌려준다(회원 c_plan 이 재료 고치기 안내로 쓴다)."""
    from tools.calcopy.hybrid import render_itssum as RI
    from tools.calcopy.hybrid import styles as ST
    st = ST.load(style_name)
    doc, work = Path(doc), Path(work)
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    S.setdefault("voice", {k: st["voice"][k] for k in ("name", "voice_id", "provider", "emotion") if k in st["voice"]})
    RI.voice_args(S, check=True)          # 목소리 칸 검사(provider·감정 — 주인 engine/voices.check_tts). 틀리면 합성 전에 멈춘다
    RI.read_names(S, log)                 # 이름 발음 사전(engine/name_dict — preset_make.tts 와 같은 주인 apply_all, 그 목소리로 확인한 표기만)
    S.setdefault("cps_target", st.get("cps_target", 7.0))
    R = work / "render"; R.mkdir(parents=True, exist_ok=True)
    if plan_only:
        sm = align = None
        if tts:      # 계획 때 진짜 목소리 길이로(관문 ⑧ — 10-22 선우용여: 어림으로 통과 → 렌더 3번 · 10-25 이미 만든 12편 어림이 0.13~3.40초 짧음). 합성은 캐시 — 렌더가 그대로 쓴다
            sent, _, align = voice_plan(S, st, R, log)
            sm = {x["id"]: x for x in sent}
        else:
            log("[어림] --guess: 글자÷cps 길이 — 길이 관문(⑧)은 안 본다. 렌더 전 판정은 --plan(진짜 목소리)으로")
        T = timeline(S, M, st, sm, align)
        placed = plan_rows(S, T, st, make_locate(S, T, st, R, None, log, det=plan_canvas(T, M, st)) if locate else None)   # --locate = 스티커 자리·원 대상까지 계획에서(렌더 없이)
        deco_apply(placed, doc, st, log)
        placed["transitions_drawn"] = transitions_of(T, st, placed, log)
        jsave(doc / "plan/계획_시간표.json", {"timeline": T, "placement": placed})
        sheet = contact_sheet(T, M, st, doc / "plan/계획_접촉시트.jpg", S)      # G-10 렌더 없는 눈 검사(관문이 멈춰도 볼 수 있게 관문 앞에서)
        if sheet:
            log(f"접촉 시트(컷마다 처음·가운데·끝, 렌더 칸 그대로) → {sheet}")
        for c in T["cuts"]:
            log(f"  {c['line']:4s} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c.get('max')} {c['src']}@{c.get('ss')}")
        LD = st["length"]
        length = {"sec": round(T["end"], 2), "min": LD["min"], "max": LD["max"], "measured": bool(tts),
                  "ok": LD["min"] - LENGTH_TOL <= T["end"] <= LD["max"] + LENGTH_TOL}      # 판정 = bench_check '길이'와 같은 범위(±0.5)
        log(f"{'목소리 실측' if tts else '어림'} 길이 {T['end']}초 · 배치 {placed['log']}")
        from tools.calcopy import vmake_clean as VC
        erase = [] if VC.will_erase(style_name) else None        # 박힌 글자를 지우는 판(orig_text.mode=vmake·돈 막힘 아님) — 글자 컷은 멈추지 않고 '지울 컷'(사장님 10-26)
        gates = timeline_gates(T, M, st, doc, R, log, plan=True, measured=bool(tts), erase=erase, placed=placed)      # 넘침·⑧·⑥·③④⑤⑦·사진·리듬·꾸밈 전부(첫 실패에서 안 멈춘다)
        (R / GATE_STAMP).unlink(missing_ok=True)
        if tts and not erase and not any(b for _, b in gates):      # 진짜 목소리·지울 컷 없음·전부 통과일 때만 지문(지울 컷이 있으면 렌더가 지운 뒤 다시 잰다)
            jsave(R / GATE_STAMP, {"stamp": gate_stamp(T, M, st, doc), "at": __import__("time").strftime("%Y-%m-%d %H:%M:%S")})
        if erase is not None:      # 지울 컷 = 계획 시간표 칸 하나(vmake_clean.used_spans 가 읽는다) — 관문 뒤에 다시 저장
            T["vmake_cuts"] = sorted(set(erase))
            jsave(doc / "plan/계획_시간표.json", {"timeline": T, "placement": placed})
            if erase:
                log(f"[관문④ → VMake] 박힌 글자 컷 {T['vmake_cuts']} — 멈추지 않고 렌더 전 VMake 로 지운다(vmake_clean.used_spans)")
        if not report:
            gate_stop(gates)
        # report(회원 c_plan) = 멈추지 않고 전부 돌려준다 — over = 길이(⑧, length 칸이 따로 알린다) 밖 문제 글 전부 · gates = 관문별
        over_all = " / ".join(m for g, ms in gates if g != "⑧ 길이" for m in ms)
        return {"timeline": T, "placement": placed, "length": length, "over": over_all, "gates": gates, "sheet": str(sheet) if sheet else None}
    sent, tempo, align = voice_plan(S, st, R, log)      # 관문 ⑧ 주인 — 계획과 같은 함수(같은 소리·같은 길이)
    if not sent:    # 나레 없는 편(관제 263 02 2차 ②) — TTS 안 부른다(돈 0). 자막 줄(kind sub) 시간표 + 원음 + 배경음·효과음
        log("[나레 없음] tts 줄 0 — TTS 건너뜀, 자막 시간표(sub)·원음·배경음·효과음만")
    sm = {s["id"]: s for s in sent}
    T = timeline(S, M, st, sm, align)
    sp = R / GATE_STAMP
    if sp.exists() and jload(sp).get("stamp") == gate_stamp(T, M, st, doc):      # 계획이 같은 입력으로 전부 통과 — 다시 안 잰다(검수단축 ⑤)
        log(f"[렌더 전 관문] 계획({jload(sp).get('at')})과 입력이 같다(컷·원본·판·썸네일·관문 코드 지문) — 다시 안 잰다")
    else:
        gate_stop(timeline_gates(T, M, st, doc, R, log, plan=False))      # 넘침·⑧·⑥·③④⑤⑦·사진·리듬 — 영상 굽기 전에 전부 모아 멈춘다(꾸밈은 창 자리 뒤 — GATE_DEPENDS)
    win0 = render_window(T, M, st, R)                          # 창(전환 없이) — 자리 검출 화면의 재료
    placed = plan_rows(S, T, st, make_locate(S, T, st, R, win0, log))
    deco_apply(placed, doc, st, log)
    gate_stop([("꾸밈", deco_gate(placed, doc, st, log))])
    from tools.calcopy.hybrid import placement as PL
    chk = PL.check_place(placed, st)
    check_sfx(st, placed)
    MG = motion_graphics(st, T)
    if MG and MG["not_drawn"]:
        log(f"[모션그래픽] {MG['id']} — bench 자막팩이라 안 그리는 칸: {MG['not_drawn']}")
    trans = transitions_of(T, st, placed, log)
    win = window_transitions(win0, T, st, R, trans)
    look = member_look(pack)                                  # 회원 꾸민 모양(관제 266) — 있으면 판 틀 대신
    if look:
        log(f"[회원 꾸민 모양] {look.get('presetId')} — 판 틀 그림 대신 회원 스냅샷으로 틀·자막(창 영상만 넘김)"
            + (" · 댓글 카드는 창 밖이면 잘린다" if placed.get("comment") else ""))
    base = render_base(S, T, st, placed, R, win, trans, color=(MG or {}).get("color_filter"), look=bool(look))
    T["end"] = round(sum(c["frames"] for c in T["cuts"]) / FPS, 4)
    segs = [] if look else frame_segments(S, T, st)
    rows = caption_rows(placed, st, segs)
    cap = draw_motion_layers(burn_captions(base, rows, st, R, T["end"], snap=look_snapshot(st, look) if look else None), MG, R)
    mix, A = audio(S, M, st, T, sent, placed, R)
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", cap, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{T['end']:.3f}", final])
    from tools.calcopy.engine import ad_mark
    ad_mark.apply_inplace(final, log=log)
    jsave(R / "timeline.json", T)      # 썸네일 카드가 이 시간표로 장면(줄·몇 번째 컷)을 찾는다 — 카드보다 먼저 저장(10-24 09: 옛 시간표로 찾아 실패)
    if (doc / "썸네일.json").exists() and (jload(doc / "썸네일.json").get("options") or []):      # 빈 3안 = 카드 없이(flow 가 카드 반려 끝에 비운다, 10-26) · 맨 앞 2프레임 = 썸네일 카드(주인 thumb.card · 10-23 사장님 "맨 앞에 썸네일 아주 잠깐") — 카드에 '광고' 같이 찍힘
        from tools.calcopy.hybrid import thumb as TH
        tc = TH.cards(style_name, doc, work, log=log)
        TH.stamp_video(final, Path(tc["pick_jpg"]))
        log(f"썸네일 {tc['pick']} → 맨 앞 {TH.THUMB_FRAMES}프레임")      # 오른쪽 위 '광고' 표시 — 주인 = engine/ad_mark(사장님 10-22 모든 렌더)
    from tools.calcopy.engine import finalize
    finalize.seal(final, "render_bench", doc / "대본.json", log=log)      # final 을 고치는 마지막 단계(썸네일 카드) 뒤 — 납품은 이 봉인 그대로인 파일만(engine/deliver)
    jsave(R / "timeline.json", T)
    tab = {"_note": f"배치 결과 — placement.place(판 설정 {style_name}) · 시각은 final.mp4 기준 초", "pack": st["caption"]["pack"], "rows": rows,
           "sfx": placed["sfx"], "flashes": placed["flashes"], "transitions": trans, "memes": meme_overlays(placed), "comment": placed.get("comment"),
           **({"cards": placed["cards"]} if placed.get("cards") else {}), **({"lyrics": placed["lyrics"]} if placed.get("lyrics") else {}),
           **({"segments": [{k: g[k] for k in ("t0", "t1", "kind", "window", "captions", "body_text")} for g in segs]} if segs else {}),
           "log": placed["log"], "check": chk}
    jsave(R / "자막표.json", tab)
    jsave(doc / "자막표.json", tab)
    info = {"made_by": "tools/calcopy/hybrid/render_bench.py", "version": style_name, **({"member_look": look.get("presetId")} if look else {}), "tempo": tempo, "final": str(final), "final_dur": dur_of(final),
            "final_lufs": lufs(final), "audio": A, "placement_check": chk, "n_cuts": len(T["cuts"]),
            "devices": {**devices(st, trans, A, segs, T, len(sent)),
                        **({"motion_graphics": {"id": MG["id"], "layers": len(MG["layers"]), "color": MG["color_filter"], "not_drawn": MG["not_drawn"]}} if MG else {})},
            **render_marks(style_name, __file__), "line_cps": RI.line_cps(sent),
            "cuts_flat": [{k: c.get(k) for k in ("line", "src", "ss", "t0", "t1", "dur", "see")} for c in T["cuts"]]}
    jsave(R / "render_info.json", info)
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, doc / "final_sheet_1s.jpg")
    log(f"final {final} {info['final_dur']:.2f}초 LUFS/TP {info['final_lufs']} · 배치 {placed['log']}")
    return info


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("style"); ap.add_argument("doc"); ap.add_argument("work"); ap.add_argument("--plan", action="store_true")
    ap.add_argument("--guess", action="store_true", help="--plan 을 어림(글자÷cps)으로 — 합성 안 함, 길이 관문(⑧) 안 봄")
    ap.add_argument("--locate", action="store_true", help="--plan 에서 스티커 자리·원/화살표 대상(fx_target.aim, 오푸스 눈)까지 — 렌더 없이 계획 프레임으로")
    ap.add_argument("--pack", help="회원 팩 파일(~/.shortem/packs/<pid>.json) — web.look(꾸민 모양)이 있으면 판 틀 대신")
    a = ap.parse_args()
    render(a.style, Path(a.doc), Path(a.work), plan_only=a.plan or a.guess, tts=not a.guess, locate=a.locate, pack=a.pack)
