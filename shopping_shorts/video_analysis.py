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
from shopping_shorts import usage_meter
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
        # 타임아웃 미지정 시 느린 Gemini 응답에 무한 대기할 수 있음(comment_gen._client_for_key
        # 참고 — 2026-07-14 실사고).
        _client_cache[key] = usage_meter.wrap(
            genai.Client(api_key=key, http_options=types.HttpOptions(timeout=120_000)))
    return _client_cache[key]


def _wait_until_active(client, file_obj, max_wait_s=180, poll_interval=2):
    # 대기 상한 180초(2026-07-29): 예전 60초는 조급해서 '조금 느린' 영상(길거나·제미니가 잠깐
    # 붐빌 때)이 준비 전에 실패로 던져져 빈 추출→대본이 짧아졌다(5a8e089d 10초 실사고). 제미니는
    # 재업로드해도 다시 PROCESSING부터라 조급하게 끊는 이득이 없다 — 실제 준비될 때까지 기다린다.
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
        key, idx = comment_gen._next_live_key_and_idx()
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
                # 대기 후 재시도. 서버가 대기시간을 알려주면 그 값을 쓴다(2026-08-09).
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
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
        key, idx = comment_gen._next_live_key_and_idx()
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
                # 서버가 "N초 뒤에 오라"고 알려주면 그만큼 잔다(2026-08-09).
                # 고정 8초는 실제 대기(45초)에 한참 못 미쳐 재시도 3번이 전부
                # 429로 타버렸고, 결과가 조용한 빈 값이라 태거가 0/40건만 찍었다.
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return result
    return result


_CN_KEYWORD_PROMPT = """다음은 한국어 쇼츠 영상 캡션이다. 이 영상 속 '바로 그 제품/소재'와 같은 \
영상을 중국 SNS(샤오홍슈/도우인)에서 찾기 위한 중국어 검색어 하나만 출력해라.
- 넓은 카테고리(예: 发光玩具)가 아니라 그 제품을 특정하는 구체적 표현(예: 彩虹发光水枪)
- 감탄사·가격·해시태그 기호는 빼되, 제품을 특정하는 색·형태·용도·브랜드는 포함(예: 다이소→大创)
- 너무 좁혀 결과가 없을 것 같으면 한 단계만 일반화
- 2~10자, JSON만: {{"zh": "검색어"}}
캡션: {caption}"""


def cn_search_keyword(caption, max_retries=3, quota_sleep=8):
    """한국어 캡션 → 중국 SNS 검색용 중국어 소재 키워드(zh). 실패 시 ''.

    렌즈 유사영상의 샤오홍슈/도우인 자동합류용. 캡션 앞 토큰을 기계적으로 잘라 직역하면
    수식어·감탄사가 섞여 엉뚱한 검색이 됐다(라이브 실측: 무관한 영상 대량). Gemini에게
    '소재'만 뽑게 하면 정확하다(서버 실측: '작물로 만든 장아찌…'→'小菜制作'→凉菜/拌菜,
    '좁은 현관에 이거…'→'玄关收纳'→신발장 정리)."""
    if not caption or not SHORTS_GEMINI_KEYS:
        return ""
    prompt = _CN_KEYWORD_PROMPT.format(caption=caption[:400])
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return ""
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_TRANSLATE_MODEL, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return (json.loads(resp.text).get("zh") or "").strip()
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                # 서버가 "N초 뒤에 오라"고 알려주면 그만큼 잔다(2026-08-09).
                # 고정 8초는 실제 대기(45초)에 한참 못 미쳐 재시도 3번이 전부
                # 429로 타버렸고, 결과가 조용한 빈 값이라 태거가 0/40건만 찍었다.
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return ""
    return ""


