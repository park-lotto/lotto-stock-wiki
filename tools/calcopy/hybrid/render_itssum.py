# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 — **잇썸홈판** 렌더러(한 벌). 대본.json + 재료.json + 틀(frame_얜샷템.json)만 읽는다 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/hybrid/render_itssum.py <doc_dir> <work_dir> [--plan] [--desktop <mp4>]

정본 = 하이브리드_함익병/잇썸홈판/make_render.py 계열(함익병·박세리·장윤정·최은경 네 편의 손질을 전부 한 벌에 모음):
  · 원음 조각 여럿(pieces · pad_after/gap_after, 박세리) · 원음 줄 둘(O1·O2 + gap_before, 최은경) · 남의 소리 끄기(mute, 함익병)
  · 줄별 TTS 갈아 끼우기(tts_override — 이름 발음, 최은경) · 느린 줄 ≤10% 당김(장윤정) · 컷이 원본 샷(max)보다 길면 멈춤
  · 자막은 A·B 경계를 넘지 않음 · O1 끝 자막은 말 끝나고 내림 · 쉼표 자리 쉼 늘림(tts_pauses, B18)
흐름: Typecast 1회(H+B 한 번에, 있으면 재사용) → tts_spans 로 문장 자르기 → atempo(목표 자/초, 줄별 ±10%)
  → 시간표(timeline — 시각의 주인 한 곳) → A(얜샷템 틀 1080² 창, emph 자막) + B(잇썸홈 전체화면_가운데자막 프리셋)
  → 나레+원음+BGM(나레 −14.4dB, 원음 창 −10dB 덕킹) → −8.6 LUFS 마스터.

대본.json(필수): title · source_label · voice.voice_id · cps_target · bgm{id,db_below_voice,duck_orig_db} · lines[]
  lines: {id, seg:"A"|"B", kind:"tts", tts, caps[]} / {id, seg:"A", kind:"orig", src, (spans|span|pieces), (caps_rel|caps), mute?, gap_before?}
  선택: tts_spans{id:[a,b]} · tts_pauses{id:[[s,e,목표초]]} · tts_override{id:mp3} · render{gap,gap_ab,tail,target_lufs,tp,orig_af,a_end_pad}
재료.json: cand_dir · A{H:[{src,ss,crop,see,weight?,max?}], O:[{at,src,ss,crop,see,max?}]} · B[{line,toks,src,ss,max,crop,see}]
  (A.H 는 [0,o0] 을 weight 비례로 나눔(기본 균등) · 마지막 H 에 reach_orig:true 면 ss 를 첫 원음 원본 초에 닿게 거꾸로 잡음(박세리 한 줄기 이어감)
   A.O 의 at = 원음 이어 붙인 시간(초, 쉼 pad·gap 포함) · 마지막 O 는 a_end 까지)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import (FPS, FRAME_A_DEFAULT, PRESET_ITSSUM_B, ROOT, SR, StageError, dur_of, frame_png, jload, jsave,  # noqa: E402
                                         lufs, nchar, run, silences)

DEF = {"gap": 0.20, "gap_ab": 0.20, "gap_oo": 0.25, "tail": 0.50, "target_lufs": -8.6, "tp": -3.2, "orig_af": "highpass=f=90",
       "a_end_pad": 0.0, "orig_fade": 0.015, "bgm_dir": "shopping_shorts/assets/bgm_lib", "preset_b": str(PRESET_ITSSUM_B)}


def cfg(S: dict) -> dict:
    return {**DEF, **(S.get("render") or {})}


def tts_lines(S):
    return [l for l in S["lines"] if l["kind"] == "tts"]


def orig_lines(S):
    return [l for l in S["lines"] if l["kind"] == "orig"]


def b_ids(S):
    return [l["id"] for l in tts_lines(S) if l.get("seg", "B") == "B"]


def h_id(S):
    a = [l["id"] for l in tts_lines(S) if l.get("seg") == "A"]
    if len(a) != 1:
        raise StageError(f"A 구간 TTS 줄은 하나(H)여야 한다: {a}")
    return a[0]


