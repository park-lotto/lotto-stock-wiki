# -*- coding: utf-8 -*-
"""TTS — 카드 문장 + 컷마다 따로 합성(볼케이노 방식), 길이는 파일을 ffprobe로 잰다. 정렬 응답에 의존하지 않는다.

합성기는 주입한다: synth(text, out_path) → None. 기본은 typecast_tts.synthesize(voice_id 필요).
누적 글자수로 비용 상한(spec.POLICY_MAX_TTS_CHARS)을 지킨다 — 돈 나가기 전에 센다.
"""
import os
import subprocess

from . import spec, timing


def typecast_synth(voice_id, **kw):
    from shopping_shorts import typecast_tts

    def synth(text, out_path):
        typecast_tts.synthesize(text, out_path, voice_id=voice_id, **kw)
    return synth


def _to_wav(src, dst):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "44100", "-ac", "2", dst],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"voice: wav 변환 실패 {src} — {r.stderr[-200:]}")


def _sidecar(wav):
    return wav[:-4] + ".txt"


def synth_all(script, workdir, synth, *, spent_chars=0, log=print):
    """→ {"card_sec", "cut_secs":[...], "files":[...], "chars", "synthesized"}  파일은 workdir/tts/00.wav(카드), 01.wav..

    - 재사용 조건은 "파일이 있다"가 아니라 **옆 .txt의 글자가 같다** (아스트라 3R: 대본을 바꿔도 옛 음성이 붙던 버그)
    - 비용 상한은 잡당 **누적**: spent_chars(이전 합성분) + 이번에 실제로 새로 합성할 글자 (재사용분은 안 센다)
    """
    texts = [script["title"]["card"]] + [g["text"] for g in script["groups"]]
    td = os.path.join(workdir, "tts")
    os.makedirs(td, exist_ok=True)
    todo = []
    for i, t in enumerate(texts):
        wav = os.path.join(td, f"{i:02d}.wav")
        same = os.path.exists(wav) and os.path.exists(_sidecar(wav)) and open(_sidecar(wav), encoding="utf-8").read() == t
        if not same:
            todo.append(i)
    new_chars = sum(len(texts[i]) for i in todo)
    if spent_chars + new_chars > spec.POLICY_MAX_TTS_CHARS:
        raise RuntimeError(f"voice: TTS 누적 {spent_chars}+{new_chars}자 > 상한 {spec.POLICY_MAX_TTS_CHARS} — 돈 나가기 전에 멈춤")
    files, secs = [], []
    for i, t in enumerate(texts):
        wav = os.path.join(td, f"{i:02d}.wav")
        if i in todo:
            raw = os.path.join(td, f"{i:02d}.raw.mp3")
            for stale in (wav, _sidecar(wav)):
                if os.path.exists(stale):
                    os.remove(stale)
            synth(t, raw)
            _to_wav(raw, wav)
            os.remove(raw)
            with open(_sidecar(wav), "w", encoding="utf-8") as fh:
                fh.write(t)
        sec = timing.wav_seconds(wav)
        if sec <= 0.05:
            raise RuntimeError(f"voice: {i}번 음성이 비었습니다 ({sec:.3f}s) «{t}»")
        files.append(wav); secs.append(sec)
    log(f"[brainbulb.voice] {len(files)}개 중 {len(todo)}개 새로 합성({new_chars}자, 누적 {spent_chars + new_chars}), 합계 {sum(secs):.2f}s")
    return {"card_sec": secs[0], "cut_secs": secs[1:], "files": files, "chars": new_chars,
            "spent_chars": spent_chars + new_chars, "synthesized": todo}