# ── 렌즈 유사영상: 프레임 비전 추출 + 유사도 판정(2026-07-18) ──
# 사장님 요구: 캡션 텍스트만으로는 부족. 영상 프레임/썸네일에 박힌 제품명("LED 물총")과
# 물건 생김새까지 보고 제품을 특정해야 한다("영상 보고 샤오홍슈 검색어 뽑기" + 장치 추가).
_CN_VISION_PROMPT = """이 이미지는 한국어 쇼츠 영상의 한 장면(썸네일)이다. 화면에 박힌 글자\
(제품명 등)와 물건의 생김새를 보고, 아래 캡션과 종합해 '이 영상이 소개하는 바로 그 제품/소재'를 \
특정하라. 그 제품과 같은 영상을 중국 SNS(샤오홍슈/도우인)에서 찾을 중국어 검색어를 만들라.
- 넓은 카테고리 말고 제품 특정(색·형태·용도·브랜드 포함, 예: 다이소→大创, 물총→水枪)
- 화면 글자에 제품명이 있으면 그것을 최우선 반영
- 너무 좁혀 결과가 없을 것 같으면 한 단계만 일반화
- 2~10자, JSON만: {{"product": "한국어 제품명(짧게)", "zh": "중국어 검색어"}}
캡션: {caption}"""


_SUBJECT_TAGS_PROMPT = """이 이미지는 한국어 쇼츠 영상의 썸네일이다. 화면에 박힌 글자(제목·주제어)\
와 물건의 생김새를, 아래 캡션과 종합해 이 영상이 다루는 '주제'를 특정하라. 랭킹 검색에서
"오이"·"빵" 같은 검색어로 이 영상이 잡히게 만드는 게 목적이다.
- 화면 글자에 주제어가 있으면 그것을 최우선 반영(캡션엔 없고 자막에만 있는 경우가 많다).
- subject: 이 영상의 주제 명사 1개(짧게. 예: 오이무침, 블루투스 스피커, 베이글, 소파).
- keywords: 검색에 쓸 3~6개(주제 명사·핵심 재료·용도·상위 분류. 예: ["오이","다이어트반찬","여름반찬"]).
  ⚠️ 캡션에 우연히 들어간 말이 아니라 '영상이 실제로 다루는 것'만.
- JSON만: {{"subject": "...", "keywords": ["...", ...]}}
캡션: {caption}"""

_SUBJECT_TAGS_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
    },
    "required": ["subject", "keywords"],
}


# ★키 선택은 전부 comment_gen._next_live_key_and_idx()를 쓴다(2026-08-06).
# _current_key_and_idx는 늘 live[0]만 돌려주므로, 키가 23개여도 이 파일의 모든
# 요청이 1번 키 하나를 때렸다 — 무료등급 분당 15건(실측: 16번째에 429)에 묶여
# 병렬로 돌려도 처리량이 안 늘었다(워커 8→24로 올려도 37~39건/분 평평).
# 라운드로빈으로 바꾸면 키 수만큼 곱해진다. 2026-07-23에 comment_gen 쪽을 고칠 때
# (성공률 7%→29%) 이 파일 9곳이 통째로 빠져 있었다.
def subject_tags_vision(image_bytes, caption, max_retries=3, quota_sleep=8):
    """썸네일 이미지(+캡션) → {"subject": str, "keywords": [str]}. 랭킹 검색용 주제태그.
    화면 자막·물건 생김새를 읽어 캡션에 없는 주제어도 뽑는다. 키 없음/실패 시 {} (→ 캡션 백업 검색)."""
    if not image_bytes or not SHORTS_GEMINI_KEYS:
        return {}
    prompt = _SUBJECT_TAGS_PROMPT.format(caption=(caption or "(캡션 없음)")[:400])
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return {}
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_TRANSLATE_MODEL,  # flash-lite — 썸네일 1장이라 가벼운 모델로 충분
                contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_SUBJECT_TAGS_SCHEMA,
                ),
            )
            data = json.loads(resp.text)
            subject = (data.get("subject") or "").strip()
            keywords = [k.strip() for k in (data.get("keywords") or []) if k and k.strip()]
            if not subject and not keywords:
                return {}
            return {"subject": subject, "keywords": keywords}
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                # 서버가 "N초 뒤에 오라"고 알려주면 그만큼 잔다(2026-08-09).
                # 고정 8초는 실제 대기(45초)에 한참 못 미쳐 재시도 3번이 전부
                # 429로 타버렸고, 결과가 조용한 빈 값이라 태거가 0/40건만 찍었다.
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return {}
    return {}


