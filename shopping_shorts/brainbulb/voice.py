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


def synth_all(script, workdir, synth, *, log=print):
    """→ {"card_sec", "cut_secs":[...], "files":[...], "chars"}  파일은 workdir/tts/00.wav(카드), 01.wav.."""
    texts = [script["title"]["card"]] + [g["text"] for g in script["groups"]]
    chars = sum(len(t) for t in texts)
    if chars > spec.POLICY_MAX_TTS_CHARS:
        raise RuntimeError(f"voice: TTS 글자 {chars}자 > 상한 {spec.POLICY_MAX_TTS_CHARS} — 돈 나가기 전에 멈춤")
    td = os.path.join(workdir, "tts")
    os.makedirs(td, exist_ok=True)
    files, secs = [], []
    for i, t in enumerate(texts):
        wav = os.path.join(td, f"{i:02d}.wav")
        if not os.path.exists(wav):
            raw = os.path.join(td, f"{i:02d}.raw.mp3")
            synth(t, raw)
            _to_wav(raw, wav)
            os.remove(raw)
        sec = timing.wav_seconds(wav)
        if sec <= 0.05:
            raise RuntimeError(f"voice: {i}번 음성이 비었습니다 ({sec:.3f}s) «{t}»")
        files.append(wav); secs.append(sec)
    log(f"[brainbulb.voice] {len(files)}개 합성, {chars}자, 합계 {sum(secs):.2f}s")
    return {"card_sec": secs[0], "cut_secs": secs[1:], "files": files, "chars": chars}
