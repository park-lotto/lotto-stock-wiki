# -*- coding: utf-8 -*-
"""숨은 감정 13종 + 문장끝 피치 실측 — 진짜 소리가 바뀌는지 확인."""
import hashlib
import io
import os
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
KEY = os.environ.get("TYPECAST_API_KEY", "")
URL = "https://api.typecast.ai/v1/text-to-speech"
VOICE = "tc_692799c46508f6b9468c54c7"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emo")
os.makedirs(OUT, exist_ok=True)
TEXT = "이거 수리 맡기면 30만원은 그냥 깨지죠."

# API 에러가 뱉은 전체 20종. 문서엔 7종만 적혀 있었다.
ALL = ["normal", "sad", "happy", "angry", "regret", "urgent", "whisper", "scream",
       "shout", "trustful", "soft", "cold", "sarcasm", "inspire", "cute", "cheer",
       "casual", "tonemid", "toneup", "tonedown"]
DOCUMENTED = {"normal", "sad", "happy", "angry", "whisper", "toneup", "tonedown"}


def synth(body, path=None):
    b = dict({"voice_id": VOICE, "text": TEXT, "model": "ssfm-v30",
              "language": "kor", "seed": 42}, **body)
    r = requests.post(URL, headers={"X-API-KEY": KEY}, json=b, timeout=90)
    if r.status_code != 200:
        return None, f"HTTP{r.status_code} {r.text[:120]}"
    if path:
        with open(path, "wb") as f:
            f.write(r.content)
    return r.content, None


print("=== 감정 프리셋 20종 — 실제로 소리가 다른가 ===")
digests = {}
for e in ALL:
    tag = "" if e in DOCUMENTED else "  ★문서에 없던 것"
    data, err = synth(
        {"prompt": {"emotion_type": "preset", "emotion_preset": e, "emotion_intensity": 1.5},
         "output": {"audio_format": "wav"}},
        os.path.join(OUT, f"{e}.wav"))
    if err:
        print(f"  [FAIL] {e}: {err}")
        continue
    d = hashlib.md5(data).hexdigest()[:10]
    digests[e] = d
    print(f"  [OK] {e:10s} {len(data)//1024:4d}KB  md5={d}{tag}")

uniq = len(set(digests.values()))
print(f"\n  고유 음성 {uniq}종 / 합성 {len(digests)}종  "
      f"→ {'전부 다르다(진짜 감정)' if uniq == len(digests) else '중복 있음 — 별칭이거나 미지원'}")

print()
print("=== 문장 끝 피치 (last_pitch) — 값이 실제로 먹히나 ===")
prev = None
for v in (-6, 0, 6):
    data, err = synth({"output": {"audio_format": "wav", "last_pitch": v}},
                      os.path.join(OUT, f"lastpitch_{v}.wav"))
    if err:
        print(f"  [FAIL] last_pitch={v}: {err}")
        continue
    d = hashlib.md5(data).hexdigest()[:10]
    same = " (앞과 동일 → 무시되는 필드)" if d == prev else ""
    print(f"  last_pitch={v:+d}  {len(data)//1024}KB  md5={d}{same}")
    prev = d

print()
print("=== duration — 값이 실제로 먹히나 ===")
prev = None
for v in (2.0, 5.0):
    data, err = synth({"output": {"audio_format": "wav", "duration": v}},
                      os.path.join(OUT, f"dur_{v}.wav"))
    if err:
        print(f"  [FAIL] duration={v}: {err}")
        continue
    d = hashlib.md5(data).hexdigest()[:10]
    same = " (앞과 동일 → 무시되는 필드)" if d == prev else ""
    print(f"  duration={v}  {len(data)//1024}KB  md5={d}{same}")
    prev = d

print()
print("=== 대조군: 아무 옵션 없음 ===")
data, err = synth({"output": {"audio_format": "wav"}}, os.path.join(OUT, "baseline.wav"))
if not err:
    print(f"  baseline  {len(data)//1024}KB  md5={hashlib.md5(data).hexdigest()[:10]}")