_FACE_FORWARD_PROMPT = """이 이미지는 한국어 쇼츠 영상의 썸네일이다. 사람(진행자)의 얼굴·모습이
화면의 주인공인지 판정하라. 쇼핑 제품을 보여주는 채널을 찾는 게 목적이다.
- true = 사람 얼굴·상반신이 주인공(인물 브이로그·연예인·본인출연 토크·리액션).
- false = 제품·음식·공간이 주인공.
  ⚠️ 손만 나오는 것은 false다 — 손은 제품을 쥐거나 시연하는 도구다.
  ⚠️ 사람이 배경에 조금 걸치거나 뒷모습·신체 일부만 나오는 것도 false다.
JSON만: {"face_forward": true/false}"""

_FACE_FORWARD_SCHEMA = {
    "type": "object",
    "properties": {"face_forward": {"type": "boolean"}},
    "required": ["face_forward"],
}


def face_forward_vision(image_bytes, max_retries=3, quota_sleep=8):
    """썸네일 1장 → True(사람이 주인공) / False(제품이 주인공) / None(판정 실패).

    None과 False를 구분하는 게 중요하다 — 호출부가 '판정 실패'를 '제품채널'로
    오해하면, 키가 잠긴 날 인물채널이 전부 통과해버린다(반대로 전부 제외돼도
    곤란하다). 실패는 None으로 올려 호출부가 '판정 안 함'으로 다루게 한다."""
    if not image_bytes or not SHORTS_GEMINI_KEYS:
        return None
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return None
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_TRANSLATE_MODEL,   # flash-lite — 썸네일 1장이라 가벼운 모델로 충분
                contents=[_FACE_FORWARD_PROMPT,
                          types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_FACE_FORWARD_SCHEMA,
                ),
            )
            return bool(json.loads(resp.text).get("face_forward"))
        except Exception as e:  # noqa: BLE001 — 판정 실패는 None(제외 안 함)으로 흘린다
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                # 서버가 "N초 뒤에 오라"고 알려주면 그만큼 잔다(2026-08-09).
                # 고정 8초는 실제 대기(45초)에 한참 못 미쳐 재시도 3번이 전부
                # 429로 타버렸고, 결과가 조용한 빈 값이라 태거가 0/40건만 찍었다.
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return None
    return None


_TEXT_LEVEL_PROMPT = """이 이미지는 SNS 숏폼 영상의 썸네일이다. 화면에 박힌 글자(제목·자막·설명
텍스트)가 원본 장면(제품·사람·배경)을 얼마나 가리는지 판단하라.
- none: 화면에 텍스트가 거의/전혀 없음
- light: 작은 워터마크·짧은 자막 정도, 원본 장면이 잘 보임
- heavy: 큰 제목 텍스트·자막이 화면 상당 부분을 가려 원본 장면이 잘 안 보임
JSON만: {"text_level": "none"|"light"|"heavy"}"""

_TEXT_LEVEL_SCHEMA = {
    "type": "object",
    "properties": {"text_level": {"type": "string", "enum": ["none", "light", "heavy"]}},
    "required": ["text_level"],
}


