# -*- coding: utf-8 -*-
"""TTS 쉼 규칙 — 판단은 여기 한 곳(사장님 2026-10-17 "쉼표를 주고 약간의 무음 컷을 주는 규칙. 계속 얘기 안 해도 규칙이 돼야 한다").

왜 이 파일인가: 소리 크기만 보고 쉼을 짐작하면 받침 막힘('맞|벌이' 0.08초)을 쉼으로, 짧게 읽힌 쉼표('만들었다는데, 싱크대랑' 0.1초)를
틈으로 오판한다(10-17 샘플 10~13에서 둘 다 실제로 틀렸다). 그래서 **타입캐스트가 돌려주는 글자별 시각**으로 쉼표·마침표 자리를
정확히 찾아 **그 자리만** 고친다. 낱말 안은 절대 건드리지 않는다.

규칙
  쉼표(,)  → 쉼 PAUSE[","] 초    마침표(.?!) → 쉼 PAUSE["."] 초
  짧으면 그 쉼 자신의 소리(숨·잔향)를 이어 붙여 늘리고(디지털 무음 금지 — 구멍처럼 들림), 길면 가운데를 잘라 줄인다. 이음매는 15ms 겹침.
  합성은 숏템 그대로: 성우 속도 voice_presets.default_speed, 대본 통째 1회(typecast_tts.synthesize, 타임스탬프 엔드포인트).

쓰는 법
  py tools/calcopy/engine/tts_pause.py <대본.txt 또는 문자열> <출력.mp3> [--voice tc_…] [--emotion happy] [--speed 1.25]
"""
from __future__ import annotations
import argparse, array, json, os, subprocess, sys, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

PAUSE = {",": 0.22, ".": 0.30}
XF_SEC = 0.015
FILL_PEAK_MAX = 328          # −40 dBFS(16비트) — 이어 붙일 쉼 조각이 이보다 크면 말소리가 섞인 것
PUNCT = {",": ",", ".": ".", "?": ".", "!": "."}


def synth(text: str, out_mp3: str, voice: str, emotion: str | None, speed: float | None):
    """숏템 typecast_tts.synthesize 를 그대로 부른다(통째 1회). 키는 칼카피 provider 키를 넘긴다."""
    from shopping_shorts import typecast_tts, voice_presets
    from shopping_shorts.channelkit import providers
    key = providers.typecast_key(None)
    typecast_tts.api_key = lambda *a, **k: key            # keyroute DB 가 없는 로컬 실행용
    sp = speed if speed is not None else voice_presets.default_speed(voice)
    align = typecast_tts.synthesize(text, out_mp3, voice_id=voice, speed=sp, emotion=emotion, intensity=1.0 if emotion else None)
    return align, sp


def pause_slots(align: dict) -> list[tuple[str, float, float]]:
    """쉼표·마침표마다 (종류, 앞 글자 끝, 뒤 글자 시작). 공백·문장부호는 건너뛴다."""
    ch = align["characters"]; s = align["character_start_times_seconds"]; e = align["character_end_times_seconds"]
    out = []
    for i, c in enumerate(ch):
        if c not in PUNCT:
            continue
        j = i - 1
        while j >= 0 and (ch[j].isspace() or ch[j] in PUNCT):
            j -= 1
        k = i + 1
        while k < len(ch) and (ch[k].isspace() or ch[k] in PUNCT):
            k += 1
        if j < 0 or k >= len(ch):
            continue
        out.append((PUNCT[c], float(e[j]), float(s[k])))
    return out


def _read(path):
    tmp = str(path) + ".pcm.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "44100", tmp], check=True)
    w = wave.open(tmp); sr = w.getframerate(); x = array.array("h", w.readframes(w.getnframes())); w.close(); os.remove(tmp)
    return x, sr


def _join(a, b, n):
    n = min(n, len(a), len(b))
    for i in range(n):
        t = i / n
        a[len(a) - n + i] = int(a[len(a) - n + i] * (1 - t) + b[i] * t)
    a.extend(b[n:])
    return a


