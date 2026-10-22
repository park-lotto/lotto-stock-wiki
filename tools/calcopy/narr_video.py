# -*- coding: utf-8 -*-
"""나레 있는 칼카피 한 편 — 틀 여러 장(훅 카드·본문) + 누적형 자막 + 가변 그림 칸 + TTS 나레 + BGM (관제 097, 2026-10-16).

remake_video.py(나레 없는 '원음+자막')의 짝. yummyknow rGFXQlS9Cp4 꼴:
  - 틀: 구간마다 다른 frame.json (0~훅 끝 = 훅 카드, 그 뒤 = 본문 게시글). 구간마다 scene_style.compose 로 그리고 잇는다.
  - 자막: 나레 문장을 한 줄 조각(약 14자)으로 나눠 1줄 → 1줄+2줄(줄바꿈 \\n) → 새 1줄 … (누적형). 렌더러는 lines>1 자막을 pre-line 으로 그린다.
  - 시각: TTS 한 파일의 말 구간(silencedetect)에 글자 수 비례로 놓고, 조각 경계는 가까운 쉼(±0.4초)에 붙인다.
  - 그림 칸: 재료.json shots[i].box_w(기본 750px)로 폭을 맞춰 창 맨 위 가운데에 놓고 나머지는 흰 바탕(원본: 컷마다 크기 다름).
  - 컷: 새 1줄 조각이 시작할 때(원본 컷=자막교체 1.0). 한 페이지 안에서 더 바꾸려면 재료 shots[i].cuts(판단 주인 shot_pieces).

    PYTHONUTF8=1 py tools/calcopy/narr_video.py <plan.json>
plan = {"tteutgi","frames":[{"frame","t_end"}...],"script","tts","materials","out","bgm","bgm_ratio","lufs","chunk"}
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import bgm_lib, scene_style, video_assemble as va  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402
from tools.calcopy.remake_video import _lufs, sfx_list, title_text  # noqa: E402


# ── 자막 조각 ─────────────────────────────────────────────────────────────
def chunk_sentence(s: str, n: int = 14) -> list[str]:
    """문장 → 한 줄 조각들(공백 제외 n자 안팎, 쉼표 뒤에서 먼저 끊는다). 원본 한 줄 중앙 ≈ 10~14자(OCR 실측)."""
    words, out, cur = s.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if cur and len(cand.replace(" ", "")) > n:
            out.append(cur); cur = w
        else:
            cur = cand
        if cur.endswith(",") and len(cur.replace(" ", "")) >= n * 0.6:
            out.append(cur); cur = ""
    if cur:
        out.append(cur)
    cap = n + CHUNK_SLACK
    if len(out) > 1 and _len(out[-1].rstrip(",.?!")) <= 5:   # '있음.' 처럼 짧은 꼬리는 혼자 두지 않는다(혼자 뜨면 어색 — 10-16 2판)
        if _len(out[-2]) + _len(out[-1]) <= cap:
            tail = out.pop()
            out[-1] = out[-1] + " " + tail
        else:   # 붙이면 상한을 넘으면 앞 조각 끝 낱말을 꼬리로 넘긴다(10-16 썰풀다: --chunk 10 에 16자 조각)
            prev, tail = out[-2].split(), out[-1].split()
            while len(prev) > 1 and _len(" ".join(tail).rstrip(",.?!")) <= 5 and _len(" ".join([prev[-1]] + tail)) <= cap:
                tail.insert(0, prev.pop())
            out[-2], out[-1] = " ".join(prev), " ".join(tail)
    out = _fix_dangling(out, cap=cap)
    return [o.rstrip(",") for o in out]


CHUNK_SLACK = 3   # 조각 상한 = n + 이것. 붙이기(꼬리·꾸밈 낱말·짧은 조각)도 이 상한을 넘지 않는다 — 판단 주인 chunk_sentence


def _len(t: str) -> int:
    return len(t.replace(" ", ""))


# 뒤 낱말을 꾸미는 한 낱말(관형사·부사) — 조각 끝에 홀로 남으면 다음 조각으로 넘긴다
# (10-16 3호: '처음엔 사양하던 그 / 팬은…' 이 '그 팬'을 갈랐고, '퍽을 또' 가 0.4초만 떴다)
DANGLE = {"그", "이", "저", "또", "더", "한", "잘", "좀", "꼭", "딱", "다", "그런", "이런", "저런", "아주", "너무", "정말"}


def _fix_dangling(out: list[str], short: int = 3, cap: int | None = None) -> list[str]:
    """cap = 붙인 결과 상한(공백 제외 글자) — 넘으면 안 붙인다(chunk_sentence 가 n + CHUNK_SLACK 을 준다)."""
    out = list(out)
    fits = (lambda a, b: True) if cap is None else (lambda a, b: _len(a) + _len(b) <= cap)
    for i in range(len(out) - 1):
        ws = out[i].split()
        while len(ws) > 1 and ws[-1] in DANGLE and fits(ws[-1], out[i + 1]):
            out[i + 1] = ws.pop() + " " + out[i + 1]
        out[i] = " ".join(ws)
    i = 0
    while i < len(out) and len(out) > 1:   # 3자 이하 조각은 혼자 두지 않는다 — 다음(넘치면·없으면 앞) 조각에 붙인다
        if _len(out[i].rstrip(",.?!")) <= short:
            if i + 1 < len(out) and fits(out[i], out[i + 1]):
                out[i + 1] = out[i] + " " + out[i + 1]
            elif i > 0 and fits(out[i - 1], out[i]):
                out[i - 1] = out[i - 1] + " " + out[i]
            else:
                i += 1
                continue
            out.pop(i)
            continue
        i += 1
    return out


def steps_of(sentences: list[str], n: int = 14, mode: str = "accumulate", chunks_of=None) -> list[dict]:
    """mode=replace(교체형: 조각마다 새 1줄, 컷=새 문장 — 썰풀다 틀 B 1초 교체) 이면 아래 누적형 대신 이것.
    chunks_of(문장, n) = 문장 → 한 줄 조각들(기본 chunk_sentence). preset_make 가 대본의 '/' 줄바꿈(벤치 줄 그대로)을 쓰려고 넘긴다."""
    if mode == "replace":
        out = []
        subs = [(li, x) for li, line in enumerate(sentences) for x in re.split(r"(?<=[?.!])\s+", line.strip()) if x]
        for si, (li, s) in enumerate(subs):
            for k, c in enumerate(chunk_sentence(s, n)):
                out.append({"text": c, "chars": len(c.replace(" ", "")), "new_cut": k == 0, "sent": si, "line": li})
        return out
    return _steps_accumulate(sentences, n, chunks_of)


def _steps_accumulate(sentences: list[str], n: int = 14, chunks_of=None) -> list[dict]:
    """누적형 단계: 조각 짝마다 [1줄] → [1줄\\n2줄]. 문장이 바뀌면 새로. 반환 [{text, chars(새로 읽는 글자), new_cut}]"""
    steps = []
    subs = [(li, x) for li, line in enumerate(sentences) for x in re.split(r"(?<=[?.!])\s+", line.strip()) if x]   # 한 줄에 문장 여럿이면 문장마다 새로
    for si, (li, s) in enumerate(subs):
        ch = (chunks_of or chunk_sentence)(s, n)
        for k in range(0, len(ch), 2):
            a = ch[k]
            steps.append({"text": a, "chars": len(a.replace(" ", "")), "new_cut": True, "sent": si, "line": li})
            if k + 1 < len(ch):
                steps.append({"text": a + "\n" + ch[k + 1], "chars": len(ch[k + 1].replace(" ", "")), "new_cut": False, "sent": si, "line": li})
    return steps


def speech_segments(audio: str, noise="-38dB", d=0.12) -> tuple[list[tuple[float, float]], float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", audio, "-af", f"silencedetect=noise={noise}:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio],
                               capture_output=True, text=True).stdout.strip())
    sil = sorted(zip(st, en + [dur] * (len(st) - len(en))))
    segs, t = [], 0.0
    for a, b in sil:
        if a > t + 0.05:
            segs.append((t, a))
        t = max(t, b)
    if dur > t + 0.05:
        segs.append((t, dur))
    return segs, dur


def _place(steps: list[dict], segs: list[tuple[float, float]], snap: float, first: float, end: float) -> list[float]:
    """구간 [first, end) 안에서 조각 시작 — 말 구간(segs)에 글자 수 비례로 놓고 가까운 말 구간 시작(±snap)에 붙인다. 첫 조각 = first."""
    loc = [(max(a, first), min(b, end)) for a, b in segs if b > first and a < end] or [(first, end)]
    total_speech = sum(b - a for a, b in loc)
    total_chars = sum(s["chars"] for s in steps) or 1

    def at(frac):   # 말 시간 비율 → 실제 시각
        x = frac * total_speech
        for a, b in loc:
            if x <= b - a:
                return a + x
            x -= b - a
        return loc[-1][1]
    starts, c = [], 0
    for s in steps:
        t = at(c / total_chars)
        near = min((a for a, _ in loc), key=lambda a: abs(a - t))
        starts.append(near if abs(near - t) <= snap else t)
        c += s["chars"]
    if starts:
        starts[0] = first
    for i in range(1, len(starts)):            # 순서 보장(붙이기로 뒤집히지 않게)
        starts[i] = max(starts[i], starts[i - 1] + 0.3)
    return starts


def tts_transcript(audio: str, ask=None) -> tuple[list[dict] | None, str]:
    """나레 받아쓰기(구절 start/end/text) — 무료 제미나이 1회(gemini_free.ask, 지시문 = transcribe_free.P), 결과는 <audio>.asr.json 캐시
    (같은 파일 md5 면 재호출 0). 돌려주는 값 (구절 목록|None, 출처/실패 이유)."""
    import hashlib
    ap = Path(audio)
    md5 = hashlib.md5(ap.read_bytes()).hexdigest()
    cache = ap.with_name(ap.name + ".asr.json")
    if cache.exists():
        try:
            c = json.loads(cache.read_text(encoding="utf-8"))
            if c.get("md5") == md5 and isinstance(c.get("segments"), list):
                seg, how = _fit_asr_len(c["segments"], audio)
                return seg, f"캐시 {cache.name}{how}"
        except ValueError:
            pass
    if ask is None and os.environ.get("CALCOPY_CUSTOMER_MODE") == "1":
        # 고객 PC(관제 234): 서버 무료 제미나이 키 묶음(gemini_free·gemini_keys)은 고객 묶음 밖 — 동봉 위스퍼(asr_local)로 받아쓴다.
        #   10-20 라이브 시험 추적: 나레 시간 맞추기가 gemini_keys 를 불러 고객 PC 에서 멈출 자리였다
        from tools.calcopy.engine import asr_local
        r = asr_local.transcribe(str(ap))
        seg = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in r.get("segments") or [] if s.get("text")]
        if not seg:
            return None, "받아쓰기 실패: 로컬 위스퍼 빈 답"
        cache.write_text(json.dumps({"md5": md5, "model": r.get("engine"), "segments": seg}, ensure_ascii=False, indent=1), encoding="utf-8")
        seg, how = _fit_asr_len(seg, audio)
        return seg, f"받아쓰기 {r.get('engine')}{how}"
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask
    from tools.calcopy.transcribe_free import P
    tmp = ap.with_name(ap.stem + "_asr16k.mp3")
    va._run_ffmpeg(["ffmpeg", "-y", "-i", str(ap), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(tmp)])
    data = tmp.read_bytes(); tmp.unlink()
    d, err = ask([(data, "audio/mp3")], P, "tts_asr")
    seg = [x for x in ((d or {}).get("segments") or []) if isinstance(x, dict) and x.get("text") is not None and x.get("start") is not None]
    if not seg:
        return None, f"받아쓰기 실패: {err or '빈 답'}"
    cache.write_text(json.dumps({"md5": md5, "model": (d or {}).get("_model"), "segments": seg}, ensure_ascii=False, indent=1), encoding="utf-8")
    seg, how = _fit_asr_len(seg, audio)
    return seg, f"받아쓰기 {(d or {}).get('_model')}{how}"


def _fit_asr_len(seg: list[dict], audio: str) -> tuple[list[dict], str]:
    """제미나이 받아쓰기 시각이 소리 길이보다 5% 넘게 길면(시각이 고르게 늘어남 — 썰템쇼 작품1 30.6초 vs 실제 25.7초, 줄 머리를
    소리 길이 비율로 줄이면 쉼 자리와 ±0.3초 안) 소리 길이 비율로 줄인다. 캐시 원본은 그대로 둔다."""
    end = max(float(x.get("end") or x.get("start") or 0) for x in seg)
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio], capture_output=True, text=True)
    dur = float(r.stdout.strip() or 0)
    if not dur or end <= dur * 1.05:
        return seg, ""
    k = dur / end
    return [{**x, "start": round(float(x["start"]) * k, 3), **({"end": round(float(x["end"]) * k, 3)} if x.get("end") is not None else {})} for x in seg],         f" · 시각 ×{k:.3f}(받아쓰기 끝 {end:.1f}초 > 소리 {dur:.1f}초)"


def _norm_ko(t: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t or "").lower()


ASR_KEY_CHARS = (8, 6, 5, 4)   # 줄 머리 정규화 글자 수 — 긴 것부터 찾고 못 찾으면 줄인다


def asr_line_starts(lines: list[str], segs: list[dict]) -> list[float | None]:
    """(줄 시작의 1순위) 받아쓰기 구절을 이어 붙인 글에서 줄 k 머리(정규화 앞 8→4자)를 앞 줄 뒤부터 찾는다.
    찾은 글자가 구절 안 몇 번째인지로 그 구절 start~end 를 글자 비례해 시각을 낸다. 못 찾은 줄은 None."""
    text, owner = "", []
    for i, sg in enumerate(segs):
        z = _norm_ko(sg.get("text"))
        text += z
        owner += [(i, j, len(z)) for j in range(len(z))]
    out, pos = [0.0], 0
    for line in lines[1:]:
        z = _norm_ko(line)
        hit = None
        for n in ASR_KEY_CHARS:
            if len(z) >= n:
                k = text.find(z[:n], pos)
                if k >= 0:
                    hit = k
                    break
        if hit is None:   # 머리 1~2글자만 잘못 들은 줄(작품1 '후훗'→'푸훗', '까 보면'→'보면') — 그 글자를 건너뛴 5자로 한 번 더
            for skip in (1, 2):
                if len(z) >= skip + 5:
                    k = text.find(z[skip:skip + 5], pos)
                    if k >= 0 and (pos == 0 or k - skip >= pos - 1):
                        hit = max(pos, k - skip)
                        break
        if hit is None and len(z) >= 3:   # 마지막: 머리 3자('성분표') — 앞 줄 머리 뒤 20자 안에서만(멀리 있는 같은 말에 붙지 않게)
            k = text.find(z[:3], pos, pos + 20 + len(z))
            hit = k if k >= 0 else None
        if hit is None:
            out.append(None)
            continue
        i, j, L = owner[hit]
        a, b = float(segs[i]["start"]), float(segs[i].get("end") or segs[i]["start"])
        out.append(round(a + (b - a) * j / max(1, L), 3))
        pos = hit + 1
    return out


BREAK_NEAR = 0.5   # 줄 끝 쉼이 글자 비례 예상(말 시간)에서 이보다 멀면 '그 경계엔 쉼 없음' — 방구석처럼 TTS 쉼을 0.07초로 줄인 나레(10-16)


ASR_WORD_DUR, ASR_SNAP_WORD = 0.6, 0.15   # 구절 길이 중앙값이 0.6초 밑 = 낱말 단위 → 쉼에 붙이는 거리 0.15초
ASR_SNAP = 1.2   # 받아쓰기 줄 시작 → 가까운 쉼 끝(-38dB/0.08초)에 붙이는 거리. 제미나이 구절 시각은 거칠다
#   (10-16 방구석 3편 narr_final2: '사실…' 구절 시작 7.03 vs 실제 쉼 끝 8.13 — 받아쓰기는 '어느 쉼인가'를 정하고 시각은 쉼이 정한다)


def line_starts(audio: str, lines: list[str], segs: list[tuple[float, float]], expected: list[float] | None = None, log=print,
                asr: bool = True, ask=None) -> list[float]:
    """(판단 주인) 대본 줄마다 시작 — 줄 끝 쉼(hottem_audio.break_points) 다음 첫 말 구간 시작. 줄 0 = 0.
    10-16 핫템 HONOR 실측: 전체 글자 비례로 놓으면 줄 시작이 실제 말보다 0.46~0.75초 늦었다(자막·컷 늦음).
    ★그 경계 근처(예상 말 시간 ±BREAK_NEAR)에 쉼이 없으면 그 경계만 글자 비례 예상(expected[k])으로 되돌리고 [경보]
      (10-16 방구석 3편: 쉼을 0.07초로 줄인 나레라 엉뚱한 쉼에 붙어 훅이 3.71초까지 늘었다 — 실제 2줄 시작 1.6초)."""
    from tools.calcopy import hottem_audio as ha
    # ★1순위 = 받아쓰기 정렬(10-16 조율자: 쉼 방식은 핫템·방구석에서 세 번 어긋났다 — 쉼표 쉼에 붙음)
    A = [None] * len(lines)
    snap_max = ASR_SNAP
    if asr:
        tr, why = tts_transcript(audio, ask)
        if tr and sorted(float(x.get("end") or x["start"]) - float(x["start"]) for x in tr)[len(tr) // 2] < ASR_WORD_DUR:
            # 낱말 단위 받아쓰기(스피치매틱스 words)는 시각이 정확하다 — 쉼에 붙이는 거리를 줄인다(10-22 썰템홈샷 02: 줄 사이 쉼이 없어
            #   24.57초 '이 얘기 듣고,' 줄이 안쪽 쉼표 쉼 25.06초로 끌려가 자막·컷 0.49초 늦음)
            snap_max = ASR_SNAP_WORD
        if tr:
            A = asr_line_starts(lines, tr)
            miss = [k for k in range(1, len(lines)) if A[k] is None]
            if miss:
                log(f"[경보] 받아쓰기에서 줄 {miss} 머리를 못 찾음 — 그 줄만 쉼 방식→글자 비례 ({why})")
        else:
            log(f"[경보] {why} — 전 줄 쉼 방식→글자 비례로")
    pauses = [(e, e - a) for a, e in ha._silences(audio, "-38dB", 0.08)] if any(x is not None for x in A[1:]) else []
    out = [0.0]
    for k, (mid, dist) in enumerate(ha.break_points(audio, lines)):
        if A[k + 1] is not None:
            t = A[k + 1]
            # 가까운 쉼 끝 — 거리에서 쉼 길이를 빼서 고른다(줄 사이 쉼은 문장 안 쉼보다 길다. 10-18 작품1: 0.40 떨어진 0.22초 쉼(줄 경계)과
            #   0.398 떨어진 0.16초 쉼('까 보면,' 안)이 거의 같아 안쪽 쉼에 붙어 자막이 0.8초 늦었다)
            ends = [(e, ln) for e, ln in pauses if e > out[-1] + 0.3]
            near = min(ends, key=lambda x: abs(x[0] - t) - x[1], default=(t, 0))[0]
            out.append(near if abs(near - t) <= snap_max else t)
            continue
        anchored = next((a for a, _ in segs if a >= mid - 1e-3), mid) if mid is not None else None
        if (dist > BREAK_NEAR or anchored is None) and expected:
            log(f"[경보] 줄 {k + 1} 시작: 예상 근처(±{BREAK_NEAR}초 말 시간)에 쉼 없음(가장 가까운 쉼 {mid}초, 거리 {dist}) → 글자 비례 {expected[k + 1]:.3f}초")
            out.append(expected[k + 1])
        else:
            out.append(anchored)
    return out


def time_steps(steps: list[dict], audio: str, snap: float = 0.4, lines: list[str] | None = None, log=print, asr: bool = True, ask=None) -> tuple[list[dict], float]:
    """조각 시각. lines(대본 줄)를 주면 줄 시작을 실제 말 시작(line_starts)에 고정하고 줄 안에서만 글자 비례.
    안 주면(또는 한 줄) 전체를 글자 비례로(종전)."""
    segs, dur = speech_segments(audio)
    if lines and len(lines) > 1 and steps and all("line" in s for s in steps):
        g = _place(steps, segs, snap, 0.0, dur)   # 글자 비례(종전) — 쉼 없는 경계의 되돌림 값
        exp = [next(t for t, s in zip(g, steps) if s["line"] == li) if any(s["line"] == li for s in steps) else 0.0 for li in range(len(lines))]
        W = line_starts(audio, lines, segs, exp, log, asr, ask) + [dur]
        for li in range(1, len(W) - 1):   # 순서 보장(받아쓰기·쉼·비례가 섞여도 뒤집히지 않게)
            W[li] = max(W[li], W[li - 1] + 0.3)
        starts = []
        for li in range(len(lines)):
            st = [s for s in steps if s["line"] == li]
            starts += _place(st, segs, snap, W[li], W[li + 1])
        order = [s for li in range(len(lines)) for s in steps if s["line"] == li]
    else:
        starts, order = _place(steps, segs, snap, 0.0, dur), steps
    starts[0] = 0.0
    out = [{**s, "t0": round(starts[i], 3), "t1": round(starts[i + 1] if i + 1 < len(starts) else dur, 3)} for i, s in enumerate(order)]
    return out, dur


# ── 재료(그림 칸) ──────────────────────────────────────────────────────────
# ── 꾸밈 얹기(빨간 원·이모지 스티커) — 원본 자리·크기를 캔버스(1080×1920) 좌표로 받는다 (관제 097, 10-16 3호) ──
def overlay_png(ov: dict, dst: Path) -> Path:
    """ov.kind = red_circle(지름 size·두께 stroke·색 color) / emoji(글자 emoji, 한 변 size). 투명 PNG."""
    from PIL import Image, ImageDraw, ImageFont
    size = int(ov.get("size", 170))
    if ov["kind"] == "red_circle":
        sw = int(ov.get("stroke", 6)); pad = sw
        im = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([pad, pad, pad + size, pad + size], outline=tuple(ov.get("color", (232, 22, 26))) + (255,), width=sw)
    elif ov["kind"] == "emoji":
        font = ImageFont.truetype(ov.get("font", "C:/Windows/Fonts/seguiemj.ttf"), size)   # Segoe UI Emoji = 색 벡터(COLR) — 제 크기로 그려 흐림 없음
        im = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((size, size), ov["emoji"], font=font, embedded_color=True, anchor="mm")
        im = im.crop(im.getbbox()).resize((size, size), Image.LANCZOS)
    else:
        raise SystemExit(f"모르는 꾸밈 {ov['kind']}")
    im.save(dst)
    return dst


def _lerp_expr(keys, idx):
    """[(t, x, y)…] 시각별 중심 → ffmpeg 식(사이는 직선으로 잇고 끝은 멈춤). idx 1=x 2=y. 원본 빨간 원이 퍽을 따라 움직인다."""
    if len(keys) == 1:
        return f"{keys[0][idx]}"
    e = f"{keys[-1][idx]}"
    for (t0, *p0), (t1, *p1) in reversed(list(zip(keys, keys[1:]))):
        v0, v1 = p0[idx - 1], p1[idx - 1]
        e = f"if(lt(t,{t1}),{v0}+({v1}-{v0})*(t-{t0})/{t1 - t0},{e})"
    return f"if(lt(t,{keys[0][0]}),{keys[0][idx]},{e})"


def still_move(src, src_crop, ar, dur: float, move) -> str:
    """(판단 주인) 그림 파일 컷의 움직임 — 사장님 10-18 "정지 장면이 많다, 이미지를 쓰려면 확대 효과를 주든지 계속 움직이게".
    move = "in"(천천히 다가감) · "out"(물러남) · "left"/"right"(살짝 확대한 채 옆으로 흐름) 또는 {"kind":…, "zoom":1.2}.
    src_crop·ar 로 자른 뒤의 그림 크기 그대로 내보내므로 뒤 채우기(cover·box·contain)는 그대로 돈다. 2배로 키운 뒤 움직여 픽셀 떨림을 줄인다."""
    from PIL import Image
    mv = move if isinstance(move, dict) else {"kind": move}
    kind, z1 = mv.get("kind", "in"), float(mv.get("zoom", 1.2))
    iw, ih = Image.open(src).size
    if src_crop:
        iw, ih = src_crop[2], src_crop[3]
    if ar:
        iw, ih = min(iw, ih * ar), min(ih, iw / ar)
    ow, oh = int(iw) // 2 * 2, int(ih) // 2 * 2
    n = max(1, round(dur * FPS))
    p = f"min(on/{n},1)"
    z = {"in": f"1+{z1 - 1:.4f}*{p}", "out": f"{z1:.4f}-{z1 - 1:.4f}*{p}"}.get(kind, f"{z1:.4f}")
    x = {"left": f"(iw-iw/zoom)*(1-{p})", "right": f"(iw-iw/zoom)*{p}"}.get(kind, "(iw-iw/zoom)/2")
    return f"scale={ow * 2}:{oh * 2},zoompan=z='{z}':x='{x}':y='(ih-ih/zoom)/2':d=1:s={ow}x{oh}:fps={FPS},"


def box_top(by: int, min_y: int, anchor: bool = True, cap_top: int | None = None) -> int:
    """그림 칸 윗변. 기본(anchor) = 자막 바로 밑에 붙임(10-16 조율자: 게시글형 y1185 칸이 빈칸 위에 떠 아마추어처럼 보였다).
    ★자막이 그림 **안에서 시작하는** 틀(자막 윗변 cap_top > 칸 윗변 — 얜샷템 창 y420·자막 y1206, 영상 위에 자막이 겹친다)은 원본 자리 그대로:
    10-20 회원 실시험에서 무조건 끌어내려 창 1080 중 870px 가 흰 바탕이 됐다. anchor=False = 자막 밑으로만 밀어냄(겹치지 않게)."""
    if not anchor:
        return max(by, min_y)
    if cap_top is not None and cap_top > by:
        return by
    return min_y


def shot_clip(src, ss, dur, win, box_w, full, out, ar=None, box=None, fit="cover", min_y=0, src_crop=None, loop=False, anchor=True, overlays=None,
              frames=None, move=None, cap_top=None):
    """창(win = video 층) 크기 캔버스: full=True 면 꽉 채움(cover), 아니면 흰 바탕 위 box_w 폭 그림을 맨 위 가운데.
    ar = 가로/세로 비율로 먼저 가운데 자르기(가로 소스를 원본 그림 칸처럼 세로로). src 가 그림 파일이면 dur 동안 멈춘 그림."""
    W, H = 1080, 1920
    w, h = win["w"], win["h"]
    top = (H - h) // 2
    pre = f"crop='min(iw,ih*{ar})':'min(ih,iw/{ar})'," if ar else ""
    if src_crop:   # 소스에서 먼저 잘라 낼 [x,y,w,h](소스 픽셀) — 남의 채널 그래픽(표 상자 등)을 화면 밖으로(10-16 조율자 조건)
        x, y, w_, h_ = src_crop
        pre = f"crop={w_}:{h_}:{x}:{y}," + pre
    if box:   # 원본 그 컷의 그림 칸 [x,y,w,h](캔버스 좌표, 뜯기 cuts.picture_boxes) — cover=꽉 채워 자름 / contain=다 보이게 줄임
        bx, by, bw, bh = box
        by = box_top(by, min_y, anchor, cap_top)
        bh = min(bh, win["y"] + win["h"] - by)
        oy = max(0, by - win["y"])
        if fit == "contain":
            core = (f"scale={bw}:{bh}:force_original_aspect_ratio=decrease,crop='min(iw,{bw})':'min(ih,{bh})',"   # 반올림으로 1px 넘치면 pad 가 실패했다
                    f"pad={bw}:ih:(ow-iw)/2:0:white")
        else:
            core = f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh}"
        vf = f"{core},pad={w}:{h}:{bx}:{oy}:white,pad={W}:{H}:0:{top}:white,setsar=1,fps=30"
    elif full:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},pad={W}:{H}:0:{top}:white,setsar=1,fps=30"
    else:
        bh = h - 16
        vf = (f"scale={box_w}:{bh}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:8:white,"
              f"pad={W}:{H}:0:{top}:white,setsar=1,fps=30")
    still = Path(src).suffix.lower() in (".png", ".jpg", ".jpeg")
    if still and move:
        pre += still_move(src, src_crop, ar, frames / FPS if frames else dur, move)
    # loop = 짤처럼 짧은 소스가 컷보다 짧으면 되풀이(짤 3초 < 컷 3.9초 — 10-16 4판)
    inp = ["-loop", "1", "-framerate", str(FPS), "-i", str(src)] if still else ([*(["-stream_loop", "-1"] if loop else []), "-ss", f"{ss:.3f}", "-i", str(src)])
    # ★색 범위 통일: 그림 파일(png=rgb·jpg=yuvj pc)·영상(tv)이 섞여 이으면 장면 통째가 회색(흰 255→235)이 됐다(10-16 2판) → 전부 tv
    # ★색 표식 통일(10-20 샥탬 9편): 컷마다 표식이 다르면(bt709 / 없음 / smpte170m) -c copy 로 이은 재료에서 compose 가 컷 경계에
    #   제목·자막 층을 몇 프레임 빠뜨리고 프레임도 줄었다(시험 90→87장·제목 빠짐 1장) → 컷 클립은 전부 bt709·tv 표식(픽셀 값은 그대로 — 표식만,
    #   완성본은 원래 bt709 로 나가 옛 픽셀과 같다). 판단 한 곳 = 이 tail(컷 클립을 만드는 곳은 shot_clip 하나).
    tail = ",scale=out_range=tv,format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709"
    if not overlays:
        va._run_ffmpeg(["ffmpeg", "-y", *inp, *_len_args(dur, frames), "-vf", pre + vf + tail, "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-an",
                        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])
        return out
    # 꾸밈: 캔버스 좌표 중심 at=[x,y] 또는 path=[[t,x,y]…](컷 안 시각), t=[보이기 시작, 끝](컷 안 시각)
    fc, ins, last = f"[0:v]{pre}{vf}[b0]", [], "b0"
    for k, ov in enumerate(overlays):
        png = overlay_png(ov, Path(out).with_name(Path(out).stem + f"_ov{k}.png"))
        ins += ["-loop", "1", "-i", str(png)]
        keys = [tuple(p) for p in ov["path"]] if ov.get("path") else [(0.0, *ov["at"])]
        # ★좌표 = 완성본 캔버스(1080×1920). 이 컷 캔버스는 창을 가운데(top)에 두고, compose 가 가운데 창 높이만 잘라 창 y 에 놓는다
        #   → 컷 y = 완성본 y − 창 y + top (10-16 시험: 바꾸기 전엔 얹은 것이 창 y−top = 173px 아래로 갔다)
        keys = [(t, x, y - win["y"] + top) for t, x, y in keys]
        a, b = ov.get("t", [0.0, dur])
        fc += (f";[{k + 1}:v]format=rgba[o{k}];[{last}][o{k}]overlay=x='{_lerp_expr(keys, 1)}-overlay_w/2':y='{_lerp_expr(keys, 2)}-overlay_h/2'"
               f":enable='between(t,{a},{b})':eval=frame[b{k + 1}]")
        last = f"b{k + 1}"
    fc += f";[{last}]{tail.lstrip(',')}[v]"
    va._run_ffmpeg(["ffmpeg", "-y", *inp, *ins, "-filter_complex", fc, "-map", "[v]", *_len_args(dur, frames), "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-an",
                    "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])
    return out


# ── 페이지 안 다중 컷 — 재료.json shots[i].cuts (관제 097, 10-16 바나나 2편: build_combos.py 가 밖에서 미리 잇던 일을 안으로) ──
# shots[i].cuts = [{src, ss, dur, (src_crop·ar·fit·kind 덮어쓰기)}, …] — 그 컷(자막 페이지) 안에서 순서대로 이어 붙인다.
# 칸(box·box_w·full·anchor)은 컷 하나 = 그 shot 값을 같이 쓴다. 마지막 토막은 페이지 끝까지 늘어난다(dur 은 최소 길이가 아니라 '여기서 바꾼다').
FPS = 30
CUT_KEYS = ("src", "ss", "src_crop", "ar", "fit", "kind", "move")


def shot_pieces(sh: dict, off: float, dur: float) -> list[dict]:
    """(판단 주인) 컷 하나(sh)의 [off, off+dur) 구간을 토막으로 → [{"sh": 토막 재료(shot 값 + cut 덮어쓰기), "ss": 소스 시작초,
    "t": 컷 안 시작초(off 기준 아님 — sh 시작 기준), "dur": 길이}]. cuts 없으면 토막 하나(sh.ss + off). 토막 경계는 1/FPS 격자에 맞춘다
    (토막마다 따로 인코딩하므로 격자 밖 경계는 잇는 동안 프레임이 밀린다)."""
    cuts = sh.get("cuts")
    if not cuts:
        return [{"sh": sh, "ss": float(sh.get("ss", 0)) + off, "t": off, "dur": dur}]
    end = off + dur
    starts, t = [], 0.0
    for c in cuts:
        starts.append(round(t * FPS) / FPS)
        t += float(c["dur"])
    out = []
    for k, c in enumerate(cuts):
        a = starts[k]
        b = starts[k + 1] if k + 1 < len(cuts) else end   # 마지막 토막 = 페이지 끝까지
        a2, b2 = max(a, off), min(b, end)
        if b2 - a2 <= 0.5 / FPS:
            continue
        piece = {**{kk: v for kk, v in sh.items() if kk != "cuts"}, **{kk: c[kk] for kk in CUT_KEYS if kk in c}}
        if "src_crop" not in c:   # 토막이 자기 소스를 가지면 shot 의 src_crop 은 그 소스 픽셀이 아니다
            piece.pop("src_crop", None)
        out.append({"sh": piece, "ss": float(c.get("ss", 0)) + (a2 - a), "t": a2, "dur": b2 - a2})
    if not out:
        raise SystemExit(f"cuts 토막이 [{off:.2f},{end:.2f}) 구간에 하나도 안 걸림: {cuts}")
    return out


def frame_at(t: float) -> int:
    """(판단 주인) 조각 시각(틀 구간 시작 기준 초) → 프레임 번호. 반올림(0.5 올림) — ffmpeg -t 가 내는 프레임 수와 같은 규칙(10-16 실측 1.017초=31·1.05초=32).
    컷·토막 길이를 따로 반올림하면 오차가 쌓여 뒤 컷이 1~2프레임 당겨졌다(바나나 cuts판 실측) → 경계를 절대 시각에서 한 번만 반올림한다."""
    return int(t * FPS + 0.5 + 1e-9)


def _len_args(dur: float, frames: int | None) -> list[str]:
    return ["-frames:v", str(frames)] if frames is not None else ["-t", f"{dur:.3f}"]


def _shift_overlays(overlays, dt: float):
    """꾸밈 시각(t·path 의 t)은 컷 안 시각 — 토막·틀 경계로 dt 만큼 늦게 시작하면 그만큼 당긴다."""
    return [dict(o, t=[x - dt for x in o["t"]], **({"path": [[p[0] - dt, p[1], p[2]] for p in o["path"]]} if o.get("path") else {}))
            if o.get("t") else o for o in overlays or []] or None


def render_shot(base: Path, sh: dict, off: float, dur: float, win: dict, full: bool, box, min_y: int, out: Path, seg_t0: float | None = None,
                cap_top: int | None = None) -> Path:
    """컷 하나 → 영상 파일 하나. 토막(shot_pieces)마다 shot_clip 으로 같은 칸·같은 크기로 그리고 이어 붙인다(같은 인코딩이라 복사로 잇는다).
    seg_t0 = 이 컷이 틀 구간 안에서 시작하는 초 — 주면 토막마다 프레임 수를 frame_at(끝)−frame_at(시작)으로 정해 합이 구간 시각과 맞는다."""
    pcs = shot_pieces(sh, off, dur)
    files = []
    for j, pc in enumerate(pcs):
        p = pc["sh"]
        f = out if len(pcs) == 1 else out.with_name(f"{out.stem}_c{j}.mp4")
        nf = None
        if seg_t0 is not None:
            a_ = seg_t0 + (pc["t"] - off)
            b_ = seg_t0 + (pcs[j + 1]["t"] - off) if j + 1 < len(pcs) else seg_t0 + dur
            nf = frame_at(b_) - frame_at(a_)
            if nf <= 0:
                continue
        shot_clip(base / p["src"], pc["ss"], pc["dur"], win, p.get("box_w", 750), full, f, p.get("ar"), box, p.get("fit", "cover"), min_y,
                  p.get("src_crop"), p.get("kind") == "짤", p.get("anchor", True), _shift_overlays(sh.get("overlays"), pc["t"]), nf, p.get("move"),
                  cap_top=cap_top)
        files.append(f)
    if len(files) > 1:
        lst = out.with_suffix(".txt")
        lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
        va._run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out


# ── 자막 사건(빈 자막·강조 자막) — 대본.json caption_events (관제 097, 10-16 핫템 담당 요청) ──────────────
# 원음 리액션 구간 동안 앞 나레 자막이 계속 떠 있었다 → [{kind:"blank", t0, dur}] 그 구간 자막 없음
# 원음 리액션에 맞춰 띄우는 색 자막 → [{kind:"emph", text, rgb, t0, dur}] 흰 자막 대신 그 색(같은 글꼴·크기·외곽선·자리)
# 시각은 완성본 초. 컷 시각은 건드리지 않는다(자막만). 판단 주인 = apply_caption_events 한 곳.
def apply_caption_events(steps: list[dict], events: list[dict], dur: float) -> list[dict]:
    """steps(t0·t1·text) → 이어진 자막 조각 [{t0,t1,text}] — blank·emph 구간은 text "" (emph 글자는 emph_png 가 따로 얹는다)."""
    holes = sorted((float(e["t0"]), float(e["t0"]) + float(e["dur"])) for e in events or [] if e.get("kind") in ("blank", "emph"))
    out = []
    for s in steps:
        pieces = [(s["t0"], s["t1"])]
        for a, b in holes:
            nxt = []
            for x, y in pieces:
                if b <= x or a >= y:
                    nxt.append((x, y)); continue
                if x < a:
                    nxt.append((x, a))
                if b < y:
                    nxt.append((b, y))
            pieces = nxt
        # 0.25초 미만 조각은 글자 없이(빈 구간 끝 0.1초에 앞 자막이 번쩍 — 10-16 시험)
        out += [{"t0": x, "t1": y, "text": s["text"] if y - x >= 0.25 or not holes else ""} for x, y in pieces if y - x > 0.02]
    out += [{"t0": a, "t1": min(b, dur), "text": ""} for a, b in holes if a < dur]
    out.sort(key=lambda r: r["t0"])
    return out


def _font_file(family: str) -> str:
    """틀의 글꼴 이름 → 파일. 렌더러(scene-style-ui-showcase.html @font-face)와 같은 이름표를 읽고, 같은 이름의 otf/ttf 가 있으면 그것(PIL 용)."""
    html = (ROOT / "out" / "scene-style-ui-showcase.html").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'font-family:"%s";src:url\("\.\./([^"]+)"' % re.escape(family), html)
    if not m:
        raise SystemExit(f"글꼴 {family} 을 @font-face 에서 못 찾음")
    w2 = ROOT / m.group(1)
    for ext in (".otf", ".ttf"):
        c = w2.parent.parent / (w2.stem + ext)
        if c.exists():
            return str(c)
    return str(w2)


def emph_png(text: str, cap: dict, rgb, dst: Path, dy: int = 0) -> Path:
    """강조 자막 한 장(1080×1920 투명) — 틀 자막 층(cap)과 같은 글꼴·크기·외곽선·자리, 채움색만 rgb."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(_font_file(cap["font"]), int(round(cap["size"])))
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    ol = cap.get("outline") or {}
    anchor = {"left": "lm", "right": "rm"}.get(cap.get("align", "center"), "mm")   # schema: x 는 align 기준(가운데·왼쪽 끝·오른쪽 끝)
    # dy = 완성본 좌표 → 재료 캔버스(창이 가운데 놓인 1080×1920) 좌표
    ImageDraw.Draw(im).text((cap["x"], cap["y"] + cap["line_h"] / 2 + dy), text, font=font, fill=tuple(int(v) for v in rgb) + (255,),
                            anchor=anchor, stroke_width=int(round(ol.get("px", 0))), stroke_fill=tuple(ol.get("rgb", (0, 0, 0))) + (255,))
    im.save(dst)
    return dst


