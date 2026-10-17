# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 — **재미썸홈판** 렌더러(한 벌). 대본.json + 재료.json + 틀만 읽는다 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/hybrid/render_jaemi.py <doc_dir> <work_dir> [--plan] [--desktop <mp4>]

정본 = 하이브리드_함익병/재미썸홈판/{make.py,render_hybrid.py} 계열(함익병·박세리·장윤정·최은경의 손질을 한 벌에):
  · A 원음 밑 화면 = 원음 이어 붙인 시간의 컷 목록(장윤정 A_VIS) · F1 컷 여럿(from_piece) · 쉼 찾기 d 조절 + 맞붙은 무음 합침(최은경)
  · A|B 자름 = min(B 첫 조각 −0.04, 문장부호 쉼 끝 −0.10)(박세리 'ㅈ' 잘림 수리) · 오프너 효과음 −0.25초(장윤정 '저 영상' 덮임 수리)
  · 끝 문장만 atempo 따로(B15, ±10% 안) · 쉼표 0.22·마침표 0.30(엔진 tts_pause.shape, B18) · 끝 컷 늘림 end_pad(B4 ≥1.5초)
흐름: Typecast 필재 1회(tempo 1.25) → 앞뒤 무음 자르기·긴 쉼 0.28 → atempo(전체·끝 문장) → 문장부호 쉼 모양 → 조각 시각(엔진 _place)
  → A(얜샷템 틀: 원음 컷 + F1 TTS 한마디) + B(재미썸홈 t11 프리셋, body_all) → 원음·나레(RMS 중앙 −17.5dBFS)·A BGM(덕킹)·B 효과음(low) → target_lufs.

대본.json: title · source_label · body_title · voice{voice_id,tempo} · cps_target · orig[{id,span}] · orig_caps[[원본초,글]] · lines[{slot,text,tts}]
  pieces[{caption}](줄은 글자 순서로 자동 배정) · 선택: tts_tempo{all,last}(없으면 자동) · punct_at[[",",초]](없으면 자동 추정) ·
  render{end_pad,gap_o_f1,duck_db,bgm_a_rms,voice_rms,target_lufs,silence_d,voice_af,sfx_density} · bgm{id} · frame_a · preset_b
재료.json: cand_dir · src_main · A[{at,src,ss,crop[x,y,w,h],see}] · F1[{src,ss,crop,from_piece,see}] · B[{src,ss,crop[x,y,h],kind,pieces[],seen}]
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import (FPS, FRAME_A_DEFAULT, PRESET_JAEMI_B, ROOT, SR, StageError, dur_of, frame_png, jload, jsave,  # noqa: E402
                                         lufs, nchar, probe, run, silences)

WIN_A = 1080
WIN_B = (1080, 1407)
DEF = {"end_pad": 0.7, "gap_o_f1": 0.12, "duck_db": -10.0, "bgm_a_rms": -31.5, "voice_rms": -17.5, "target_lufs": -14.0, "silence_d": 0.08,
       "voice_af": "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1", "sfx_density": "low",
       "tempo_max": 1.27, "tempo_min": 0.85, "last_tempo_tol": 0.10, "pause_long": 0.28, "pause_comma": 0.235, "pause_period": 0.315,
       "opener_at": -0.25, "preset_b": str(PRESET_JAEMI_B)}


def cfg(S):
    return {**DEF, **(S.get("render") or {})}


def piece_lines(S) -> list[int]:
    """조각 → 줄 번호(대사 글자 순서대로 소비). 조각에 line 이 적혀 있으면 그것."""
    if all("line" in p for p in S["pieces"]):
        return [int(p["line"]) for p in S["pieces"]]
    out, li, used = [], 0, 0
    for p in S["pieces"]:
        while used >= nchar(S["lines"][li]["text"]):
            li, used = li + 1, 0
        out.append(li); used += nchar(p["caption"])
    return out


def check_pieces(S):
    whole = "".join(re.findall(r"[가-힣A-Za-z0-9]", " ".join(l["text"] for l in S["lines"])))
    pcs = "".join(re.findall(r"[가-힣A-Za-z0-9]", " ".join(p["caption"] for p in S["pieces"])))
    if whole != pcs:
        raise StageError("자막 조각이 대사와 다르다")
    bad = [p["caption"] for p in S["pieces"] if len(p["caption"]) > 13]
    if bad:
        raise StageError(f"자막 조각 13자 넘음: {bad}")


def groups_of(M, times):
    """B 컷 묶음에 조각 시각을 붙인다 → [{src,ss,crop,kind,t0,t1,pieces,seen}]."""
    gs = []
    for g in M["B"]:
        ps = list(g["pieces"])
        gs.append({**g, "t0": times[ps[0]][0], "t1": times[ps[-1]][1]})
    return gs


