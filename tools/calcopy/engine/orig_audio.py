# -*- coding: utf-8 -*-
"""(판단 주인) 칼카피 한 편 제작기의 원음 길 — 나레 사이 원음 단독 줄(kind:"orig")과 원음 깔기(source_audio) (재미썸홈 원음 옵션, 사장님 10-25).

대본.json 줄:
  {"kind":"orig","src":"<원본 파일>","spans":[[a,b]],"text":"“번역 자막”"}   원음 단독 줄 — 나레 대신 원본 소리 [a,b]초가 그 자리에 들어간다.
      화면 컷은 재료.json 의 그 줄 컷(같은 src) — ss 는 여기서 원음 시작에 맞춘다(입 맞춤). 나레 크기에 맞춘 뒤 앞뒤 페이드.
대본.json 머리:
  "source_audio": {"keep": true, "volume": 25, "duck_db": 12}   원음 깔기 — 판단 주인 shopping_shorts.video_assemble.source_audio_settings·
      source_audio_bed 를 **부르기만** 한다(숏템메이커 렌더·캡컷과 같은 함수). 재료.json 컷 "bed": true 인 컷의 원본 소리만 깐다
      (배경음악·남의 설명 나레가 든 원본은 빼려고 — 컷마다 고른다).
칸이 없으면 아무것도 안 한다 — 예전 편은 그대로(check_fx.py same 로 확인)."""
from __future__ import annotations

from pathlib import Path

PAD = 0.12     # 원음 앞뒤 숨(초) — 나레와 붙지 않게
FADE = 0.12    # 원음 경계 페이드(초) — 규칙서 ⑥ 0.1~0.2


def has_orig(w: dict) -> bool:
    return any(l.get("orig") for l in w["lines"])


def narr_view(w: dict) -> dict:
    """나레 줄만 남긴 작품 보기(TTS·말속도·줄 시각은 이걸로) — 줄 번호는 나레 줄끼리 다시 매긴다."""
    keep = [i for i, l in enumerate(w["lines"]) if not l.get("orig")]
    new = {old: k for k, old in enumerate(keep)}
    pieces = [{**p, "line": new[p["line"]]} for p in w["pieces"] if p["line"] in new]
    return {**w, "lines": [w["lines"][i] for i in keep], "pieces": pieces}


def _voice_db(path, run_bytes) -> float:
    import numpy as np
    raw = run_bytes(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "44100", "-f", "f32le", "-"])
    a = np.frombuffer(raw, dtype=np.float32)
    k = int(0.02 * 44100)
    fr = a[: len(a) // k * k].reshape(-1, k)
    rms = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    return float(np.median(rms[rms > rms.max() - 30]))


def splice(w: dict, wn: dict, timed_n: list, narr: Path, out: Path, run, run_bytes, dur_of, log: dict):
    """나레(나레 줄만) 사이에 원음 줄 소리를 끼운 한 줄 + 전 조각 시각. 원음은 나레 목소리 크기(중앙 dB)에 맞추고 앞뒤 FADE.
    반환 (timed_all, dur, narr_all) — timed_all 은 w['pieces'] 순서."""
    starts = {}
    for t in timed_n:
        starts.setdefault(t["line"], t["t0"])
    dn = dur_of(narr)
    nspan = [(starts[k], starts[k + 1] if k + 1 in starts else dn) for k in range(len(wn["lines"]))]
    nv = _voice_db(narr, run_bytes)
    ins, flt, labs, timed, off, nk, olog = [], [], [], [], 0.0, 0, []
    tn = iter(timed_n)
    for li, line in enumerate(w["lines"]):
        mine = [p for p in w["pieces"] if p["line"] == li]
        if line.get("orig"):
            o = line["orig"]
            src = w["data"] / o["src"]
            a, b = o["spans"][0]
            clip = out / f"orig_{li}.wav"
            run(["ffmpeg", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src, "-vn", "-ac", "1", "-ar", "44100", clip])
            g = nv - _voice_db(clip, run_bytes)
            d = b - a
            ins += ["-i", clip]
            j = len(ins) // 2 - 1
            flt.append(f"[{j}:a]volume={g:.2f}dB,afade=t=in:d={FADE},afade=t=out:st={max(0, d - FADE):.3f}:d={FADE},"
                       f"adelay={int(PAD * 1000)},apad=pad_dur={PAD}[o{li}]")
            labs.append(f"[o{li}]")
            span = d + 2 * PAD
            for k, p in enumerate(mine):
                timed.append({"text": p["text"], "chars": p["chars"], "new_cut": True, "line": li,
                              "t0": round(off + span * k / len(mine), 3), "t1": round(off + span * (k + 1) / len(mine), 3)})
            line["orig_at"] = (off + PAD, a)            # 완성본에서 원음이 시작하는 초 · 원본 초(컷 입 맞춤용)
            olog.append({"line": li, "src": o["src"], "span": [a, b], "at": round(off + PAD, 3), "gain_db": round(g, 2)})
            off += span
            continue
        a, b = nspan[nk]
        ins += ["-i", narr]
        j = len(ins) // 2 - 1
        flt.append(f"[{j}:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=mono[n{li}]")
        labs.append(f"[n{li}]")
        for p in mine:
            t = next(tn)
            timed.append({**t, "line": li, "t0": round(t["t0"] - a + off, 3), "t1": round(t["t1"] - a + off, 3)})
        off += b - a
        nk += 1
    allw = out / "narr_orig.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(flt) + ";" + "".join(labs) + f"concat=n={len(labs)}:v=0:a=1[o]",
         "-map", "[o]", "-ar", "44100", "-ac", "1", allw])
    log["orig_lines"] = olog
    return timed, dur_of(allw), allw


