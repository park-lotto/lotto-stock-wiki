# -*- coding: utf-8 -*-
"""뜯기(analyze) 판독 창구 한 곳 — kal.py step_tteutgi 가 analyze(llm=ask) 로 넘긴다 (관제 319, 2026-11-06 감시 빈 곳 2).

판단 주인: '이 판독은 어느 창구로 가나' 는 이 파일 ask() 하나.
  그림·글 = claude_cli.analyze_llm 그대로(사장님 10-18 그림 판독 제미나이 금지).
  소리   = listen(): 받아쓰기(구절 시각·글·언어·낱말 시각) = 스피치매틱스(asr_local.transcribe engine='speechmatics', 메모리 10-25 '받아쓰기=스피치매틱스')
           + 소리 판독(화자 성별·TTS 여부·구절 kind·효과음·BGM·목소리 톤) = gemini_free.ask(같은 ASR_PROMPT — 메모리 10-25 '제미나이 소리 판독 허용').
           둘을 합쳐 analyze.ASR_PROMPT 답 꼴로 돌려준다. 구절은 스피치매틱스 것을 쓰고 kind·speaker 는 시간이 가장 많이 겹치는 제미나이 구절에서.
           스피치매틱스가 아니면(키 없음 → 위스퍼로 넘어감·실패) 실패로 돌려준다 — 공급자 몰래 바꾸기 금지(make-공통-05).
           제미나이 소리 판독만 실패하면 구절은 그대로 두고 kind=unknown · _judge_failed 에 이유(조용히 버리지 않는다).
Jev(11-06): 해결 0.82·위험 0.44·신뢰 0.87 (대안: 제미나이만 0.38 · claude_cli 소리 갈래를 스피치매틱스로 0.47).
"""
from __future__ import annotations

import os
import tempfile


def ask(parts: list, prompt: str, tag: str = ""):
    aud = [x for x in parts or [] if isinstance(x, tuple)]
    if aud:
        return listen(bytes(aud[0][0]), prompt, tag)
    from tools.calcopy.engine import claude_cli
    return claude_cli.analyze_llm(parts, prompt, tag)


def _overlap(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def listen(audio: bytes, prompt: str, tag: str = "", asr=None, judge=None, mime: str = "audio/mp3"):
    """소리 bytes → (ASR_PROMPT 꼴 dict, None) | (None, 이유). asr·judge 는 시험 주입용."""
    if asr is None:
        from tools.calcopy.engine import asr_local

        def asr(p):
            return asr_local.transcribe(p, engine="speechmatics")
    if judge is None:
        from tools.calcopy.engine import gemini_free
        judge = gemini_free.ask
    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio)
        try:
            sm = asr(path)
        except Exception as e:  # noqa: BLE001 — 이유를 돌려준다(부르는 analyze 가 transcript.failed 로 적는다)
            return None, f"받아쓰기(speechmatics) 실패: {type(e).__name__} {str(e)[:120]}"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if not isinstance(sm, dict) or sm.get("engine") != "speechmatics":
        return None, f"받아쓰기가 speechmatics 가 아님({(sm or {}).get('engine')}: {(sm or {}).get('note', '키 없음?')}) — 위스퍼로 몰래 바꾸지 않는다"
    g, gerr = judge([(audio, mime)], prompt, tag)
    g = g if isinstance(g, dict) else {}
    gseg = [s for s in (g.get("segments") or []) if isinstance(s, dict)]
    lang = str(sm.get("lang") or "").lower()
    segs = []
    for s in sm.get("segments") or []:
        a0, a1 = float(s["start"]), float(s["end"])
        best = max(gseg, key=lambda x: _overlap(a0, a1, float(x.get("start") or 0), float(x.get("end") or 0)), default=None)
        hit = best if best is not None and _overlap(a0, a1, float(best.get("start") or 0), float(best.get("end") or 0)) > 0 else None
        segs.append({"start": a0, "end": a1, "text": str(s.get("text") or "").strip(),
                     "speaker": (hit or {}).get("speaker") or "S?", "lang": (hit or {}).get("lang") or lang,
                     "kind": (hit or {}).get("kind") or "unknown"})
    out = {k: g.get(k) for k in ("speakers", "sfx", "bgm", "voice_tone", "ambient") if g.get(k) is not None}
    out.update({"segments": segs, "words": sm.get("words") or [], "_asr": "speechmatics",
                "_model": "speechmatics+" + str(g.get("_model") or ("gemini 실패" if gerr else "gemini"))})
    if gerr:
        out["_judge_failed"] = str(gerr)[:200]
    return out, None