def punct_marks(S) -> list[str]:
    """TTS 글에서 문장부호 자리(쉼표·마침표) 순서 — 마지막 문장 끝은 뺀다(쉼 모양 대상 아님)."""
    text = " ".join(l["tts"] for l in S["lines"])
    marks = [{"?": ".", "!": "."}.get(m, m) for m in re.findall(r"[,.?!]", text)]
    return marks[:-1] if marks and marks[-1] == "." else marks


# ── 나레 ───────────────────────────────────────────────────────────────
def tts_once(S, R: Path, log=print) -> Path:
    full = R / "narr_full.mp3"
    if not full.exists():
        from shopping_shorts.channelkit import providers
        providers.typecast_synth(S["voice"]["voice_id"], tempo=S["voice"].get("tempo", 1.25))(" ".join(l["tts"] for l in S["lines"]), str(full))
        log(f"TTS 1회: {full} {dur_of(full):.2f}초")
    return full


def auto_tempo(S, tight: Path, split: float, chars_all: int) -> dict:
    """tts_tempo 가 없을 때: 전체 atempo = 목표 자/초 ÷ 원속(상한 tempo_max) · 끝 문장은 평균 속도에 맞춰 따로(전체 대비 ±10% 안)."""
    C = cfg(S)
    d0 = dur_of(tight)
    last_chars = nchar(S["lines"][-1]["tts"])
    rate_body = (chars_all - last_chars) / max(split, 0.1)
    rate_last = last_chars / max(d0 - split, 0.1)
    t_all = round(min(C["tempo_max"], max(C["tempo_min"], S["cps_target"] / rate_body)), 2)
    t_last = t_all * (rate_body / rate_last) * 0.98                    # 끝 문장은 평균보다 조금 느리게(B15)
    t_last = round(min(t_all * (1 + C["last_tempo_tol"]), max(t_all * (1 - C["last_tempo_tol"]), t_last)), 3)
    return {"all": t_all, "last": t_last, "auto": True, "rate_body": round(rate_body, 2), "rate_last": round(rate_last, 2)}


def auto_punct_at(S, pre: Path, sil: list[tuple[float, float]]) -> list[list]:
    """punct_at 이 없을 때: 문장부호 자리를 **앞 부호 자리부터 글자 수 × 평균 말속도**로 어림해 가장 가까운 뒤쪽 무음에 붙인다(차례대로).
    전체 비례 한 번에 하면 말속도 굴곡으로 0.3초씩 어긋난다(장윤정 '테클라.' 실측) — 부호마다 다시 기준을 잡으면 0.2초 안.
    낱말 안 받침 막힘(0.08초) 같은 가짜 쉼이 섞일 수 있어 결과는 render_info 에 남기고, 어긋남 >0.3초면 멈춘다(punct_at 손으로)."""
    from tools.calcopy import narr_video as N
    marks = punct_marks(S)
    text = " ".join(l["tts"] for l in S["lines"])
    before = [nchar(text[:m.start()]) for m in re.finditer(r"[,.?!]", text)][:len(marks)]
    total = nchar(text)
    segs, dur = N.speech_segments(str(pre), "-40dB", 0.06)
    speech = sum(b - a for a, b in segs) or dur
    sec_per_char = speech / max(total, 1)
    out, used, prev_t, prev_c = [], set(), 0.0, 0
    for kind, c in zip(marks, before):
        est = prev_t + (c - prev_c) * sec_per_char
        # 후보 무음: 어림과 가깝고 **긴** 무음(문장부호 쉼 ≥0.1초 · 낱말 안 받침 막힘 0.06~0.09초)을 앞세운다
        cand = sorted((abs((a + b) / 2 - est) - 1.5 * min(b - a, 0.3), abs((a + b) / 2 - est), (a, b)) for a, b in sil if (a, b) not in used and a >= prev_t - 0.05)
        if not cand:
            raise StageError("문장부호 자리에 붙일 무음이 모자란다")
        _, d, s = cand[0]
        if d > 0.45:
            raise StageError(f"문장부호 '{kind}' 어림 {est:.2f}초 근처에 무음이 없다(가장 가까운 {s}) — 대본 punct_at 을 손으로 적어라")
        used.add(s)
        out.append([kind, round((s[0] + s[1]) / 2, 3)])
        prev_t, prev_c = s[1], c
    return out