def plan_times(plan: dict, S: dict | None = None) -> dict:
    """자막 조각 시각·훅 카드 끝·컷 시각 — 판단 한 곳(build 와 컷 계획표가 같이 부른다, 10-22 썰템홈샷 하이브리드)."""
    S = S or json.loads(Path(plan["script"]).read_text(encoding="utf-8"))
    sentences = [l["text"] for l in S["final"]["lines"]]
    steps, dur = time_steps(steps_of(sentences, plan.get("chunk", 14), plan.get("caption_mode", "accumulate")), plan["tts"], lines=sentences,
                            asr=plan.get("line_asr", True))   # 줄 시작 받아쓰기 정렬(시험은 꺼서 네트워크 0)
    # 훅 카드 끝 = 둘째 문장이 시작하는 시각(원본: 훅 카드 1.5초 = 첫 문장 "…억울했던 이유?" 동안)
    one = len(plan["frames"]) == 1   # 틀 한 장(훅 카드 없음 — 썰풀다 틀 B) 이면 처음부터 끝까지 그 틀
    hook_end = 0.0 if one else (plan["frames"][0].get("t_end") or next(s["t0"] for s in steps if s["sent"] >= 1))
    # 훅 카드 구간은 자막 없음(원본: 훅 카드엔 제목만) — 첫 문장 조각은 훅 동안 말로만
    cuts = [s["t0"] for s in steps if s["new_cut"] and s["t0"] >= hook_end - 1e-6]
    cuts = sorted(set([0.0, hook_end] + cuts)) + [dur]
    shots_t = [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a > 0.05]
    return {"steps": steps, "dur": dur, "one": one, "hook_end": hook_end, "shots": shots_t}