def orig_pieces(S) -> list[dict]:
    """원음 줄들 → 조각 목록(순서대로) [{id, line, src, span, pad, gap}] — spans / span / pieces 세 꼴을 한 꼴로."""
    out = []
    for L in orig_lines(S):
        if L.get("pieces"):
            ps = [{"id": p["id"], "span": list(p["span"]), "pad": float(p.get("pad_after", 0.0)), "gap": float(p.get("gap_after", 0.0))} for p in L["pieces"]]
        elif L.get("spans"):
            ps = [{"id": f"{L['id']}{k}", "span": list(s), "pad": 0.0, "gap": 0.0} for k, s in enumerate(L["spans"])]
        else:
            ps = [{"id": L["id"], "span": list(L["span"]), "pad": 0.0, "gap": 0.0}]
        for p in ps:
            out.append({**p, "line": L["id"], "src": L["src"], "mute": [m for m in (L.get("mute") or []) if p["span"][0] <= m[0] < p["span"][1]]})
    if not out:
        raise StageError("원음 줄(kind=orig)이 없다")
    return out


# ── TTS ────────────────────────────────────────────────────────────────
def tts_once(S, R: Path, log=print) -> Path:
    full = R / "narr_full.mp3"
    if not full.exists():
        from shopping_shorts.channelkit import providers
        text = " ".join(l["tts"] for l in tts_lines(S))
        providers.typecast_synth(S["voice"]["voice_id"], tempo=S["voice"].get("tempo"))(text, str(full))
        log(f"Typecast 1회: {full} ({dur_of(full):.2f}초)")
    return full


def split_sentences(full, n):
    """무음 -40dB ≥0.16초 중 긴 것 n-1개 = 문장 경계(자동). 손으로 확인한 tts_spans 가 있으면 그것이 이긴다."""
    sil = silences(full, "-40dB", 0.16)
    total = dur_of(full)
    head = sil[0][1] if sil and sil[0][0] <= 0.02 else 0.0
    tail = sil[-1][0] if sil and sil[-1][1] >= total - 0.02 else total
    inner = [s for s in sil if s[0] > head + 0.05 and s[1] < tail - 0.05]
    cut = sorted(sorted(inner, key=lambda s: s[1] - s[0], reverse=True)[:n - 1])
    edges = [head] + [x for s in cut for x in s] + [tail]
    return [(edges[2 * i], edges[2 * i + 1]) for i in range(n)], inner


