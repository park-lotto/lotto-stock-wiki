# -*- coding: utf-8 -*-
"""대화형 대본의 칸 음성 — 이어진 일레븐 화자 줄은 **대화 API 한 번**으로, 타입캐스트 화자 줄은 줄마다 (관제 128).

왜 한 번에: 줄마다 따로 합성하면(v3는 앞뒤 문맥을 못 받는다) 주고받는 억양이 사라져 "말투가 어색"했다
(2026-10-05 사장님 청취 — 같은 대사를 대화 API로 한 번에 구우니 자연스러웠다, tools/voice_format/).
★판단 주인: 화자·연기 지시·성우 = dialogue_script(job.script_structure["dialogue"]). 여기는 굽고 자르기만.
★결과 계약은 통짜 합성(tts_joined)과 같다: 칸마다 mp3 + 정렬 사이드카 → 호출부가 finalize_beat_audio.
  자르기(_cut)·정렬 조각(_slice_alignment)·조각 찾기(_spans)는 tts_joined 것을 그대로 쓴다(0순위-B).
★실패는 조용히 한 목소리로 되돌아가지 않는다 — DialogueError 로 job 을 실패시킨다(0순위-C).
"""
import base64
import sys
from pathlib import Path

import requests

from shopping_shorts import audio_post, tts, tts_joined, tts_timestamps, typecast_tts

_DIALOGUE_TS = "https://api.elevenlabs.io/v1/text-to-dialogue/with-timestamps"
_PAD = 0.05          # 화자 조각 앞뒤 여백(초) — 이웃 조각을 넘지 않게 아래에서 죈다


class DialogueError(RuntimeError):
    pass


def _groups(beats, lines, voices):
    """[(엔진, [칸 번호…])] — 이어진 일레븐 화자 칸은 한 덩어리, 타입캐스트 칸은 하나씩."""
    out = []
    for i, _b in enumerate(beats):
        v = voices[lines[i]["speaker"]]
        eng = "tc" if typecast_tts.is_typecast(v.get("model_id")) else "el"
        if eng == "el" and out and out[-1][0] == "el":
            out[-1][1].append(i)
        else:
            out.append((eng, [i]))
    return out


def _el_group(idx, beats, lines, voices, work, customer_id, post=None):
    """일레븐 대화 API(with-timestamps) 한 번 → 칸별 [(i, 조각 경로, 정렬)]."""
    inputs = []
    for i in idx:
        tag = lines[i].get("tag") or ""
        inputs.append({"text": (f"[{tag}] " if tag else "") + beats[i]["narration"],
                       "voice_id": voices[lines[i]["speaker"]]["voice_id"]})
    r = (post or requests.post)(_DIALOGUE_TS, headers={"xi-api-key": tts._api_key(customer_id),
                                                        "Content-Type": "application/json"},
                                json={"model_id": "eleven_v3", "inputs": inputs}, timeout=240)
    if r.status_code != 200:
        raise DialogueError(f"대화 합성 실패 {r.status_code}: {r.text[:160]}")
    j = r.json()
    full = work / f"_dlg_{idx[0]:02d}.mp3"
    full.write_bytes(base64.b64decode(j["audio_base64"]))
    align = j.get("alignment") or {}
    segs = j.get("voice_segments") or []
    st, en = align.get("character_start_times_seconds") or [], align.get("character_end_times_seconds") or []
    dur = audio_post._audio_dur(str(full)) or (en[-1] if en else 0.0)
    # 칸 k 의 소리 구간 = 그 입력의 voice_segments 합. 글자 구간 = 정렬에서 대사 글(태그 뺀)을 찾은 곳.
    spans = tts_joined._spans(align.get("characters") or [], [beats[i]["narration"] for i in idx])
    res, bounds = [], []
    for k, i in enumerate(idx):
        ss = [s for s in segs if s.get("dialogue_input_index") == k]
        if not ss:
            raise DialogueError(f"{i}번 칸 소리 구간이 응답에 없다")
        bounds.append((min(s["start_time_seconds"] for s in ss), max(s["end_time_seconds"] for s in ss)))
    for k, i in enumerate(idx):
        a, b = bounds[k]
        lo = bounds[k - 1][1] if k else 0.0
        hi = bounds[k + 1][0] if k + 1 < len(idx) else dur
        start, end = max(lo, a - _PAD), min(hi, b + _PAD)
        dst = Path(beats[i]["_tts_out"])
        tts_joined._cut(full, dst, start, end)
        tts_timestamps.clear(str(dst))
        if spans:
            c0, c1 = spans[k]
            tts_timestamps.save(str(dst), tts_joined._slice_alignment(align, c0, c1, start, end - start))
        res.append(i)
    return res


def _tc_line(i, beats, lines, voices, customer_id):
    """타입캐스트 한 줄. tts.synthesize_tts 는 타입캐스트가 꺼져 있으면 미나로 바꿔치기하므로 직접 부른다."""
    v = voices[lines[i]["speaker"]]
    s = v.get("settings") or {}
    dst = beats[i]["_tts_out"]
    tts_timestamps.clear(dst)
    align = typecast_tts.synthesize(beats[i]["narration"], dst, voice_id=v["voice_id"], speed=1.0,
                                    emotion=s.get("emotion"), intensity=s.get("emotion_intensity"),
                                    model_id=v.get("model_id"), customer_id=customer_id)
    if align:
        tts_timestamps.save(dst, align)


def synthesize(beats, dialogue, outs, *, tempo=1.0, silence_trim="off", pace_mode=False,
               customer_id=0, work_dir=None, post=None):
    """칸마다 outs[i] 에 음성을 쓴다. 성공하면 None, 실패는 DialogueError.

    dialogue = job.script_structure["dialogue"] (lines[i] = 칸 i 의 화자·연기 지시, voices = 화자별 성우 스냅샷).
    tempo: 작업 성우 배속 하나로 전원 통일(화자마다 빠르기가 다르면 주고받기가 어긋난다)."""
    lines = (dialogue or {}).get("lines") or []
    voices = (dialogue or {}).get("voices") or {}
    if len(lines) != len(beats):
        raise DialogueError(f"대화 줄 {len(lines)}개 ≠ 칸 {len(beats)}개 — 대본이 바뀌었으면 대화형으로 다시 변환하세요")
    missing = {ln["speaker"] for ln in lines} - set(voices)
    if missing:
        raise DialogueError(f"성우가 안 정해진 화자 {sorted(missing)}")
    work = Path(work_dir or Path(outs[0]).parent)
    work.mkdir(parents=True, exist_ok=True)
    for b, o in zip(beats, outs):
        b["_tts_out"] = str(o)
    try:
        for eng, idx in _groups(beats, lines, voices):
            if eng == "el":
                _el_group(idx, beats, lines, voices, work, customer_id, post=post)
            else:
                _tc_line(idx[0], beats, lines, voices, customer_id)
        for o in outs:
            # 엔진이 둘이라 크기가 다르다 — 조각마다 loudnorm(통짜처럼 한 번에 걸 수 없다)
            audio_post.finish_line_audio(str(o), tempo=tempo, silence_trim=silence_trim,
                                         pace_mode=pace_mode, loudnorm=True)
    finally:
        for b in beats:
            b.pop("_tts_out", None)
    print(f"[tts_dialogue] {len(beats)}칸 대화 합성 완료", file=sys.stderr)
