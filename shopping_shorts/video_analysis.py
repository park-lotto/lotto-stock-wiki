"""Gemini에 영상 파일 자체를 입력해 제품/장면 키워드 추출 — 캡션 텍스트만 보는
tubefactory와의 차별화 핵심(설계문서 §1 참고). 전용 키 풀(comment_gen.py와 동일 패턴).

comment_gen.py와 같은 SHORTS_GEMINI_KEYS 풀을 사용하므로, 두 모듈은 같은
shorts_gemini_state.json 상태 파일을 공유해 하루 내 키 소진 추적을 동기화한다."""
import json
import sys
import time
from google import genai
from google.genai import types
from shopping_shorts.config import SHORTS_GEMINI_KEYS
from shopping_shorts import comment_gen
from pipeline.atoms import key_vault

_MODEL = "gemini-3.5-flash"  # 비디오 입력 지원 모델 — "gemini-3-flash"는 실존하지 않는 모델명이었음
# (2026-07-09 배포 후 실단말 검증 중 404 NOT_FOUND로 발견, 실제 사용 가능 모델 목록에서 확인 후 교체)

# 5개 언어(2026-07-10, "다른 프로그램보다 정확도 떨어짐" 피드백 대응) — ko/en만
# 검색에 쓰던 걸 5개어로 확장. zh는 원래도 생성만 하고 검색엔 안 쓰고 있었음
# (app.py의 _COLLECT_LANG_PRIORITY가 ko/en만 참조) — 중국어권(더우인·샤오홍슈
# 잠재대상)·일본어·러시아어권 창작자 콘텐츠를 전혀 못 찾던 게 정확도 격차의
# 실제 원인 중 하나.
_LANGS = ["ko", "en", "zh", "ja", "ru"]
_EMPTY = {"keywords": {lang: [] for lang in _LANGS}, "category": ""}

# response_mime_type="application/json"만으로는 필드 생략이 허용돼 Gemini가
# zh/ja/ru를 실제로 빈 배열([])로 돌려주는 사례가 실측 확인됨(2026-07-10,
# 프로덕션 DB에서 zh/ja/ru가 전부 [] — 샤오홍슈/도우인이 번역 없이 영어
# 문구로 검색되던 원인). minItems로 각 언어 배열이 최소 1개는 채워지도록
# 스키마로 강제.
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "object",
            "properties": {
                lang: {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5}
                for lang in _LANGS
            },
            "required": _LANGS,
        },
        "category": {"type": "string"},
        "lens_hint_sec": {"type": "number"},
    },
    "required": ["keywords", "category"],
}

_PROMPT = """이 영상을 보고 어떤 제품/장면을 다루는지 파악해라.

캡션(참고용, 영상 내용이 우선): {caption}

다음 JSON으로만 출력해라:
{{
  "keywords": {{
    "ko": ["핵심 키워드 2~5개, 한국어"],
    "en": ["같은 키워드의 영어 번역"],
    "zh": ["같은 키워드의 중국어(간체) 번역"],
    "ja": ["같은 키워드의 일본어 번역"],
    "ru": ["같은 키워드의 러시아어 번역"]
  }},
  "category": "카테고리 (예: 생활용품/홈케어, 뷰티, 주방가전, 식품/레시피 등)",
  "lens_hint_sec": "영상 내에서 그 제품(또는 완성된 요리)이 가장 선명하고 크게 화면을 채우는 순간의 타임스탬프(초, 숫자). 정면·클로즈업일수록 좋음"
}}

먼저 이 영상이 "상품을 보여주는 영상"인지 "레시피/조리법을 보여주는 영상"인지
구분해라 — 조리도구(에어프라이어·믹서기 등)가 화면에 보여도 그건 요리에 쓰인
도구일 뿐, 레시피 영상이면 진짜 주제는 그 도구가 아니라 완성되는 요리다.
카테고리도 "식품/레시피"로, 키워드도 도구 이름이 아니라 요리/기법 이름으로 잡아라
(예: 감자를 에어프라이어로 튀겨 속을 비우는 영상이면 카테고리="식품/레시피",
키워드="풍선 감자" ○ / 카테고리="주방가전", 키워드="에어프라이어" ×).

키워드는 반드시 영상 속에 실제로 등장하는 그 대상(상품이면 브랜드/모델,
레시피면 그 요리/기법의 정확한 이름)을 지칭해야 한다 — 그 이름을 검색했을 때
이 영상과 같은 것이 나와야 한다.

절대 하지 말 것: "아기 목욕", "목욕용품", "머리감기", "생활용품" 같이 카테고리
전체를 포괄하는 일반 명사나 행동 묘사. 이런 키워드로 검색하면 전혀 다른 무관한
결과가 쏟아진다. 예를 들어 아기가 물안경을 쓰고 목욕하는 영상이면 키워드는
"아기 물안경", "유아 수영 고글" 처럼 화면에 보이는 그 제품 자체여야 하고,
"아기 목욕"·"머리감기"는 안 된다.

각 언어 배열의 첫 번째 키워드는 가장 구체적인 것(브랜드/모델명이 보이면 그것)으로,
마지막 키워드 하나는 검색 실패에 대비한 대체용으로 만들어라 — 여전히 그 제품군을
가리켜야 하지만(카테고리 전체로 넓어지면 안 됨) 브랜드/모델 같은 세부 디테일을 뺀
한 단계 넓은 표현으로 한다("○○ 무선 청소기 A1 프로" → 대체 "무선 핸디청소기").

zh/ja/ru는 ko/en 문구를 그대로 축자 번역하지 말고, 그 언어권 창작자가 릴스·숏폼
캡션·해시태그에 실제로 쓸 법한 자연스러운 표현으로 써라(어순·조사·관용 표현
포함). 구체성 수준은 5개 언어 전부 동일하게 유지한다. 다른 텍스트 없이 JSON만
출력."""

