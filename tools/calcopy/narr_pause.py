# -*- coding: utf-8 -*-
"""나레 쉼의 주인 — 합성할 글 · 합성 뒤 쉼 깎기 · 쉼 검사 (2026-10-22 사장님 "바로 붙여서 읽어 버리니까 어색 / 근본적으로").

실측(01b 요플레, 박창수):
  줄을 마침표 없이 공백으로 이어 한 번에 합성 → 타입캐스트가 한 문장으로 읽어 쉼표 쉼을 버린다
  ("그대로라," 뒤 쉼: 이어붙임 0초 / 그 줄만 0.27초 / 줄마다 마침표 0.36초).
  줄마다 마침표를 찍어 한 번에 보내도 쉼표 둘(그대로라, / 빙그레는,)은 여전히 0초 — 여러 문장을 한 번에 보내면 쉼표를 버린다.
  → 줄마다 따로 합성하고 줄 사이 쉼은 우리가 LINE_GAP 으로 넣는다(쉼의 주인이 타입캐스트가 아니라 여기).
  합성 뒤 '0.1초 넘는 쉼은 0.07초로' 깎기 → 줄 끝 0.29~0.36초가 0.15~0.18초로 납작(쉼표·줄 끝 구분이 사라짐).
목소리와 무관(필재 때도 같았다) — 글을 보내는 꼴과 깎는 값이 원인이다.

    synth_lines(synth, lines, wdir, out) → 줄마다 통째 합성(글 같으면 재합성 안 함) → 깎기 → 버린 쉼표 쉼만 끼워 넣기(_open_commas) → LINE_GAP·END_TAIL 넣어 잇기
    synth_text(lines)            → 한 줄을 보낼 글(문장 끝 부호, 쉼표 보존)
    squeeze_af()                 → ffmpeg -af (앞뒤 무음 자르기 + 긴 쉼만 줄이기, 쉼표·줄 끝 쉼은 남김)
    pause_check(mp3, lines, words) → 쉼표·줄 끝 자리마다 실제 쉼(초), 모자란 자리 목록
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

END = ".?!~…"
EDGE = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
KEEP = 0.22        # 이보다 긴 쉼만 줄인다(쉼표 0.2~0.27초는 그대로)
LEFT = 0.2         # 줄인 쉼에 남기는 길이
COMMA_GAP = 0.16  # 쉼표 마디 사이 무음(줄 사이 LINE_GAP 보다 짧게)
END_TAIL = 0.6   # 마지막 줄 뒤 여운 — 없으면 영상이 마지막 말과 함께 뚝 끝난다(사장님 10-24 "마지막에 음성이 뚝 끊기는데")
LINE_GAP = 0.24   # 줄 사이에 넣는 무음 — 쉼표 쉼(0.2~0.3초)보다 짧으면 리듬이 거꾸로다(0.15 때 줄 끝 0.17 < 쉼표 0.29, 10-22)
MIN_PAUSE = {",": 0.08, "줄끝": 0.12}   # 검사 기준 — 이보다 짧으면 '붙여 읽음'


def synth_text(lines: list[str]) -> str:
    """줄마다 문장 끝 부호를 붙여 잇는다. 쉼표는 지우지 않는다(지우면 쉼이 사라진다)."""
    out = []
    for t in lines:
        t = t.strip()
        if t and t[-1] not in END:
            t += "."
        out.append(t)
    return " ".join(out)


def synth_lines(synth, lines: list[str], wdir, out) -> None:
    """synth(text, path) = providers.typecast_synth(...). 줄 파일·글 표식은 wdir 에 — 바뀐 줄만 다시 산다."""
    import subprocess
    from pathlib import Path
    wdir = Path(wdir); wdir.mkdir(parents=True, exist_ok=True)
    # 줄은 **통째로** 합성한다(발음) — 쉼표 마디로 쪼개 보내면 맥락이 없어 '녹음기'를 '농운기'로 읽었다(10-24 노트핀 실측: 통째 = 녹음기).
    # 대신 1.1배에서 타입캐스트가 버린 쉼표 쉼은, 그 줄 받아쓰기로 쉼표 자리 시각을 찾아 COMMA_GAP 무음을 끼워 넣는다(쉼이 이미 있으면 그대로).
    ins = []
    for i, t in enumerate(lines):
        raw, stamp = wdir / f"line_{i:02d}.mp3", wdir / f"line_{i:02d}.txt"
        text = f"{getattr(synth, 'tag', '')}|{synth_text([t])}"
        if not (raw.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == text):
            synth(synth_text([t]), str(raw))
            stamp.write_text(text, encoding="utf-8")
        wav = wdir / f"line_{i:02d}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", squeeze_af(), "-ar", "44100", "-ac", "1", str(wav)],
                       check=True, stdin=subprocess.DEVNULL)
        ins.append(_open_commas(wav, t, wdir / f"line_{i:02d}_p.wav"))
    fc, parts = [], []
    for n in range(len(ins)):
        parts.append(f"[{n}:a]")
        fc.append(f"anullsrc=r=44100:cl=mono,atrim=0:{LINE_GAP if n < len(ins) - 1 else END_TAIL}[g{n}]")
        parts.append(f"[g{n}]")
    fc.append(f"{''.join(parts)}concat=n={len(parts)}:v=0:a=1[o]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *sum((["-i", str(p)] for p in ins), []), "-filter_complex", ";".join(fc), "-map", "[o]",
                    "-c:a", "libmp3lame", "-q:a", "2", str(out)], check=True, stdin=subprocess.DEVNULL)


def _words(wav) -> list[dict]:
    """그 줄 소리의 낱말 시각(스피치매틱스, md5 캐시). 위스퍼로 넘어간 답은 쓰지 않는다."""
    import hashlib
    import json
    from pathlib import Path
    cache = Path(str(wav) + ".words.json")
    md5 = hashlib.md5(Path(wav).read_bytes()).hexdigest()
    if cache.exists():
        c = json.loads(cache.read_text(encoding="utf-8"))
        if c.get("md5") == md5:
            return c["words"]
    from tools.calcopy.engine import asr_local
    r = asr_local.transcribe(str(wav), engine="speechmatics")
    if r.get("engine") != "speechmatics":
        raise RuntimeError(f"쉼표 자리 받아쓰기가 스피치매틱스가 아님({r.get('engine')}) — 잠시 뒤 다시")
    w = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in (r.get("words") or r.get("segments") or []) if s.get("text")]
    cache.write_text(json.dumps({"md5": md5, "words": w}, ensure_ascii=False), encoding="utf-8")
    return w


def _open_commas(wav, line: str, out):
    """쉼표 자리마다: 이미 MIN_PAUSE[','] 이상 쉬면 그대로, 아니면 그 낱말 사이에 COMMA_GAP 무음을 넣는다(자른 곳 5ms 페이드)."""
    import subprocess
    from tools.calcopy.hybrid.common import silences
    if not re.search(r",(?!\d)", line):
        return wav
    ws = _words(wav)
    L = _flat_map(line)[0]
    hc, ht = [], []
    for w in ws:
        f = _flat_map(w["text"])[0]
        hc.append(f); ht += [(w["start"], w["end"])] * len(f)
    m = {a + j: b + j for a, b, n in SequenceMatcher(None, L, "".join(hc), autojunk=False).get_matching_blocks() for j in range(n)}
    sil = silences(wav, noise="-45dB", d=0.03)
    cuts = []
    for mm in re.finditer(r",(?!\d)", line):
        k = len(_flat_map(line[:mm.start()])[0])
        a0 = next((m[j] for j in range(k - 1, k - 4, -1) if j in m), None)
        b0 = next((m[j] for j in range(k, k + 3) if j in m), None)
        if a0 is None or b0 is None:
            continue
        lo, hi = ht[a0][1], ht[b0][0]
        if hi < lo:
            lo, hi = hi, lo
        near = [(a, b) for a, b in sil if b > lo - 0.1 and a < hi + 0.1]
        if any(b - a >= MIN_PAUSE[","] for a, b in near):
            continue
        cuts.append(round((near[0][0] + near[0][1]) / 2 if near else (lo + hi) / 2, 3))
    if not cuts:
        return wav
    pts = [0.0] + sorted(cuts)
    fc, parts = [], []
    for n, a in enumerate(pts):
        b = pts[n + 1] if n + 1 < len(pts) else None
        trim = f"atrim=start={a}" + (f":end={b}" if b is not None else "")
        fade = (f",afade=t=in:d=0.005" if n else "") + (f",areverse,afade=t=in:d=0.005,areverse" if b is not None else "")
        fc.append(f"[0:a]{trim},asetpts=PTS-STARTPTS{fade}[s{n}]")
        parts.append(f"[s{n}]")
        if b is not None:
            fc.append(f"anullsrc=r=44100:cl=mono,atrim=0:{COMMA_GAP}[z{n}]")
            parts.append(f"[z{n}]")
    fc.append(f"{''.join(parts)}concat=n={len(parts)}:v=0:a=1[o]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-filter_complex", ";".join(fc), "-map", "[o]", "-ar", "44100", "-ac", "1", str(out)],
                   check=True, stdin=subprocess.DEVNULL)
    return out


def squeeze_af() -> str:
    mid = f"silenceremove=stop_periods=-1:stop_duration={KEEP}:stop_threshold=-45dB:stop_silence={LEFT}"
    return f"{EDGE},areverse,{EDGE},areverse,{mid}"


def _flat_map(s: str):
    keep = [(i, c) for i, c in enumerate(s) if re.match(r"[가-힣A-Za-z0-9]", c)]
    return "".join(c for _, c in keep), [i for i, _ in keep]


def breaks(lines: list[str]) -> list[dict]:
    """쉼이 있어야 할 자리 = 줄 안 쉼표 + 줄 끝(마지막 줄 제외). flat = 글자만 센 위치(그 앞 글자까지)."""
    out, base = [], 0
    for li, t in enumerate(lines):
        flat, _ = _flat_map(t)
        for m in re.finditer(",", t):
            k = len(_flat_map(t[:m.start()])[0])
            if 0 < k < len(flat):
                out.append({"line": li, "kind": ",", "flat": base + k, "at": t[max(0, m.start() - 6):m.start() + 7]})
        base += len(flat)
        if li < len(lines) - 1:
            out.append({"line": li, "kind": "줄끝", "flat": base, "at": t[-6:] + " / " + lines[li + 1][:6]})
    return out


def pause_check(mp3, lines: list[str], words: list[dict]) -> dict:
    """words = 받아쓰기 낱말 [{start,end,text}]. 쉼 자리마다 앞 낱말 시작~뒤 낱말 끝 안의 가장 긴 무음을 잰다."""
    from tools.calcopy.hybrid.common import silences
    S = _flat_map(" ".join(lines))[0]
    hc, ht = [], []
    for w in words:
        f = _flat_map(w["text"])[0]
        hc.append(f); ht += [(w["start"], w["end"])] * len(f)
    H = "".join(hc)
    m = {}
    for a, b, n in SequenceMatcher(None, S, H, autojunk=False).get_matching_blocks():
        for j in range(n):
            m[a + j] = b + j
    sil = silences(mp3, noise="-45dB", d=0.03)
    rows, bad = [], []
    for br in breaks(lines):
        k = br["flat"]
        a0 = next((m[j] for j in range(k - 1, k - 4, -1) if j in m), None)   # 받아쓰기가 글자를 잘못 들은 자리(두 곳→두고)는 가까운 글자로
        b0 = next((m[j] for j in range(k, k + 3) if j in m), None)
        if a0 is None or b0 is None:
            rows.append({**br, "pause": None}); bad.append(rows[-1]); continue
        lo, hi = ht[a0][0], ht[b0][1]
        p = max([min(b, hi) - max(a, lo) for a, b in sil if b > lo and a < hi] or [0.0])
        row = {**br, "pause": round(max(p, 0.0), 3)}
        rows.append(row)
        if row["pause"] < MIN_PAUSE[br["kind"]]:
            bad.append(row)
    return {"rows": rows, "bad": bad, "ok": not bad and all(r["pause"] is not None for r in rows)}