def narr_prep(S, R: Path, log=print):
    """앞뒤 무음 자르기 + 0.28초 넘는 쉼만 0.28초로 → atempo(전체·끝 문장) → 문장부호 쉼 모양(엔진 tts_pause.shape).
    반환 narr.wav, tempo 기록, 글자 수, 원 길이, 줄 머리 시각(문장부호 쉼 끝)."""
    C = cfg(S)
    from tools.calcopy import narr_video as N
    from tools.calcopy.engine import tts_pause as TP
    full, tight, narr = R / "narr_full.mp3", R / "narr_tight.wav", R / "narr.wav"
    f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
    mid = f"silenceremove=stop_periods=-1:stop_duration={C['pause_long']}:stop_threshold=-40dB:stop_silence={C['pause_long']}"
    run(["ffmpeg", "-y", "-i", full, "-af", f"{f},areverse,{f},areverse,{mid}", "-ar", SR, "-ac", "1", tight])
    chars = sum(nchar(l["tts"]) for l in S["lines"])
    d0 = dur_of(tight)
    segs, _ = N.speech_segments(str(tight), "-40dB", 0.1)
    split = segs[-1][0] - 0.02                    # 마지막 쉼 끝 = 끝 문장 시작
    tempo = S.get("tts_tempo") or auto_tempo(S, tight, split, chars)
    p1, p2, pre = R / "narr_p1.wav", R / "narr_p2.wav", R / "narr_pre.wav"
    run(["ffmpeg", "-y", "-i", tight, "-af", f"atrim=0:{split:.3f},atempo={tempo['all']}", "-ar", SR, p1])
    run(["ffmpeg", "-y", "-i", tight, "-af", f"atrim={split:.3f},asetpts=PTS-STARTPTS,atempo={tempo['last']}", "-ar", SR, p2])
    run(["ffmpeg", "-y", "-i", p1, "-i", p2, "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", "-ar", SR, "-ac", "1", pre])
    TP.PAUSE = {",": C["pause_comma"], ".": C["pause_period"]}   # 이음매 겹침 15ms 만큼 짧게 나와 그만큼 더 줌 → 0.22/0.30
    sil = silences(pre, "-40dB", C["silence_d"])
    punct = S.get("punct_at") or auto_punct_at(S, pre, sil)
    ch, st, en, slots = [], [], [], []
    for kind, at in punct:
        a_, b_ = min(sil, key=lambda x: abs((x[0] + x[1]) / 2 - at))
        if abs((a_ + b_) / 2 - at) >= 0.2:
            raise StageError(f"문장부호 {kind} {at}초 근처 무음 없음(가장 가까운 {a_:.2f}~{b_:.2f}) — punct_at 확인")
        ch += ["가", kind, "가"]; st += [a_ - 0.05, a_, b_]; en += [a_, b_, b_ + 0.05]; slots.append((a_, b_))
    log_ = TP.shape(str(pre), {"characters": ch, "character_start_times_seconds": st, "character_end_times_seconds": en}, str(R / "narr_shaped.mp3"))
    run(["ffmpeg", "-y", "-i", R / "narr_shaped.mp3", "-ar", SR, "-ac", "1", narr])
    shift, ends = 0.0, []
    for k, ((a_, b_), lg) in enumerate(zip(slots, log_)):   # 이음매(15ms 겹침)마다 그만큼 앞당겨진다
        shift += lg["now"] - lg["was"]
        ends.append(round(b_ + shift - TP.XF_SEC * (2 * k + 1), 3))
    # 줄 머리 = 각 줄 끝 문장부호 쉼 끝. 줄 끝 부호가 아닌 쉼표(문장 안)는 건너뛴다
    heads, i = [0.0], 0
    for l in S["lines"][:-1]:
        n_in = len([m for m in re.findall(r"[,.?!]", l["tts"])])
        i += n_in
        heads.append(ends[i - 1])
    return narr, {**tempo, "split_raw": round(split, 3), "pauses": log_, "punct_at": punct}, chars, d0, heads