def room_tone(x, sr: int, win_sec: float = 0.04) -> array.array:
    """TTS 전체에서 가장 조용한 40ms(방 잡음) — 쉼 자리 소리가 조용하지 않을 때 대신 이어 붙인다(디지털 무음 금지 규칙 유지)."""
    w = max(1, int(win_sec * sr)); step = max(1, w // 4)
    best, best_i = None, 0
    for i in range(0, max(1, len(x) - w), step):
        e = sum(s * s for s in x[i:i + w:8])
        if best is None or e < best:
            best, best_i = e, i
    return array.array("h", x[best_i:best_i + w]) or array.array("h", [0])


def shape(src_mp3: str, align: dict, out_mp3: str) -> list[dict]:
    """쉼표·마침표 자리만 PAUSE 길이로 맞춘다. 반환: 자리별 (종류, 원래, 결과)."""
    x, sr = _read(src_mp3)
    xf = int(XF_SEC * sr)
    out = array.array("h"); last = 0; log = []
    for kind, a, b in pause_slots(align):
        i0, i1 = int(a * sr), int(b * sr)
        if i1 < i0 or i0 < last:
            continue
        cur = (i1 - i0) / sr; want = PAUSE[kind]
        gap = x[i0:i1]
        if cur < want:
            need = int((want - cur) * sr); core = gap[len(gap) // 4: 3 * len(gap) // 4] or gap or array.array("h", [0])
            # 틈이 없거나(쉼 안 쉰 마침표 — 10-18 손태영 재미썸 '거.|한국') 20ms 미만이면 방 잡음으로(디지털 무음 금지)
            if len(core) < int(0.02 * sr) or max(abs(s) for s in core) > FILL_PEAK_MAX:      # 짧은 틈에 말 꼬리가 섞임 → 반복하면 쉼이 사라진다(10-18 샥탬 4편 L7|L9 0.137초)
                core = room_tone(x, sr)
            fill = array.array("h")
            while len(fill) < need:
                fill.extend(core)
            new_gap = gap + fill[:need]
        else:
            keep = int(want * sr); h = keep // 2
            new_gap = _join(array.array("h", gap[:h]), array.array("h", gap[len(gap) - (keep - h):]), xf)
        out = _join(out, array.array("h", x[last:i0]), xf) if out else array.array("h", x[last:i0])
        out = _join(out, new_gap, xf)
        last = i1
        log.append({"kind": kind, "at": round(a, 2), "was": round(cur, 3), "now": round(len(new_gap) / sr, 3)})
    out = _join(out, array.array("h", x[last:]), xf)
    tmp = out_mp3 + ".w.wav"
    w = wave.open(tmp, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(out.tobytes()); w.close()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-b:a", "192k", out_mp3], check=True)
    os.remove(tmp)
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text"); ap.add_argument("out")
    ap.add_argument("--voice", default="tc_68257f68bc6e3c161ab5078d")   # 필재
    ap.add_argument("--emotion", default=None)
    ap.add_argument("--speed", type=float, default=None)
    a = ap.parse_args()
    text = Path(a.text).read_text(encoding="utf-8") if os.path.exists(a.text) else a.text
    raw = a.out + ".raw.mp3"
    align, sp = synth(text, raw, a.voice, a.emotion, a.speed)
    if not align:
        raise SystemExit("타임스탬프가 안 왔다 — 쉼 규칙을 적용할 수 없다(소리 짐작으로 되돌아가지 않는다)")
    Path(a.out + ".align.json").write_text(json.dumps(align, ensure_ascii=False), encoding="utf-8")
    log = shape(raw, align, a.out)
    os.remove(raw)
    print(json.dumps({"speed": sp, "emotion": a.emotion, "pauses": log}, ensure_ascii=False))


if __name__ == "__main__":
    main()
