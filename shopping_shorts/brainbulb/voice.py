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


# 앞뒤 무음 제거 — 볼케이노 컷 wav엔 무음이 없다(실측), Typecast 원본엔 0.2초씩 붙는다.
# ★stop_periods로 뒤를 자르면 **문장 중간 첫 쉼**에서 뒷말이 통째로 잘린다(실측 2026-09-12: 9음절이 0.21초).
#   앞만 자르는 필터를 뒤집어서 두 번 쓴다(areverse 샌드위치).
_TRIM = ("silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.02,areverse,"
         "silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.03,areverse,"
         # 컷 안 쉼 압축 — 볼케이노 28컷엔 0.15s 이상 내부무음이 1건(0.24s)뿐인데 우리는 10건 2.56s였다(사장님: "늘어짐").
         # 0.2s 넘는 쉼을 전부 0.1s로 줄인다(stop_periods=-1 = 모든 구간).
         "silenceremove=stop_periods=-1:stop_duration=0.12:stop_threshold=-40dB:stop_silence=0.06")
# v004 실측: 앞 잔여 31ms·뒤 70ms(볼케이노 27·38), 나레 전체 무음 1.63s(볼케이노 0.98) → 뒤 트림 -40dB/0.03, 쉼 0.12s↑→0.06s (사장님: "무음구간 많아")


def _to_wav(src, dst):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", _TRIM, "-ar", "44100", "-ac", "2", dst],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"voice: wav 변환 실패 {src} — {r.stderr[-200:]}")


def _sidecar(wav):
    return wav[:-4] + ".txt"


def _takes_role(fn):
    import inspect
    try:
        ps = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return "role" in ps or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in ps.values())


def plan_emotion(role, meme, *, hook=False):
    """역할·훅·밈 감정 → Typecast (감정, 강도). 판정은 여기 한 곳(0순위-B). whisper는 어떤 경로로도 안 나간다."""
    if spec.POLICY_EMOTION_ALL:
        out = spec.POLICY_EMOTION_ALL
    elif hook and spec.POLICY_EMOTION.get("HOOK"):
        out = spec.POLICY_EMOTION["HOOK"]
    elif role == "CHAR" and spec.POLICY_EMOTION.get("CHAR") is None:
        e = spec.MEME_TO_TC_EMOTION.get(meme or "")     # CHAR 고정 감정이 없을 때만 밈 감정을 따른다
        out = (e, 1.2) if e else None
    else:
        out = spec.POLICY_EMOTION.get(role)
    if out and out[0] in spec.FORBIDDEN_EMOTIONS:
        raise RuntimeError(f"voice: 금지된 감정 {out[0]} (사장님 지시 — spec.FORBIDDEN_EMOTIONS)")
    return out


def synth_all(script, workdir, synth, *, spent_chars=0, log=print):
    """→ {"card_sec", "cut_secs":[...], "files":[...], "chars", "synthesized"}  파일은 workdir/tts/00.wav(카드), 01.wav..

    - 재사용 조건은 "파일이 있다"가 아니라 **옆 .txt의 글자가 같다** (아스트라 3R: 대본을 바꿔도 옛 음성이 붙던 버그)
    - 비용 상한은 잡당 **누적**: spent_chars(이전 합성분) + 이번에 실제로 새로 합성할 글자 (재사용분은 안 센다)
    """
    texts = [script["title"]["card"]] + [g["text"] for g in script["groups"]]
    roles = ["NARR"] + [g.get("role", "NARR") for g in script["groups"]]     # 역할별 성우(3명) — 카드는 나레 목소리
    emos = [plan_emotion("NARR", None, hook=True)] + [
        plan_emotion(g.get("role", "NARR"), g.get("meme"), hook=(i < spec.POLICY_HOOK_CUTS))
        for i, g in enumerate(script["groups"])]      # 훅(카드+첫 컷) whisper / CHAR는 밈 감정 / PUNCH toneup
    tag_for = getattr(synth, "tag_for", None)         # 역할별 목소리|템포|모델 — 그 역할만 바뀌면 그 컷만 재합성
    tag = getattr(synth, "tag", "")
    def _key(t, e, role):
        tg = tag_for(role) if tag_for else tag
        return (tg + "|" + str(e) + "\n" + t) if tg else t
    keys = [_key(t, e, r) for t, e, r in zip(texts, emos, roles)]
    td = os.path.join(workdir, "tts")
    os.makedirs(td, exist_ok=True)
    todo = []
    for i, k in enumerate(keys):
        wav = os.path.join(td, f"{i:02d}.wav")
        same = os.path.exists(wav) and os.path.exists(_sidecar(wav)) and open(_sidecar(wav), encoding="utf-8").read() == k
        if not same:
            todo.append(i)
    # 새로 과금되는 글자 = 원본 mp3가 없는 것만 (원본이 남아 있으면 변환만 다시 한다)
    new_chars = sum(len(texts[i]) for i in todo if not os.path.exists(os.path.join(td, f"{i:02d}.raw.mp3")))
    if spent_chars + new_chars > spec.POLICY_MAX_TTS_CHARS:
        raise RuntimeError(f"voice: TTS 누적 {spent_chars}+{new_chars}자 > 상한 {spec.POLICY_MAX_TTS_CHARS} — 돈 나가기 전에 멈춤")
    files, secs = [], []
    for i, t in enumerate(texts):
        wav = os.path.join(td, f"{i:02d}.wav")
        if i in todo:
            raw = os.path.join(td, f"{i:02d}.raw.mp3")
            old_key = open(_sidecar(wav), encoding="utf-8").read() if os.path.exists(_sidecar(wav)) else None
            for stale in (wav, _sidecar(wav)) + ((raw,) if old_key is not None and old_key != keys[i] else ()):
                if os.path.exists(stale):
                    os.remove(stale)               # 글자가 바뀌었으면 원본 mp3도 버린다
            if not os.path.exists(raw):            # 원본 mp3는 보존 — 트림 필터만 바꿔 다시 돌릴 때 재과금 없이
                if _takes_role(synth):
                    e = emos[i] or (None, None)
                    synth(t, raw, role=roles[i], emotion=e[0], intensity=e[1])
                else:                              # role을 모르는 합성기(테스트 가짜 등)
                    synth(t, raw)
            _to_wav(raw, wav)
            with open(_sidecar(wav), "w", encoding="utf-8") as fh:
                fh.write(keys[i])
        sec = timing.wav_seconds(wav)
        if sec <= 0.05:
            raise RuntimeError(f"voice: {i}번 음성이 비었습니다 ({sec:.3f}s) «{t}»")
        files.append(wav); secs.append(sec)
    log(f"[brainbulb.voice] {len(files)}개 중 {len(todo)}개 새로 합성({new_chars}자, 누적 {spent_chars + new_chars}), 합계 {sum(secs):.2f}s")
    return {"card_sec": secs[0], "cut_secs": secs[1:], "files": files, "chars": new_chars,
            "spent_chars": spent_chars + new_chars, "synthesized": todo}
