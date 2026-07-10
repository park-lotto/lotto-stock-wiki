"""수집된 후보를 원본 프레임과 Gemini로 비교해 유사도 점수 매김 — tubefactory에 없는
검증 단계(설계문서 §3-5). 전용 키 풀 재사용.

comment_gen.py/video_analysis.py와 같은 SHORTS_GEMINI_KEYS 풀·상태 파일을 공유해
로테이션한다(2026-07-09, 최종 리뷰 Finding 3 — 예전엔 키[0]을 하드코딩해서 키[0]
소진 후 모든 후보가 영구 "미검증"으로 남는 버그가 있었음)."""
import json
import time
import requests
from google import genai
from google.genai import types
from shopping_shorts.config import SHORTS_GEMINI_KEYS
from shopping_shorts import comment_gen
from pipeline.atoms import key_vault

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


def score_candidate(original_frame_paths, candidate_thumbnail_url, max_retries=3, quota_sleep=8):
    """원본 프레임들 vs 후보 썸네일 URL → 0~1 유사도. 실패 시 None(미검증으로 남김).

    comment_gen.py/video_analysis.py와 같은 전용 키 풀(SHORTS_GEMINI_KEYS) 내에서
    로테이션한다 — 키[0]이 소진돼도 keys[1]/[2]로 계속 검증을 이어간다.

    quota_sleep: 분당 쿼터 초과 시 대기 시간(초). 로테이션 가능한 키가 있으면
    먼저 로테이션(대기 없음), 전부 소진됐을 때만 짧게 대기."""
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
    except Exception:
        return None

    for attempt in range(max_retries):
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            return None  # 전용 풀 전체 소진

        try:
            resp = _client_for_key(key).models.generate_content(
                model=_MODEL, contents=parts,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            data = json.loads(resp.text)
            return float(data.get("score", 0.0))
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)  # 확실한 일일 한도 소진·계정비활성 영구 제외
                continue
            if key_vault.is_quota_error(e):
                # 분당 제한 등 "일일 소진"까지는 확인 안 되는 429 — 같은 키로
                # 짧게 대기 후 재시도(comment_gen/video_analysis와 동일 패턴)
                time.sleep(quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return None

    return None