def make_sentences(S, full: Path, R: Path, log=print):
    """문장 자르기 → 쉼 고치기(tts_pauses) → atempo. atempo 는 전체 한 값(B17), 빠른 줄은 평균까지 늦추고(≤10%)
    느린 줄(평균의 90% 미만)은 ≤10% 당긴다(장윤정 편). 줄별 tts_override 가 있으면 그 파일을 그 줄 소스로(최은경 이름 발음)."""
    L = tts_lines(S)
    spans, inner = split_sentences(full, len(L))
    if S.get("tts_spans"):
        spans = [tuple(S["tts_spans"][l["id"]]) for l in L]
    P = S.get("tts_pauses") or {}
    OV = S.get("tts_override") or {}
    chars = [nchar(l["tts"]) for l in L]

    def eff(l, a, b, tempo):
        return (b - a) - sum(e - s for s, e, _ in P.get(l["id"], [])) + sum(t * tempo for _, _, t in P.get(l["id"], []))
    tempo = 1.1
    for _ in range(5):
        speech = sum(eff(l, a, b, tempo) for l, (a, b) in zip(L, spans))
        tempo = round(min(1.25, max(0.85, S["cps_target"] / (sum(chars) / speech))), 4)
    durs = [eff(l, a, b, tempo) / tempo for l, (a, b) in zip(L, spans)]
    mean = sum(chars) / sum(durs)
    out = []
    for l, (a, b), c, d in zip(L, spans, chars, durs):
        tl = tempo
        if c / d > mean * 1.03:
            tl = round(max(tempo * 0.9, tempo * mean / (c / d)), 4)
        elif c / d < mean * 0.9:
            tl = round(min(tempo * 1.1, tempo * mean * 0.95 / (c / d)), 4)
        x = max(0, a - 0.02)
        cuts = sorted(P.get(l["id"], []))
        fc, lab = [], []
        for k, (s0, e0, tg) in enumerate(cuts):
            fc.append(f"[0:a]atrim={x:.3f}:{s0:.3f},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates={SR}:channel_layouts=mono[a{k}]"); lab.append(f"[a{k}]")
            fc.append(f"anullsrc=r={SR}:cl=mono,atrim=0:{tg * tl:.3f},aformat=sample_fmts=fltp[z{k}]"); lab.append(f"[z{k}]")
            x = e0
        fc.append(f"[0:a]atrim={x:.3f}:{b + 0.03:.3f},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates={SR}:channel_layouts=mono[aE]"); lab.append("[aE]")
        fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1,atempo={tl}[o]")
        p = R / f"s_{l['id']}.wav"
        src_l = OV.get(l["id"]) or full
        run(["ffmpeg", "-y", "-i", src_l, "-filter_complex", ";".join(fc), "-map", "[o]", "-ar", SR, "-ac", "1", p])
        out.append({"id": l["id"], "wav": str(p), "dur": round(dur_of(p), 3), "chars": c, "raw": [round(a, 3), round(b, 3)], "tempo": tl, "pauses": cuts,
                    "override": str(src_l) if src_l is not full else None})
    log(f"atempo 기본 {tempo} · 평균 {mean:.2f}자/초 · " + " ".join(f"{o['id']}:{o['chars'] / o['dur']:.2f}@{o['tempo']}" for o in out))
    return out, tempo, inner