# ── 시간표(판단 주인: 이 함수 한 곳) ────────────────────────────────────
def timeline(S, M, narr: Path | None, line_heads: list[float] | None, est_cps: float | None = None) -> dict:
    """조각 시각(완성본 초)·A 컷·B 묶음. narr 가 None 이면 글자 수 ÷ est_cps 로 어림(계획 시트)."""
    C = cfg(S)
    from tools.calcopy import narr_video as N
    pl = piece_lines(S)
    P = S["pieces"]
    nF1 = sum(1 for li in pl if li == 0)
    o_len = sum(b - a for _, (a, b) in ((o["id"], o["span"]) for o in S["orig"]))
    f1_at = o_len + C["gap_o_f1"]
    if narr is None:
        t, timed = 0.0, []
        for k, p in enumerate(P):
            d = nchar(p["caption"]) / est_cps
            timed.append({"text": p["caption"], "line": pl[k], "t0": round(t, 3), "t1": round(t + d, 3)}); t += d
        cut = timed[nF1]["t0"]
        ndur = t
    else:
        steps = [{"text": p["caption"], "chars": nchar(p["caption"]), "new_cut": True, "line": li} for p, li in zip(P, pl)]
        segs, ndur = N.speech_segments(str(narr))
        W = list(line_heads) + [ndur]
        if len(W) != len(S["lines"]) + 1:
            raise StageError(f"줄 머리 수가 줄 수와 다르다 {len(W) - 1} vs {len(S['lines'])}")
        timed = []
        for li in range(len(S["lines"])):
            st = [s_ for s_ in steps if s_["line"] == li]
            timed += [{**s_, "t0": round(t_, 3)} for s_, t_ in zip(st, N._place(st, segs, 0.4, W[li], W[li + 1]))]
        for i, s_ in enumerate(timed):
            s_["t1"] = timed[i + 1]["t0"] if i + 1 < len(timed) else round(ndur, 3)
        # F1 | B 나눔 — B 첫 줄 말 시작 바로 앞(쉼 안). 글자 비례 −0.04 로 자르면 'ㅈ' 이 잘려(박세리 '너 영상') 문장부호 쉼 끝 −0.10 과 더 앞인 쪽
        cut = min(timed[nF1]["t0"] - 0.04, line_heads[1] - 0.10)
    A_end = round(round((f1_at + cut) * FPS) / FPS, 4)
    T = []
    for k, s in enumerate(timed):
        if k < nF1:
            T.append((f1_at + s["t0"], f1_at + min(s["t1"], cut)))
        else:
            T.append((A_end + s["t0"] - cut, A_end + s["t1"] - cut))
    T[nF1 - 1] = (T[nF1 - 1][0], A_end)
    END = round(T[-1][1] + C["end_pad"], 3)
    T[-1] = (T[-1][0], END)
    T = [(round(a, 3), round(b, 3)) for a, b in T]
    # A 컷: 원음 밑 화면(at = 원음 이어 붙인 초) → F1 컷들(from_piece)
    a_shots = []
    for k, c in enumerate(M["A"]):
        nxt = M["A"][k + 1]["at"] if k + 1 < len(M["A"]) else o_len
        a_shots.append({**c, "t0": float(c["at"]), "t1": float(nxt), "who": "O"})
    F1 = M["F1"]
    for k, c in enumerate(F1):
        fp = int(c.get("from_piece", 0 if k == 0 else nF1 - 1))
        t0 = o_len if k == 0 else T[fp][0]
        t1 = T[int(F1[k + 1].get("from_piece", nF1 - 1))][0] if k + 1 < len(F1) else A_end
        a_shots.append({**c, "t0": round(t0, 3), "t1": round(t1, 3), "who": "F1"})
    for s in a_shots:
        s["dur"] = round(s["t1"] - s["t0"], 3)
    Tb = [(a - A_end, b - A_end) for a, b in T[nF1:]]
    gs = []
    for g in M["B"]:
        ps = list(g["pieces"])
        gs.append({**g, "t0": round(T[ps[0]][0] - A_end, 3), "t1": round(T[ps[-1]][1] - A_end, 3)})
    return {"pieces": [{"i": k + 1, "line": pl[k], "caption": P[k]["caption"], "t": list(T[k])} for k in range(len(T))], "timed": timed, "cut": cut,
            "o_len": round(o_len, 3), "f1_at": round(f1_at, 3), "A_end": A_end, "END": END, "a_shots": a_shots, "b_groups": gs, "Tb": Tb, "nF1": nF1,
            "piece_lines": pl, "ndur": round(ndur, 3)}


def frame_a(S, dst: Path):
    fr = jload(S.get("frame_a") or FRAME_A_DEFAULT)
    for l in fr["layers"]:
        if l.get("role") == "title":
            l["text"] = S["title"]
        if l.get("role") == "label":
            l["text"] = S["source_label"]
    fr.setdefault("made_from", {})["episode"] = f"얜샷템 하이브리드 재미썸홈판 {S.get('slug', '')} (tools/calcopy/hybrid/render_jaemi.py)"
    jsave(dst, fr)
    return fr


