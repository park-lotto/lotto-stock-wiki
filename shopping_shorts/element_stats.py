"""대본 위키 학습소재 통계 — 자유서술 구조값(주변인물·말투 등)을 Gemini로
비슷한 것끼리 카테고리로 묶는다(2026-07-13, "학습소재 선택기").

topic_grouper.py와 같은 계열: 키풀 로테이션·클라이언트 캐시는 comment_gen 재사용.
표본이 너무 적으면(MIN_SAMPLES 미만) Gemini를 부르지 않고 즉시 []를 반환한다 —
데이터 부족한데 억지로 카테고리를 만들어내지 않기 위한 안전장치."""
import json

from google.genai import types

from shopping_shorts import comment_gen

_MODEL = comment_gen._MODEL
MIN_SAMPLES = 20

_PROMPT = """너는 한국 쇼핑 숏폼 대본의 "{element}" 요소를 분석하는 전문가다.
아래는 여러 잘 써진 대본에서 뽑은 실제 "{element}" 값들이다. 비슷한 것끼리
2~6개 카테고리로 묶어라(데이터가 다양하면 더 많이, 뻔하면 적게 — 억지로
개수를 맞추지 마라).

각 카테고리에: label(짧은 이름, 2~6자), description(1문장 설명),
examples(그 카테고리에 속하는 원본 값 중 대표적인 것 2~3개, 입력값 그대로).

[실제 값들]
{values}

다음 JSON으로만 출력: {{"categories": [{{"label":"...", "description":"...", "examples":["...","..."]}}]}}"""


def cluster_element_values(element, raw_values, max_key_tries=3):
    """자유서술 값 목록 → 카테고리 리스트. 표본부족(MIN_SAMPLES 미만)이거나
    무키·실패면 []."""
    values = [v for v in (raw_values or []) if (v or "").strip()]
    if len(values) < MIN_SAMPLES or not comment_gen.SHORTS_GEMINI_KEYS:
        return []
    prompt = _PROMPT.format(element=element, values="\n".join(f"- {v}" for v in values[:200]))
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return []
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            data = json.loads(resp.text)
            cats = data.get("categories") or []
            return [c for c in cats if c.get("label")]
        except Exception as e:  # noqa: BLE001 — 통계 실패는 치명적 아님(부가기능)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            return []
    return []