_client_cache = {}


def _client_for_key(key):
    if key not in _client_cache:
        _client_cache[key] = genai.Client(api_key=key)
    return _client_cache[key]


def _wait_until_active(client, file_obj, max_wait_s=60, poll_interval=2):
    waited = 0
    state = file_obj.state.name
    while state == "PROCESSING" and waited < max_wait_s:
        time.sleep(poll_interval)
        waited += poll_interval
        file_obj = client.files.get(name=file_obj.name)
        state = file_obj.state.name
    if state != "ACTIVE":
        raise RuntimeError(f"video_analysis: 파일 처리 실패(state={state})")
    return file_obj


def analyze_video(video_path, caption, max_retries=5, quota_sleep=8):
    """영상 파일 → {"keywords": {...}, "category": "..."}. 실패 시 빈 결과.

    전용 키 풀(SHORTS_GEMINI_KEYS) 내에서만 로테이션 — comment_gen.py와 같은
    shorts_gemini_state.json 상태 파일을 공유해 하루 내 소진 추적을 동기화.
    전용 풀이 다 소진되면 그냥 {}. 최종 실패 시에도 {}.

    quota_sleep: 분당 쿼터 초과 시 대기 시간(초). 로테이션 가능한 키가 있으면
    먼저 로테이션(대기 없음), 전부 소진됐을 때만 짧게 대기."""
    if not SHORTS_GEMINI_KEYS:
        raise RuntimeError("video_analysis: SHORTS_GEMINI_KEY가 설정되지 않았습니다")

    prompt = _PROMPT.format(caption=caption or "(캡션 없음)")

    for attempt in range(max_retries):
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            return dict(_EMPTY)  # 전용 풀 전체 소진 — 공유 풀로 넘어가지 않고 여기서 멈춤

        client = _client_for_key(key)
        file_obj = None
        try:
            with open(video_path, "rb") as fh:
                file_obj = client.files.upload(file=fh, config=types.UploadFileConfig(mime_type="video/mp4"))
            file_obj = _wait_until_active(client, file_obj)
            resp = client.models.generate_content(
                model=_MODEL,
                contents=[file_obj, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                ),
            )
            data = json.loads(resp.text)
            got = data.get("keywords", {})
            return {
                "keywords": {lang: got.get(lang, []) for lang in _LANGS},
                "category": data.get("category", ""),
                "lens_hint_sec": data.get("lens_hint_sec"),
            }
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)  # 확실한 일일 한도 소진·계정비활성 영구 제외
                continue
            if key_vault.is_quota_error(e):
                # 분당 제한 등 "일일 소진"까지는 확인 안 되는 429 — 키를 영구
                # 제외하면 전용 풀(3개뿐)이 금방 동나므로, 같은 키로 짧게
                # 대기 후 재시도
                time.sleep(quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            print(f"video_analysis: 미분류 오류로 빈 결과 반환 — {e!r}", file=sys.stderr)
            return dict(_EMPTY)
        finally:
            if file_obj is not None:
                try:
                    client.files.delete(name=file_obj.name)
                except Exception:
                    pass

    return dict(_EMPTY)


_TRANSLATE_MODEL = "gemini-3.1-flash-lite"  # 텍스트 번역만이라 가벼운 모델로 충분 — 영상분석용 모델과 분리

_TRANSLATE_PROMPT = """다음 한국어 키워드를 4개 언어(영어/중국어 간체/일본어/러시아어)로
번역해라. 축자번역 대신 그 언어권 창작자가 실제 릴스·숏폼 캡션·해시태그에
쓸 법한 자연스러운 표현으로 쓰고, 구체성 수준은 한국어 원문과 동일하게 유지해라.

한국어 키워드: {keyword}

다음 JSON으로만 출력해라: {{"en": "...", "zh": "...", "ja": "...", "ru": "..."}}"""


def translate_keyword(keyword, max_retries=3, quota_sleep=8):
    """사용자가 직접 입력한 한국어 키워드 → 5개 언어(ko 포함) 딕셔너리.

    Gemini 자동 분석이 영상 내용을 잘못 짚었을 때(예: 레시피 영상을 조리도구
    상품 키워드로 잘못 잡음, 2026-07-13 실사용 피드백) 사용자가 정확한
    키워드를 직접 넣고 5개 언어로 바로 검색 링크를 만들 수 있게 한다.
    번역 실패해도 ko는 항상 채워서 반환 — 실패한 언어만 빈 문자열."""
    result = {"ko": keyword, "en": "", "zh": "", "ja": "", "ru": ""}
    if not keyword or not SHORTS_GEMINI_KEYS:
        return result

    prompt = _TRANSLATE_PROMPT.format(keyword=keyword)
    for attempt in range(max_retries):
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            return result
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_TRANSLATE_MODEL, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            data = json.loads(resp.text)
            for lang in ("en", "zh", "ja", "ru"):
                if data.get(lang):
                    result[lang] = data[lang]
            return result
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                time.sleep(quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return result
    return result