def text_level_vision(image_bytes, max_retries=3, quota_sleep=8):
    """썸네일 이미지 → 자막/텍스트 오버레이 정도 {"text_level": "none"|"light"|"heavy"}.
    해외HOT 발굴에서 자막 없는 원본 소스 영상만 골라내기 위한 판정(2026-07-29). 실패·키없음 시 {}
    (overseas_funnel.passes_caption_clutter가 판정없는 항목은 통과시키므로 과필터 안 됨)."""
    if not image_bytes or not SHORTS_GEMINI_KEYS:
        return {}
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return {}
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_TRANSLATE_MODEL,  # flash-lite — 썸네일 1장이라 가벼운 모델로 충분
                contents=[_TEXT_LEVEL_PROMPT, types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_TEXT_LEVEL_SCHEMA,
                ),
            )
            data = json.loads(resp.text)
            level = (data.get("text_level") or "").strip()
            if level not in ("none", "light", "heavy"):
                return {}
            return {"text_level": level}
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                # 서버가 "N초 뒤에 오라"고 알려주면 그만큼 잔다(2026-08-09).
                # 고정 8초는 실제 대기(45초)에 한참 못 미쳐 재시도 3번이 전부
                # 429로 타버렸고, 결과가 조용한 빈 값이라 태거가 0/40건만 찍었다.
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return {}
    return {}


def _referer_for(url):
    """CDN 핫링크 차단 우회용 Referer. xhscdn(샤오홍슈)은 인스타 Referer로는 막힌다(2026-07-29 실측)."""
    if "xhscdn.com" in url or "rednote.com" in url:
        return "https://www.rednote.com/"
    return "https://www.instagram.com/"


def fetch_thumb_bytes(url, timeout=15):
    """썸네일 URL → 이미지 bytes. 인스타/샤오홍슈 CDN 핫링크 차단 우회 헤더 포함. 실패 시 None."""
    if not url:
        return None
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": _referer_for(url),
        })
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def cn_search_keyword_vision(image_bytes, caption, max_retries=3, quota_sleep=8):
    """프레임 이미지(+캡션) → {"product","zh"}. 화면 글자·제품 생김새까지 반영. 실패 시 {}."""
    if not image_bytes or not SHORTS_GEMINI_KEYS:
        return {}
    prompt = _CN_VISION_PROMPT.format(caption=(caption or "(캡션 없음)")[:400])
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return {}
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_MODEL,
                contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {"product": {"type": "string"}, "zh": {"type": "string"}},
                        "required": ["product", "zh"],
                    },
                ),
            )
            data = json.loads(resp.text)
            return {"product": (data.get("product") or "").strip(),
                    "zh": (data.get("zh") or "").strip()}
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                # 서버가 "N초 뒤에 오라"고 알려주면 그만큼 잔다(2026-08-09).
                # 고정 8초는 실제 대기(45초)에 한참 못 미쳐 재시도 3번이 전부
                # 429로 타버렸고, 결과가 조용한 빈 값이라 태거가 0/40건만 찍었다.
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return {}
    return {}


_CN_CANDIDATES_PROMPT = """이 이미지는 한국어 쇼츠 영상의 한 장면(썸네일)이다. 화면에 박힌 글자\
(제품명·주제어)와 물건의 생김새를 아래 캡션과 종합해 '이 영상이 소개하는 바로 그 제품/소재'를 \
특정하라. 그 제품과 같은 영상을 중국 SNS(샤오홍슈/도우인)에서 찾을 **중국어 검색어 후보 3~4개**를 만들라.
- 넓은 제품+방식(예: 에어프라이어 감자칩→空气炸锅土豆片) → 좁은 제품명(예: 气泡土豆) 순으로 다양하게.
- 화면 글자에 제품명이 있으면 최우선 반영. 서로 다른 각도의 검색어(재료·조리법·모양)를 섞어라.
- 각 후보에 한국어 뜻(ko)을 짧게 달라(사용자가 뭘 누르는지 알게).
- JSON만: {{"product": "한국어 제품명(짧게)", \
"candidates": [{{"ko": "한국어 뜻", "zh": "중국어 검색어"}}, ...]}}
캡션: {caption}"""

_CN_CANDIDATES_SCHEMA = {
    "type": "object",
    "properties": {
        "product": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"ko": {"type": "string"}, "zh": {"type": "string"}},
                "required": ["ko", "zh"],
            },
            "minItems": 1, "maxItems": 4,
        },
    },
    "required": ["product", "candidates"],
}