# ── 시간표(판단 주인: 이 함수 한 곳) ────────────────────────────────────
def timeline(S, M, sent: dict) -> dict:
    """sent = {id: dur}. 반환: 줄 시각·원음 조각 시각(opos)·자막 조각 시각·A 컷·B 컷."""
    C = cfg(S)
    Lm = {l["id"]: l for l in S["lines"]}
    H, Bs = h_id(S), b_ids(S)
    lines = {H: [0.0, sent[H]]}
    o0 = sent[H] + C["gap"]
    t, opos, prev_line = o0, [], None
    for p in orig_pieces(S):
        if prev_line is not None and p["line"] != prev_line:
            t += float(Lm[p["line"]].get("gap_before", C["gap_oo"]))
        a, b = p["span"]
        opos.append({**p, "t0": round(t, 3), "t1": round(t + (b - a), 3)})
        t = t + (b - a) + p["pad"] + p["gap"]
        prev_line = p["line"]
    for L in orig_lines(S):
        mine = [p for p in opos if p["line"] == L["id"]]
        lines[L["id"]] = [mine[0]["t0"], mine[-1]["t1"]]
    a_end = round(opos[-1]["t1"] + C["a_end_pad"], 3)
    if C["a_end_pad"]:
        a_end = round(round(a_end * FPS) / FPS, 4)

    def o_time(s, line=None):      # 원본 초 → 완성본 초(원음 조각 안이어야 한다)
        for p in opos:
            if (line is None or p["line"] == line) and p["span"][0] - 0.001 <= s <= p["span"][1] + 0.001:
                return p["t0"] + s - p["span"][0]
        raise StageError(f"원음 자막 시각 {s} 가 어느 조각에도 없다")
    t = a_end + C["gap_ab"]
    for k in Bs:
        lines[k] = [t, t + sent[k]]
        t = t + sent[k] + C["gap"]
    end = lines[Bs[-1]][1] + C["tail"]
    caps = []
    for k in [H] + Bs:
        a, b = lines[k]
        cs = Lm[k]["caps"]
        w = [nchar(c) for c in cs]
        x = a
        for j, (c, ww) in enumerate(zip(cs, w)):
            y = x + (b - a) * ww / sum(w)
            caps.append({"line": k, "j": j, "text": c, "t0": round(x, 3), "t1": round(y, 3), "kind": "나레"})
            x = y
    for L in orig_lines(S):
        if L.get("caps_rel"):
            for c, s0, s1 in L["caps_rel"]:
                caps.append({"line": L["id"], "j": 0, "text": c, "t0": round(o0 + s0, 3), "t1": round(o0 + s1, 3), "kind": "원음"})
        else:
            for c, s0, s1 in L["caps"]:
                caps.append({"line": L["id"], "j": 0, "text": c, "t0": round(o_time(s0, L["id"]), 3), "t1": round(o_time(s1, L["id"]), 3), "kind": "원음"})
    caps.sort(key=lambda c: c["t0"])
    a_ids = {H} | {L["id"] for L in orig_lines(S)}
    last_orig = orig_lines(S)[-1]["id"]
    for i, c in enumerate(caps):          # 자막은 다음 자막(또는 그 구간 끝)까지 — A·B 경계를 넘지 않는다
        seg_end = a_end if c["line"] in a_ids else end
        nxt = caps[i + 1]["t0"] if i + 1 < len(caps) else end
        if c["kind"] == "원음" and c["line"] != last_orig and nxt > c["t1"] + 0.05:
            nxt = c["t1"] + 0.05               # 앞 원음 줄의 끝 자막은 말 끝나고 내린다(다음 원음 줄 앞 빈 사이)
        c["show"] = [c["t0"], round(min(nxt, seg_end) if nxt <= seg_end else seg_end, 3)]
    # A 컷(화면): H 컷들은 [0,o0] 을 weight 비례, O 컷은 원음 이어 붙인 시간 at
    A = M["A"]
    hs = A["H"]
    ws = [float(h.get("weight", 1.0)) for h in hs]
    ash, x = [], 0.0
    for k, (h, w) in enumerate(zip(hs, ws)):
        t1 = o0 if k == len(hs) - 1 else round(x + o0 * w / sum(ws), 3)
        ss = h.get("ss")
        if h.get("reach_orig"):
            ss = round(opos[0]["span"][0] - (t1 - x), 3)
        ash.append({**h, "ss": ss, "t0": round(x, 3), "t1": round(t1, 3), "who": "H"})
        x = t1
    for k, c in enumerate(A["O"]):
        t0 = o0 + float(c["at"])
        t1 = o0 + float(A["O"][k + 1]["at"]) if k + 1 < len(A["O"]) else a_end
        ash.append({**c, "t0": round(t0, 3), "t1": round(t1, 3), "who": "O"})
    for s in ash:
        s["dur"] = round(s["t1"] - s["t0"], 3)
        if s.get("max") is not None and s["dur"] > float(s["max"]) + 1e-6:
            raise StageError(f"A 컷이 원본 샷보다 길다: {s['src']}@{s['ss']} {s['dur']} > max {s['max']}")
    # B 컷: 줄의 첫 컷은 그 줄 시작(B1 은 A 끝)에서, 줄 안 경계는 그 컷 첫 조각 시작에서
    cuts = []
    for i, m in enumerate(M["B"]):
        tok0 = next(c for c in caps if c["line"] == m["line"] and c["j"] == m["toks"][0])
        first_of_line = i == 0 or M["B"][i - 1]["line"] != m["line"]
        t0 = (a_end if i == 0 else lines[m["line"]][0]) if first_of_line else tok0["t0"]
        cuts.append(dict(m, t0=round(t0, 3)))
    for i, c in enumerate(cuts):
        c["t1"] = cuts[i + 1]["t0"] if i + 1 < len(cuts) else round(end, 3)
        c["dur"] = round(c["t1"] - c["t0"], 3)
        c["over"] = round(c["dur"] - c["max"], 3) if c["dur"] > c["max"] else 0.0
    return {"lines": {k: [round(a, 3), round(b, 3)] for k, (a, b) in lines.items()}, "a_end": a_end, "end": round(end, 3), "o0": round(o0, 3),
            "opos": opos, "a_shots": ash, "caps": caps, "cuts": cuts, "h_id": H, "b_ids": Bs}


