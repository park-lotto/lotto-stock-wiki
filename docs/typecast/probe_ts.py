# -*- coding: utf-8 -*-
"""타임스탬프(자막 싱크) 실측 — 타입캐스트가 문자/단어 시각을 주는가.

왜 이걸 재나: 우리 파이프라인은 mp3 옆 사이드카에 ElevenLabs /with-timestamps의
{"characters":[...], "character_start_times_seconds":[...]}를 저장해 자막을 맞춘다
(tts_timestamps.words_from_alignment). 타입캐스트로 갈아타려면 같은 값을 받아야
자막이 안 밀린다. 없으면 GROQ Whisper 재전사 폴백으로 되돌아간다(비용·오차 부활).

실행: py docs/typecast/probe_ts.py
"""
import io
import json
import os
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _load_key():
    """.env에서 TYPECAST_API_KEY. 환경변수가 있으면 그쪽 우선."""
    k = os.environ.get("TYPECAST_API_KEY", "")
    if k:
        return k
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        with open(os.path.join(root, ".env"), encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("TYPECAST_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


KEY = _load_key()
BASE = "https://api.typecast.ai"
VOICE = "tc_692799c46508f6b9468c54c7"
TEXT = "이거 수리 맡기면 30만원은 그냥 깨지죠."
HDR = {"X-API-KEY": KEY}

# 우리 파이프라인이 실제로 읽는 키(tts_timestamps.words_from_alignment:114-115)
NEEDED = ("characters", "character_start_times_seconds")


def _body(**extra):
    return dict({"voice_id": VOICE, "text": TEXT, "model": "ssfm-v30",
                 "language": "kor", "seed": 42}, **extra)


def post(label, path, body):
    """POST 후 (status, 헤더요약, JSON여부, 본문미리보기) 출력. 정렬 흔적을 찾는다."""
    try:
        r = requests.post(BASE + path, headers=HDR, json=body, timeout=90)
    except Exception as e:
        print(f"  [ERR ] {label}: {type(e).__name__} {e}")
        return None
    ctype = r.headers.get("content-type", "")
    print(f"  [{r.status_code}] {label}  ct={ctype}  {len(r.content)}B")
    # 오디오가 그냥 오면 정렬은 없다는 뜻 — 헤더에 실려오는지도 본다
    interesting = {k: v for k, v in r.headers.items()
                   if any(w in k.lower() for w in ("align", "time", "stamp", "dur", "sync"))}
    if interesting:
        print(f"         헤더 후보: {interesting}")
    if "json" in ctype:
        try:
            d = r.json()
            if isinstance(d, dict):
                print(f"         JSON keys: {list(d.keys())[:12]}")
                hit = [k for k in NEEDED if k in d]
                if hit:
                    print(f"         ★우리 형식 일치: {hit}")
            else:
                print(f"         JSON: {json.dumps(d, ensure_ascii=False)[:200]}")
        except ValueError:
            print(f"         본문: {r.text[:200]}")
    elif r.status_code != 200:
        print(f"         본문: {r.text[:260]}")
    return r


print(f"키 길이: {len(KEY)}\n")

print("=== A. 전용 타임스탬프 엔드포인트가 있는가 (ElevenLabs식 경로 탐색) ===")
for p in ("/v1/text-to-speech/with-timestamps",
          "/v1/text-to-speech/timestamps",
          "/v1/text-to-speech/alignment",
          f"/v1/text-to-speech/{VOICE}/with-timestamps"):
    post(p, p, _body())

print("\n=== B. 요청 필드로 정렬을 요구할 수 있는가 ===")
for label, extra in (("with_timestamps", {"with_timestamps": True}),
                     ("return_alignment", {"return_alignment": True}),
                     ("output.with_timestamps", {"output": {"with_timestamps": True}}),
                     ("output.alignment", {"output": {"alignment": True}}),
                     ("timestamps", {"timestamps": True})):
    post(label, "/v1/text-to-speech", _body(**extra))

print("\n=== C. 기본 응답 자체에 정렬이 실려오는가 (대조군) ===")
post("plain", "/v1/text-to-speech", _body())

print("\n=== D. 문서화된 엔드포인트 목록 (GET 탐색) ===")
for p in ("/v1/text-to-speech", "/openapi.json", "/docs"):
    try:
        r = requests.get(BASE + p, headers=HDR, timeout=20)
        print(f"  [{r.status_code}] GET {p}  ct={r.headers.get('content-type','')}  {len(r.content)}B")
        if p == "/openapi.json" and r.status_code == 200:
            try:
                spec = r.json()
                paths = list(spec.get("paths", {}).keys())
                print(f"         ★공개 경로 {len(paths)}개: {paths}")
            except ValueError:
                pass
    except Exception as e:
        print(f"  [ERR ] GET {p}: {type(e).__name__}")