def cn_search_candidates(image_bytes, caption, max_retries=3, quota_sleep=8, exclude=None):
    """프레임(+캡션) → {"product": str, "candidates": [{"ko","zh"}]}. 실패/키없음 시 빈 리스트.

    exclude: 이미 보여준 검색어들(ko/zh 문자열 리스트). 렌즈의 '🔄 다른 검색어'가 넘긴다 —
    같은 프레임으로 다시 물어도 비전이 매번 비슷한 3~4개를 뽑아 '복불복'이 되던 걸 막고
    (2026-08-14 사장님), 이미 나온 건 빼고 **다른 각도**로 뽑게 프롬프트에 박는다.
    ★모델 출력은 확률적이라 프롬프트만으론 완벽히 안 지켜진다 → 아래에서 실제로 걸러낸다."""
    empty = {"product": "", "candidates": []}
    if not image_bytes or not SHORTS_GEMINI_KEYS:
        return empty
    seen = {str(s).strip() for s in (exclude or []) if str(s or "").strip()}
    prompt = _CN_CANDIDATES_PROMPT.format(caption=(caption or "(캡션 없음)")[:400])
    if seen:
        prompt += ("\n\n※ 아래 검색어들은 **이미 사용자에게 보여준 것**이다. 이것들과 "
                   "겹치지 않는 **완전히 다른 각도**의 후보만 만들라(재료·조리법·모양·"
                   "브랜드·사용상황 등 아직 안 쓴 축으로):\n"
                   + "\n".join(f"- {s}" for s in sorted(seen)[:20]))
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return empty
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_MODEL,
                contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_CN_CANDIDATES_SCHEMA,
                ),
            )
            data = json.loads(resp.text)
            cands = []
            for c in (data.get("candidates") or []):
                ko, zh = (c.get("ko") or "").strip(), (c.get("zh") or "").strip()
                if zh and zh not in seen and (not ko or ko not in seen):
                    cands.append({"ko": ko, "zh": zh})
                    seen.add(zh)          # 같은 응답 안의 중복도 막는다
            return {"product": (data.get("product") or "").strip(), "candidates": cands}
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                # 서버가 "N초 뒤에 오라"고 알려주면 그만큼 잔다(2026-08-09).
                # 고정 8초는 실제 대기(45초)에 한참 못 미쳐 재시도 3번이 전부
                # 429로 타버렸고, 결과가 조용한 빈 값이라 태거가 0/40건만 찍었다.
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return empty
    return empty


_KW_EXPAND_PROMPT = """사용자가 찾으려는 소재: "{keyword}"

이 소재의 쇼츠·릴스를 여러 SNS(인스타/틱톡/샤오홍슈/도우인)에서 찾기 위한 **검색어 조합 \
{n}개**를 만들라. 사용자가 던진 건 짧은 소재어일 뿐이니, 실제로 결과가 잘 나오는 검색어로 \
넓혀·좁혀 다양하게 펼쳐라.
- 서로 **다른 축**으로: 재료 조합 / 조리·사용 방법 / 완성 형태·비주얼 / 상황·용도 / 상위 카테고리
- 넓은 것(결과 많음) → 좁은 것(정확도 높음) 순으로 섞어라
- ★인스타·틱톡용 한국어(ko)는 '만들기·하는 법' 같은 동사꼬리를 빼고 **명사 중심**으로 \
짧게(인스타 키워드 검색이 긴 구문에 매우 약하다)
- 중국어(zh)는 축자번역이 아니라 중국 창작자가 실제로 쓰는 표현으로
- JSON만: {{"candidates": [{{"ko": "한국어 검색어", "zh": "중국어 검색어"}}, ...]}}"""

_KW_EXPAND_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"ko": {"type": "string"}, "zh": {"type": "string"}},
                "required": ["ko", "zh"],
            },
            "minItems": 1, "maxItems": 8,
        },
    },
    "required": ["candidates"],
}