def crop_vf(c, w, h):
    x, y, cw, ch = c
    return f"crop={cw}:{ch}:{x}:{y},scale={w}:{h}:flags=lanczos,setsar=1,fps={FPS}"


def frame_a(S, dst: Path) -> dict:
    fr = jload(S.get("frame_a") or FRAME_A_DEFAULT)
    next(l for l in fr["layers"] if l.get("role") == "title")["text"] = S["title"]
    next(l for l in fr["layers"] if l.get("role") == "label")["text"] = S["source_label"]
    fr.setdefault("made_from", {})["episode"] = f"얜샷템 하이브리드 잇썸홈판 {S.get('slug', '')} — title·label 글만 바꿈 (tools/calcopy/hybrid/render_itssum.py)"
    jsave(dst, fr)
    return fr


# ── 계획 시트(TTS 전) ───────────────────────────────────────────────────
def plan_sheet(S, M, T, path: Path):
    from PIL import Image, ImageDraw, ImageFont
    from tools.calcopy import narr_video as nv
    font = ImageFont.truetype(nv._font_file("Cafe24Ohsquare"), 22)
    src = Path(M["cand_dir"])
    Lm = {l["id"]: l for l in S["lines"]}
    rows = []
    for a in T["a_shots"]:
        d = a["dur"]
        rows.append((f"A/{a['who']} {a['t0']:.2f}~{a['t1']:.2f} ({d:.2f}s) {Path(a['src']).stem}@{a['ss']}  {(a.get('see') or '')[:30]}", src / a["src"],
                     [a["ss"] + 0.05, a["ss"] + d / 2, a["ss"] + d - 0.05], a["crop"], (300, 300)))
    for c in T["cuts"]:
        txt = " ".join(Lm[c["line"]]["caps"][c["toks"][0]:c["toks"][1] + 1])
        rows.append((f"{c['line']} {c['t0']:.2f}~{c['t1']:.2f} ({c['dur']:.2f}s max {c['max']}) {Path(c['src']).stem}@{c['ss']}  「{txt}」",
                     src / c["src"], [c["ss"] + 0.05, c["ss"] + c["dur"] / 2, c["ss"] + c["dur"] - 0.05], c["crop"], (169, 300)))
    W_, H_ = 1200, 340
    sheet = Image.new("RGB", (W_, H_ * len(rows)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for r, (label, video, ts, crop, size) in enumerate(rows):
        d.text((8, r * H_ + 6), label, font=font, fill=(255, 230, 0))
        for k, t in enumerate(ts):
            sheet.paste(frame_png(video, t, crop, size), (8 + k * (size[0] + 10), r * H_ + 36))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=85)
    return path


# ── 렌더 ────────────────────────────────────────────────────────────────
def render_a(S, M, T, fr, R: Path):
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    from tools.calcopy import narr_video as nv
    src = Path(M["cand_dir"])
    n = round(T["a_end"] * FPS)
    parts = R / "a_parts"
    shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst = []
    for k, c in enumerate(T["a_shots"]):
        nf = round(c["t1"] * FPS) - round(c["t0"] * FPS)
        c["frames"] = nf
        p = parts / f"a{k:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{c['ss']:.3f}", "-i", src / c["src"], "-an", "-vf", crop_vf(c["crop"], 1080, 1080), "-frames:v", nf,
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", p])
        lst.append(f"file '{p.as_posix()}'")
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    mat = R / "a_mat.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", mat])
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": round(n / FPS, 3), "narration": "", "caption_lines": [], "role": "hook",
           "primary": {"video_id": "s0", "start": 0.0, "end": round(n / FPS, 3)}}]
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(fr))
    seg = R / "a_seg.mp4"
    shutil.rmtree(R / "work_a", ignore_errors=True)
    scene_style.compose(str(mat), tl, snap, str(seg), R / "work_a", {"text": S["title"]})
    cap = next(l for l in fr["layers"] if l.get("kind") == "text" and l.get("role") == "caption")
    a_ids = {T["h_id"]} | {L["id"] for L in orig_lines(S)}
    ins, fc, last = [], "", "0:v"
    caps = [c for c in T["caps"] if c["line"] in a_ids]
    for k, c in enumerate(caps):
        png = nv.emph_png(c["text"], cap, cap["rgb"] if c["kind"] == "나레" else [255, 255, 255], R / f"a_cap{k}.png", dy=0)
        ins += ["-loop", "1", "-i", png]
        a, b = c["show"]
        fc += f"{';' if fc else ''}[{last}][{k + 1}:v]overlay=0:0:enable='between(t,{a:.3f},{b - 0.001:.3f})'[e{k}]"
        last = f"e{k}"
    out = R / "a_final.mp4"
    run(["ffmpeg", "-y", "-i", seg, *ins, "-filter_complex", fc + f";[{last}]format=yuv420p[v]", "-map", "[v]", "-frames:v", n,
         "-r", FPS, "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", out])
    return out, n


