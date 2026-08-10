# -*- coding: utf-8 -*-
"""숨은 파라미터 실측 — 문서에 없는 필드를 API에 직접 던져 응답으로 확인."""
import io
import json
import os
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

KEY = os.environ.get("TYPECAST_API_KEY", "")
URL = "https://api.typecast.ai/v1/text-to-speech"
VOICE = "tc_692799c46508f6b9468c54c7"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe")
os.makedirs(OUT, exist_ok=True)
TEXT = "이거 수리 맡기면 30만원은 그냥 깨지죠."


def probe(label, body, save=False):
    b = dict({"voice_id": VOICE, "text": TEXT, "model": "ssfm-v30",
              "language": "kor", "seed": 42}, **body)
    try:
        r = requests.post(URL, headers={"X-API-KEY": KEY}, json=b, timeout=90)
    except Exception as e:
        print(f"  [ERR ] {label}: {e}")
        return False
    if r.status_code == 200:
        if save:
            with open(os.path.join(OUT, f"{label}.wav"), "wb") as f:
                f.write(r.content)
        print(f"  [PASS] {label}  ({len(r.content)//1024}KB)")
        return True
    # 에러 본문이 어떤 필드를 문제 삼는지가 곧 스펙이다
    try:
        d = r.json()
        msg = json.dumps(d, ensure_ascii=False)[:260]
    except Exception:
        msg = r.text[:260]
    print(f"  [{r.status_code}] {label}: {msg}")
    return False


print("=== A. emotion_prompt (커스텀 감정 — 문장으로 지정) ===")
probe("custom_emotion_kr",
      {"prompt": {"emotion_type": "custom", "emotion_prompt": "다급하고 놀란 목소리로"}}, save=True)
probe("custom_emotion_en",
      {"prompt": {"emotion_type": "custom", "emotion_prompt": "urgent and shocked"}}, save=True)
probe("emotion_prompt_only",
      {"prompt": {"emotion_prompt": "놀란 목소리로"}}, save=True)
probe("preset_plus_prompt",
      {"prompt": {"emotion_type": "preset", "emotion_preset": "angry",
                  "emotion_prompt": "놀란 목소리로"}})

print()
print("=== B. 문장 끝 피치 (last_pitch) ===")
for f in ("last_pitch", "audio_last_pitch", "pitch_end"):
    probe(f, {"output": {"audio_format": "wav", f: 3}}, save=True)

print()
print("=== C. 길이 제어 (duration / max_length) ===")
for f in ("duration", "audio_duration", "max_length", "max_duration"):
    probe(f, {"output": {"audio_format": "wav", f: 3.0}}, save=True)

print()
print("=== D. SSFM style ===")
for f in ("style", "style_label", "speaking_style"):
    probe(f, {"prompt": {"emotion_type": "preset", "emotion_preset": "normal", f: "narration"}})

print()
print("=== E. 잘못된 값 → 허용 목록이 에러에 드러난다 ===")
probe("bad_emotion_type", {"prompt": {"emotion_type": "ZZZ"}})
probe("bad_preset", {"prompt": {"emotion_type": "preset", "emotion_preset": "ZZZ"}})
probe("bad_output_field", {"output": {"audio_format": "wav", "zzz_unknown": 1}})
probe("intensity_over", {"prompt": {"emotion_type": "preset",
                                    "emotion_preset": "happy", "emotion_intensity": 5.0}})
probe("pitch_over", {"output": {"audio_format": "wav", "audio_pitch": 30}})