def expand_search_keywords(keyword, n=6, exclude=None, max_retries=3, quota_sleep=8):
    """한국어 소재어('시금치 치아바타') → [{"ko","zh"}] 검색어 조합. 실패·키없음 시 [].

    왜(2026-08-14 사장님): 렌즈의 후보 검색어는 **화면(프레임) 기반**이라 사장님이 머리로
    떠올린 소재는 새로고침해도 안 나온다. 그래서 '키워드를 직접 넣으면 조합이 나오는' 입구를
    따로 판다. 프레임이 필요 없으므로 렌즈를 안 열어도 쓸 수 있고, 한국어를 넣으면 중국어
    번역까지 같이 나와 4개 플랫폼 버튼이 한 줄에 다 생긴다.
    exclude: 이미 보여준 검색어(중복 방지 — '🔄 더'와 같은 방식).
    ★텍스트만이라 가벼운 모델(_TRANSLATE_MODEL)을 쓴다 — 비전 쿼터를 안 먹는다."""
    kw = (keyword or "").strip()
    if not kw or not SHORTS_GEMINI_KEYS:
        return []
    seen = {str(s).strip() for s in (exclude or []) if str(s or "").strip()}
    prompt = _KW_EXPAND_PROMPT.format(keyword=kw[:100], n=max(1, min(int(n or 6), 8)))
    if seen:
        prompt += ("\n\n※ 아래는 이미 보여준 검색어다. 겹치지 않는 다른 축으로만 만들라:\n"
                   + "\n".join(f"- {s}" for s in sorted(seen)[:20]))
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return []
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_TRANSLATE_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_KW_EXPAND_SCHEMA,
                ),
            )
            data = json.loads(resp.text)
            out = []
            for c in (data.get("candidates") or []):
                ko, zh = (c.get("ko") or "").strip(), (c.get("zh") or "").strip()
                if not (ko or zh) or ko in seen or (zh and zh in seen):
                    continue
                out.append({"ko": ko, "zh": zh})
                seen.update(x for x in (ko, zh) if x)
            return out
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return []
    return []


_CN_JUDGE_PROMPT = """기준 제품: {product}
아래는 검색 결과 영상 제목들(주로 중국어)이다. 각 제목이 '기준 제품과 같은(또는 거의 같은) 제품'을 \
다루는지 판정하라.
- "same": 같은/거의 같은 제품
- "similar": 같은 카테고리지만 다른 제품
- "no": 무관
입력 제목의 순서·개수와 정확히 일치하는 배열로. JSON만: {{"verdicts": ["same"|"similar"|"no", ...]}}
제목들:
{titles}"""


def judge_same_product(product, titles, max_retries=2, quota_sleep=8):
    """기준 제품 vs 결과 제목들 → ["same"|"similar"|"no", ...](제목 순서대로). 실패·불일치 시 []."""
    if not product or not titles or not SHORTS_GEMINI_KEYS:
        return []
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    prompt = _CN_JUDGE_PROMPT.format(product=product, titles=numbered)
    for attempt in range(max_retries):
        key, idx = comment_gen._next_live_key_and_idx()
        if key is None:
            return []
        try:
            client = _client_for_key(key)
            resp = client.models.generate_content(
                model=_TRANSLATE_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {"verdicts": {"type": "array", "items": {
                            "type": "string", "enum": ["same", "similar", "no"]}}},
                        "required": ["verdicts"],
                    },
                ),
            )
            v = json.loads(resp.text).get("verdicts") or []
            return v if len(v) == len(titles) else []
        except Exception as e:
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                # 서버가 "N초 뒤에 오라"고 알려주면 그만큼 잔다(2026-08-09).
                # 고정 8초는 실제 대기(45초)에 한참 못 미쳐 재시도 3번이 전부
                # 429로 타버렸고, 결과가 조용한 빈 값이라 태거가 0/40건만 찍었다.
                time.sleep(key_vault.retry_delay_seconds(e) or quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return []
    return []