def render_b(S, M, T, R: Path):
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    from tools.calcopy.engine import preset_save as P
    src = Path(M["cand_dir"])
    parts = R / "b_parts"
    shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst = []
    for k, c in enumerate(T["cuts"]):
        n = round(c["t1"] * FPS) - round(c["t0"] * FPS)
        c["frames"] = n
        p = parts / f"p{k:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{c['ss']:.3f}", "-i", src / c["src"], "-an", "-vf", crop_vf(c["crop"], 1080, 1920), "-frames:v", n,
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", p])
        lst.append(f"file '{p.as_posix()}'")
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    mat = R / "b_mat.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", mat])
    pre, Mf = P.load(Path(cfg(S)["preset_b"]))
    F = P.apply(pre, None, None, Mf["variable_stats"], None, Mf["rules"])
    jsave(R / "frame_b.json", F)
    b0 = T["a_end"]
    nb = sum(c["frames"] for c in T["cuts"])
    bcaps = [c for c in T["caps"] if c["line"] in T["b_ids"]]
    tl = []
    for bi, c in enumerate(bcaps):
        a, b = c["show"]
        if bi == 0:
            a = b0
        a2, b2 = round(a - b0, 3), round(min(b - b0, nb / FPS), 3)
        tl.append({"beat_idx": bi, "t0": a2, "dur": round(b2 - a2, 3), "narration": c["text"], "caption_lines": [c["text"]],
                   "role": "hook" if bi == 0 else "body", "primary": {"video_id": "s0", "start": a2, "end": b2}})
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(F))
    seg = R / "b_seg.mp4"
    shutil.rmtree(R / "work_b", ignore_errors=True)
    scene_style.compose(str(mat), tl, snap, str(seg), R / "work_b", {"text": ""})
    return seg, nb


def _mute_expr(p: dict) -> str:
    """원음 조각 안 남의 소리 구간(대본 mute, 원본 초)을 끈다 — 20ms 경사. 조각 시작 기준 초."""
    f = ""
    for a, b, *_ in p.get("mute") or []:
        a, b = a - p["span"][0], b - p["span"][0]
        f += f",volume='if(between(t,{a:.3f},{b:.3f}),max(0,1-min(t-{a:.3f},{b:.3f}-t)/0.02),1)':eval=frame"
    return f


