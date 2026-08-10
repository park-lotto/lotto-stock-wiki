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
from shopping_shorts import serpapi_client
from shopping_shorts.config import SERPAPI_KEY, SERPAPI_KEYS, SHORTS_GEMINI_KEYS

_LENS_ENDPOINT = "https://serpapi.com/search"
_MODEL = "gemini-3.1-flash-lite"

_PROMPT = """너는 이 영상이 정확히 무엇을 다루는지 찾아내는 전문가다. 상품을
홍보하는 쇼핑 영상일 수도 있고, 레시피·조리법·기법·챌린지를 보여주는 영상일
수도 있다.

이 영상의 카테고리: {category}
캡션: {caption}

아래는 영상의 여러 프레임을 구글 렌즈로 역검색한 결과다. 프레임마다 번호가
있고, 그 프레임과 시각적으로 유사한 웹 이미지들의 제목이 나열돼있다.
주의: 일부 프레임은 영상 속 배경 소품이나 조리도구처럼 부수적인 사물을
잘못 잡았을 수 있다 — 예를 들어 레시피 영상에 에어프라이어가 화면에 보여도
그건 조리에 쓰인 도구일 뿐, 영상이 진짜 보여주려는 건 그 안에서 만들어지는
요리 자체다(2026-07-13, "풍선감자 레시피가 에어프라이어 상품으로 잘못 잡힘"
실사용 피드백). 마찬가지로 화면 구석의 인형·장식품이나 프레임 안의 진짜
동물·사람도 맥락일 뿐 주제가 아니다 — 그런 걸 낚아 엉뚱한 이름(예: 선풍기
옆 강아지 인형 때문에 "강아지 선풍기")을 짓지 마라(2026-07-29 실사용
피드백).

{results}

여러 프레임에 걸쳐 일관되게 나타나는 진짜 주제의 정확한 명칭을 찾아라:
- 상품 홍보 영상이면 브랜드+모델명
- 레시피·요리 영상이면 그 요리/기법의 정확한 이름 (조리도구 이름이 아니라
  완성되는 요리·기법의 이름. 예: "풍선 감자" ○, "에어프라이어" ×)
- 그 외 트렌드·챌린지라면 그 명칭

확신이 서면 정확한 명칭을, 없으면 빈 문자열을 다음 JSON으로만 출력해라:
{{"product_name": "정확한 명칭 또는 빈 문자열"}}"""


def _lens_matches(image_url, api_key=None, max_results=5, timeout=60):
    """프레임 이미지 URL → [{"source","title"}, ...]. 실패 시 []( SerpApi
    호출 실패는 이 기능 전체가 "정밀도 향상 시도"일 뿐이라 조용히 스킵)."""
    keys = [api_key] if api_key else (SERPAPI_KEYS or ([SERPAPI_KEY] if SERPAPI_KEY else []))
    if not keys:
        return []
    # 키 로테이션(2026-07-26): 현재 키가 월 무료한도 소진(429 등)이면 다음 키로 전환.
    for key in keys:
        params = {"engine": "google_lens", "url": image_url, "api_key": key}
        try:
            r = requests.get(_LENS_ENDPOINT, params=params, timeout=timeout)
            data = r.json()
        except (requests.RequestException, ValueError):
            return []
        if serpapi_client.is_exhausted(getattr(r, "status_code", 200), data):
            continue   # 이 키 소진 → 다음 키
        try:
            r.raise_for_status()
        except requests.RequestException:
            return []
        matches = data.get("visual_matches") or []
        return [{"source": m.get("source", ""), "title": m.get("title", "")}
                for m in matches[:max_results] if m.get("title")]
    return []   # 전 키 소진


def fetch_lens_lines(frame_urls):
    """프레임 URL 목록 → 프레임별 렌즈 매칭 결과를 프롬프트용 텍스트 줄로.

    이 함수는 SerpApi 호출(느린 네트워크 I/O)만 담당하고 category/caption에
    의존하지 않는다 — video_analysis.analyze_video()와 입력이 완전히 독립적
    이라 app.py에서 둘을 병렬 실행할 수 있게 분리함(2026-07-11, "분석" 버튼이
    느리다는 실사용 피드백 대응 — 기존엔 analyze_video 끝난 뒤에야 이 함수를
    불러 두 단계 시간이 그대로 더해졌음)."""
    if not (SERPAPI_KEYS or SERPAPI_KEY) or not frame_urls:
        return []
    with ThreadPoolExecutor(max_workers=len(frame_urls)) as ex:
        all_matches = list(ex.map(_lens_matches, frame_urls))

    lines = []
    for i, matches in enumerate(all_matches):
        if not matches:
            continue
        titles = "; ".join(m["title"] for m in matches)
        lines.append(f"프레임{i + 1}: {titles}")
    return lines


def identify_product_from_lines(lines, category="", caption="", max_retries=3, quota_sleep=8):
    """fetch_lens_lines() 결과(프레임별 렌즈 매칭 텍스트) → Gemini로 여러
    프레임에 걸쳐 일관된 제품명 하나를 확정. 확신 없으면 ""."""
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


def identify_product(frame_urls, category="", caption="", max_retries=3, quota_sleep=8):
    """프레임 이미지 URL 목록 → 정확한 제품명(문자열) 또는 확신 없으면 "".

    fetch_lens_lines()+identify_product_from_lines()를 순차로 묶은 편의
    함수(단독 호출 시 사용). app.py는 analyze_video()와 병렬 실행하려고
    fetch_lens_lines()를 직접 부른다."""
    if not (SERPAPI_KEYS or SERPAPI_KEY) or not frame_urls:
        return ""
    lines = fetch_lens_lines(frame_urls)
    return identify_product_from_lines(lines, category, caption, max_retries, quota_sleep)
