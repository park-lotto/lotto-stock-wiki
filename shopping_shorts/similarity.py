"""수집된 후보를 원본 프레임과 Gemini로 비교해 유사도 점수 매김 — tubefactory에 없는
검증 단계(설계문서 §3-5). 전용 키 풀 재사용."""
import json
import requests
from google import genai
from google.genai import types
from shopping_shorts.config import SHORTS_GEMINI_KEYS

_MODEL = "gemini-3.5-flash"  # "gemini-3-flash"는 실존하지 않는 모델명이었음(2026-07-09 발견, video_analysis.py와 동일 이슈)

_PROMPT = """첫 번째 이미지들은 원본 영상의 대표 장면이고, 마지막 이미지는 다른 곳에서 찾은
후보 영상의 썸네일이다. 후보가 원본과 같은 제품/장면을 다루고 있는지 판단해라.

JSON으로만 출력: {"score": 0.0~1.0 사이 유사도, "reason": "짧은 근거"}
같은 제품이 확실하면 0.8 이상, 관련은 있으나 다른 제품이면 0.3~0.6, 전혀 무관하면 0.2 이하."""

_client_cache = {}


def _client_for_key(key):
    if key not in _client_cache:
        _client_cache[key] = genai.Client(api_key=key)
    return _client_cache[key]


def score_candidate(original_frame_paths, candidate_thumbnail_url):
    """원본 프레임들 vs 후보 썸네일 URL → 0~1 유사도. 실패 시 None(미검증으로 남김)."""
    if not SHORTS_GEMINI_KEYS:
        return None
    try:
        parts = []
        for p in original_frame_paths:
            with open(p, "rb") as fh:
                parts.append(types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg"))
        cand_bytes = requests.get(candidate_thumbnail_url, timeout=15).content
        parts.append(types.Part.from_bytes(data=cand_bytes, mime_type="image/jpeg"))
        parts.append(_PROMPT)

        resp = _client_for_key(SHORTS_GEMINI_KEYS[0]).models.generate_content(
            model=_MODEL, contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        data = json.loads(resp.text)
        return float(data.get("score", 0.0))
    except Exception:
        return None