def audio(S, M, T, sent, R: Path):
    """나레(H·B) + 원음 조각(묶음: gap 에서 끊음) + BGM → mix.wav (target_lufs)."""
    C = cfg(S)
    src = Path(M["cand_dir"])
    fd = C["orig_fade"]
    groups, cur = [], []
    for p in T["opos"]:
        cur.append(p)
        if p["gap"] > 0 or p is T["opos"][-1]:
            groups.append(cur); cur = []
    o_wavs = []
    for gi, g in enumerate(groups):
        pcs = []
        for k, p in enumerate(g):
            a, b = p["span"]
            w = R / f"o_{gi}_{k}.wav"
            run(["ffmpeg", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src / p["src"], "-vn", "-ac", "1", "-ar", SR,
                 "-af", f"{C['orig_af']}{_mute_expr(p)},afade=t=in:d={fd},afade=t=out:st={b - a - fd:.3f}:d={fd}", w])
            pcs.append(w)
            if p["pad"] > 0:
                z = R / f"o_{gi}_{k}_pad.wav"
                run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{p['pad']:.3f}", z])
                pcs.append(z)
        ow = R / f"o_raw{gi}.wav"
        run(["ffmpeg", "-y", *[x for p_ in pcs for x in ("-i", p_)], "-filter_complex",
             "".join(f"[{i}:a]" for i in range(len(pcs))) + f"concat=n={len(pcs)}:v=0:a=1[o]", "-map", "[o]", "-ar", SR, ow])
        o_wavs.append((ow, g[0]["t0"]))
    narr_cat = R / "narr_only.wav"
    (R / "narr_list.txt").write_text("".join(f"file '{Path(s['wav']).as_posix()}'\n" for s in sent), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", R / "narr_list.txt", "-c", "copy", narr_cat])
    o_cat = R / "o_raw.wav"
    run(["ffmpeg", "-y", *[x for w, _ in o_wavs for x in ("-i", w)], "-filter_complex",
         "".join(f"[{i}:a]" for i in range(len(o_wavs))) + f"concat=n={len(o_wavs)}:v=0:a=1[o]", "-map", "[o]", "-ar", SR, o_cat])
    nI, _ = lufs(narr_cat)
    oI, _ = lufs(o_cat)
    og = round(nI - oI, 2)                      # 원음 크기 = 나레 크기(같은 LUFS)
    pieces = [(s["wav"], T["lines"][s["id"]][0], 0.0) for s in sent] + [(str(w), t0, og) for w, t0 in o_wavs]
    ins, fc = [], []
    for k, (p, t, g) in enumerate(pieces):
        ins += ["-i", p]
        fc.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,volume={g}dB,adelay={int(round(t * 1000))}[p{k}]")
    fc.append("".join(f"[p{k}]" for k in range(len(pieces))) + f"amix=inputs={len(pieces)}:normalize=0,apad,atrim=0:{T['end']:.3f}[n]")
    voice = R / "voice.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[n]", "-ar", SR, voice])
    BGM = ROOT / C["bgm_dir"] / f"{S['bgm']['id']}.mp3"
    bI, _ = lufs(BGM)
    g = round((nI - S["bgm"]["db_below_voice"]) - bI, 2)
    k = 10 ** (S["bgm"]["duck_orig_db"] / 20)
    a = T["opos"][0]["t0"]; b = T["opos"][-1]["t1"]      # 원음 창 전체(조각 사이 쉼 포함) 덕킹 0.15초 경사
    duck = f"(1-{1 - k:.4f}*clip(min((t-{a - 0.15:.3f})/0.15,({b + 0.15:.3f}-t)/0.15),0,1))"
    end = T["end"]
    mix_raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", "-i", voice, "-stream_loop", "-1", "-i", BGM, "-filter_complex",
         f"[1:a]aresample={SR},aformat=channel_layouts=mono,atrim=0:{end:.3f},asetpts=PTS-STARTPTS,volume={g}dB,volume='{duck}':eval=frame,"
         f"afade=t=out:st={end - 0.6:.3f}:d=0.6[b];[0:a][b]amix=inputs=2:normalize=0:duration=first[o]", "-map", "[o]", "-ar", SR, mix_raw])
    mix = R / "mix.wav"
    gain, res = 16.0, None
    for _ in range(14):
        run(["ffmpeg", "-y", "-i", mix_raw, "-af", f"dynaudnorm=f=100:g=9:p=0.9:m=20,acompressor=threshold=0.125:ratio=8:attack=1:release=40,"
             f"volume={gain:.2f}dB,alimiter=limit={10 ** (C['tp'] / 20):.4f}:level=false:attack=1:release=30", "-ar", SR, mix])
        res = lufs(mix)
        if res[0] >= C["target_lufs"] - 0.4 or gain >= 40:
            break
        gain += 2.0
    return mix, {"narr_lufs": nI, "orig_raw_lufs": oI, "orig_gain": og, "bgm_gain": g, "master_gain": gain, "mix": res, "orig_groups": len(groups)}


