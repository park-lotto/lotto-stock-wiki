# -*- coding: utf-8 -*-
"""샥탬스토리(벤치 해외쇼츠 샤크탱크) 채널 렌더러 한 벌 — 나레↔원음 N회 교대 + 원음 번역 자막 + 원음 밑 B롤 컷 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/shark/render.py <편 doc 폴더> <작업 폴더> [--plan] [--tts-only] [--confirm-tts] [--cps 8.4]

  --plan        TTS 없이 나레 말속도 추정(기본 8.4자/초)으로 줄표·컷표·자막표만 → <작업>/plan/render_info.json·컷표.md
  --tts-only    TTS(1회, 이미 있으면 재사용) + 실제 줄 시각까지만 → <작업>/render/render_info.json
  --preview     TTS 없이 --plan 시각 그대로 끝까지 렌더(나레 자리 = 삐 소리) → <작업>/preview/final.mp4 — 컷·자막·원음·크롭 눈 확인용(비용 0)
  (없음)        렌더 끝까지 → <작업>/render/final.mp4 (+ check.py 로 B표)
  --confirm-tts 타입캐스트를 **처음** 부를 때만 필요(페이블 OK 뒤 1회 — 비용). 이미 narr_raw.mp3 가 있으면 다시 안 부른다.
  --tts-from    옛 렌더 폴더의 narr_raw.* 를 복사해 재사용(새 엔진으로 다시 렌더할 때 — 비용 0)

선례 channel/itemhome/1편_안유진로션/make_render.py(편 전용)를 채널 한 벌로. 엔진은 부르기만 한다:
  TTS = engine/tts_pause.synth(통째 1회, 성우 속도 voice_presets) → atempo(상한 1.27) → tts_pause.shape(쉼표 0.22·마침표 0.30)
  화면 = narr_video.build(틀 한 장·자막 페이지 1개 × shots[0].cuts = 컷 전부, 판단 주인 shot_pieces) — 자막은 build 에서 안 그림
  원음 = hottem_audio.add_source_bed(줄 단위 원음 시간표, gap_gain = 원음 창 올림) — 원음 창엔 나레 없음(J컷 꼬리만 덕킹)
  자막·꾸밈 = narr_video.emph_png(나레 꼴 / 원음 꼴 두 층)·overlay_png 을 완성본 좌표로 얹음
  BGM = bgm_lib 곡, 원음 창에서 덕킹 → 목표 −14.0 LUFS · 트루피크 ≤ −1.5 dBTP(R5 사장님 10-19 '음량이 너무커', 값 주인 rules.json loudness)

판단 주인(한 함수씩) — 렌더·검사(check.py)는 render_info.json 의 같은 값을 읽는다:
  줄 시각   line_times()    · 컷 시각   cut_times()    · 자막 시각  caption_times()    · 원음 소리 시간표  audio_pieces()
입력 꼴 두 가지를 load_doc() 한 곳에서 같은 꼴로 바꾼다:
  1편꼴 lines[{id, kind:tts|orig, tts, caps[], span, en}] · shots[{line, src, ss, dur, src_crop, mute, audio_span}] · 재료.window
  3편꼴 lines[{id, kind:나레|원음, text, tts, orig_span, orig_en}](caps 없음 → 엔진 chunk_sentence) · shots[{…, audio_ss, audio_dur(J컷)}]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid.common import SR, StageError, dur_of, jload, jsave, lufs, nchar, run  # noqa: E402

from tools.calcopy.shark import fx as FX  # noqa: E402  — 자막·꾸밈·번쩍·효과음 그림/자리 주인(값은 shark/rules.json)

FALLBACK_PRESET = ROOT / "channel/mantem/preset/얜샷템"
ENGINE = "shark-v2 2026-10-19 (R3 물건 원·R4 적중 검사·고급 모양·R5 −14 LUFS)"   # render_info 표식 — 하이브리드가 앞 렌더 판을 이걸로 가린다
LOUD = FX.R()["loudness"]
DEF = {
    "gap": 0.08,            # 줄과 줄 사이(원음 뒤·원음 앞) — 1편 대본 t_final 간격
    "end_pad": 0.6,         # 끝 줄 뒤 여유
    "cps_plan": 8.4,        # --plan 나레 말속도 추정(자/초, 공백·부호 뺀 글자)
    "comma_pause": 0.22, "period_pause": 0.30,   # tts_pause.PAUSE 와 같은 값(추정용)
    "cap_chunk": 10,        # caps 가 없는 줄의 자막 조각 n(엔진 chunk_sentence, 상한 n+3)
    "tempo_max": 1.27, "tempo_min": 0.85,
    "narr_lufs": -15.0,     # narr_video 나레 목표
    "orig_rel_db": 0.0,     # 원음 창 크기 = 나레 LUFS + 이것
    "orig_gain_clamp": [-6.0, 18.0],
    "bgm": "sweets", "bgm_lufs": -24.5, "duck_db": -10.0,
    "target_lufs": LOUD["target_lufs"], "peak_max": LOUD["true_peak_max"],
}
FX_KINDS = FX.KINDS


def log(*a):
    print(*a, flush=True)


# ── 입력: 편 폴더 → 한 꼴 ─────────────────────────────────────────────
def _kind(l) -> str:
    k = l.get("kind")
    if k in ("tts", "나레"):
        return "N"
    if k in ("orig", "원음"):
        return "O"
    raise StageError(f"줄 {l.get('id')} kind '{k}' 모름(tts|orig|나레|원음)")


def load_doc(doc: Path) -> dict:
    S = jload(doc / "대본.json")
    M = jload(doc / "재료.json")
    F = S["final"]
    C = {**DEF, **(S.get("render") or {})}
    lines = []
    for l in F["lines"]:
        k = _kind(l)
        x = {"id": l["id"], "kind": k, "fx": l.get("fx")}
        if k == "N":
            x["tts"] = l.get("tts") or l.get("text")
            x["show"] = l.get("text") or x["tts"]
        else:
            sp = l.get("span") or l.get("orig_span")
            if not sp:
                raise StageError(f"원음 줄 {l['id']} 에 span/orig_span 없음")
            x["span"] = [float(sp[0]), float(sp[1])]
            x["en"] = l.get("en") or l.get("orig_en")
            x["show"] = l.get("text") or " ".join(l.get("caps") or [])
            x["src"] = l.get("src")
            if l.get("cap_at"):           # 원음 자막 조각 시작(원본 초 — 받아쓰기 낱말 시각) — 있으면 이것이 이긴다
                x["cap_at"] = [float(v) for v in l["cap_at"]]
        if l.get("caps"):
            x["caps"], x["caps_from"] = list(l["caps"]), "대본 caps"
        else:
            from tools.calcopy import narr_video as nv
            x["caps"], x["caps_from"] = nv.chunk_sentence(x["show"], C["cap_chunk"]), f"chunk_sentence(n={C['cap_chunk']})"
        lines.append(x)
    ids = [l["id"] for l in lines]
    if len(set(ids)) != len(ids):
        raise StageError(f"줄 id 중복 {ids}")
    shots = []
    for s in M["shots"]:
        if s["line"] not in ids:
            raise StageError(f"재료 컷 {s.get('i')} 의 줄 {s['line']} 이 대본에 없음")
        a = {"i": s.get("i", len(shots)), "line": s["line"], "src": s["src"], "ss": float(s["ss"]), "dur": float(s["dur"]),
             "src_crop": s.get("src_crop"), "mute": bool(s.get("mute")), "see": s.get("ours") or s.get("why", ""),
             **{k: s[k] for k in SHOT_KEYS if s.get(k) is not None}, "cover": bool(s.get("cover"))}
        if Path(s["src"]).suffix.lower() in STILL and not s.get("mute") and not (s.get("cover") and s.get("audio_src")):
            # 그림 컷 = 소리 없음. 단 cover(화면만 다른 장면, 소리는 원음) 이면 audio_src(원음 파일)·audio_ss 로 원음을 쓴다(10-20 엔진 요청)
            raise StageError(f"재료 컷 {s.get('i')}: 그림 파일({s['src']})은 소리가 없다 — mute: true, 또는 cover: true + audio_src·audio_ss(원음)")
        if not s.get("mute"):
            a["audio_src"] = s.get("audio_src") or s["src"]
            if s.get("audio_ss") is not None:
                a["audio_ss"] = float(s["audio_ss"])
                if s.get("audio_dur") is not None:
                    a["audio_dur"] = float(s["audio_dur"])
            elif s.get("audio_span"):
                a["audio_ss"], a["audio_dur"] = float(s["audio_span"][0]), float(s["audio_span"][1]) - float(s["audio_span"][0])
        shots.append(a)
    for l in lines:
        if not any(s["line"] == l["id"] for s in shots):
            raise StageError(f"줄 {l['id']} 에 재료 컷이 없음")
    win = M.get("window")
    bw = (S.get("bench") or {}).get("window")
    box = next((s["box"] for s in M["shots"] if s.get("box")), None)
    if win and len(win) == 2:          # 1편꼴 [가로, 세로] / 4·6편꼴 [x, y, w, h] — 둘 다(프리셋이 있으면 창은 프리셋 것)
        win = [0, 434, win[0], win[1]]
    window = bw or box or win
    T = S.get("titles") or {}
    title = T.get("hook") or "\n".join(x for x in (T.get("line1"), T.get("line2")) if x)
    voice = S.get("voice") or (F.get("voice") if isinstance(F.get("voice"), dict) else None)
    return {"S": S, "M": M, "C": C, "lines": lines, "shots": shots, "cand_dir": Path(M["cand_dir"]), "window": window, "title": title,
            "voice": voice, "cps_target": F.get("cps_target") or F.get("narr_cps_assumed"), "bench": S.get("bench") or {},
            "effects": M.get("effects") or [], "sources": M.get("sources") or {},
            "fx_notes": [f"{e.get('at')}: {e.get('fx')}" for e in S.get("effects_record") or []]
                        + [f"{l['id']}: {l['fx']}" for l in lines if l.get("fx")]
                        + [f"컷{s.get('i')}({s['line']}): {s['fx']}" for s in M["shots"] if s.get("fx")]}


SHOT_KEYS = ("ar", "fit", "move", "loop")   # 컷 덮어쓰기(그림 움직임·세로/가로 비율·채우기·짧은 영상 되풀이) — 그리기는 narr_video.shot_clip 한 곳.
#   loop: true → narr_video 의 kind "짤"(재료 shots[].kind 는 이 채널에서 줄 종류 '원음/나레' 라 그대로 넘기지 않는다)
STILL = (".png", ".jpg", ".jpeg")


def check_sources(D) -> list[str]:
    """소스 파일·원음 트랙 확인. 재료 sources 에 '140-7' 같은 오디오 형식 번호가 적혀 있으면 info.json format_id 에 그 번호가 있어야 한다
    (3편 ME64bRiQi24 = 더빙 트랙 섞임 → 영어 원음 140-7 만, 근거.md 10줄)."""
    notes = []
    for f in sorted({s["src"] for s in D["shots"]} | {s["audio_src"] for s in D["shots"] if s.get("audio_src")}):
        p = D["cand_dir"] / f
        if not p.exists():
            raise StageError(f"소스 없음 {p}")
        stem = Path(f).stem
        want = re.findall(r"\b(\d{3}-\d+)\b", json.dumps(D["sources"].get(stem) or {}, ensure_ascii=False))
        info = p.with_suffix(".info.json")
        if want:
            if not info.exists():
                raise StageError(f"{f}: 원음 트랙 {want} 지정인데 info.json 없음 — 받은 트랙을 확인 못 함")
            fid = jload(info).get("format_id", "")
            if not all(w in fid.split("+") for w in want):
                raise StageError(f"{f}: 원음 트랙 {want} 이어야 하는데 받은 것 {fid} (더빙 트랙일 수 있음)")
            notes.append(f"{f}: 원음 트랙 {fid} ⊇ {want} 확인")
    return notes


# ── 나레 재기: 줄마다 말 시작·끝(나레 파일 시각) ─────────────────────────────
def _end_punct(t: str) -> str:
    t = t.strip()
    return t if re.search(r"[.?!]$", t) else t + "."


def narr_plan(D) -> dict:
    """--plan: 말속도 추정 cps 로 나레 줄마다 [start, end] 를 가상 나레 파일 시각으로(줄 사이 마침표 쉼)."""
    C, t, out = D["C"], 0.0, []
    for l in [x for x in D["lines"] if x["kind"] == "N"]:
        d = nchar(l["tts"]) / C["cps_plan"] + C["comma_pause"] * l["tts"].count(",")
        out.append({"id": l["id"], "start": round(t, 3), "end": round(t + d, 3)})
        t += d + C["period_pause"]
    return {"lines": out, "wav": None, "how": f"추정 {C['cps_plan']}자/초 + 쉼표 {C['comma_pause']}초"}


def narr_beep(NM, R: Path) -> dict:
    """--preview: 추정 시각의 나레 자리에 삐 소리(440Hz)를 넣은 가짜 나레 파일."""
    on = "+".join(f"between(t,{x['start']:.3f},{x['end']:.3f})" for x in NM["lines"])
    end = NM["lines"][-1]["end"] + 0.5
    out = R / "narr_beep.wav"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc='0.25*sin(2*PI*440*t)*({on})':s={SR}:d={end:.3f}", "-ac", "1", out])
    return {**NM, "wav": str(out), "how": NM["how"] + " · 나레 자리 삐 소리(미리보기)"}


def real_tail_ends(wav: Path, al: dict, floor_db=-40.0, win=0.01) -> list[dict]:
    """쉼표·마침표 앞 글자의 끝을 실제 소리 끝으로 늦춘다(al 을 고친다). 타입캐스트 정렬은 말 꼬리를 일찍 끊는다 —
    10-19 샥탬 10편 '닦인다고.' 정렬 8.119초, 실제 '고' 는 8.34초까지(−22~−32dB) → 쉼이 0.32초로 보여 shape 가 안 늘리고
    실제 무음 0.08초, 줄 끝(+0.10)이 꼬리를 자른다. 정렬 끝부터 10ms 창 RMS 가 floor 아래로 처음 떨어지는 곳까지 늘린다(뒤 글자 시작 −0.05 넘지 않음)."""
    import subprocess
    import numpy as np
    from tools.calcopy.engine import tts_pause as TP
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                     capture_output=True, check=True).stdout, np.float32)
    sr = int(SR); n = int(win * sr); e = al["character_end_times_seconds"]; ch = al["characters"]
    fixed = []
    for kind, a, b in TP.pause_slots(al):
        j = next(i for i in range(len(ch) - 1, -1, -1) if abs(float(e[i]) - a) < 1e-9)
        t = a
        while t + win < b - 0.05:
            w = x[int(t * sr): int(t * sr) + n]
            if len(w) == 0 or 20 * np.log10(float(np.sqrt(np.mean(w * w))) + 1e-9) < floor_db:
                break
            t += win
        if t - a >= 0.02:
            e[j] = t; fixed.append({"at": round(a, 3), "real_end": round(t, 3)})
    return fixed


def narr_tts(D, R: Path, confirm: bool) -> dict:
    """나레 줄만 TTS 1회 통째(엔진 tts_pause.synth) → atempo(목표 cps, 0.85~1.27) → tts_pause.shape → 줄마다 [start,end](정렬 글자 시각을 shape 이음매로 옮김).
    옮긴 줄 머리가 실제 말 구간 시작과 0.12초 넘게 다르면 멈춘다(조용히 어긋나지 않게)."""
    from tools.calcopy import narr_video as nv
    from tools.calcopy.engine import tts_pause as TP
    C = D["C"]
    NL = [x for x in D["lines"] if x["kind"] == "N"]
    parts = [_end_punct(l["tts"]) for l in NL]
    text = " ".join(parts)
    raw, alf, meta = R / "narr_raw.mp3", R / "narr_raw.align.json", R / "narr_raw.meta.json"
    voice = D["voice"] or {}
    vid = voice.get("voice_id") or "tc_68257f68bc6e3c161ab5078d"   # tts_pause 기본(필재) — 대본 voice 가 없을 때
    if not raw.exists():
        if not confirm:
            raise StageError("TTS 를 처음 부르려면 --confirm-tts (페이블 OK 뒤 1회 — 비용)")
        align, sp = TP.synth(text, str(raw), vid, voice.get("emotion"), voice.get("speed"))
        if not align:
            raise StageError("타임스탬프가 안 왔다 — 줄 시각을 정렬로 못 잼(소리 짐작으로 되돌아가지 않는다)")
        jsave(alf, align)
        jsave(meta, {"text": text, "voice_id": vid, "speed": sp, "emotion": voice.get("emotion")})
        log(f"TTS 1회: {raw} {dur_of(raw):.2f}초")
    align, m = jload(alf), jload(meta)
    if m["text"] != text:
        raise StageError("narr_raw.mp3 를 만든 글이 지금 대본과 다르다 — 지우고 다시(비용) 또는 대본 확인")
    # 글자 ↔ 정렬 글자(공백 무시 순서 대조)
    ch = align["characters"]
    pos, j = [], 0
    for i, c in enumerate(text):
        if c.isspace():
            pos.append(None); continue
        while j < len(ch) and ch[j].isspace():
            j += 1
        if j >= len(ch) or ch[j] != c:
            raise StageError(f"정렬 글자가 대본과 다름(글 {i} '{c}' vs 정렬 {j} '{ch[j] if j < len(ch) else '끝'}')")
        pos.append(j); j += 1
    # atempo
    segs0, _ = nv.speech_segments(str(raw), "-40dB", 0.1)
    rate = nchar(text) / max(sum(b - a for a, b in segs0), 0.1)
    tgt = D["cps_target"] or rate
    tempo = round(min(C["tempo_max"], max(C["tempo_min"], tgt / rate)), 3)
    tw = R / "narr_tempo.wav"
    run(["ffmpeg", "-y", "-i", raw, "-af", f"atempo={tempo}", "-ar", SR, "-ac", "1", tw])
    al = {"characters": ch, "character_start_times_seconds": [x / tempo for x in align["character_start_times_seconds"]],
          "character_end_times_seconds": [x / tempo for x in align["character_end_times_seconds"]]}
    tail_fix = real_tail_ends(tw, al)
    plog = TP.shape(str(tw), al, str(R / "narr_shaped.mp3"))
    narr = R / "narr.wav"
    run(["ffmpeg", "-y", "-i", R / "narr_shaped.mp3", "-ar", SR, "-ac", "1", narr])
    # shape 이 처리한 쉼(log 순서) ↔ pause_slots
    done, k = [], 0
    for kind, a, b in TP.pause_slots(al):
        if k < len(plog) and abs(plog[k]["at"] - round(a, 2)) < 0.006:
            done.append((b, plog[k]["now"] - plog[k]["was"])); k += 1
    if k != len(plog):
        raise StageError("shape 기록과 쉼 자리를 못 맞춤")

    def moved(t):   # 원래(atempo 뒤) 시각 → shape 뒤 시각: 지난 쉼의 길이 변화 + 이음매 겹침(쉼 하나에 2번, XF_SEC)
        n = [d for b, d in done if b <= t + 1e-6]
        return t + sum(n) - TP.XF_SEC * 2 * len(n)
    st, en = al["character_start_times_seconds"], al["character_end_times_seconds"]
    out, off = [], 0
    for l, p in zip(NL, parts):
        idx = [pos[off + i] for i, c in enumerate(p) if pos[off + i] is not None and re.match(r"[0-9A-Za-z가-힣]", c)]
        off += len(p) + 1
        out.append({"id": l["id"], "start": round(moved(st[idx[0]]), 3), "end": round(moved(en[idx[-1]]), 3)})
    segs, _ = nv.speech_segments(str(narr), "-40dB", 0.06)
    for o in out:
        near = min((a for a, _ in segs), key=lambda a: abs(a - o["start"]))
        if abs(near - o["start"]) > 0.12:
            raise StageError(f"줄 {o['id']} 머리: 정렬 {o['start']}초 근처(0.12)에 말 시작 없음(가장 가까운 {near:.3f}) — 정렬·쉼 확인")
        o["start"] = round(near, 3) if near <= o["start"] + 0.05 else o["start"]
    sp = sum(o["end"] - o["start"] for o in out)
    return {"lines": out, "wav": str(narr), "tempo": tempo, "cps_out": round(nchar(text) / max(sp, 0.1), 2),
            "line_cps": {o["id"]: round(nchar(l["tts"]) / max(o["end"] - o["start"], 0.1), 2) for o, l in zip(out, NL)}, "raw_cps": round(rate, 2), "target_cps": tgt, "voice": m,
            "pauses": plog, "tail_fix": tail_fix, "how": "타입캐스트 정렬(꼬리 = 실제 소리 끝) + tts_pause.shape"}


# ── 판단 주인 ─────────────────────────────────────────────────────────
def line_times(D, NM) -> dict:
    """(판단 주인: 줄 시각) 대본 순서대로 놓는다. 원음 줄 = 원본 span 길이 그대로(나레 없음), 나레 줄 = 말 시작이 줄 시작.
    줄 끝(t1) = 다음 줄 시작. 나레→나레는 TTS 의 자연 쉼(다음 줄 말 시작 − 이 줄 말 시작) 그대로, 원음 앞뒤는 gap.
    반환 lines[{id,kind,t0,t1, narr:[nar_start,nar_end](나레 파일 시각) | span}], dur."""
    C = D["C"]
    nm = {x["id"]: x for x in NM["lines"]}
    L, t = [], 0.0
    seq = D["lines"]
    for k, l in enumerate(seq):
        nxt = seq[k + 1] if k + 1 < len(seq) else None
        x = {"id": l["id"], "kind": l["kind"], "t0": round(t, 3)}
        if l["kind"] == "O":
            d = l["span"][1] - l["span"][0]
            x["span"] = l["span"]
            x["speak"] = [x["t0"], round(t + d, 3)]
            t += d + C["gap"]
        else:
            m = nm[l["id"]]
            x["narr"] = [m["start"], m["end"]]
            x["speak"] = [x["t0"], round(t + m["end"] - m["start"], 3)]
            if nxt is not None and nxt["kind"] == "N":
                t += nm[nxt["id"]]["start"] - m["start"]
            else:
                t += (m["end"] - m["start"]) + (C["gap"] if nxt is not None else C["end_pad"])
        L.append(x)
    for a, b in zip(L, L[1:]):
        a["t1"] = b["t0"]
    L[-1]["t1"] = round(t, 3)
    return {"lines": L, "dur": round(t, 3)}


def cut_times(D, LT) -> list[dict]:
    """(판단 주인: 컷 시각) 줄 창 [t0,t1) 을 그 줄의 재료 컷으로 채운다.
    원음 줄 = 재료 시각 그대로(컷 길이 그대로 이어 붙이고 끝 컷만 줄 끝까지, 넘치면 자름 → 입 모양·소리 시각 유지).
    나레 줄 = 재료 컷 길이 비례로 늘이고 줄임(나레 실제 길이에 맞춤). sync = 화면 소스=소리 소스인 원음 컷의 (화면초 − 그때 소리초)."""
    by = {}
    for s in D["shots"]:
        by.setdefault(s["line"], []).append(s)
    LD = {l["id"]: l for l in D["lines"]}
    out = []
    for x in LT["lines"]:
        sh, a, b = by[x["id"]], x["t0"], x["t1"]
        if x["kind"] == "O":
            t, bounds = a, []
            for k, s in enumerate(sh):
                e = b if k == len(sh) - 1 else min(b, t + s["dur"])
                if e - t > 1e-3:
                    bounds.append((s, t, e))
                t = e
        else:
            tot = sum(s["dur"] for s in sh)
            bounds, t = [], a
            for s in sh:
                e = t + (b - a) * s["dur"] / tot
                bounds.append((s, t, e)); t = e
        prev = None
        for s, t0, t1 in bounds:
            ss = s["ss"]
            # 나레 줄을 늘이면 같은 소스 다음 컷과 겹친다(되감김) → 무음 컷은 앞 컷 끝으로 당겨 잇는다(선례 make_render 와 같은 규칙, 5초 안)
            if x["kind"] == "N" and prev and prev["src"] == s["src"] and s["mute"]:
                pend = prev["ss"] + prev["dur"]
                if ss < pend - 1e-3 and pend - ss < 5:
                    ss = round(pend, 3)
            c = {"i": s["i"], "line": x["id"], "kind": x["kind"], "src": s["src"], "ss": round(ss, 3), "src_crop": s["src_crop"],
                 "t0": round(t0, 3), "t1": round(t1, 3), "dur": round(t1 - t0, 3), "plan_dur": s["dur"], "see": s["see"],
                 **{k: s[k] for k in SHOT_KEYS if k in s}}
            if ss != s["ss"]:
                c["ss_moved"] = s["ss"]
            if x["kind"] == "O":
                ad = audio_of(D, LD[x["id"]])
                if ad["src"] == s["src"] and not s.get("cover"):   # cover = 소리는 원음, 화면은 다른 장면(입 모양 맞출 것 없음)
                    c["sync"] = round(s["ss"] - (ad["ss"] + (t0 - a)), 3)
            out.append(c); prev = c
        if x["kind"] == "O":
            used = {c["i"] for c in out if c["line"] == x["id"]}
            for s in sh:
                if s["i"] not in used:
                    out.append({"i": s["i"], "line": x["id"], "dropped": True, "why": f"원음 창 {b - a:.2f}초 안에 안 들어감"})
    return out


def audio_of(D, l) -> dict:
    """원음 줄의 소리: 그 줄 첫 원음 컷의 audio_src/audio_ss/audio_dur(J컷 꼬리 포함), 없으면 줄 span."""
    s = next((s for s in D["shots"] if s["line"] == l["id"] and s.get("audio_src")), None)
    if s is None:
        raise StageError(f"원음 줄 {l['id']} 에 소리 있는 컷(mute=false)이 없음")
    ss = s.get("audio_ss", l["span"][0])
    d = max(s.get("audio_dur") or 0.0, l["span"][1] - l["span"][0])
    if abs(ss - l["span"][0]) > 0.02:
        raise StageError(f"원음 줄 {l['id']}: 컷 소리 시작 {ss} ≠ 대본 span {l['span'][0]}")
    return {"src": s["audio_src"], "ss": ss, "dur": round(d, 3)}


def audio_pieces(D, LT) -> list[dict]:
    """(판단 주인: 원음 소리 시간표) 0~dur 를 빈틈없이: 원음 줄 = [t0, t0+소리 길이](J컷이면 다음 줄 위로 꼬리), 나머지 = 끔."""
    LD = {l["id"]: l for l in D["lines"]}
    on = []
    for x in LT["lines"]:
        if x["kind"] == "O":
            a = audio_of(D, LD[x["id"]])
            on.append({"line": x["id"], "a": x["t0"], "b": round(min(LT["dur"], x["t0"] + a["dur"]), 3), **a})
    out, t = [], 0.0
    for p in on:
        if p["a"] < t - 1e-6:
            raise StageError(f"원음 {p['line']} 이 앞 원음 꼬리와 겹침")
        if p["a"] > t + 1e-6:
            out.append({"a": round(t, 3), "b": p["a"], "mute": True})
        out.append(p); t = p["b"]
    if LT["dur"] > t + 1e-6:
        out.append({"a": round(t, 3), "b": LT["dur"], "mute": True})
    return out


_OSPEECH: dict = {}


def orig_speech(D, l) -> list[tuple[float, float]]:
    """원음 줄 span 안 말 구간(원본 초) — 원본 소리를 잘라 엔진 speech_segments(−38dB·0.12초)."""
    key = (l["id"], tuple(l["span"]))
    if key not in _OSPEECH:
        from tools.calcopy import narr_video as nv
        a = audio_of(D, l)
        tmp = Path(__file__).resolve().parent / f"_os_{abs(hash(key))}.wav"
        run(["ffmpeg", "-y", "-ss", f"{l['span'][0]:.3f}", "-t", f"{l['span'][1] - l['span'][0]:.3f}", "-i", D["cand_dir"] / a["src"], "-vn", "-ac", "1", "-ar", SR, tmp])
        try:
            segs, _ = nv.speech_segments(str(tmp))
        finally:
            tmp.unlink(missing_ok=True)
        _OSPEECH[key] = [(l["span"][0] + p, l["span"][0] + q) for p, q in segs]
    return _OSPEECH[key]


def caption_times(D, LT, segs=None) -> list[dict]:
    """(판단 주인: 자막 시각) 나레 줄 = 엔진 narr_video._place(말 구간에 글자 비례, 말 시작 붙임), 원음 줄 = cap_at(받아쓰기 낱말 시각) 또는 원본 소리 말 구간에 _place(첫 조각 = 실제 말 시작).
    줄의 마지막 조각은 줄 끝(t1)까지. segs = 완성본 시각 나레 말 구간(없으면 줄마다 [말 시작, 말 끝] 한 덩어리)."""
    from tools.calcopy import narr_video as nv
    LD = {l["id"]: l for l in D["lines"]}
    out = []
    for x in LT["lines"]:
        l = LD[x["id"]]
        steps = [{"text": c, "chars": max(1, nchar(c))} for c in l["caps"]]
        a, e = x["speak"]
        if x["kind"] == "N":
            sg = [(p, q) for p, q in (segs or [(a, e)]) if q > a and p < e] or [(a, e)]
            st = nv._place(steps, sg, 0.4, a, e)
        elif l.get("cap_at"):
            if len(l["cap_at"]) != len(steps):
                raise StageError(f"{l['id']} cap_at {len(l['cap_at'])}개 ≠ 자막 {len(steps)}조각")
            st = [a + (v - l["span"][0]) for v in l["cap_at"]]
        else:   # 원음 말 구간(원본 소리 무음 검출)에 글자 비례 — 엔진 _place 그대로, 첫 조각 = 실제 말 시작(6편 L1: 창 시작에 띄우면 0.5초 일찍)
            sg = [(a + p - l["span"][0], a + q - l["span"][0]) for p, q in orig_speech(D, l)] or [(a, e)]
            st = nv._place(steps, sg, 0.4, max(a, sg[0][0]), e)
        for k, s in enumerate(steps):
            t1 = st[k + 1] if k + 1 < len(st) else x["t1"]
            out.append({"line": x["id"], "kind": x["kind"], "text": s["text"], "t0": round(st[k], 3), "t1": round(t1, 3)})
    return out


# ── 틀 ─────────────────────────────────────────────────────────────────
def preset_dir(doc: Path) -> tuple[Path, bool, str]:
    ch = doc.parent / "preset"
    for m in sorted(ch.glob("*/manifest.json")) if ch.exists() else []:
        if not m.parent.name.startswith("_") and (m.parent / "frame.json").exists():
            return m.parent, True, ""
    if os.environ.get("SHARK_TEMP_FRAME") != "1":
        raise StageError(f"채널 프리셋 없음({ch}) — 임시 틀로 조용히 내려가지 않는다(시험만 SHARK_TEMP_FRAME=1)")
    return FALLBACK_PRESET, False, "채널 프리셋 없음(SHARK_TEMP_FRAME=1)"


def _one_line(layer: dict) -> dict:
    """자막 층(lines 칸·valign) → 한 줄 글자의 자리. emph_png 는 y + line_h/2 에 한 줄을 그리므로(lines·valign 안 봄)
    valign center 인 n줄 칸이면 칸 가운데로 옮긴다(샥탬 프리셋: y 897·2줄·68 → 한 줄 가운데 965, 벤치 잉크 929~988)."""
    n = int(layer.get("lines") or 1)
    if n > 1 and layer.get("valign", "center") == "center":
        return {**layer, "y": layer["y"] + (n - 1) * layer["line_h"] / 2}
    return layer


def frame_and_styles(D, doc: Path, R: Path) -> dict:
    """틀 + 자막 꼴. 채널 프리셋이 있으면 engine/preset_save.apply(제목 글 = 대본, 나머지 변수 = manifest variable_stats 기본값·rules).
    자막 꼴: 프리셋 자막 층(나레·번역 같은 꼴 — channel_rules.captions.narration_and_quote_same_style) + 원음 짧은 반응 꼴('원음반응*').
    틀의 자막 층은 빼고(자막은 완성본에 얹음) 틀 frame.json 을 작업 폴더에 남긴다."""
    pdir, own, why = preset_dir(doc)
    fr = jload(pdir / "frame.json")
    man = jload(pdir / "manifest.json")
    styles = {s["name"]: s["layer"] for s in man.get("caption_styles") or []}
    notes = []
    if own:
        from tools.calcopy.engine import preset_save
        try:
            fr = preset_save.apply(fr, overrides={"layers[text:title].text": D["title"]}, defaults=man.get("variable_stats"), rules=man.get("rules"))
        except ValueError as e:
            raise StageError(f"프리셋 {pdir.name} 변수 못 채움: {e}")
        vtop = next(l["y"] for l in fr["layers"] if l["kind"] == "video")
        fit = None
        for i, l in enumerate(fr["layers"]):
            if l.get("role") == "title":
                fr["layers"][i], fit = title_fit({**l, "text": D["title"]}, man, vtop)
        notes.append(f"프리셋 {pdir.name} (preset_save.apply) · 제목 title_fit {fit}")
    cap_frame = next((l for l in fr["layers"] if l.get("role") == "caption"), None)
    same = (((man.get("channel_rules") or {}).get("captions") or {}).get("narration_and_quote_same_style"))
    narr = cap_frame if own else next((v for k, v in styles.items() if k.startswith("나레")), cap_frame)
    orig = narr if same else next((v for k, v in styles.items() if k.startswith("원음") and "반응" not in k), narr)
    react = next((v for k, v in styles.items() if "반응" in k), None)
    if not narr:
        raise StageError(f"틀 {pdir} 에 자막 꼴이 없다")
    layers = []
    for l in fr["layers"]:
        if l.get("kind") == "text" and l.get("role") == "caption":
            continue
        if l.get("kind") == "text" and l.get("role") == "title":
            l = {**l, "text": D["title"]}
        elif l.get("kind") == "text" and l.get("text") == "$per_video":
            notes.append(f"층 {l.get('role')} 뺌($per_video, 이 채널엔 출처·라벨 없음)")
            continue
        if l.get("kind") == "video" and not own and D["window"]:
            x, y, w, h = D["window"]
            l = {**l, "x": x, "y": y, "w": w, "h": h}
            notes.append(f"임시 틀: 창을 벤치 {D['window']} 로")
        layers.append(l)
    fr = {**fr, "layers": layers}
    R.mkdir(parents=True, exist_ok=True)
    jsave(R / "frame.json", fr)
    if not own:
        notes.insert(0, f"★{why} → 임시 {pdir.relative_to(ROOT)}")
    return {"preset": str(pdir), "own": own, "frame": str(R / "frame.json"), "narr_style": _one_line(narr), "orig_style": _one_line(orig),
            "react_style": _one_line(react) if react else None, "notes": notes, "win": next(l for l in layers if l["kind"] == "video")}


def _rule(man: dict, key: str, how="default"):
    k = ((man.get("rules") or {}).get("keys") or {}).get(key) or {}
    if how == "median":
        v = sorted(x for x in (k.get("values") or {}).values() if isinstance(x, (int, float)))
        return v[len(v) // 2] if v else None
    return k.get("default")


TITLE_RENDER_DY = 10   # 모형(PIL 줄 칸 가운데) 대비 렌더러(scene_style.compose) 실측 차 — 10-18 회색 1초 합성: 아래 끝 398 vs 모형 408(두 번 같음)


def title_fit(layer: dict, man: dict, video_top: float) -> tuple[dict, dict]:
    """(판단 주인: 제목 크기·자리) 프리셋 title_rule — 줄마다 크기를 그 줄 잉크 폭이 벤치 폭(rules.fill_w 8편 중앙)에 맞게(상한 size_cap),
    2줄 잉크 아래 끝 = 창 위 − gap_ink(8편 중앙 27px → 벤치 404~416). 기본값 그대로 두면 긴 줄이 칸 폭(1000)을 넘어 렌더러가 줄여
    잉크가 위로 뜬다(10-18 1차 실측: 아래 끝 389, 줄 크기 줄어듦). 색·글꼴은 프리셋(apply) 값 그대로."""
    from tools.calcopy.engine import to_frame as tf
    fam, text = layer["font"], layer["text"].split(chr(10))
    cap, lhr, gap = _rule(man, "size_cap") or layer["size"], _rule(man, "lh_ratio") or 1.035, _rule(man, "gap_ink") or 27
    target_w = _rule(man, "fill_w", "median") or 906
    sizes = []
    for t in text:
        b = tf._pil_font(fam, 100).getbbox(t, anchor="ls")
        sizes.append(round(min(cap, 100 * target_w / max(1, b[2] - b[0])), 1))
    # 한 크기(가장 긴 줄이 벤치 폭에 맞는 크기) — 벤치 QMJ 와 같은 방식(두 줄 100.5 한 크기, line_scale 없음).
    # 줄마다 다른 크기(line_scale)는 렌더러 줄 칸 배치가 모형과 10px 어긋났다(10-18 시험: 아래 끝 398 vs 408) → 안 씀.
    base = min(sizes)
    sizes = [base] * len(sizes)
    lh = round(base * lhr)
    s_last = base
    f = tf._pil_font(fam, s_last)
    asc, desc = f.getmetrics()
    b = f.getbbox(text[-1], anchor="ls")
    bottom = video_top - gap
    y_last = bottom - ((lh - (asc + desc)) / 2 + asc + b[3])     # 줄 칸 안 세로 가운데(to_frame.size_and_top 과 같은 모형)
    out = {**layer, "size": base, "line_h": lh, "y": round(y_last - (len(text) - 1) * lh + TITLE_RENDER_DY),
           "line_scale": [round(x / base, 3) for x in sizes] if len(set(sizes)) > 1 else None}
    return out, {"sizes": sizes, "target_w": target_w, "ink_bottom_target": bottom, "line_h": lh, "y": out["y"]}


REACT_MAX = FX.R()["caption"]["react_max_chars"]   # 원음 짧은 반응(×1.25 꼴) — 값 주인 shark/rules.json


def cap_style(c: dict, n_caps: int, FS: dict) -> tuple[str, dict]:
    """(판단 주인: 자막 꼴) 자막 조각 → (꼴 이름, 층)."""
    if c["kind"] == "O" and FS.get("react_style") and n_caps == 1 and nchar(c["text"]) <= REACT_MAX:
        return "원음반응", FS["react_style"]
    return ("원음" if c["kind"] == "O" else "나레"), (FS["orig_style"] if c["kind"] == "O" else FS["narr_style"])


def effects(D, LT) -> tuple[list[dict], list[str], list[dict]]:
    """재료.effects[{line, kind, at:[x,y](완성본 좌표 = ★그림 가운데, 화살표 끝 아님 — fx.tip_offset) | tip:[x,y](가리킬 점), t:[줄 안 시작,끝], target·target_path·track…}]
    → 완성본 시각 + 적중 검사(fx.gate, R3·R4).
    검사 미달·fix 가 뺀 것(drop)은 그리지 않고 (line, kind, 이유)로 돌려준다(render_info fx_dropped). 좌표 없는 메모는 못 그림으로 남긴다."""
    lt = {x["id"]: x for x in LT["lines"]}
    out, dropped = [], []
    for e in D["effects"]:
        if e.get("kind") not in FX_KINDS:
            raise StageError(f"꾸밈 '{e.get('kind')}' 은 엔진(overlay_png)이 못 그린다 — 엔진 요청: {e}")
        if e.get("line") not in lt:
            raise StageError(f"꾸밈 줄 없음: {e}")
        if e.get("tip") and not e.get("at"):          # 손으로 가리킬 점(tip)을 적은 꾸밈 → 그림 가운데(at) (fx.at_from_tip 한 곳)
            e = {**e, "at": FX.at_from_tip(e["kind"], e["tip"], FX._key(e))}
        if e.get("drop") or not e.get("at"):
            dropped.append({"line": e["line"], "kind": e["kind"], "why": e.get("drop") or "자리(at) 없음"}); continue
        x = lt[e["line"]]
        a, b = e.get("t") or [0.0, x["t1"] - x["t0"]]
        out.append({**e, "T": [round(x["t0"] + a, 3), round(min(x["t1"], x["t0"] + b), 3)]})
    out, dg = FX.gate(out)
    dropped += dg
    drawn = {e["line"] for e in out}
    not_drawn = [f"안 그림(좌표 없음·엔진에 없는 꼴) — {n}" for n in D["fx_notes"] if n.split(":")[0].split(" ")[0] not in drawn]
    return out, not_drawn, dropped


# ── 계획(공통) ───────────────────────────────────────────────────────────
def plan_all(D, NM, segs=None) -> dict:
    LT = line_times(D, NM)
    cuts = cut_times(D, LT)
    caps = caption_times(D, LT, segs)
    aud = audio_pieces(D, LT)
    fx, nd, fd = effects(D, LT)
    return {"lines": LT["lines"], "dur": LT["dur"], "cuts": cuts, "captions": caps, "audio": aud, "effects": fx, "fx_not_drawn": nd, "fx_dropped": fd}


def info_of(D, P, NM, mode, extra=None) -> dict:
    live = [c for c in P["cuts"] if not c.get("dropped")]
    ds = sorted(c["dur"] for c in live)
    LD = {l["id"]: l for l in D["lines"]}
    return {"mode": mode, "engine": ENGINE, "dur": P["dur"], "bench_dur": D["bench"].get("dur"), "bench_cut_median": D["bench"].get("cut_median"),
            "narr": {k: v for k, v in NM.items() if k != "lines"}, "narr_lines": NM["lines"],
            "lines": [{**x, "caps_from": LD[x["id"]]["caps_from"], "tts": LD[x["id"]].get("tts"), "en": LD[x["id"]].get("en")} for x in P["lines"]],
            "cuts": P["cuts"], "captions": P["captions"], "audio": P["audio"], "effects": P["effects"], "fx_not_drawn": P["fx_not_drawn"], "fx_dropped": P.get("fx_dropped", []),
            "summary": {"cuts": len(live), "dropped": [c["i"] for c in P["cuts"] if c.get("dropped")], "cut_median": ds[len(ds) // 2],
                        "cut_min": ds[0], "end_cut": live[-1]["dur"], "short_cuts": [(c["i"], c["dur"]) for c in live if c["dur"] < 1.2],
                        "caps": len(P["captions"]), "cap_max_chars": max(nchar(c["text"]) for c in P["captions"]),
                        "sync_off": [(c["i"], c["line"], c["sync"]) for c in live if abs(c.get("sync", 0)) > 0.04],
                        "orig_sec": round(sum(x["speak"][1] - x["speak"][0] for x in P["lines"] if x["kind"] == "O"), 2)},
            **(extra or {})}


def table_md(info) -> str:
    L = [f"# 샥탬스토리 렌더 계획 — {info['mode']} · {info['dur']:.2f}초(벤치 {info['bench_dur']}) · 컷 {info['summary']['cuts']} 중앙 {info['summary']['cut_median']:.2f}",
         "", "## 줄", "| 줄 | 종류 | 시각 | 말/원음 | 자막 |", "|---|---|---|---|---|"]
    caps = info["captions"]
    for x in info["lines"]:
        cs = " / ".join(f"{c['t0']:.2f} {c['text']}" for c in caps if c["line"] == x["id"])
        L.append(f"| {x['id']} | {'원음' if x['kind'] == 'O' else '나레'} | {x['t0']:.2f}–{x['t1']:.2f} | {x['speak'][0]:.2f}–{x['speak'][1]:.2f} | {cs} |")
    L += ["", "## 컷", "| # | 줄 | 시각 | 길이(재료) | 소스@초 | sync | 화면 |", "|---|---|---|---|---|---|---|"]
    for c in info["cuts"]:
        if c.get("dropped"):
            L.append(f"| {c['i']} | {c['line']} | — | 빠짐 | — | — | {c['why']} |"); continue
        L.append(f"| {c['i']} | {c['line']} | {c['t0']:.2f}–{c['t1']:.2f} | {c['dur']:.2f}({c['plan_dur']}) | {Path(c['src']).stem[:6]}@{c['ss']} | "
                 f"{c.get('sync', '')} | {c['see'][:40]} |")
    L += ["", "## 원음 소리", *[f"- {p['a']:.2f}–{p['b']:.2f} " + ("끔" if p.get("mute") else f"{p['line']} {Path(p['src']).stem}@{p['ss']}+{p['dur']}") for p in info["audio"]],
          "", "## 못 그림", *([f"- {n}" for n in info["fx_not_drawn"]] or ["- 없음"]),
          "", "## 뺀 꾸밈(적중 검사·R3·R4)", *([f"- {d['line']} {d['kind']}: {d['why']}" for d in info.get("fx_dropped") or []] or ["- 없음"])]
    return "\n".join(L) + "\n"


# ── 렌더 ─────────────────────────────────────────────────────────────────
def place_narr(D, P, NM, R: Path) -> Path:
    """나레 줄마다 [말 시작−0.03, 말 끝+0.10] 을 줄 시작에 놓은 한 파일(길이 = dur)."""
    src = NM["wav"]
    ins, fc, lab = [], [], []
    k = 0
    for x in P["lines"]:
        if x["kind"] != "N":
            continue
        a, b = x["narr"]
        pre = min(0.03, a, x["t0"])   # 첫 줄이 나레(t0=0)면 앞당길 자리가 없다 — adelay 음수로 ffmpeg 실패(10-18 하이브리드 5편)
        d_ms = int(round((x["t0"] - pre) * 1000))
        fc.append(f"[0:a]atrim={a - pre:.3f}:{b + 0.10:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={b - a + pre + 0.05:.3f}:d=0.05,adelay={d_ms}:all=1[n{k}]")
        lab.append(f"[n{k}]"); k += 1
    # 나레가 전부 늦게 시작하면(첫 줄 원음) amix 출력이 첫 나레 시각부터 시작해 atrim 이 앞 무음을 잘라 나레가 0초로 당겨졌다
    # (10-19 12편 실측 narr_placed 34.33초 = 38.99−4.66). first_pts=0 으로 앞을 무음으로 채운 뒤 자른다
    fc.append("".join(lab) + f"amix=inputs={len(lab)}:normalize=0:duration=longest,aresample=async=1:first_pts=0,apad,atrim=0:{P['dur']:.3f}[a]")
    out = R / "narr_placed.wav"
    run(["ffmpeg", "-y", "-i", src, "-filter_complex", ";".join(fc), "-map", "[a]", "-ar", SR, "-ac", "1", out])
    if abs(dur_of(out) - P["dur"]) > 0.05:      # 길이가 다르면 나레 자리가 밀린 것 — 조용히 넘기지 않는다
        raise StageError(f"narr_placed 길이 {dur_of(out):.3f} ≠ 편 길이 {P['dur']:.3f} — 나레 자리 어긋남")
    return out


def orig_gains(D, P, C) -> list[list]:
    """원음 창 올림(dB) = (나레 LUFS + orig_rel_db) − 그 원본 구간 LUFS, clamp."""
    gg = []
    lo, hi = C["orig_gain_clamp"]
    for p in P["audio"]:
        if p.get("mute"):
            continue
        I, _ = lufs(D["cand_dir"] / p["src"], ["-ss", f"{p['ss']:.3f}", "-t", f"{p['dur']:.3f}"])
        if I != I or I < -60:
            raise StageError(f"원음 {p['line']} 구간 소리 크기 못 잼({I})")
        g = round(min(hi, max(lo, C["narr_lufs"] + C["orig_rel_db"] - I)), 2)
        p["src_lufs"], p["gain_db"] = I, g
        gg.append([p["a"], p["b"], g])
    return gg


def overlay_pass(D, P, FS, src_mp4: Path, R: Path) -> Path:
    """자막(낱말 색·번짐·그림자·넘김 흐림)·꾸밈·번쩍 = shark/fx.build_layer 가 그린 RGBA 층 하나를 얹는다(판단은 fx·caption_style·rules.json)."""
    n_of = {}
    for c in P["captions"]:
        n_of[c["line"]] = n_of.get(c["line"], 0) + 1
    for c in P["captions"]:
        c["style"], _ = cap_style(c, n_of[c["line"]], FS)
    layer = R / "fx_layer.mov"
    P["fx_drawn"] = FX.build_layer(P, D["S"], layer, P["dur"])
    out = R / "video_cap.mp4"
    run(["ffmpeg", "-y", "-i", src_mp4, "-i", layer, "-filter_complex", f"[0:v][1:v]overlay=0:{FX.Y0}:format=auto,format=yuv420p[v]",
         "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-color_range", "tv", "-r", "30", out])
    return out


def audio_final(D, P, C, src_mp4: Path, video: Path, R: Path) -> dict:
    """BGM(원음 창 덕킹) 섞기 → 목표 LUFS·최고점 맞춤(압축·tanh 깎기, 재고 다시 — 최대 8번)."""
    from shopping_shorts import bgm_lib
    bgm = bgm_lib.path_of(C["bgm"])
    if not bgm or not Path(bgm).exists():
        raise StageError(f"BGM '{C['bgm']}' 없음")
    k = 10 ** (C["duck_db"] / 20)
    win = [(p["a"], p["b"]) for p in P["audio"] if not p.get("mute")]
    bss = float(C.get("bgm_ss") or 0.0)   # 하이브리드 뒤: 앞 편 BGM 을 앞이 끊긴 초부터 이어 튼다(대본 render.bgm_ss, 기본 0)
    terms = "*".join(f"(1-{1 - k:.4f}*clip(min((t-{a - 0.15:.3f})/0.15,({b + 0.15:.3f}-t)/0.15),0,1))" for a, b in win) or "1"
    pre = R / "mix_pre.wav"
    run(["ffmpeg", "-y", "-i", src_mp4, "-stream_loop", "-1", "-i", bgm, "-filter_complex",
         f"[0:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=mono[m];"
         f"[1:a]atrim={bss:.3f}:{bss + P['dur']:.3f},asetpts=PTS-STARTPTS,aresample={SR},aformat=sample_fmts=fltp:channel_layouts=mono,"
         f"loudnorm=I={C['bgm_lufs']}:TP=-6:LRA=11,aresample={SR},volume='{terms}':eval=frame[b];[m][b]amix=inputs=2:normalize=0:duration=first[a]",
         "-map", "[a]", "-t", f"{P['dur']:.3f}", "-c:a", "pcm_f32le", pre])
    I0, _ = lufs(pre)
    # R5(10-19): 목표 −14 LUFS·트루피크 ≤ −1.5. 옛 −9 때 쓰던 tanh 깎기는 뺐다(소리 뭉갬 — −14 는 낮추는 쪽이라 깎을 일이 없다).
    # → 가벼운 압축(−18dB·3:1·+6dB, 나레/원음 고르게) → 이득 g → 리미터(트루피크 목표 −1dB, AAC 넘침 몫) → 16kHz 위 자름.
    #   g 만 재며 맞추고(최대 8번), 최고점이 넘으면 리미터를 낮춘다.
    final = R / "final.mp4"
    I, pk, hist = loud_fit(video, pre, I0, C["target_lufs"], C["peak_max"], P["dur"], final)
    return {"bgm": C["bgm"], "bgm_ss": bss, "bgm_lufs": C["bgm_lufs"], "duck_db": C["duck_db"], "mix_I": I0, "chain": LOUD_COMP + " → volume → alimiter → lowpass 16k", "target": [C["target_lufs"], C["peak_max"]], "passes": hist, "final_I": I, "final_peak": pk}


LOUD_COMP = "acompressor=threshold=0.125:ratio=3:attack=5:release=120:knee=4:makeup=2"


def next_gain(hist: list[dict], target: float, tol: float) -> float:
    """(판단 주인: 소리 맞춤 다음 이득) 잰 점들로 할선(secant) — 대상 구간(목표±tol 밖 아래·위 가장 가까운 점) 안으로 가두고,
    밖이면 반으로 가른다(이분법). 첫 걸음만 옛 규칙(차×2).
    옛 규칙 '차×2' 를 계속 쓰면 이득↔LUFS 기울기가 ~1 인 소리(삐 소리판·−14 LUFS)에서 위아래로 같은 폭만큼 튀어 안 모인다
    (10-20 하이브리드 --preview −13.1↔−14.9 8번 멈춤, 10편 하이브리드 5번)."""
    pts = [(h["gain"], h["I"]) for h in hist if h["I"] == h["I"]]     # 리미터만 낮춘 걸음도 같은 곡선으로 친다(I 차이 0.1 안팎)
    g, I = pts[-1]
    if len(pts) < 2:
        return g + (target - I) * 2.0
    lo = max((p for p in pts if p[1] < target - tol), default=None, key=lambda p: p[0])
    hi = min((p for p in pts if p[1] > target + tol), default=None, key=lambda p: p[0])
    (g0, I0) = pts[-2]
    slope = (I - I0) / (g - g0) if abs(g - g0) > 1e-3 else 1.0
    slope = min(1.5, max(0.3, slope)) if slope > 0 else 1.0
    nx = g + (target - I) / slope
    if lo and hi and lo[0] < hi[0]:
        if not (lo[0] < nx < hi[0]):
            nx = (lo[0] + hi[0]) / 2
    return round(nx, 2)


def loud_fit(video: Path, pre: Path, I0: float, target: float, peak_max: float, dur: float, final: Path, tries: int = 10):
    """(판단 주인: 마지막 소리 크기) 가벼운 압축 → 이득 g → 리미터(트루피크 목표 −1dB, AAC 넘침 몫) → 16kHz 위 자름.
    g 는 next_gain 으로 재며 맞추고, 최고점이 넘으면 리미터를 낮춘다(이득은 그대로)."""
    g, lim, hist = target - I0, 10 ** ((peak_max - 1.0) / 20), []
    for it in range(tries):
        run(["ffmpeg", "-y", "-i", video, "-i", pre, "-filter_complex",
             f"[1:a]{LOUD_COMP},volume={g:.2f}dB,alimiter=limit={lim:.3f}:attack=2:release=40:level=false,lowpass=f=16000[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.3f}", final])
        I, pk = lufs(final)
        hist.append({"gain": round(g, 2), "limit": round(lim, 3), "I": I, "peak": pk})
        if abs(I - target) <= LOUD["tol"] and pk <= peak_max:
            return I, pk, hist
        if pk > peak_max:
            lim *= 10 ** ((peak_max - pk - 0.2) / 20)
        else:
            g = next_gain(hist, target, LOUD["tol"])
    raise StageError(f"소리 크기 못 맞춤 {hist}")


def reuse_tts(R: Path, src: Path | None) -> str | None:
    """옛 렌더 폴더의 타입캐스트 원본(narr_raw.mp3·정렬·meta)을 새 작업 폴더로 복사 — 타입캐스트 다시 안 부른다(비용 0).
    글이 다르면 narr_tts 가 meta.text 대조로 멈춘다(조용히 다른 나레를 쓰지 않는다)."""
    if not src:
        return None
    if (R / "narr_raw.mp3").exists():
        return f"TTS 재사용: 이미 있음 {R / 'narr_raw.mp3'}"
    names = ("narr_raw.mp3", "narr_raw.align.json", "narr_raw.meta.json")
    if not all((src / n).exists() for n in names):
        raise StageError(f"--tts-from {src} 에 {names} 가 다 없다")
    R.mkdir(parents=True, exist_ok=True)
    for n in names:
        shutil.copy2(src / n, R / n)
    return f"TTS 재사용: {src} → {R}"


def render(doc: Path, work: Path, mode: str, confirm_tts=False, cps=None, cps_target=None, tts_from: Path | None = None) -> dict:
    D = load_doc(doc)
    if cps:
        D["C"]["cps_plan"] = cps
    if cps_target:   # 페이블 지시 말속도(대본 cps_target 보다 앞선다) — render_info.narr.target_cps 에 남는다
        D["cps_target"] = cps_target
    src_notes = check_sources(D)
    R = work / {"plan": "plan", "preview": "preview"}.get(mode, "render")
    R.mkdir(parents=True, exist_ok=True)
    FS = frame_and_styles(D, doc, R)
    if mode == "plan":
        NM = narr_plan(D)
        P = plan_all(D, NM)
        info = info_of(D, P, NM, "plan", {"frame": FS["frame"], "preset": FS["preset"], "frame_notes": FS["notes"], "sources": src_notes})
        jsave(R / "render_info.json", info)
        (R / "컷표.md").write_text(table_md(info), encoding="utf-8")
        return info
    from tools.calcopy import narr_video as nv, hottem_audio as ha
    tts_note = reuse_tts(R, tts_from) if mode != "preview" else None
    NM = narr_beep(narr_plan(D), R) if mode == "preview" else narr_tts(D, R, confirm_tts)
    P0 = plan_all(D, NM)
    placed = place_narr(D, P0, NM, R)
    segs, _ = nv.speech_segments(str(placed), "-40dB", 0.06)
    P = plan_all(D, NM, segs)
    base = {"frame": FS["frame"], "preset": FS["preset"], "frame_notes": FS["notes"], "sources": src_notes, "narr_placed": str(placed), "tts_reuse": tts_note}
    if mode == "tts":
        info = info_of(D, P, NM, "tts-only", base)
        jsave(R / "render_info.json", info)
        (R / "컷표.md").write_text(table_md(info), encoding="utf-8")
        return info
    C = D["C"]
    live = [c for c in P["cuts"] if not c.get("dropped")]
    jsave(R / "script_render.json", {"_note": "shark/render.py — narr_video 용(자막은 완성본에 따로 얹음)", "final": {"lines": [{"text": "가"}]}})
    jsave(R / "materials_render.json", {"cand_dir": str(D["cand_dir"]), "shots": [{
        "i": 0, "full": True, "src": live[0]["src"], "ss": live[0]["ss"],
        "cuts": [{"src": c["src"], "ss": c["ss"], "dur": c["dur"], **({"src_crop": c["src_crop"]} if c.get("src_crop") else {}),
                  **{k: c[k] for k in SHOT_KEYS if c.get(k) is not None and k != "loop"}, **({"kind": "짤"} if c.get("loop") else {})} for c in live]}]})
    nvout = R / "nv"
    final_nv = nv.build({"tteutgi": None, "frames": [{"frame": FS["frame"], "t_end": None}], "script": str(R / "script_render.json"), "tts": str(placed),
                         "materials": str(R / "materials_render.json"), "out": str(nvout), "bgm": None, "lufs": C["narr_lufs"], "chunk": 14,
                         "caption_mode": "replace", "line_asr": False})
    gg = orig_gains(D, P, C)
    jsave(R / "audio_timeline.json", {"shots": [[p["a"], p["b"]] for p in P["audio"]], "dur": P["dur"]})
    jsave(R / "audio_materials.json", {"cand_dir": str(D["cand_dir"]), "shots": [
        {"src": p.get("src") or live[0]["src"], "ss": p.get("ss", 0.0), **({"mute": True} if p.get("mute") else {"audio_src": p["src"], "audio_ss": p["ss"]})}
        for p in P["audio"]]})
    bed = R / "final_src.mp4"
    ha.add_source_bed(str(final_nv), str(R / "audio_timeline.json"), str(R / "audio_materials.json"), str(placed), str(bed), 1.0, 10.0,
                      work=str(R / "srcbed"), gap_gain=gg)
    video = overlay_pass(D, P, FS, bed, R)
    sfx = FX.sfx_events(P)
    A = audio_final(D, P, C, FX.add_sfx(bed, sfx, R), video, R)
    info = info_of(D, P, NM, mode, {**base, "final": str(R / "final.mp4"), "audio_mix": A, "orig_gain": gg, "fx_drawn": P.get("fx_drawn"), "sfx": sfx,
                                         "fx_timed": [{k: e.get(k) for k in ("line", "kind", "T", "color", "moved_into_dashed", "snapped", "cut_end") if e.get(k) is not None} for e in FX.timed(P)]})   # 실제 그린 시각(effects 는 옮기기 전 계획 값)
    jsave(R / "render_info.json", info)
    (R / "컷표.md").write_text(table_md(info), encoding="utf-8")
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc"); ap.add_argument("work")
    ap.add_argument("--plan", action="store_true"); ap.add_argument("--tts-only", action="store_true")
    ap.add_argument("--preview", action="store_true"); ap.add_argument("--confirm-tts", action="store_true"); ap.add_argument("--cps", type=float)
    ap.add_argument("--cps-target", type=float, help="TTS atempo 목표 자/초(없으면 대본 final.cps_target)")
    ap.add_argument("--tts-from", help="옛 렌더 폴더(narr_raw.mp3·정렬·meta) — 타입캐스트를 다시 안 부르고 복사해 쓴다")
    a = ap.parse_args()
    mode = "plan" if a.plan else ("preview" if a.preview else ("tts" if a.tts_only else "render"))
    try:
        info = render(Path(a.doc).resolve(), Path(a.work).resolve(), mode, a.confirm_tts, a.cps, a.cps_target, Path(a.tts_from) if a.tts_from else None)
    except StageError as e:
        print(f"[멈춤] {e}", file=sys.stderr)
        sys.exit(2)
    s = info["summary"]
    log(f"[{info['mode']}] 길이 {info['dur']:.2f}초(벤치 {info['bench_dur']}) · 컷 {s['cuts']} 중앙 {s['cut_median']:.2f} 최단 {s['cut_min']:.2f} 끝 {s['end_cut']:.2f}"
        f" · 1.2초 미만 {s['short_cuts']} · 빠진 컷 {s['dropped']} · 자막 {s['caps']}조각 최대 {s['cap_max_chars']}자 · 원음 {s['orig_sec']}초"
        f" · 화면≠소리 시각 {s['sync_off']} · 못 그림 {len(info['fx_not_drawn'])} · 뺀 꾸밈 {len(info.get('fx_dropped') or [])}")
    for d in info.get("fx_dropped") or []:
        log("   뺀 꾸밈", d["line"], d["kind"], d["why"])
    for n in info.get("frame_notes", []) + info.get("sources", []):
        log("  ", n)


if __name__ == "__main__":
    main()