# ── 계획 시트 ───────────────────────────────────────────────────────────
def plan(S, M, doc: Path, log=print) -> dict:
    from PIL import Image, ImageDraw, ImageFont
    check_pieces(S)
    SRC = Path(M["cand_dir"])
    T = timeline(S, M, None, None, est_cps=S["cps_target"])
    for g in T["b_groups"]:
        w, h, sd = probe(SRC / g["src"])
        cw = int(round(g["crop"][2] * WIN_B[0] / WIN_B[1]))
        if g["ss"] + (g["t1"] - g["t0"]) > sd:
            raise StageError(f"B 컷이 소스 끝을 넘는다 {g['src']} {g['ss']}+{g['t1'] - g['t0']:.2f} > {sd:.2f}")
        if g["crop"][0] + cw > w or g["crop"][1] + g["crop"][2] > h:
            raise StageError(f"B 크롭이 화면 밖 {g['src']} {g['crop']} ({w}x{h})")
        g["zoom"] = round(WIN_B[1] / g["crop"][2], 2)
    rows = []
    for a in T["a_shots"]:
        rows.append({"label": f"A/{a['who']} {a['t0']:.2f}+{a['dur']:.2f}", "src": a["src"], "a": a["ss"], "b": a["ss"] + a["dur"], "crop": a["crop"], "size": (300, 300),
                     "caps": "", "seen": a.get("see", "")})
    for g in T["b_groups"]:
        x, y, h = g["crop"]
        rows.append({"label": f"B {g['t0']:.2f}+{g['t1'] - g['t0']:.2f} {g.get('kind', '')}", "src": g["src"], "a": g["ss"], "b": g["ss"] + g["t1"] - g["t0"],
                     "crop": [x, y, int(round(h * WIN_B[0] / WIN_B[1])), h], "size": (230, 300), "caps": " / ".join(S["pieces"][k]["caption"] for k in g["pieces"]), "seen": g.get("seen", "")})
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 17)
    small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    COLW, ROWH, PER, head = 3 * 300 + 330, 310, 2, 64
    sheet = Image.new("RGB", (COLW * PER, head + ROWH * ((len(rows) + PER - 1) // PER)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"얜샷템 하이브리드 {S.get('slug', '')} — 재미썸홈판 계획 시트(TTS 전) · 예상 {T['END']:.1f}초 · A 원음 {T['o_len']:.2f}초 + TTS · B 컷 {len(T['b_groups'])}", fill="black", font=font)
    d.text((10, 34), "프레임 3장 = 컷 시작+0.1 · 가운데 · 끝−0.1, 완성본 크롭 그대로(A 1080², B 1080×1407)", fill="#444", font=small)
    for k, r in enumerate(rows):
        x0, y0 = (k % PER) * COLW, head + (k // PER) * ROWH
        for j, tt in enumerate((r["a"] + 0.1, (r["a"] + r["b"]) / 2, r["b"] - 0.1)):
            sheet.paste(frame_png(SRC / r["src"], tt, r["crop"], r["size"]), (x0 + j * 300, y0))
        tx = x0 + 905
        d.text((tx, y0 + 2), r["label"], fill="black", font=font)
        d.text((tx, y0 + 26), f"{str(r['src'])[:22]} {r['a']:.2f}~{r['b']:.2f}", fill="#333", font=small)
        for i in range(0, min(len(r["caps"]), 120), 20):
            d.text((tx, y0 + 48 + i // 20 * 20), r["caps"][i:i + 20], fill="#000", font=font)
        for i in range(0, min(len(r["seen"]), 60), 20):
            d.text((tx, y0 + 180 + i // 20 * 18), r["seen"][i:i + 20], fill="#555", font=small)
    (doc / "plan").mkdir(parents=True, exist_ok=True)
    sheet.save(doc / "plan/계획_시트.jpg", quality=85)
    jsave(doc / "plan/계획_시간표.json", T)
    log(f"est {T['END']} B cuts {len(T['b_groups'])} max zoom {max(g['zoom'] for g in T['b_groups'])} → {doc / 'plan/계획_시트.jpg'}")
    return T


# ── 렌더 ────────────────────────────────────────────────────────────────
def render(doc: Path, work: Path, plan_only: bool = False, desktop: Path | None = None, log=print) -> dict:
    import numpy as np
    from tools.calcopy import narr_video as N
    from shopping_shorts import scene_style, bgm_lib, sfx_pack as SP
    from shopping_shorts.calcopy_frame import schema, to_snapshot
    doc, work = Path(doc), Path(work)
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    C = cfg(S)
    R = work / "render"
    R.mkdir(parents=True, exist_ok=True)
    frame = frame_a(S, R / "frame_A.json")
    shutil.copy(R / "frame_A.json", doc / "frame_A.json")
    if plan_only:
        return {"plan": str(doc / "plan/계획_시트.jpg"), "timeline": plan(S, M, doc, log)}
    check_pieces(S)
    SRC = Path(M["cand_dir"])
    HAM = M["src_main"]
    work_ = R / "work"; shutil.rmtree(work_, ignore_errors=True); work_.mkdir()
    tts_once(S, R, log)
    narr, tempo, chars, d0, line_heads = narr_prep(S, R, log)
    dn = dur_of(narr)
    log(f"TTS {chars / d0:.2f}자/초 → atempo {tempo['all']}/{tempo['last']} → {chars / dn:.2f}자/초 ({dn:.2f}초)")
    T = timeline(S, M, narr, line_heads)
    A_end, END, nF1, Tb, gs = T["A_end"], T["END"], T["nF1"], T["Tb"], T["b_groups"]
    Tp = [tuple(p["t"]) for p in T["pieces"]]
    o_len, f1_at, cut = T["o_len"], T["f1_at"], T["cut"]
    log(f"A_end {A_end} END {END}")
    # ── A 영상
    spec = schema.validate(frame)
    win = next(l for l in spec["layers"] if l["kind"] == "video")
    cap = next(l for l in spec["layers"] if l["kind"] == "text" and l["role"] == "caption")
    parts = []
    for k, s in enumerate(T["a_shots"]):
        nf = round(s["t1"] * FPS) - round(s["t0"] * FPS)
        p = work_ / f"a{k}.mp4"
        N.shot_clip(SRC / s["src"], s["ss"], nf / FPS, win, 750, True, p, src_crop=s["crop"], frames=nf)
        parts.append(p); s["frames"] = nf
    (work_ / "a.txt").write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    matA = work_ / "matA.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", work_ / "a.txt", "-c", "copy", matA])
    caps, ot = [], 0.0
    for o in S["orig"]:
        a, b = o["span"]
        for ts, txt in S["orig_caps"]:
            if a - 0.01 <= ts < b:
                caps.append((round(ot + ts - a, 3), txt, (255, 255, 255), "원음"))
        ot += b - a
    for k in range(nF1):
        caps.append((Tp[k][0], S["pieces"][k]["caption"], tuple(cap["rgb"]), "나레"))
    caps.sort()
    ev = []
    for j, (t0, txt, rgb, who) in enumerate(caps):
        t1 = caps[j + 1][0] if j + 1 < len(caps) else A_end
        if who == "원음" and j + 1 < len(caps) and caps[j + 1][3] == "나레":
            t1 = o_len                            # 원음 마지막 자막은 원음 끝에서 내린다
        ev.append({"t0": t0, "t1": round(t1, 3), "text": txt, "rgb": rgb, "who": who})
    ins, fc, last = [], "", "0:v"
    for k, e in enumerate(ev):
        png = N.emph_png(e["text"], cap, e["rgb"], work_ / f"emph{k}.png", dy=(1920 - win["h"]) // 2 - win["y"])
        ins += ["-loop", "1", "-i", str(png)]
        fc += f"{';' if fc else ''}[{last}][{k + 1}:v]overlay=0:0:enable='between(t,{e['t0']:.3f},{e['t1'] - 0.001:.3f})'[e{k}]"
        last = f"e{k}"
    matA2 = work_ / "matA_emph.mp4"
    run(["ffmpeg", "-y", "-i", matA, *ins, "-filter_complex", fc + f";[{last}]format=yuv420p[v]", "-map", "[v]", "-t", f"{A_end:.3f}",
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-color_range", "tv", matA2])
    tlA = [{"beat_idx": 0, "t0": 0.0, "dur": A_end, "narration": "", "caption_lines": [], "role": "hook", "primary": {"video_id": "s0", "start": 0.0, "end": A_end}}]
    vidA = work_ / "vidA.mp4"
    scene_style.compose(str(matA2), tlA, scene_style.validate_snapshot(to_snapshot.to_snapshot(frame)), str(vidA), work_ / "composeA", {"text": S["title"]})
    # ── B 영상
    lst = []
    for gi, g in enumerate(gs):
        nf = round(g["t1"] * FPS) - round(g["t0"] * FPS)
        x, y, h = g["crop"]; w = int(round(h * WIN_B[0] / WIN_B[1])) // 2 * 2
        out = work_ / f"b{gi:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{g['ss']:.3f}", "-i", SRC / g["src"], "-an", "-vf",
             f"crop={w}:{h}:{x}:{y},scale={WIN_B[0]}:{WIN_B[1] + 1}:flags=lanczos,setsar=1,fps={FPS}", "-frames:v", nf,
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", out])
        lst.append(f"file '{out.as_posix()}'")
        g.update({"frames": nf, "dur": round(nf / FPS, 3), "src_end": round(g["ss"] + nf / FPS, 3), "t0_final": round(A_end + g["t0"], 3), "t1_final": round(A_end + g["t1"], 3)})
    (work_ / "b.txt").write_text("\n".join(lst), encoding="utf-8")
    matB = work_ / "matB.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", work_ / "b.txt", "-c", "copy", matB])
    PRE = jload(C["preset_b"])
    snapB = scene_style.validate_snapshot({"mode": "story", "presetId": PRE["template"]["preset_id"], "frameRule": "body_all",
                                           "text": {"channel": PRE["brand"]["channel_name"], "hook1": "", "hook2": "", "bodyTitle": S["body_title"]}})
    tlB = [{"beat_idx": k, "t0": round(a, 3), "dur": round(b - a, 3), "narration": S["pieces"][k + nF1]["caption"], "caption_lines": [S["pieces"][k + nF1]["caption"]],
            "role": "body", "primary": {"video_id": "s0", "start": round(a, 3), "end": round(b, 3)}} for k, (a, b) in enumerate(Tb)]
    vidB = work_ / "vidB.mp4"
    scene_style.compose(str(matB), tlB, snapB, str(vidB), work_ / "composeB", {"text": "", "body_title": S["body_title"]})
    vid = work_ / "video.mp4"
    (work_ / "v.txt").write_text(f"file '{vidA.as_posix()}'\nfile '{vidB.as_posix()}'\n", encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", work_ / "v.txt", "-an", "-r", FPS, "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", vid])
    total = dur_of(vid)
    # ── 소리
    oparts, ot = [], 0.0
    for k, o in enumerate(S["orig"]):
        a, b = o["span"]
        p = work_ / f"o{k}.wav"
        run(["ffmpeg", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", SRC / HAM, "-vn", "-ac", "1", "-ar", SR, "-af",
             f"{C['voice_af']},afade=t=in:d=0.015,afade=t=out:st={b - a - 0.015:.3f}:d=0.015", p])
        oparts.append((p, ot)); ot += b - a
    f1 = work_ / "narr_f1.wav"; nb = work_ / "narr_b.wav"
    run(["ffmpeg", "-y", "-i", narr, "-af", f"atrim=0:{cut:.3f},afade=t=out:st={cut - 0.02:.3f}:d=0.02", f1])
    run(["ffmpeg", "-y", "-i", narr, "-af", f"atrim={cut:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.01", nb])

    def rms_med(p):
        a = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", "44100", "-f", "f32le", "-"], capture_output=True).stdout, dtype=np.float32)
        k20 = int(0.02 * 44100); fr_ = a[: len(a) // k20 * k20].reshape(-1, k20)
        r = 20 * np.log10(np.sqrt((fr_ ** 2).mean(1)) + 1e-9)
        return float(np.median(r[r > r.max() - 30]))
    ngain = C["voice_rms"] - rms_med(narr)
    ocat = work_ / "orig_cat.wav"
    run(["ffmpeg", "-y", *[x for p, _ in oparts for x in ("-i", p)], "-filter_complex", "".join(f"[{i}:a]" for i in range(len(oparts))) + f"concat=n={len(oparts)}:v=0:a=1[o]", "-map", "[o]", ocat])
    ogain = C["voice_rms"] - rms_med(ocat)
    pl = T["piece_lines"]
    stl = []
    for li in range(1, len(S["lines"])):
        mine = [k for k in range(nF1, len(S["pieces"])) if pl[k] == li]
        a, b = Tb[mine[0] - nF1][0], Tb[mine[-1] - nF1][1]
        stl.append({"beat_idx": li - 1, "t0": round(a, 3), "dur": round(b - a, 3), "narration": " ".join(S["pieces"][k]["caption"] for k in mine),
                    "caption_lines": [S["pieces"][k]["caption"] for k in mine], "cap_durs": [round(Tb[k - nF1][1] - Tb[k - nF1][0], 3) for k in mine],
                    "cap_lead": 0.0, "cap_offset": 0.0, "role": S["lines"][li]["slot"]})
    pname, pdir = SP.pack_for(0)
    pack = {"name": pname, "dir": pdir, "density": C["sfx_density"], "level": "normal", "mute_beats": []}
    evs = SP.events(stl, pack)
    evs = [(pth, (C["opener_at"] if Path(pth).stem == "opener" else tt), mul) for pth, tt, mul in evs]   # 오프너는 틀이 바뀌는 쉼 안으로
    jsave(R / "sfx_events.json", {"pack": pname, "plan": SP.plan_events(stl, density=C["sfx_density"]), "events": evs, "timeline": stl, "offset": A_end})
    bgm = bgm_lib.path_of(S["bgm"]["id"])
    ins = ["-i", str(f1), "-i", str(nb), "-i", str(ocat), "-stream_loop", "-1", "-i", bgm]
    flt = [f"[0:a]volume={ngain:.2f}dB,adelay={int(f1_at * 1000)}|{int(f1_at * 1000)}[n1]",
           f"[1:a]volume={ngain:.2f}dB,adelay={int(A_end * 1000)}|{int(A_end * 1000)}[n2]",
           f"[2:a]volume={ogain:.2f}dB[o]"]
    bgain = C["bgm_a_rms"] - rms_med(bgm)
    duck = 10 ** (C["duck_db"] / 20)
    flt.append(f"[3:a]aformat=channel_layouts=mono,aresample={SR},atrim=0:{A_end:.3f},volume={bgain:.2f}dB,"
               f"volume='if(lt(t,{o_len + 0.1:.3f}),{duck:.4f},1)':eval=frame,afade=t=in:d=0.3,afade=t=out:st={A_end - 0.5:.3f}:d=0.5[b]")
    lab = ["[n1]", "[n2]", "[o]", "[b]"]
    for j, (path, tt, mul) in enumerate(evs):
        ins += ["-i", path]
        ms = int(round((A_end + tt) * 1000))
        flt.append(f"[{4 + j}:a]aresample={SR},aformat=channel_layouts=mono,volume={mul:.4f},adelay={ms}|{ms}[s{j}]")
        lab.append(f"[s{j}]")
    flt.append("".join(lab) + f"amix=inputs={len(lab)}:normalize=0:duration=longest,atrim=0:{total:.3f},apad=whole_dur={total:.3f}[m]")
    raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[m]", "-ar", SR, "-ac", "1", raw])
    mix = R / "mix.wav"
    gain = 4.0
    for _ in range(10):
        run(["ffmpeg", "-y", "-i", raw, "-af", f"acompressor=threshold=0.125:ratio=3:attack=2:release=60,volume={gain:.2f}dB,"
             f"alimiter=limit={10 ** (-1.0 / 20):.4f}:level=false:attack=1:release=30", "-ar", SR, "-ac", "2", mix])
        oI, _ = lufs(mix)
        if abs(oI - C["target_lufs"]) <= 0.3:
            break
        gain += (C["target_lufs"] - oI) * 0.9
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    fI, fpk = lufs(final)
    starts = [next(s["t0"] for s in T["timed"] if s["line"] == li) for li in range(len(S["lines"]))] + [T["ndur"]]
    rates = [round(nchar(S["lines"][i]["tts"]) / (starts[i + 1] - starts[i]), 2) for i in range(len(S["lines"]))]
    rep = {"made_by": "tools/calcopy/hybrid/render_jaemi.py", "version": "재미썸홈판", "final": str(final), "dur": dur_of(final), "lufs": fI, "peak_dbfs": fpk,
           "atempo": tempo, "cps_out": round(chars / dn, 2), "line_rates": rates, "A_end": A_end, "orig_sec": round(o_len, 2), "b_cuts": len(gs),
           "b_cut_median": sorted(g["dur"] for g in gs)[len(gs) // 2], "end_cut": gs[-1]["dur"], "sfx": len(evs), "ngain": round(ngain, 2), "ogain": round(ogain, 2),
           "mix_gain": round(gain, 2), "max_caption": max(len(p["caption"]) for p in S["pieces"])}
    cuts_flat = [{"src": g["src"], "ss": g["ss"], "t0": g["t0_final"], "t1": g["t1_final"], "dur": g["dur"], "seg": "B", "line": pl[g["pieces"][0]], "see": g.get("seen", "")} for g in gs]
    cuts_flat += [{"src": s["src"], "ss": s["ss"], "t0": s["t0"], "t1": s["t1"], "dur": s["dur"], "seg": "A", "line": s["who"], "see": s.get("see", "")} for s in T["a_shots"]]
    info = {"report": rep, "pieces": T["pieces"], "a_shots": T["a_shots"], "a_caps": ev, "b_groups": gs, "timed": T["timed"], "cut": cut, "cuts_flat": cuts_flat,
            "lines": [{"slot": l["slot"], "text": l["text"], "tts": l["tts"], "chars": nchar(l["tts"])} for l in S["lines"]]}
    jsave(R / "render_info.json", info)
    jsave(R / "timeline.json", info)
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, doc / "final_sheet_1s.jpg")
    if desktop:
        from tools.calcopy.hybrid.common import md5
        Path(desktop).parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy(final, desktop)
            rep["desktop"] = {"path": str(desktop), "md5_same": md5(final) == md5(desktop)}
        except PermissionError as e:
            rep["desktop"] = {"path": str(desktop), "error": str(e)}
        jsave(R / "render_info.json", info)
    log(json.dumps(rep, ensure_ascii=False))
    return info


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("doc"); ap.add_argument("work")
    ap.add_argument("--plan", action="store_true"); ap.add_argument("--desktop")
    a = ap.parse_args()
    render(Path(a.doc), Path(a.work), plan_only=a.plan, desktop=Path(a.desktop) if a.desktop else None)


if __name__ == "__main__":
    main()
