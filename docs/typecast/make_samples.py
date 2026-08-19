# -*- coding: utf-8 -*-
"""타입캐스트 샘플 굽기 — 사장님 청취용(감정 x 속도 조합).

일레븐랩스 기존 샘플과 **같은 대사**(build_voice_samples.DEMO_TEXT)를 써서 바로 비교되게 한다.
`/with-timestamps`로 받아 정렬 사이드카까지 같이 저장 — 자막 싱크가 실제 파일에서도
살아있는지 확인하려는 것(실측 2026-08-19에서 형식 일치는 확인됨).

실행: py docs/typecast/make_samples.py
출력: out/typecast_samples/*.mp3 (+ .align.json)
"""
import base64
import io
import json
import os
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "out", "typecast_samples")
URL = "https://api.typecast.ai/v1/text-to-speech/with-timestamps"

# 일레븐랩스 샘플과 동일 대사(shopping_shorts/scripts/build_voice_samples.py:15)
DEMO_TEXT = "시어머니가 알려주신 이 세제로 욕실을 청소했더니 구석구석 반짝반짝, 찌든 때가 싹 없어졌더라고요."

# 채널 톤(시월드형·엄마정보통형)에 맞는 한국 여성 화자 위주 + 대조용 남성 1명.
# emotions는 /v1/voices 실측값 — 지원 안 하는 감정을 걸면 EMOTION_NOT_SUPPORTED 422.
VOICES = [
    ("Seohyeon", "tc_69f2e455ea79fd197aa0476f"),
    ("Jungsook", "tc_694b51e6dc12c8f4ec1a959c"),
    ("Okji",     "tc_699d27b557c86e3f4249c051"),
    ("Mongsil",  "tc_699d27e0e061695d6ed39bc6"),
]

# 프리셋 default_speed가 1.6이라 그 값을 반드시 포함한다(ElevenLabs는 1.2 clamp라 못 내던 소리).
CASES = [
    ("normal_x1.0",  "normal",   1.0, 1.0),
    ("normal_x1.6",  "normal",   1.0, 1.6),
    ("happy_x1.6",   "happy",    1.3, 1.6),
    ("toneup_x1.6",  "toneup",   1.3, 1.6),
    ("whisper_x1.4", "whisper",  1.0, 1.4),
]


def _key():
    k = os.environ.get("TYPECAST_API_KEY", "")
    if k:
        return k
    with open(os.path.join(ROOT, ".env"), encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("TYPECAST_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


KEY = _key()


def to_alignment(chars):
    """타입캐스트 characters[] → 우리 사이드카 형식(tts_timestamps.words_from_alignment).

    ★end까지 실어야 한다 — 하나라도 빠지면 None을 반환해 조용히 ASR 폴백으로 강등된다
    (2026-08-19 실측에서 직접 밟은 함정)."""
    return {
        "characters": [c["text"] for c in chars],
        "character_start_times_seconds": [c["start"] for c in chars],
        "character_end_times_seconds": [c["end"] for c in chars],
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f"키 {len(KEY)}자 · 대사 {len(DEMO_TEXT)}자 · 출력 {OUT}\n")
    ok = fail = 0
    for vname, vid in VOICES:
        for label, emo, intensity, tempo in CASES:
            name = f"{vname}_{label}"
            body = {
                "voice_id": vid, "text": DEMO_TEXT, "model": "ssfm-v30",
                "language": "kor", "seed": 42,
                "prompt": {"emotion_type": "preset", "emotion_preset": emo,
                           "emotion_intensity": intensity},
                "output": {"audio_format": "mp3", "audio_tempo": tempo},
            }
            try:
                r = requests.post(URL, headers={"X-API-KEY": KEY}, json=body, timeout=120)
            except Exception as e:
                print(f"  [ERR ] {name}: {type(e).__name__}")
                fail += 1
                continue
            if r.status_code != 200:
                print(f"  [{r.status_code}] {name}: {r.text[:120]}")
                fail += 1
                continue
            d = r.json()
            mp3 = os.path.join(OUT, name + ".mp3")
            with open(mp3, "wb") as f:
                f.write(base64.b64decode(d["audio"]))
            chars = d.get("characters") or []
            if chars:
                with open(mp3 + ".align.json", "w", encoding="utf-8") as f:
                    json.dump(to_alignment(chars), f, ensure_ascii=False)
            print(f"  [OK] {name:<24} {d.get('audio_duration')}초  "
                  f"{os.path.getsize(mp3)//1024}KB  정렬 {len(chars)}자")
            ok += 1
    print(f"\n성공 {ok} · 실패 {fail}")

    # 사이드카가 실제로 우리 함수를 통과하는지 파일 기준으로 재확인
    sys.path.insert(0, ROOT)
    from shopping_shorts import tts_timestamps
    made = sorted(f for f in os.listdir(OUT) if f.endswith(".mp3"))
    if made:
        probe = os.path.join(OUT, made[0])
        words = tts_timestamps.words_from_mp3(probe)
        print(f"\n사이드카 검증({made[0]}): 단어 {len(words) if words else 0}개")
        for w in (words or [])[:5]:
            print(f"    {json.dumps(w, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
