"""SerpApi Google Lens로 레퍼런스 영상 프레임들을 역검색해 정확한 제품명
(브랜드+모델)을 추론(2026-07-10, "제품 직접 홍보형" 영상의 검색 정밀도
개선용). 어제는 이 Lens 역검색을 "구매처(쇼핑몰) 찾기"로 잘못 썼다가
삭제했는데, 오늘은 용도를 바꿔 검색 키워드 정밀도를 높이는 내부 단계로
재사용한다 — 결과를 사용자에게 보여주지 않고 키워드 생성에만 쓴다.

프레임마다 배경 소품(무관한 사물)을 잘못 잡는 경우가 실측 확인됐어서
(2026-07-09), 6개 프레임 전부 역검색한 뒤 Gemini에게 한번에 보여주고
여러 프레임에 걸쳐 일관되게 나오는 제품을 고르게 한다."""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from google.genai import types

from pipeline.atoms import key_vault
from shopping_shorts import comment_gen
from shopping_shorts.config import SERPAPI_KEY, SHORTS_GEMINI_KEYS

_LENS_ENDPOINT = "https://serpapi.com/search"
_MODEL = "gemini-3.1-flash-lite"

_PROMPT = """너는 쇼핑 영상 속 정확한 제품명을 찾아내는 전문가다.

이 영상의 카테고리: {category}
캡션: {caption}

아래는 영상의 여러 프레임을 구글 렌즈로 역검색한 결과다. 프레임마다 번호가
있고, 그 프레임과 시각적으로 유사한 웹 이미지들의 제목이 나열돼있다.
주의: 일부 프레임은 영상 속 배경 소품(무관한 사물)을 잘못 잡았을 수 있다.

{results}

여러 프레임에 걸쳐 일관되게 나타나는 제품(브랜드+모델명)이 있다면 그것이
진짜 홍보 대상 제품일 가능성이 높다. 확신이 서면 정확한 제품명을, 없으면
빈 문자열을 다음 JSON으로만 출력해라: {{"product_name": "브랜드+모델명 또는 빈 문자열"}}"""


def _lens_matches(image_url, api_key=None, max_results=5, timeout=60):
    """프레임 이미지 URL → [{"source","title"}, ...]. 실패 시 []( SerpApi
    호출 실패는 이 기능 전체가 "정밀도 향상 시도"일 뿐이라 조용히 스킵)."""
    key = api_key or SERPAPI_KEY
    if not key:
        return []
    params = {"engine": "google_lens", "url": image_url, "api_key": key}
    try:
        r = requests.get(_LENS_ENDPOINT, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return []
    matches = data.get("visual_matches") or []
    return [{"source": m.get("source", ""), "title": m.get("title", "")}
            for m in matches[:max_results] if m.get("title")]


def identify_product(frame_urls, category="", caption="", max_retries=3, quota_sleep=8):
    """프레임 이미지 URL 목록 → 정확한 제품명(문자열) 또는 확신 없으면 ""."""
    if not SERPAPI_KEY or not frame_urls:
        return ""
    with ThreadPoolExecutor(max_workers=len(frame_urls)) as ex:
        all_matches = list(ex.map(_lens_matches, frame_urls))

    lines = []
    for i, matches in enumerate(all_matches):
        if not matches:
            continue
        titles = "; ".join(m["title"] for m in matches)
        lines.append(f"프레임{i + 1}: {titles}")
    if not lines or not SHORTS_GEMINI_KEYS:
        return ""

    prompt = _PROMPT.format(category=category or "(미상)", caption=caption or "(없음)",
                             results="\n".join(lines))
    for attempt in range(max_retries):
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            return ""
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            data = json.loads(resp.text)
            return data.get("product_name") or ""
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                time.sleep(quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return ""
    return ""