def render(doc: Path, work: Path, plan_only: bool = False, desktop: Path | None = None, log=print) -> dict:
    """doc = 대본.json·재료.json 폴더(결과 문서도 여기), work = 렌더 작업 폴더(render/ 아래 중간물·final.mp4)."""
    doc, work = Path(doc), Path(work)
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    R = work / "render"
    R.mkdir(parents=True, exist_ok=True)
    fr = frame_a(S, R / "frame_A.json")
    shutil.copy(R / "frame_A.json", doc / "frame_A.json")
    if plan_only:
        est = {l["id"]: round(nchar(l["tts"]) / S["cps_target"], 3) for l in tts_lines(S)}
        T = timeline(S, M, est)
        jsave(doc / "plan/계획_시간표.json", T)
        plan_sheet(S, M, T, doc / "plan/계획_시트.jpg")
        for c in T["cuts"]:
            log(f"  {c['line']} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c['max']} over {c['over']} {c['src']}@{c['ss']}")
        log(f"A 끝 {T['a_end']} 전체 {T['end']} → {doc / 'plan/계획_시트.jpg'}")
        return {"plan": str(doc / "plan/계획_시트.jpg"), "timeline": T}
    full = tts_once(S, R, log)
    sent, tempo, inner = make_sentences(S, full, R, log)
    T = timeline(S, M, {s["id"]: s["dur"] for s in sent})
    over = [c for c in T["cuts"] if c["over"] > 0]
    if over:
        raise StageError("컷이 원본 샷보다 길다: " + str([(c["line"], c["src"], c["dur"], c["max"]) for c in over]))
    a_mp4, na = render_a(S, M, T, fr, R)
    b_mp4, nb = render_b(S, M, T, R)
    (R / "ab.txt").write_text(f"file '{a_mp4.as_posix()}'\nfile '{b_mp4.as_posix()}'\n", encoding="utf-8")
    vid = R / "video.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", R / "ab.txt", "-an", "-r", FPS, "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", vid])
    T["end"] = round((na + nb) / FPS, 3)
    mix, A = audio(S, M, T, sent, R)
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    info = {"made_by": "tools/calcopy/hybrid/render_itssum.py", "version": "잇썸홈판", "tempo": tempo, "sentences": sent, "inner_silences": inner,
            "timeline": T, "audio": A, "final": str(final), "final_dur": dur_of(final), "final_lufs": lufs(final),
            "cuts_flat": [{"src": c["src"], "ss": c["ss"], "t0": c["t0"], "t1": c["t1"], "dur": c["dur"], "seg": "B", "line": c["line"], "see": c.get("see", "")} for c in T["cuts"]]
            + [{"src": a["src"], "ss": a["ss"], "t0": a["t0"], "t1": a["t1"], "dur": a["dur"], "seg": "A", "line": a["who"], "see": a.get("see", "")} for a in T["a_shots"]]}
    jsave(R / "render_info.json", info)
    log(f"final {final} {info['final_dur']:.2f}초 LUFS/TP {info['final_lufs']} {json.dumps(A, ensure_ascii=False)}")
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, doc / "final_sheet_1s.jpg")
    if desktop:
        from tools.calcopy.hybrid.common import md5
        Path(desktop).parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy(final, desktop)
            info["desktop"] = {"path": str(desktop), "md5_same": md5(final) == md5(desktop)}
        except PermissionError as e:
            info["desktop"] = {"path": str(desktop), "error": str(e)}
        jsave(R / "render_info.json", info)
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