def sync_cuts(w: dict, fps: int):
    """원음 줄 컷 = 그 원본의 원음 자리 그대로(입 맞춤) — ss 를 원음 시작에 맞추고 늘림(fit_shot)은 안 한다."""
    for c in w["cuts"]:
        li = w["pieces"][c["pieces"][0]]["line"]
        line = w["lines"][li]
        if line.get("orig") and line.get("orig_at"):
            at, a = line["orig_at"]
            if c["src"] != line["orig"]["src"] and Path(c["src"]).name != line["orig"]["src"]:
                raise ValueError(f"원음 줄 {li} 컷 원본 {c['src']} ≠ 원음 원본 {line['orig']['src']} (원음 구간 화면은 그 원본 그대로)")
            c["ss"] = round(max(0.0, a - (at - c["f0"] / fps)), 3)
            c["orig"] = True
            c["speed"] = 1.0
            if c["ss"] + c["n"] / fps > c["src_dur"] + 1e-3:
                raise ValueError(f"원음 줄 {li} 컷이 원본 끝을 넘는다 {c['src']} {c['ss']}+{c['n'] / fps:.2f}>{c['src_dur']:.2f}")


def bed(w: dict, narr: Path, out: Path, fps: int, log: dict) -> Path:
    """원음 깔기 — source_audio_settings·source_audio_bed(숏템메이커 판단 주인) 호출. 컷 하나 = 칸 하나로 컷 계획을 옮긴다."""
    from shopping_shorts import video_assemble as VA
    st = VA.source_audio_settings({"source_audio": w["S"].get("source_audio")})
    if not st:
        return narr
    plan, frames, paths = [], [], {}
    for k, c in enumerate(w["cuts"]):
        frames.append((k, c["n"]))
        if c.get("bed") and not c.get("orig"):
            paths[str(k)] = str(c["path"])
            plan.append({"idx": k, "clips": [{"video_id": str(k), "start": c["ss"], "c_src": c["n"] / fps * c.get("speed", 1.0),
                                              "play_out": c["n"] / fps, "cfr": c["n"]}]})
    d = out / "bed"
    d.mkdir(parents=True, exist_ok=True)
    mixed = VA.source_audio_bed(plan, paths, frames, str(narr), st, d, mix=True)
    log["source_audio"] = {**st, "bed_cuts": [w["cuts"][p["idx"]]["src"] for p in plan]}
    return Path(mixed)
