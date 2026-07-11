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
                lang: {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5}
                for lang in _LANGS
            },
            "required": _LANGS,
        },
        "category": {"type": "string"},
    },
    "required": ["keywords", "category"],
}

_PROMPT = """이 영상을 보고 어떤 제품/장면을 다루는지 파악해라.

캡션(참고용, 영상 내용이 우선): {caption}

다음 JSON으로만 출력해라:
{{
  "keywords": {{
    "ko": ["핵심 키워드 3~5개, 한국어"],
    "en": ["같은 키워드의 영어 번역"],
    "zh": ["같은 키워드의 중국어(간체) 번역"],
    "ja": ["같은 키워드의 일본어 번역"],
    "ru": ["같은 키워드의 러시아어 번역"]
  }},
  "category": "제품 카테고리 (예: 생활용품/홈케어, 뷰티, 주방가전 등)"
}}

키워드는 반드시 영상 속에 실제로 등장하는 그 제품(브랜드/모델/구체적 형태)을
지칭해야 한다 — 그 제품을 검색했을 때 이 영상과 같은 제품이 나와야 한다.

절대 하지 말 것: "아기 목욕", "목욕용품", "머리감기", "생활용품" 같이 카테고리
전체를 포괄하는 일반 명사나 행동 묘사. 이런 키워드로 검색하면 전혀 다른 무관한
제품이 쏟아진다. 예를 들어 아기가 물안경을 쓰고 목욕하는 영상이면 키워드는
"아기 물안경", "유아 수영 고글" 처럼 화면에 보이는 그 제품 자체여야 하고,
"아기 목욕"·"머리감기"는 안 된다.

같은 원칙으로 5개 언어 전부 동일한 구체성을 유지해라(번역만 다르고 포괄
범위가 넓어지면 안 됨). 다른 텍스트 없이 JSON만 출력."""

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
