# -*- coding: utf-8 -*-
"""/v1/text-to-speech/with-timestamps 응답 구조 해부 → 우리 사이드카 형식과 대조.

우리가 읽는 형식(tts_timestamps.words_from_alignment:114-115):
    {"characters": [...], "character_start_times_seconds": [...]}
타입캐스트가 뭘 주는지 실제 값으로 확인하고, 변환 가능한지 판정한다.
"""
import io
import json
import os
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

VOICE = "tc_692799c46508f6b9468c54c7"
TEXT = "이거 수리 맡기면 30만원은 그냥 깨지죠."


def _load_key():
    """.env에서 TYPECAST_API_KEY. probe_ts를 import하면 그쪽 본문이 다시 실행되므로 복사."""
    k = os.environ.get("TYPECAST_API_KEY", "")
    if k:
        return k
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    with open(os.path.join(root, ".env"), encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("TYPECAST_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


KEY = _load_key()
URL = "https://api.typecast.ai/v1/text-to-speech/with-timestamps"

r = requests.post(URL, headers={"X-API-KEY": KEY},
                  json={"voice_id": VOICE, "text": TEXT, "model": "ssfm-v30",
                        "language": "kor", "seed": 42}, timeout=90)
print("status", r.status_code)
d = r.json()

print("\n=== 최상위 키 ===")
for k, v in d.items():
    if isinstance(v, str) and len(v) > 80:
        print(f"  {k}: <str {len(v)}자>")
    elif isinstance(v, list):
        print(f"  {k}: <list {len(v)}개>")
    else:
        print(f"  {k}: {v!r}")

print("\n=== words 앞 5개 ===")
for w in (d.get("words") or [])[:5]:
    print(f"  {json.dumps(w, ensure_ascii=False)}")

print("\n=== characters 앞 8개 ===")
chars = d.get("characters") or []
for c in chars[:8]:
    print(f"  {json.dumps(c, ensure_ascii=False)}")

print(f"\n=== 대조: 원문 글자수 vs characters 개수 ===")
print(f"  원문 {len(TEXT)}자 / characters {len(chars)}개")

# 우리 형식으로 변환 가능한지 실제로 해본다
print("\n=== 우리 형식으로 변환 시도 ===")
try:
    if chars and isinstance(chars[0], dict):
        keys = list(chars[0].keys())
        print(f"  character 항목 키: {keys}")
        tk = next((k for k in keys if "text" in k or "char" in k), None)
        sk = next((k for k in keys if "start" in k), None)
        print(f"  → 글자 필드={tk!r}  시작시각 필드={sk!r}")
        ek = next((k for k in keys if "end" in k), None)
        print(f"  → 끝시각 필드={ek!r}")
        if tk and sk and ek:
            # words_from_alignment는 end까지 있어야 한다(:117 — 하나라도 없으면 None)
            alignment = {
                "characters": [c[tk] for c in chars],
                "character_start_times_seconds": [c[sk] for c in chars],
                "character_end_times_seconds": [c[ek] for c in chars],
            }
            print(f"  ★변환 성공: characters {len(alignment['characters'])}개")
            print(f"    앞 12글자: {alignment['characters'][:12]}")
            print(f"    앞 12시각: {[round(float(x), 3) for x in alignment['character_start_times_seconds'][:12]]}")
            # 실제로 우리 함수에 먹여본다
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sys.path.insert(0, root)
            from shopping_shorts import tts_timestamps
            words = tts_timestamps.words_from_alignment(alignment)
            print(f"  ★우리 words_from_alignment 통과: 단어 {len(words)}개")
            for w in words[:6]:
                print(f"      {json.dumps(w, ensure_ascii=False)}")
except Exception as e:
    print(f"  [ERR] {type(e).__name__}: {e}")

print("\n=== 오디오 포맷 (현행은 mp3 사이드카 전제) ===")
print(f"  audio_format={d.get('audio_format')!r}  audio_duration={d.get('audio_duration')!r}")
