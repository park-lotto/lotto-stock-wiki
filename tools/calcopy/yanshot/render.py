# -*- coding: utf-8 -*-
"""⑤ 만들기 — 판단 주인: make(B, T, S, P, W) (관제 097, 2026-10-17).

정본 make_render.py(channel/yanshottem/장윤정_덴마크수건) 길을 함수로 굳혔다 — 엔진은 부르기만:
  미나 TTS 1회(tools/calcopy/mina_tts.synth, 나레 두 줄 한 번에) → 줄 사이 쉼(hottem_audio.break_points)에서 갈라
  줄별 atempo = 8.4자/초(줄끼리 ±10% 안 — B17 말투 유지) → 컷 시각 다시 맞춤(plan.retime) → 나레를 블록 자리에 끼운 narr_gapped.wav
  → narr_video.build(한 페이지 shots[].cuts, 자막 = captions 전부 emph: 나레 노랑·원음 흰, BGM 없음, line_asr=False)
  → hottem_audio.add_source_bed(컷 단위 원음 = 본인 말만) — 원음 창 올림은 자동(나레와 같은 크기로, 1회 재서 1회 다시)
  → BGM 원음 창 덕킹 섞기 → 벤치 LUFS → render/final.mp4.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tools.calcopy.yanshot.common import StageError, dur_of, jload, jsave, lufs_of, run

CPS = 8.4
TEMPO_SPREAD = 0.10          # B17: 줄별 늘림/줄임은 평균 배속 ±10% 안
LINE_GAP = 0.30              # TTS 파일 안 두 줄 사이(렌더에서는 블록 자리로 다시 놓는다)
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
LUFS_NARR = -15.0
BGM, BGM_DB, DUCK_DB = "sweets", -27.0, -10.0
ORIG_VS_NARR = 0.0           # 원음 창 목표 = 나레 크기 + 이것(dB)


def _speech(wav, a: float, b: float, noise="-35dB") -> tuple[float, float]:
    """[a,b] 안 말 시작·끝(앞뒤 무음 뺌)."""
    e = run(["ffmpeg", "-hide_banner", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(wav), "-af", f"silencedetect=noise={noise}:d=0.05",
             "-f", "null", "-"], check=False).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", e)]
    s0 = en[0] if st and st[0] <= 0.02 and en else 0.0
    e0 = st[-1] if st and (len(en) < len(st) or en[-1] >= (b - a) - 0.02) else (b - a)
    return round(a + max(0.0, s0 - 0.02), 3), round(a + min(b - a, e0 + 0.03), 3)


def tempo_plan(chars: list[int], talks: list[float]) -> list[float]:
    """(판단 주인) 줄별 atempo — 줄마다 8.4자/초가 되게, 단 평균 배속 ±10% 안으로 묶는다(B15 고르게 · B17 말투)."""
    want = [t / (c / CPS) for c, t in zip(chars, talks)]
    mean = sum(talks) / (sum(chars) / CPS)
    return [round(min(mean * (1 + TEMPO_SPREAD), max(mean * (1 - TEMPO_SPREAD), w)), 3) for w in want]


def tts(S: dict, R: Path, log=print) -> dict:
    """미나 1회 → 줄별 배속 → narr_t.wav + 줄 구간(slices). 이미 있으면 다시 부르지 않는다(재과금 0)."""
    from tools.calcopy import hottem_audio as ha
    from tools.calcopy import mina_tts
    R.mkdir(parents=True, exist_ok=True)
    raw = R / "narr_mina.mp3"
    sent = [l["tts"] for l in S["lines"]]
    if not raw.exists():
        mina_tts.synth(" ".join(sent), str(raw))
        log(f"[make] 미나 TTS 1회 → {raw.name} {dur_of(raw):.2f}초")
    D = dur_of(raw)
    bp = ha.break_points(raw, sent)
    if bp[0][0] is None:
        raise StageError(f"TTS 두 줄 사이 쉼을 못 찾음 — {bp}")
    m = bp[0][0]
    spans = [_speech(raw, 0.0, m), _speech(raw, m, D)]
    talks = [round(b - a, 3) for a, b in spans]
    chars = [l["chars"] for l in S["lines"]]
    tp = tempo_plan(chars, talks)
    out = R / "narr_t.wav"
    fc = (f"[0:a]atrim={spans[0][0]:.3f}:{spans[0][1]:.3f},asetpts=N/SR/TB,atempo={tp[0]},aresample=48000,aformat=channel_layouts=mono[a];"
          f"anullsrc=r=48000:cl=mono,atrim=0:{LINE_GAP}[g];"
          f"[0:a]atrim={spans[1][0]:.3f}:{spans[1][1]:.3f},asetpts=N/SR/TB,atempo={tp[1]},aresample=48000,aformat=channel_layouts=mono[b];"
          "[a][g][b]concat=n=3:v=0:a=1[o]")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-filter_complex", fc, "-map", "[o]", "-c:a", "pcm_s16le", str(out)])
    d1 = round(talks[0] / tp[0], 3)
    d2 = round(talks[1] / tp[1], 3)
    sl = {"N1": [0.0, d1], "N2": [round(d1 + LINE_GAP, 3), round(d1 + LINE_GAP + d2, 3)]}
    info = {"raw": str(raw), "raw_dur": D, "break": m, "spans_raw": spans, "talks_raw": talks, "atempo": tp, "slices": sl, "wav": str(out),
            "cps": [round(c / (t / f), 2) for c, t, f in zip(chars, talks, tp)]}
    jsave(R / "tts.json", info)
    log(f"[make] 줄 배속 {tp} → 말속도 {info['cps']}자/초 · 줄 구간 {sl}")
    return info


def gapped(narr_wav, P: dict, slices: dict, out, total: float):
    """나레 줄을 그 블록 시작 자리에, 나머지는 무음(정본 make_render.gapped 와 같은 길)."""
    fc, lab, t = [], [], 0.0
    nb = [b for b in P["blocks"] if b["kind"] == "나레"]
    for i, b in enumerate(nb):
        a, e = slices[b["id"]]
        t0 = b["t"][0]
        if t0 - t > 1e-3:
            fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{t0 - t:.3f}[g{i}]"); lab.append(f"[g{i}]")
        fc.append(f"[0:a]atrim={a:.3f}:{e:.3f},asetpts=N/SR/TB,aresample=48000,aformat=channel_layouts=mono[p{i}]"); lab.append(f"[p{i}]")
        t = t0 + (e - a)
    if total - t > 1e-3:
        fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{total - t:.3f}[ge]"); lab.append("[ge]")
    fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1[a]")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(narr_wav), "-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", str(out)])


def ramp(a, b, g, up=0.06, down=0.10, depth=6.0):
    """원음 창 올림 꼴 — 정본 make_render.ramp 그대로(창 앞뒤를 부드럽게)."""
    st = 4
    out = [[round(a + up * i / st, 3), round(a + up * (i + 1) / st, 3), round(g - 12 * (1 - (i + 1) / st), 2)] for i in range(st)]
    out.append([round(a + up, 3), round(b - down, 3), g])
    out += [[round(b - down + down * i / st, 3), round(b - down + down * (i + 1) / st, 3), round(g - depth * (i + 1) / st, 2)] for i in range(st)]
    return out


def windows(P: dict) -> list[tuple[float, float]]:
    """이어 붙은 원음 블록은 창 하나로(정본 merged_windows)."""
    out = []
    for b in P["blocks"]:
        if b["kind"] != "원음":
            continue
        a, e = b["t"]
        if out and abs(out[-1][1] - a) < 1e-3:
            out[-1] = (out[-1][0], e)
        else:
            out.append((a, e))
    return out


def bgm_mix(src_mp4, out_mp4, win, dur, lufs_final, work: Path) -> dict:
    """정본 make_render.bgm_mix 그대로 — BGM 을 원음 창에서 덕킹해 섞고 벤치 LUFS 로."""
    from shopping_shorts import bgm_lib
    bgm = bgm_lib.path_of(BGM)
    k = 10 ** (DUCK_DB / 20)
    terms = "*".join(f"(1-{1 - k:.4f}*clip(min((t-{a - 0.15:.3f})/0.15,({b + 0.15:.3f}-t)/0.15),0,1))" for a, b in win) or "1"
    tmp = work / "work_bgm.wav"
    run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", bgm, "-t", f"{dur:.3f}", "-af",
         f"aresample=48000,aformat=channel_layouts=mono,loudnorm=I={BGM_DB}:TP=-6:LRA=11,volume='{terms}':eval=frame,afade=t=out:st={dur - 0.6:.3f}:d=0.6",
         "-c:a", "pcm_s16le", str(tmp)])
    mixed = work / "work_mix.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src_mp4), "-i", str(tmp), "-filter_complex",
         "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[m];[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[b];"
         "[m][b]amix=inputs=2:normalize=0:duration=first[a]", "-map", "[a]", "-c:a", "pcm_s24le", str(mixed)])
    I = lufs_of(mixed)["I"]
    g = round(lufs_final - I, 2)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src_mp4), "-i", str(mixed), "-filter_complex", f"[1:a]volume={g}dB,alimiter=limit=0.89:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_mp4)])
    return {"bgm": BGM, "bgm_lufs": BGM_DB, "duck_db": DUCK_DB, "mix_I": I, "gain": g}


def make(B: dict, T: dict, S: dict, P: dict, W: Path, log=print) -> dict:
    """(판단 주인) 렌더 → W/render/final.mp4 + W/make.json."""
    from tools.calcopy import hottem_audio as ha
    from tools.calcopy import narr_video as nv
    from tools.calcopy.yanshot import plan as pl
    W = Path(W)
    R = W / "render"
    doc = W / "doc"
    info = tts(S, R, log=log)
    P = pl.retime(B, T, S, W, P, info["slices"], log=log)        # TTS 실측 길이로 블록·컷·자막 시각 다시(판단은 plan 한 곳)
    total = P["dur"]
    src_mp4 = Path(T["source"]["mp4"])
    voice = src_mp4.parent / "voice48k.wav"
    if not voice.exists():
        run(["ffmpeg", "-y", "-v", "error", "-i", str(src_mp4), "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, str(voice)])
    WAV = R / "narr_gapped.wav"
    gapped(info["wav"], P, info["slices"], WAV, total)
    Sd = jload(doc / "대본.json")
    M = jload(doc / "재료.json")
    L = [" ".join(l["text"].replace(",", "").rstrip(".") for l in Sd["final"]["lines"]) + "."]
    _, dur = nv.time_steps(nv.steps_of(L, 10, "replace"), str(WAV), lines=L, asr=False)
    if abs(dur - total) > 0.15:
        raise StageError(f"렌더 길이 {dur:.3f} ≠ 계획 {total:.3f}")
    shots = M["shots"]
    cuts_r = [{"src": x["src"], "ss": x["ss"], "src_crop": x["src_crop"], "dur": x["dur"], "plan_i": x["i"]} for x in shots]
    cuts_r[-1]["dur"] = round(dur - sum(c["dur"] for c in cuts_r[:-1]), 3)
    mat_r = {"_note": "yanshot render — 페이지 1 × shots[].cuts(재료.json t_final 그대로)", "cand_dir": M["cand_dir"],
             "shots": [{"i": 0, "full": True, "kind": "원본재편집", "src": shots[0]["src"], "ss": shots[0]["ss"], "src_crop": shots[0]["src_crop"],
                        "cuts": cuts_r, "t_final": [0.0, round(dur, 3)]}]}
    jsave(doc / "재료_render.json", mat_r)
    tl, aud = [], []
    for x in shots:
        s, e = x["t_final"]
        tl.append([round(s, 3), round(e, 3)])
        snd = {"i": len(aud), "src": x["src"], "ss": x["ss"], "plan_i": x["i"], "t_final": [round(s, 3), round(e, 3)]}
        if x.get("mute") or not x.get("audio_src"):
            snd["mute"] = True
        else:
            snd["audio_src"], snd["audio_ss"] = voice.name, x["audio_ss"]
        aud.append(snd)
    jsave(R / "audio_timeline.json", {"shots": tl, "dur": dur})
    jsave(R / "audio_materials.json", {"cand_dir": M["cand_dir"], "shots": aud})
    fr = jload(doc / "frame.json")
    ycol = next(l for l in fr["layers"] if l.get("role") == "caption")["rgb"]
    cp = Sd["captions_plan"]
    ev = []
    for j, c in enumerate(cp):
        b = cp[j + 1]["t0"] if j + 1 < len(cp) else dur
        ev.append({"kind": "emph", "text": c["text"], "rgb": ycol if c["kind"] == "나레" else [255, 255, 255], "t0": round(c["t0"], 3),
                   "dur": round(b - c["t0"], 3), "who": c["kind"]})
    win = windows(P)
    SR = dict(Sd, caption_events=ev, final=dict(Sd["final"], lines=[{"text": L[0], "note": "렌더용 한 문장 — 원문 줄은 대본.json"}]),
              render={"windows": [list(w) for w in win], "dur": dur, "tts": f"미나 1회 → 줄별 atempo {info['atempo']}"})
    jsave(doc / "대본_render.json", SR)
    plan_ = {"tteutgi": None, "frames": [{"frame": str(doc / "frame.json"), "t_end": None}], "script": str(doc / "대본_render.json"), "tts": str(WAV),
             "materials": str(doc / "재료_render.json"), "out": str(R), "bgm": None, "lufs": LUFS_NARR, "chunk": 10, "caption_mode": "replace",
             "line_asr": False}
    final = Path(nv.build(plan_))
    narr_final = R / "final_narr.mp4"
    final.replace(narr_final)
    narr_spans = [(b["t"][0], b["t"][0] + info["slices"][b["id"]][1] - info["slices"][b["id"]][0]) for b in P["blocks"] if b["kind"] == "나레"]
    gains = [0.0] * len(win)
    meas = None
    for rnd in range(2):                                   # 1회 재고 1회 다시 — 원음 창 = 나레 크기
        gg = [r for w, g in zip(win, gains) for r in ramp(w[0], min(w[1] + 0.06, dur), g)]
        ha.add_source_bed(str(narr_final), str(R / "audio_timeline.json"), str(R / "audio_materials.json"), str(WAV), str(R / "final_src.mp4"),
                          1.0, 10.0, work=str(R / "srcbed"), gap_gain=gg)
        mo = ha.measure(str(R / "final_src.mp4"), win)
        mn = ha.measure(str(R / "final_src.mp4"), narr_spans)
        nI = sum(x["lufs_I"] for x in mn if x["lufs_I"] is not None) / max(1, len([x for x in mn if x["lufs_I"] is not None]))
        meas = {"round": rnd, "gains": gains, "orig": mo, "narr_I": round(nI, 2)}
        if rnd == 0:
            gains = [round(max(-6.0, min(18.0, nI + ORIG_VS_NARR - (x["lufs_I"] if x["lufs_I"] is not None else nI))), 1) for x in mo]
            if all(abs(g) < 1.0 for g in gains):
                break
    target = (B.get("measure") or {}).get("lufs") or -15.4
    mix = bgm_mix(R / "final_src.mp4", R / "final.mp4", win, dur, target, R)
    res = {"final": str(R / "final.mp4"), "dur": round(dur_of(R / "final.mp4"), 3), "tts": info, "orig_gain": meas, "bgm": mix, "lufs_target": target,
           "windows": win, "narr_spans": narr_spans}
    jsave(W / "make.json", res)
    log(f"[make] final {res['dur']}초 · 원음 창 올림 {meas['gains']} · BGM {mix}")
    return res