def build(plan: dict):
    out = Path(plan["out"]).resolve()
    shutil.rmtree(out / "work", ignore_errors=True); (out / "work").mkdir(parents=True, exist_ok=True)
    S = json.loads(Path(plan["script"]).read_text(encoding="utf-8"))
    M = json.loads(Path(plan["materials"]).read_text(encoding="utf-8"))
    P = plan_times(plan, S)
    steps, dur, one, hook_end, shots_t = P["steps"], P["dur"], P["one"], P["hook_end"], P["shots"]
    events = [dict(e, t0=float(e["t0"]), dur=float(e["dur"])) for e in S.get("caption_events") or []]
    cap_steps = apply_caption_events(steps, events, dur)   # 컷은 위 steps 로 이미 정했다 — 자막만 비우거나 바꾼다
    mshots = M["shots"]
    if len(mshots) < len(shots_t):
        raise SystemExit(f"재료 컷 {len(mshots)}개 < 필요한 컷 {len(shots_t)}개 — 재료.json shots 를 늘려라(컷 시각: {shots_t})")
    base = Path(M["cand_dir"])
    J = json.loads(Path(plan["tteutgi"]).read_text(encoding="utf-8")) if plan.get("tteutgi") else {}
    pboxes = [x["box"] for x in (((J.get("cuts") or {}).get("picture_boxes") or {}).get("per_shot") or []) if x.get("box")]
    seg_files = []
    for fi, fr in enumerate(plan["frames"]):
        t_a = 0.0 if fi == 0 else plan["frames"][fi - 1]["t_end"] or hook_end
        t_b = fr.get("t_end") or dur
        if fi == 0 and not one:
            t_b = hook_end
        frame = json.loads(Path(fr["frame"]).read_text(encoding="utf-8"))
        spec = schema.validate(frame)
        win = next(l for l in spec["layers"] if l["kind"] == "video")
        has_cap = any(l["kind"] == "text" and l["role"] == "caption" for l in spec["layers"])
        cap = next((l for l in spec["layers"] if l["kind"] == "text" and l["role"] == "caption"), None)
        min_y = int(cap["y"] + cap["lines"] * cap["line_h"] + 12) if cap else 0
        parts = []
        for k, (a, b) in enumerate(shots_t):
            if b <= t_a + 1e-6 or a >= t_b - 1e-6:
                continue
            a2, b2 = max(a, t_a), min(b, t_b)
            sh = mshots[k]
            box = sh.get("box") or (pboxes[k % len(pboxes)] if pboxes else None)   # 칸 크기 기본 = 뜯기 cuts.picture_boxes 같은 순번
            if sh.get("full") and not sh.get("box"):
                box = None   # ★full=꽉 채움이 이긴다(10-16 3호: 틀 한 장이면 뜯기 칸이 full 컷까지 덮어 창 아래 칸으로 밀렸다)
            p = out / "work" / f"f{fi}_s{k:02d}.mp4"
            # 컷이 틀 경계로 잘려 늦게 시작하면(a2 > a) 소스 시작·꾸밈 시각을 그만큼 — 페이지 안 다중 컷(sh.cuts)도 render_shot 한 곳에서
            parts.append(render_shot(base, sh, a2 - a, b2 - a2, win, sh.get("full", fi == 0 and not one), None if (fi == 0 and not one) else box,
                                     min_y, p, seg_t0=a2 - t_a, cap_top=int(cap["y"]) if cap else None))
        lst = out / "work" / f"f{fi}.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        mat = out / "work" / f"f{fi}_mat.mp4"
        va._run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                        "-shortest", "-c:v", "copy", "-c:a", "aac", str(mat)])
        emph = [e for e in events if e.get("kind") == "emph" and cap and e["t0"] < t_b and e["t0"] + e["dur"] > t_a]
        if emph:   # 강조 자막 = 재료 영상 위(틀 층 아래)에 얹는다 — 자막 자리는 영상 창 안(틀 B)
            ins, fc, last = [], "", "0:v"
            for k, e in enumerate(emph):
                png = emph_png(e["text"], cap, e.get("rgb", (120, 200, 255)), out / "work" / f"f{fi}_emph{k}.png", dy=(1920 - win["h"]) // 2 - win["y"])
                ins += ["-loop", "1", "-i", str(png)]
                a0, b0 = max(0.0, e["t0"] - t_a), min(t_b, e["t0"] + e["dur"]) - t_a
                fc += f"{';' if fc else ''}[{last}][{k + 1}:v]overlay=0:0:enable='between(t,{a0:.3f},{b0:.3f})'[e{k}]"
                last = f"e{k}"
            mat2 = out / "work" / f"f{fi}_mat_emph.mp4"
            va._run_ffmpeg(["ffmpeg", "-y", "-i", str(mat), *ins, "-filter_complex", fc + f";[{last}]format=yuv420p[v]", "-map", "[v]", "-map", "0:a",
                            "-t", f"{t_b - t_a:.3f}", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-color_range", "tv", "-c:a", "copy", str(mat2)])
            mat = mat2
        tl, bi = [], 0
        for s in cap_steps:
            a, b = max(s["t0"], t_a), min(s["t1"], t_b)
            if b - a <= 0.02:
                continue
            txt = s["text"] if has_cap else ""
            tl.append({"beat_idx": bi, "t0": round(a - t_a, 3), "dur": round(b - a, 3), "narration": txt, "caption_lines": [txt] if txt else [],
                       "role": "hook" if bi == 0 else "body", "primary": {"video_id": "s0", "start": a - t_a, "end": b - t_a}})
            bi += 1
        title_t = title_text(spec, S)   # 판단 한 곳 = remake_video.title_text
        snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
        seg = out / "work" / f"seg{fi}.mp4"
        scene_style.compose(str(mat), tl, snap, str(seg), out / "work" / f"compose{fi}", {"text": title_t})
        seg_files.append(seg)
    vlist = out / "work" / "segs.txt"
    vlist.write_text("".join(f"file '{p.as_posix()}'\n" for p in seg_files), encoding="utf-8")
    vid = out / "work" / "video.mp4"
    # ★-c copy 로 이으면 두 조각의 시간 단위가 달라 r_frame_rate 120 이 됐다(대조가 길이 7.97초로 잼, 10-16) → 다시 인코딩해 30fps 로
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(vlist), "-an", "-r", "30", "-c:v", "libx264", "-crf", "16",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", str(vid)])
    # 소리: 나레(목표 LUFS) + BGM(나레 대비 비율) — 원본 '원음 깔림 False'
    target = plan.get("lufs", -16.2)
    bgm = bgm_lib.path_of(plan.get("bgm")) if plan.get("bgm") else None
    fc = f"[1:a]loudnorm=I={target}:TP=-1.5:LRA=11,aresample=48000[n]"
    ins = ["-i", plan["tts"]]
    if bgm:
        ins += ["-stream_loop", "-1", "-i", bgm]
        fc += (f";[2:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,loudnorm=I={target}:TP=-1.5:LRA=11,aresample=48000,volume={plan.get('bgm_ratio', 0.15)}[b]"
               f";[n][b]amix=inputs=2:normalize=0:duration=first[m]")
    fc += f";[{'m' if bgm else 'n'}]alimiter=limit=0.89:level=false[a]"
    mixed = out / "work" / "mixed.wav"
    va._run_ffmpeg(["ffmpeg", "-y", *ins, "-filter_complex", fc.replace("[1:a]", "[0:a]", 1).replace("[2:a]", "[1:a]", 1),
                    "-map", "[a]", "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(mixed)])
    gain = round(target - _lufs(mixed)["I"], 2)   # 한 번 loudnorm 은 목표보다 ~1dB 덜 나온다(remake_video 와 같은 보정)
    final = out / "final.mp4"
    # 효과음(재료.json sfx: [{file, t(초 또는 "end-0.2"), db}]) — 원본 효과음 자리(뜯기 audio.composition.sfx.times)
    sfx = sfx_list(M, dur)   # 판단 한 곳 = remake_video.sfx_list
    fc2 = f"[1:a]volume={gain}dB[a0]"
    for k, (fp, t, db) in enumerate(sfx):
        ms = int(round(t * 1000))
        fc2 += f";[{k + 2}:a]aresample=48000,aformat=channel_layouts=stereo,volume={db}dB,adelay={ms}|{ms}[s{k}]"
    if sfx:
        fc2 += ";[a0]" + "".join(f"[s{k}]" for k in range(len(sfx))) + f"amix=inputs={len(sfx) + 1}:normalize=0:duration=first[a1]"
    fc2 += f";[{'a1' if sfx else 'a0'}]alimiter=limit=0.89:level=false[a]"
    va._run_ffmpeg(["ffmpeg", "-y", "-i", str(vid), "-i", str(mixed), *[a for fp, _, _ in sfx for a in ("-i", str(fp))], "-filter_complex", fc2,
                    "-map", "0:v", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(final)])
    (out / "timeline.json").write_text(json.dumps({"steps": steps, "hook_end": hook_end, "shots": shots_t, "dur": dur},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "audio.json").write_text(json.dumps({"tts": plan["tts"], "bgm": plan.get("bgm"), "bgm_ratio": plan.get("bgm_ratio", 0.15),
                                                "target_lufs": target, "sfx": [(str(fp), t, db) for fp, t, db in sfx], "final": _lufs(final)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("final:", final)
    return final


if __name__ == "__main__":
    build(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
