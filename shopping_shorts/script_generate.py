"""S급 대본의 구조를 빌려 새 20초 대본 초안 생성 — 유지/변형 토글 + 모드 remake/transplant.

위키의 검증된 뼈대(주변인물·발상전환·전개방식·훅·어필포인트·말투)를 재료로,
사용자가 각 요소를 '유지/변형' 지정하면 그에 맞춰 Gemini가 여러 초안을 만든다.
- 모드 remake: 원본 소재 그대로 유지, 표현(훅·문장·순서·말투)만 새로 써서 중복 회피 리라이트.
- 모드 transplant: 구조만 빌려 사용자가 준 '내 주제/제품'에 이식.
(구버전 A→remake / B→transplant 하위호환.)
전용 키풀(comment_gen) 재사용. 실패/무키면 [].
"""
import json
import os
import random
import re

from google.genai import types

from shopping_shorts import comment_gen
from pipeline.atoms import key_vault
from shopping_shorts import keyroute

_MODEL = comment_gen._MODEL

# produce 대본생성(우리믹스)은 comment_gen 전용키(1개, 쉽게 소진) 대신
# key_vault 공유풀을 캐스케이드로 쓴다 — 배치된 예비키(general→ingest→embed→briefing)를
# 전부 활용해 소진 사고를 피한다(2026-07-13).
_GEN_GROUP = "general"

# ★대본 생성에 넣는 재료 영상의 상한 — **이 한 곳에서만** 정한다(0순위-B).
#   app.py의 `_FACTS_MAX_SOURCES`는 이 값을 빌려 쓰는 별칭이다(숫자를 다시 안 적는다).
#
#   2026-08-20 실측 사고: app.py는 5인데 여기 그릇이 `sources[:3]`이라 **5편 뽑아 3편만
#   넣고** 있었다. 같은 판단을 두 벌로 적으면 반드시 어긋난다.
#
#   5의 근거 두 가지가 같은 값을 가리킨다:
#    · 사장님 지시(2026-08-19) "영상은 최대 5개까지만. 더 넣어봐야 의미없다"
#    · 히트작 200편 실측(raw/analysis/썰쇼핑_히트작200_2026-08-20):
#      필요 장면 평균 3.3 / 중앙값 3 / 범위 2~5
#
#   ⚠️더 올리지 마라: 재료 1편당 프롬프트 ~2.8천자(본문 800 + 장면 20줄)라
#     5편이 이미 ~14천자다.
SOURCE_MAX = 5


def _style_extra():
    """채널 스타일 블록(style_profiles, 2026-08-05). 실패해도 생성을 죽이지 않는다."""
    try:
        from shopping_shorts import style_profiles
        return style_profiles.style_block()
    except Exception:
        return ""


def _call_json(prompt, schema, note=None):
    """key_vault 캐스케이드 키풀로 JSON 1콜. 소진키는 마킹하고 다음 키로.
    무키·전부실패면 {} (호출부는 반드시 빈 dict 허용 — fail-open).

    note: dict를 주면 **왜 실패했는지**를 담아 돌려준다(2026-08-22 추가).
      이 함수는 ①키가 아예 없음 ②키는 있는데 전부 소진 ③응답 오류를 **전부 `{}`로**
      돌려줘서, 호출부가 원인을 구분할 방법이 없었다. 그 결과 화면에는 원인과 무관하게
      늘 "키 소진 또는 응답 오류"가 떴다(실측 2026-08-22: 키가 멀쩡한데도 그 문구).
      note를 안 주면 종전과 완전히 동일하다(회귀 0).
    """
    keys = keyroute.gemini_keys(_GEN_GROUP)
    if note is not None:
        note["keys"] = len(keys)
        if not keys:
            # ★키가 하나도 안 남았을 때만 진짜 '키 소진'이다.
            note["reason"] = "no_keys"
    for key in keys:
        try:
            resp = key_vault.get_client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=schema),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 — 생성 실패는 치명적 아님
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                key_vault.mark_exhausted(key_vault._owner_group(key) or _GEN_GROUP, key)
                if note is not None:
                    note["reason"] = "exhausted"     # 돌다가 다 말랐다 = 진짜 소진
                continue
            if key_vault.is_quota_error(e):
                if note is not None:
                    note["reason"] = "rate_limit"    # 분당 한도 — 잠시 뒤 재시도가 맞다
                continue  # 순간 rate limit — 다음 키로
            if note is not None:
                # 키 문제가 아니다 — 응답·스키마·네트워크 쪽. '잠시 후 재시도'는 헛말이다.
                note["reason"] = "api_error"
                note["detail"] = "%s: %s" % (type(e).__name__, str(e)[:200])
            return {}
    return {}


def _generate_drafts(prompt):
    """key_vault 캐스케이드 키풀로 대본 초안 리스트 생성. 무키·전부실패면 []."""
    return _call_json(prompt, _SCHEMA).get("drafts", [])


_BREATH_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
    "required": ["lines"],
}

# 이 길이(공백 제외)까지는 규칙 분할로 충분하다 — 호출 자체를 안 해 비용 0.
_BREATH_MIN_CHARS = 13


def ai_breath_lines(narration):
    """자막 호흡 줄 — Gemini가 문장을 '숨 쉬는 자리'에서만 끊는다(글자 불변, 줄만 나눔).

    폴백 칸 전용(2026-08-29 사장님 "자연스러운 호흡으로 끊는 게 기본"): caption_lines가
    없는 비트만 재합성 관문(mix_pipeline._ensure_breath_lines)이 부른다. 규칙 분할
    (_caption_segments)은 표면 글자만 봐서 관형형('안다는')과 조사('언니는')를 못 가르는데,
    여기는 문장을 이해하고 끊는다. 실패·무키·불일치 → None(=규칙 폴백, 종전과 동일).

    검증: 이어붙인 줄이 원문과 같아야 한다 — 대조 기준은 cap_preset_key **한 곳**만 쓴다
    (0순위-B: 여기서 다른 기준으로 재면 "저장은 통과, 렌더는 폴백" 두 벌 사고가 재발한다).
    """
    text = (narration or "").strip()
    flat = "".join(text.split())
    if len(flat) <= _BREATH_MIN_CHARS:
        return None
    # ⚠️로컬 pytest는 .env 실키가 있어 네트워크를 타면 게이트가 느려지고 흔들린다
    #   (ops_alert.py와 같은 가드). 로직 테스트는 delenv로 걷고 _call_json을 목으로.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    # ★.format() 금지(중괄호 예시가 KeyError를 삼킨다 — memory 대본템플릿 빈칸 짝맞추기)
    prompt = (
        "아래 한국어 쇼츠 내레이션 한 비트를 자막 줄로 나눠라.\n"
        "규칙:\n"
        "- 사람이 말하다 숨을 쉬는 자연스러운 호흡 단위(의미 덩어리)로만 끊는다.\n"
        "- 글자를 추가·삭제·수정하지 마라. 원문 어절 그대로, 줄만 나눈다.\n"
        "- 한 줄은 공백 제외 4~14자. 명사구나 '조사 앞' 한가운데를 끊지 마라.\n"
        "  (좋은 예: '인테리어 고수들만 안다는' | '비밀 테이블이 있어요')\n"
        '- JSON {"lines": ["줄1", "줄2", ...]} 로만 답하라.\n'
        "원문: " + text
    )
    out = _call_json(prompt, _BREATH_SCHEMA)
    lines = [str(l).strip() for l in (out.get("lines") or []) if str(l).strip()]
    if not lines:
        return None
    from shopping_shorts.video_assemble import cap_preset_key   # 지연 — 순환 import 방지
    if cap_preset_key("".join(lines)) != cap_preset_key(text):
        return None
    return lines

# 유지/변형 토글 대상 요소(키 → 표시 라벨). 프론트·엔드포인트가 공유.
ELEM_LABELS = {
    "characters": "등장 주변인물",
    "twist": "발상전환",
    "development": "전개방식",
    "hook": "훅",
    "appeal": "어필포인트",
    "tone": "말투/어미",
    "devices": "설득장치",
    "cta": "마무리/CTA",
}
ELEM_KEYS = list(ELEM_LABELS)

_SCHEMA = {
    "type": "object",
    "properties": {
        "drafts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hook": {"type": "string"},
                    "script": {"type": "string"},
                    "applied": {"type": "string"},
                    "story_person": {"type": "string"},
                    "story_event": {"type": "string"},
                    "story_resolution": {"type": "string"},
                    "cta_line": {"type": "string"},
                    "cta_keyword": {"type": "string"},
                },
                "required": ["hook", "script", "applied", "story_person", "story_event",
                             "story_resolution", "cta_line", "cta_keyword"],
            },
        }
    },
    "required": ["drafts"],
}

# 요리·음식 소재 감각 표현 라이브러리(2026-07-20 사장님 요구) — 레시피 대본은 맛·식감·
# 비주얼을 밋밋하게 쓰지 말고 생생한 감각어로 살린다. 모델이 소재 보고 자가판단해 골라 쓴다.
# ★{ } 금지(아래 헌장이 .format()을 탄다). 쉼표 나열만.
_SENSORY_LIB = (
    "촉촉하게, 부드럽게, 폭신폭신, 몽실몽실, 쫀득쫀득, 쫄깃쫄깃, 바삭바삭, 아삭아삭, "
    "사르르 녹는, 탱글탱글, 말랑말랑, 꾸덕꾸덕, 포슬포슬, 겉바속촉, "
    "윤기 좌르륵, 자르르 흐르는, 반질반질, 자작자작, 기름이 자글자글, 촉촉하게 스며든, "
    "노릇노릇, 지글지글, 보글보글, 바글바글, 김이 모락모락, 겉이 노릇하게, "
    "고소하게, 진하게, 감칠맛 폭발, 달큰하게, 짭조름하게, 담백하게, 입에서 살살 녹는, 깊은 풍미, "
    "먹음직스럽게, 침샘 폭발, 색감이 살아있는, 결이 살아있는, 속이 꽉 찬, 윤기가 도는"
)

# 스토리 헌장 — _GEN_PROMPT·_MIX_PROMPT·리파인 공통 주입(모듈 레벨 문자열 연결).
# 사장님 요구: (1) 가장 중요한 건 스토리라인 (2) 인과·상관관계가 말이 되고 훅이 끝까지
# 이어짐 (3) 훅·CTA 두 자리에 가장 중요한 걸 배치 (4) 레시피는 표현(감각어)에 집중.
# CTA는 하드코딩 1문구가 아니라 소재 적합형 선택 — "레시피라고 다 같지 않다".
# ★헌장 텍스트에 { } 금지 — _GEN_PROMPT/_MIX_PROMPT/리파인이 .format()을 쓴다(깨진다).
_STORY_RULES_CORE = """- ★★★짤드라마 필수(이게 이 포맷의 생명): 이건 정보영상이 아니라 '짧은 이야기(짤드라마)'다.
  구체적 인물이 구체적 상황에서 겪는 미니 드라마로 써라. '여러분'·'우리' 같은 일반 청자
  호칭이나 '이렇게 드세요/하세요'식 설명·나열·강의체는 절대 금지 — 그건 허접한 튜토리얼이다.
  반드시 '누가(엄마·남편·시어머니·아이·지인·나) 어떤 상황에서(갑자기 왔는데·밤마다·매번·어느날)
  겪은 일'로, 장면이 눈에 그려지는 이야기로 시작해 전개하라.
  예: "어제 시어머니가 예고도 없이 들이닥쳤는데" / "남편이 매일 밤 야식 타령을 하길래" /
      "애가 아침을 통 안 먹어서 속 터졌는데" / "다이어트 중인 언니가 이건 괜찮냐고 묻길래".
  → 인물·갈등·전환(반전)·해소가 있는 하나의 장면. 정보는 그 이야기 속에 녹여라.
- ★★★탄탄한 회수(느슨한 스토리 반려): 훅에서 등장시킨 그 인물·갈등이 결말에서 반드시
  '회수'돼야 한다. 남편이 야식을 찾으며 시작했으면 결말도 '그 남편이 이제 이것만 찾는다'로
  닫아라 — 중간에 슬그머니 다른 인물(아이들 등)로 갈아타 시작한 갈등을 버리지 마라.
  그리고 각 문장은 앞 문장의 '결과 또는 이유'여야 한다(인과 다리): "투덜대더라고요 → (그래서)
  홧김에 다르게 해봤더니 → (그랬더니) 웬걸" 처럼 왜 그 행동을 했는지 연결하라. 근거 없이
  "그런데 갑자기 이렇게 하니까"로 점프하면 스토리가 끊긴다. 시작(설정)–중간(전환)–끝(회수)이
  한 인물의 한 사건으로 꿰여야 '탄탄하다'.
- ★★★화자(말하는 사람)는 끝까지 한 사람이다 — 아래는 실제로 나온 **실패작**이다(2026-08-23):
  ✗ "저 친구네 집 갔다가 충격 받았잖아요 / 남편 턱이 훨씬 깔끔하게 달라진 거예요 /
     ... / 저도 해보니까 자극 없이 밀리는 거죠"
  무엇이 틀렸나: ①친구 남편인데 그냥 "남편"이라 써서 **화자 본인의 남편**으로 읽힌다
  ②친구 남편 얘기로 시작해놓고 결말은 "저도 해보니까"로 **화자가 직접 쓴 사람**이 된다
  (여성 화자가 남성용 면도기를 자기 턱에 미는 그림이 된다 = 말이 안 된다).
  ○ 이렇게 써라: "친구 **남편** 턱이 달라졌길래 / 뭐 썼냐고 물어봤더니 / **우리 남편한테도**
     사줬거든요 / 이제 아침마다 이것만 찾는 거 있죠"
  → 남의 물건을 보고 내가 샀다면 **"그래서 우리 ○○한테 사줬더니"** 같은 다리를 반드시 놓아라.
     3인칭 인물의 소유물은 **누구 것인지 밝혀라**("친구 남편"·"언니네 아이").
     화자의 성별·처지가 도중에 바뀌면 안 된다.
- ★가장 중요한 건 스토리라인이다. 아래 규칙은 전부 '하나의 탄탄한 이야기'를 위한 것 —
  사람이 자기 이야기를 들려주듯 자연스럽게 흐르게 하라. 정보 나열·설명문 금지.
- ★한 스토리 원칙: 대본 전체가 인물 1명·사건 1개·결말 1개의 '하나의 이야기'다.
  훅에서 던진 궁금증/문제가 전개에서 원인→전환점으로 풀리고 결말에서 해소돼야 한다.
  각 문장은 앞 문장의 결과나 이유여야 한다(인과 사슬). 뜬금없는 소재 점프,
  근거 없는 효능 비약, 훅 따로 본문 따로 전개 금지.
- ★훅 원칙: 첫 문장(훅)에는 이 영상에서 가장 강력한 한 방 — 제일 놀랍거나 궁금하거나
  이득이 큰 핵심 —을 앞세워라. 밋밋한 인사·서론·배경설명으로 시작하지 마라.
  훅과 CTA가 영상에서 가장 중요한 두 자리다(첫 1초에 붙잡고 끝에 행동시킨다).
- ★★★훅은 은행에서 직접 가져와라(하드코딩 반복 금지): 아래 [은행] 블록의 '훅' 부품에서 골라 써라.
  ★후보 3개 중 **최소 2개**는 은행 훅을 **거의 그대로 살려** 써라 — 문장 뼈대·리듬·강도를 유지하고
  **소재 단어만** 이 영상에 맞게 갈아끼워라(예: '여러분! 식빵 절대 돈 주고 사 먹지 마세요' →
  '여러분! 이 아침 대용식 절대 돈 주고 사 먹지 마세요'). 나머지 1개만 자유 변형.
  ★★단, 훅에 인명·상표·지명 등 **특정 고유명사**가 박혀 있으면 그 부분은 우리 소재로 바꿔라
  (남의 브랜드·사연 통째 복사 금지). 은행 훅이 없을 때만 아래 유형(충격/감탄·뒤늦은 발견·극찬·강한 경고·
  자기고백)의 '구조 감'으로 새로 창작하라. ⚠️어느 경우든 매 영상 같은 훅('천재 아닌가요?'·'이런 게
  진작 있었네요?' 류)을 반복하면 실패다 — 후보마다·영상마다 훅이 확실히 달라야 한다.
- ★★강한 훅 오프너 필수(약한 훅 반려): 첫 문장은 반드시 감탄·충격·궁금증을 터뜨리는 오프너로
  시작하라. '남편이 야식을 찾길래…' 같은 잔잔한 상황설명을 첫 문장에 두지 마라 — 강한 오프너를
  먼저 던지고 그 다음 문장에서 상황을 풀어라.
  강한 오프너 → (상황·인물) → 반전 → 회수 순으로 흐르게 하라.
- ★고조 연결어(해결심화, 2026-08-04 사장님 확정 구조: 훅→문제→장점해결→해결심화→CTA):
  해결을 보여준 뒤 한 단계 더 올라가는 문장을 반드시 하나 두고, 그 문장은 고조 연결어로
  시작하라 — '심지어' / '더군다나' / '근데 이게 대박인 게' / '놀랍게도' / '이걸 왜 몰랐는지' /
  '이럴 수가 있나 싶게' 중 소재에 맞는 것 하나(훅·CTA엔 금지, 한 번만 — 남발하면 죽는다).
  ★연결어 뒤엔 반드시 **앞에서 안 나온 새로운 추가 장점**이 와야 한다 — 이미 말한 장점을
  되풀이하면("대박인 게 얼룩이 지워져요" 뒤에 또 얼룩 얘기) 고조가 아니라 동어반복이다.
- ★종결어미를 풍부하게(2026-08-04 사장님 지시): 전 문장이 '~요/~니다'로 끝나면 낭독문처럼
  들린다. '~거든요' '~있죠' '~더라고요' '~잖아요' '~는 거예요' '~네요'를 문장마다 다르게
  섞어 옆에서 말해주는 리듬을 만들어라(같은 어미 연속 2회 금지).
- ★CTA 원칙: 마지막 문장은 반드시 행동유도(CTA)로 끝난다. 핵심 비법 하나는 본문에서
  다 밝히지 말고 아껴서, CTA가 그 아낀 비법과 자연스럽게 이어지게 하라.
  · ★소재 불문 반드시 댓글 키워드형으로 끝내라(2026-08-04 사장님 확정 — 저장·팔로우
    유도로 빠지지 마라. 댓글 하나가 링크 클릭으로 이어지는 구조라 CTA는 무조건 댓글이다):
    [댓글 달 수밖에 없는 명분 한 줄] + "댓글에 'OO' 남겨주시면 [받는 것] 드릴게요"
    (OO = 소재에서 뽑은 2~6자 키워드). ★남기면 **뭘 받는지**를 반드시 말하라 — 받는 게
    안 보이면 아무도 안 남긴다. 받는 것 예: 제가 산 링크 그대로·정확한 레시피·최저가
    정보·감춘 킥(비법 한 가지). "남겨주세요"로만 끝나면 실패다.
    명분 예: 검색해도 안 나옴·다들 물어봐서 댓글로만·모르고 사면 비쌈 — 소재에 맞게
    변주, 없는 가격·할인·한정수량 지어내기 금지.
- ★레시피/비법 궁금증 원칙(요리·살림팁 소재 = 이 포맷의 생명): 스토리로 '결과가 놀랍다'는
  보여주되(감각표현으로 먹음직스럽게), 정작 '어떻게 만드는지'의 결정적 비법 하나(킥)는 절대 다
  밝히지 마라. 핵심 재료·비율·타이밍·순서 한 가지를 "이것 한 스푼", "집에 있는 그거",
  "이 타이밍에만"처럼 감춰서 → 보는 사람이 '그래서 그거 어떻게 하는 건데?' 참을 수 없게
  궁금하게 만들어라. 그 감춘 킥이 곧 CTA 미끼다(궁금해서 댓글 달게). 방법을 다 까발리면
  (예: "밥솥에 버튼만 누르면 끝") 궁금할 게 없어 CTA가 죽는다 — 반드시 킥 하나는 남겨라.
- ★표현 원칙(요리·음식 소재일 때만): 맛·식감·비주얼을 밋밋하게 쓰지 말고 생생한 감각
  표현으로 살려라. 장면에 맞는 걸 골라 자연스럽게 녹여라(억지로 여러 개 나열 금지).
  예시: """ + _SENSORY_LIB + """
  요리·음식 소재가 아니면 이 항목은 무시하라."""

_STORY_DECLARE = """- 각 초안에 반드시 채워라: story_person(주인공 1명), story_event(사건 한 줄),
  story_resolution(결말 한 줄), cta_line(마지막 CTA 문장 그대로),
  cta_keyword(댓글 유도 키워드 — 댓글형 CTA가 아니면 빈 문자열)."""


_GEN_PROMPT = """너는 한국 쇼핑 숏폼(살림·요리·인테리어) 대본 작가다. 아래 'S급 원본 대본'의
검증된 구조를 빌려, 약 {seconds}초 분량(대략 {words}단어)의 새 대본 초안 {n}개를 만들어라.

[S급 원본 대본]
{full_text}

[구조 요소별 지시 — 유지/변형]
{elems}

[{topic_line}]{bank}

규칙:
- 각 초안은 실제로 읽을 나레이션(구어체). 0초 훅부터 끝 CTA까지 이어지게.
- 실제 말하듯 자연스러운 추임새·감탄사를 적재적소에 넣어라(예: "와~", "진짜", "정말",
  "헐", "대박", "어머", "이거 봐", "글쎄"). 문어체처럼 딱딱하지 않게, 말투/어미 요소와 어울리게.
- '변형' 요소는 원본을 베끼지 말고 참신하게 바꾸고, '유지' 요소는 그 강점을 그대로 살려라.
- 주변인물을 쓸 땐 오버하지 말고 자연스럽게(예: "농원 하는 언니가", "김밥집 사장님이",
  "병원 하는 지인이"). 억지 설정·과장 금지.
- 초안끼리 서로 다르게(훅·전개를 다양하게 시도).
""" + _STORY_RULES_CORE + "\n" + _STORY_DECLARE + """
각 초안: hook(첫 훅 한 줄), script(전체 나레이션 대본), applied(무엇을 유지/변형했는지 한 줄).
JSON만 출력."""


_MIX_PROMPT = """너는 한국 쇼핑 숏폼 대본 작가다. 아래 여러 개의 검증된 S급 대본이 있다.
약 {seconds}초 분량(대략 {words}단어)의 새 대본 초안 {n}개를 만들어라.

[재료 대본들]
{sources}{bank}

규칙:
- ★초안마다 먼저 '인물 1명·사건 1개·결말 1개'를 정하라. 다른 대본에서는 훅 방식·표현·
  말투·전개 리듬만 빌리고, 인물과 사건은 절대 섞지 마라(대본 A의 인물이 대본 B의
  사건을 겪으면 안 된다).
- 특정 대본을 통째로 베끼지 말고, 좋은 부분만 골라 하나의 이야기로 녹여 새로 써라.
- 실제로 읽을 구어체 나레이션(0초 훅 → … → 끝 CTA). 억지 설정·과장 금지.
- 초안끼리 서로 다르게(정한 인물·사건·훅을 다양하게).
""" + _STORY_RULES_CORE + "\n" + _STORY_DECLARE + """
각 초안: hook(첫 훅 한 줄), script(전체 나레이션 대본), applied(어느 대본에서 무엇을 빌렸고
어떤 한 스토리로 유지했는지 한 줄).
JSON만 출력."""


def _source_benefits(s):
    """소스의 특장점 문장 리스트(무자막 영상용). list/str 모두 허용, 없으면 []."""
    raw = s.get("product_benefits")
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    return [t.strip() for t in raw if isinstance(t, str) and t.strip()]


def _mix_source_block(sources):
    lines = []
    for i, s in enumerate(sources, 1):
        st = s.get("structure") or {}
        chs = ", ".join(f"{c.get('who')}({c.get('role')})" for c in (st.get("characters") or [])) or "없음"
        block = (
            f"[대본 {i}] {s.get('name') or ''}\n"
            f"- 훅: {st.get('hook') or '(미상)'}\n"
            f"- 전개방식: {st.get('development') or '(미상)'}\n"
            f"- 주변인물: {chs}\n"
            f"- 말투/어미: {st.get('tone') or '(미상)'}\n"
            f"- 전체대본: {(s.get('full_text') or '')[:800]}")
        # ★장면 목록(2026-08-18 사장님 "그 대본에 장면을 사용하면 좋다").
        #   문장마다 '어느 대목을 보고 썼는지'(src_seg)를 지목하게 하려면 **번호가 붙은
        #   목록**을 봐야 한다. 3단계는 그 번호의 장면을 1순위로 붙인다 — 짐작이 아니라
        #   원래 그 말이 나온 그림이라 가장 정확하다.
        #   ⚠️무자막 소스는 말(text)이 비고 화면 설명만 있다 — 그것도 단서라 함께 준다.
        _segs = [x for x in (s.get("segments") or []) if isinstance(x, dict) and x.get("seg_id")]
        if _segs:
            block += "\n- 장면 목록(이 대본을 참고해 쓸 때 어느 대목인지 번호로 지목하라):\n" + "\n".join(
                "  [{sid}] {say}{desc}".format(
                    sid=x.get("seg_id"),
                    say=("말:" + (x.get("text") or "").strip()[:40] + " ") if (x.get("text") or "").strip() else "",
                    desc="화면:" + (x.get("scene_desc") or "").strip()[:40])
                for x in _segs[:20])
        # 무자막 해외영상: 자막·나레이션이 없어 전체대본이 비고 특장점만 있다. 그 특장점을
        # "이 제품은 이런 장점이 있다"로 주입해 대본이 그걸 우리 말로 녹이게 한다(2026-07-26).
        benefits = _source_benefits(s)
        if benefits:
            block += "\n- 제품 특장점(화면으로 확인된 것 — 이 장점을 우리 말로 녹여라): " \
                     + " / ".join(benefits[:5])
        lines.append(block)
    out = "\n\n".join(lines)
    # ★주제는 [대본 1]로 못 박는다(2026-08-17 사장님 제보 "치아바타를 뽑았는데 도마 얘기가 나온다").
    #   재료를 담긴 영상 전부로 넓히면서 **주제를 고정하지 않은 게 내 실수**다. 한 작업에
    #   서로 다른 제품이 담겨 있으면(치아바타 224자 + 도마 694·526자) 글이 긴 쪽으로 끌려간다.
    #   "여러 편을 보라"는 지시의 뜻은 **같은 제품을 여러 각도로 보라**는 것이지
    #   다른 제품을 섞으라는 게 아니다.
    # ★소재를 코드가 못 박는다(2026-08-18). 지금까지는 "주제는 [대본 1]의 것"이라고
    #   **말로만** 지시했다 — AI가 여러 텍스트 더미를 읽고 소재를 스스로 추론해야 했고,
    #   그 추론이 학습 재료(부품은행) 쪽으로 새는 게 이번 사고였다(재료가 전부 네일펜인데
    #   결과가 '주방 기름 가림막'). 1단계 분석이 제품명을 이미 뽑아 두는데
    #   (source_brief.product — 실측 '다이소 자석 네일펜') 그 값을 생성에 한 번도 안 줬다.
    #   **아는 값을 안 주고 짐작하게 한 것**이 뿌리다. 맨 앞에 박으면 추론할 여지가 없어진다.
    _prod = ""
    for _s in sources:
        _p = (_s.get("product") or "").strip()
        if _p:
            _prod = _p
            break
    if _prod:
        out = ("★★우리 영상의 제품 = 「" + _prod + "」. 대본은 이 제품 이야기여야 한다. "
               "다른 제품·소재가 한 줄이라도 들어가면 반려된다.\n\n") + out
    if len(sources) > 1:
        out += ("\n\n★★주제는 반드시 [대본 1]의 제품·소재다. [대본 2] 이하는 **말투·전개·표현을 참고만** 하고, "
                "거기 나오는 제품·기능·사례를 주제로 삼거나 섞지 마라. "
                "[대본 1]과 다른 물건 이야기가 한 줄이라도 들어가면 반려된다.")
    return out


def generate_mix(sources, target_seconds=30, n=3, max_key_tries=3, bank_context=""):
    """여러 S급 대본(각 {name, full_text, structure})의 강점을 조합해 새 대본 초안 리스트.
    우리믹스(Feature B) 모드. 소스 2개 미만이거나 무키면 []."""
    # 무자막 해외영상(2026-07-26): full_text가 0자여도 product_benefits(화면→특장점)가 있으면
    # 대본 재료로 살린다. 예전엔 full_text만 봐서 자막 없는 소스를 통째로 제외했다 — Gemini가
    # 화면은 정확히 이해(scene_desc)하는데 text를 비우는 게 근본이라 소스 품질 문제가 아니었다.
    sources = [s for s in (sources or [])
               if (s.get("full_text") or "").strip() or _source_benefits(s)]
    if not comment_gen.SHORTS_GEMINI_KEYS or len(sources) < 2:
        return []
    n = max(1, min(int(n or 3), 5))
    seconds = max(5, min(int(target_seconds or 30), 90))
    words = max(15, round(seconds * 2.3))
    prompt = (_MIX_PROMPT.format(sources=_mix_source_block(sources[:SOURCE_MAX]), seconds=seconds, words=words, n=n,
                                 bank=("\n\n" + bank_context) if bank_context else "")
              + _style_extra())   # ★채널 스타일(2026-08-05) — format 뒤에 붙인다({} 무관)
    return _verify_and_fix(_generate_drafts(prompt), seconds)


# ---------------- 스타일 강제 생성(2026-08-15) ----------------
# 기존 generate_mix는 **같은 프롬프트를 n번 굴려 운 좋은 걸 고르는** 구조라 3안이 다 비슷할
# 수 있었다. 여기는 스타일마다 프롬프트가 갈리므로 **서로 다른 구조가 보장**되고, 나온 결과를
# script_gate가 대조해 어기면 재작성을 건다. 기존 경로는 그대로 두고 새 함수로 나란히 둔다
# (플래그 off면 아무도 안 부른다 = 회귀 0).

_STYLE_SCHEMA = {
    "type": "object",
    "properties": {
        "beats": {
            "type": "array", "minItems": 3,
            "items": {
                "type": "object",
                # ★src_seg(2026-08-18 사장님 "그 대본에 장면을 사용하면 좋다"):
                #   이 문장을 쓸 때 **참고한 소스 세그먼트 번호**. 3단계가 이 번호의 장면을
                #   1순위로 붙인다 — 짐작이 아니라 '원래 그 말이 나온 그림'이라 가장 정확하다.
                #   지어낼 수 없게 후보 목록에 있는 것만 쓰라고 프롬프트에서 못 박는다.
                #   못 고르면 빈 문자열(그때는 종전대로 3단계가 알아서 고른다 = 회귀 0).
                "properties": {"role": {"type": "string"}, "text": {"type": "string"},
                               "src_seg": {"type": "string"}},
                "required": ["role", "text", "src_seg"],
            },
        },
    },
    "required": ["beats"],
}

STYLE_REWRITES = 2       # 게이트 실패 시 다시 쓰는 횟수. 그래도 안 되면 실패로 남긴다.



def _sources_product(sources):
    """재료에서 우리 제품명 하나(첫 번째로 채워진 것). 없으면 ""."""
    for s in (sources or []):
        p = (s.get("product") or "").strip()
        if p:
            return p
    return ""

def generate_one_style(sources, style, target_seconds=30, bank_context="", facts_block="",
                       seed="",
                       note=None):
    """스타일 1개로 대본 1안. → {beats, script, hook, checks, passed, tries, style_id, style_name}

    ★조용히 통과시키지 않는다: 게이트를 못 넘으면 passed=False로 **표시해서** 돌려준다.
      기존 라이브의 병이 '규칙을 어겨도 아무도 모르는 것'이었다.

    facts_block: `product_facts.prompt_block()` 결과(쿠팡 상세·리뷰에서 확인된 사실).
      **빈 문자열이면 기존 경로 그대로 = 회귀 0.** 재료가 없다고 생성이 막히면 안 된다.
      실측 효과(2026-08-16 A/B): 없을 때 "툭하면 떨어져서 시끄럽고"(AI가 상상한 불편)·
      "펜이 수십 자루" → 있을 때 "애가 필통을 네 개씩 들고 다니니"(리뷰 실제 사연)·
      "볼펜 65자루랑 20cm 자까지".
    """
    from shopping_shorts import bank_assemble, script_gate

    seconds = max(5, min(int(target_seconds or 30), 90))
    # ★seed(job_id)를 넘겨 문장틀 순서를 job마다 돌린다 — 안 넘기면 항상 같은
    #   순서라 모델이 앞쪽 틀에 쏠린다(실측: 훅 10개 중 6개가 한 번도 안 나옴).
    head = bank_assemble.style_block(style, seconds=seconds, seed=seed)
    if not head:
        return None
    base = (_MIX_PROMPT.format(sources=_mix_source_block((sources or [])[:SOURCE_MAX]),
                               seconds=seconds, words=max(15, round(seconds * 2.3)), n=1,
                               bank=("\n\n" + bank_context) if bank_context else "")
            + _style_extra()
            + (("\n" + facts_block) if facts_block else "")
            + "\n\n" + head
            + "\n\n각 칸마다 src_seg에 **그 문장을 쓸 때 참고한 장면 번호**를 적어라"
              "([대본 N]의 '장면 목록'에 있는 번호만. 3단계가 그 장면을 화면으로 붙인다)."
              " 참고한 대목이 딱히 없으면 빈 문자열."
            + "\n\n출력은 위 칸 순서대로 beats 배열 하나만. 각 원소는 {role, text, src_seg}.")

    extra, tries, res, checks, full = "", [], None, [], ""
    # ★재작성이 끝내 통과 못 하면 **마지막 시도**가 아니라 규격에 가장 가까운 시도를 쓴다
    #   (2026-08-18 사장님 "40초 대본이 나오는데 고친 거 아니었나"). 예전엔 2번 고쳐 쓰고도
    #   실패하면 그 마지막 판을 그대로 내보냈다 — 더 길어진 판이 나가는 일이 생긴다.
    best = None
    for _ in range(STYLE_REWRITES + 1):
        data = _call_json(base + extra, _STYLE_SCHEMA, note=note)
        res = (data or {}).get("beats") or []
        if not res:
            break
        # ★facts_block을 게이트에도 넘긴다 — 재료를 줬으면 대본의 수치가 그 안에 있는지
        #   대조한다(지어낸 수치 차단). 안 줬으면 그 검사는 건너뛴다(회귀 0).
        # ★소재 일치도 함께 본다(2026-08-18) — 재료의 제품명을 그대로 넘긴다.
        #   product가 비면 그 검사는 건너뛴다(회귀 0).
        checks, full = script_gate.check(style, res, facts_text=facts_block,
                                         product=_sources_product(sources),
                                         seconds=seconds,
                                         speaker_judge=_speaker_judge)
        tries.append({"chars": len(script_gate.norm(full)),
                      "fails": [c["name"] for c in checks if not c["ok"]]})
        if script_gate.passed(checks):
            break
        _n = len(script_gate.norm(full))
        _tgt = script_gate.density_target(style, seconds)
        if best is None or abs(_n - _tgt) < best[0]:
            best = (abs(_n - _tgt), res, checks, full)
        extra = script_gate.gate_feedback(checks)

    if not script_gate.passed(checks) and best and best[3] != full:
        _, res, checks, full = best

    # ★마지막 방어는 코드가 한다(2026-08-18 사장님 "계속 다시 살아나는데 원천 해결인가").
    #   재작성은 부탁이라 언제든 어길 수 있다 — 여기서 길이만은 **결정적으로** 맞춘다.
    #   edit_plan._trim_to_budget(군더더기 부사부터 덜어내 문법을 안 깨는 재단)을 그대로
    #   재사용한다(0순위-B). 뺄 게 없으면 원문 유지 — 뜻을 훼손하면서까지 자르진 않는다.
    _cap = script_gate.density_target(style, seconds)
    if res and len(script_gate.norm(full)) > _cap:
        from shopping_shorts.edit_plan import _trim_to_budget
        _tot = sum(len(script_gate.norm(b.get("text", ""))) for b in res) or 1
        for _b in res:
            _n = len(script_gate.norm(_b.get("text", "")))
            if not _n:
                continue
            _new = _trim_to_budget(_b.get("text", ""), max(6, int(_cap * _n / _tot)))
            if _new:
                _b["text"] = _new
        # ★앞 판정을 물려준다 — 안 그러면 화자 실패가 여기서 조용히 사라지고,
        #   판정기를 다시 넘기면 유료 호출이 두 배가 된다(재단은 화자를 못 바꾼다).
        checks, full = script_gate.check(style, res, facts_text=facts_block,
                                         product=_sources_product(sources),
                                         seconds=seconds,
                                         speaker_judge=script_gate.prior_verdict(checks))
        tries.append({"chars": len(script_gate.norm(full)), "trimmed": True,
                      "fails": [c["name"] for c in checks if not c["ok"]]})

    # ★화면에 "영상으로 몇 초"를 띄우려면 초를 서버가 계산해 실어 보내야 한다
    #   (2026-08-18 사장님). 화면이 자기 상수로 따로 계산하면 판정(밀도 게이트)과
    #   다른 수를 말하게 된다 — 초 환산은 script_gate 한 곳에서만 한다(0순위-B).
    for _b in (res or []):
        _b["sec"] = script_gate.est_seconds(_b.get("text", ""))
    return {
        "style_id": style.get("id"), "style_name": style.get("name"),
        "beats": res or [], "script": full, "hook": (res or [{}])[0].get("text", ""),
        "checks": checks, "passed": script_gate.passed(checks), "tries": tries,
        "chars": len(script_gate.norm(full)), "sec": script_gate.est_seconds(full),
    }


_SPEAKER_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "why": {"type": "string"}},
    "required": ["ok", "why"],
}

_SPEAKER_PROMPT = """다음 한국어 숏폼 대본에서 **말하는 사람(화자)이 처음부터 끝까지 한 사람으로
일관되는지**만 판정해라. 다른 것(길이·문법·재미)은 보지 마라.

FAIL로 잡을 것 — 이 셋만:
1) 3인칭 인물의 소유물인데 **누구 것인지 안 밝혀** 화자 것으로 읽히는 경우.
   예: "친구네 집 갔다가" 다음에 그냥 "남편 턱이 달라진 거예요" → 누구 남편인지 없다.
       ("친구 남편"이라고 써야 맞다)
2) 시작에서 등장시킨 인물을 **중간에 슬그머니 다른 인물로 갈아탄** 경우.
   예: 친구 남편 얘기로 시작해놓고 결말이 "저도 해보니까"로 화자 본인 체험이 된다.
3) 화자의 성별·처지가 도중에 **모순**되는 경우.
   예: 남편이 있다고 해놓고 뒤에서 자기가 남편인 것처럼 말한다.

⚠️통과시킬 것(오탐 금지):
- 화자가 남의 물건을 보고 자기도 샀다는 흐름은 **연결어가 있으면 정상**이다.
  ("친구 남편 게 좋아 보여서 → 우리 남편한테도 사줬더니" = OK)
- 지인·언니·조카가 잠깐 등장했다 빠지는 건 정상이다.
- 제품을 '이거'로만 부르는 것도 정상이다.
확실히 어긋난 것만 FAIL. 애매하면 통과(ok=true)시켜라.

why에는 **무엇을 어떻게 고쳐야 하는지** 한 문장으로 적어라(FAIL일 때만).

[대본]
{script}"""


def _speaker_judge(text):
    """대본 전문 → {"ok": bool, "why": str}. 판정 못 하면 {} (게이트가 통과시킨다).

    ★fail-open: _call_json은 무키·소진·응답오류를 전부 {}로 돌려준다. 그대로
      넘기면 script_gate가 '판정 불가'로 보고 검사 항목을 안 만든다 — 키가 마른
      날 대본이 통째로 막히는 일을 막는다.
    """
    if not (text or "").strip():
        return {}
    return _call_json(_SPEAKER_PROMPT.format(script=text), _SPEAKER_SCHEMA)


_BEAT_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
}

BEAT_REGEN_TRIES = 2     # 틀 준수를 못 지켰을 때 다시 쓰는 횟수. generate_one_style과 같은 사상.
# 한 칸이 원래 길이의 몇 배까지 허용되나. 표현을 바꾸면 길이는 자연히 출렁이므로 넉넉히 두되,
# **대본 전체를 삼키는 폭주**(실측: 한 줄 훅 → 5줄)는 잡는다.
#
# ★2026-08-22 실측 수정 — 종전 `max(per*1.8, per+40)`은 **거의 언제나 `+40`이 이겨서**
#   길이 게이트가 사실상 없는 것과 같았다. 라이브 대본 166비트를 재보니 중앙값 25자·
#   p90 37자인데, 그 구간에서 `+40`이 주는 상한은:
#       10자 칸 → 50자(5.0배) · 25자 칸 → 65자(2.6배) · 37자 칸 → 77자(2.1배)
#   즉 **짧은 칸일수록 더 헐렁했다**(짧은 칸을 봐주려고 넣은 값이 정반대로 작동).
#   `1.8`은 50자 이상에서만 발동해 실제로는 거의 쓰이지도 않았다.
#   실사고(사장님 제보): 50자 '방법' 칸이 74자로 2배가 됐는데 상한 90자라 통과 →
#   4.6초가 9.0초가 되고 아래 '단계'·'질감' 칸과 내용이 겹쳤다.
#
#   그래서 배수를 조이고(1.8→1.35), 하한 여유도 +40자 → +12자로 줄인다. 12자는
#   "표현을 바꾸다 보면 이 정도는 는다"는 몫이지 문장 하나를 더 담을 수 있는 크기가
#   아니다(한국어 한 문장 ≈ 20자+). 새 상한: 10자→22자 · 25자→34자 · 37자→50자.
_BEAT_LEN_MAX = 1.35
_BEAT_LEN_SLACK = 12


def beat_len(text):
    """한 칸의 길이 — **norm(공백·문장부호 제외)**. 길이를 재는 곳은 전부 이걸 쓴다.

    ★단위를 함수로 못 박는 이유(2026-08-24 실사고): 예산은 `len(원문)`(raw)로 잡고
      판정은 `len(norm(...))`로 해서, 곱하기 1.35를 하기도 전에 이미 26%가 공짜였다.
      실효 상한이 1.8배 = **조이기 전과 같은 값**이라 "고쳤는데 또 길어진다"가 났다.
      (길이 수정이 5번째였다 — 매번 배수만 만지고 단위는 아무도 안 봤다)
    """
    # 지연 import — 이 모듈은 script_gate를 함수 안에서만 부른다(순환 import 회피 관례).
    from shopping_shorts import script_gate as _sg
    return len(_sg.norm(text or ""))


def _beat_len_cap(per):
    """한 칸을 다시 쓸 때 허용하는 최대 글자 수.

    ★`per`는 반드시 **norm 기준**이어야 한다(`beat_len()`으로 잰 값).
      raw를 넣으면 상한이 26% 헐렁해져 이 함수가 있으나 마나가 된다.

    ★판정과 최종 방어가 **같은 값을 봐야 한다**(0순위-B). 종전엔 같은 식
      `max(per*1.8, per+40)`이 재시도 루프와 마지막 반환문 **두 군데에 따로** 적혀
      있었다 — 한쪽만 고치면 "게이트는 통과인데 None이 나온다"(또는 그 반대)가 조용히
      생긴다. 값을 정하는 곳을 함수 하나로 뽑아 그 가능성을 없앤다.
    """
    return max(per * _BEAT_LEN_MAX, per + _BEAT_LEN_SLACK)


def regen_one_beat(sources, style, role, beats, template="", target_seconds=30,
                   bank_context="", facts_block=""):
    """[바꾸기] — 대본의 **한 칸만** 다시 쓴다. → {text, template, matched, tries} / 실패면 None

    ## 왜 '틀을 그대로 넣기'가 아니라 '재생성'인가 (2026-08-17 사장님 지시 B안)

    지금까지 [바꾸기]는 `spine.templates_json`의 문장틀을 **원문 그대로** 칸에 넣었다.
    그래서 화면에 `이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요`처럼 중괄호가 그대로
    박혔다. 이건 고장이 아니라 미구현이었다 — 원래 설계가 "빈칸은 AI가 이 대본 소재에
    맞게 채운다"였는데(`app.py` `/api/script/style/templates` 주석) 그 채우는 단계가
    아직 없었다(handoff/대본UI2단계.md ⏭ 4번).

    **빈칸만 치환하지 않고 칸을 통째로 다시 쓰는 이유**(사장님 B안 선택):
      · 빈칸 치환은 `{가족}`→`엄마` 한 단어만 바뀌어 **바꿔도 바뀐 느낌이 안 난다**.
        실측(2026-08-17 화면): 가족갈등 반전형 미끼 틀 4개 중 2개가
        "{장소} 갔다가 진짜 충격 받았어요" / "{가족} 때문에 진짜 충격 받았어요"로
        슬롯만 다른 사실상 같은 문장이었다. 채워도 이 문제는 남는다.
      · 틀의 **구조만 빌려** 다시 쓰면 같은 틀이라도 매번 다른 문장이 나온다 =
        [바꾸기]가 진짜 '바꾸기'가 된다.
      · 이게 곧 `[훅만 다시]` 부분 재생성이라 두 기능이 **한 벌**이 된다(0순위-B).

    ## 재료·판정을 새로 짜지 않는다

    프롬프트 재료(`_mix_source_block`·`_style_extra`·`facts_block`)도, 틀 준수 판정
    (`script_gate.template_matches`)도 **전부 전체 생성과 같은 함수**를 쓴다. 여기서
    따로 만들면 "왜 전체 생성과 [바꾸기] 결과의 결이 다르냐"가 반드시 생긴다.

    template: 사장님이 고른 틀 1개. 비면 그 칸의 틀 전체를 후보로 준다(자유 재생성).
    beats: 지금 대본 전체 — **앞뒤 문맥**으로 넣는다. 이게 없으면 새 문장이 앞뒤와 따로 논다.
    """
    from shopping_shorts import bank_assemble, script_gate

    role = (role or "").strip()
    if not role:
        return None
    # ★스파인이 없어도 돈다(2026-08-26 사장님 "픽업영상 대본은 바꾸기를 누르면
    #   ai자동바꾸기가 왜안되나"). 픽업영상 대본은 **스타일을 안 고르는 경로**라
    #   style이 None인데, 종전엔 여기서 곧장 None을 반환해 [바꾸기]가 통째로 막혔다.
    #   스파인이 없으면 역할 검증·문장틀만 건너뛰고 나머지(앞뒤 문맥·재료·길이·판정)는
    #   전체 생성과 **그대로 같은 경로**로 간다 — 여기서 따로 만들면 결이 어긋난다(0순위-B).
    roles = list((style or {}).get("beat_roles") or [])
    if roles and role not in roles:
        return None
    seconds = max(5, min(int(target_seconds or 30), 90))
    templates = ((style or {}).get("templates") or {}).get(role) or []
    # 고른 틀이 그 칸 것이 아니면 무시한다(클라이언트 값을 믿지 않는다 — work_id 사고와 같은 유형).
    picked = (template or "").strip()
    want = [picked] if picked and picked in templates else list(templates)

    # ★짝짓기는 bank_assemble.beat_descs 한 곳에서만 정한다(0순위-B) — 예전엔 여기와
    #   style_block 두 군데에 같은 zip()이 적혀 있었고, 둘 다 조용히 끊겼다.
    descs = bank_assemble.beat_descs(style)
    # ★분량은 **지금 그 칸에 있던 문장 길이**에 맞춘다(2026-08-17 실측 수정).
    #   처음엔 전체 생성과 같은 '칸 평균'(chars_per_30s ÷ 칸수)을 줬는데, 한 칸만 다시 쓸
    #   때는 그게 틀렸다 — 칸마다 제 길이가 다르기 때문이다. 실측에서 한 문장짜리 훅이
    #   2~3문장으로 부풀어 **훅의 힘이 죽었다**(미끼는 짧아야 하는 칸이다).
    #   대본 전체 밀도는 나머지 칸이 그대로 있으므로 이 칸만 제자리를 지키면 유지된다.
    prev_text = next((str(b.get("text") or "") for b in (beats or [])
                      if isinstance(b, dict) and b.get("role") == role), "")
    # ★norm으로 잰다 — 아래 판정(`n_out`)·상한(`_beat_len_cap`)과 **같은 단위**여야 한다.
    #   종전엔 여기만 raw(len)라 상한이 26% 헐렁했다(2026-08-24 실사고, beat_len 주석 참조).
    per = beat_len(prev_text)
    if not per:     # 빈 칸을 채우는 경우에만 스타일 평균으로 되돌아간다
        # 스타일 밀도도 norm으로 환산해서 쓴다(script_gate가 한 곳에서 정한다, 0순위-B).
        chars = script_gate.norm_chars_per_30s(style)
        per = int(chars * seconds / 30 / max(1, len(roles))) if chars else 0

    # 앞뒤 문맥 — 지금 대본에서 이 칸을 뺀 나머지를 순서대로 보여준다.
    ctx = []
    for b in (beats or []):
        if not isinstance(b, dict):
            continue
        mark = "  ← ★지금 다시 쓸 칸" if b.get("role") == role else ""
        ctx.append('  %s: %s%s' % (bank_assemble._sanitize(str(b.get("role") or "")),
                                   bank_assemble._sanitize(str(b.get("text") or "")), mark))

    tmpl_line = ""
    if want:
        # ★여기만은 `_sanitize`를 쓰지 않는다(실측 함정, 2026-08-17).
        #   `bank_assemble._sanitize`는 format() 안전을 위해 `{가족}` → `(가족)`으로 바꾼다.
        #   그런데 이 프롬프트에서 **중괄호가 곧 '여기가 빈칸이다'라는 신호**다 —
        #   소독해 버리면 AI가 `(가족)`을 그냥 괄호 낀 낱말로 읽어 채울 자리를 잃는다.
        #   `style_block`은 소독해도 됐다(거기는 "빈칸만 채워라"가 지시문에 따로 있다).
        #   format()에 안 태우고 **문자열로 이어붙이기만** 하므로 중괄호가 남아도 안전하다
        #   (아래 base는 어디서도 `.format()`을 부르지 않는다 — 재포맷이 없다).
        # ★틀을 하나만 고른 경우 "이 틀로 바꿔라"를 못 박는다(2026-08-17 실측).
        #   느슨하게 주니 모델이 **지금 칸에 이미 있던 다른 틀**("…욕 바가지로 먹을 뻔했어요")을
        #   그대로 유지하고 고른 틀을 무시했다 — 실측 4개 중 2개가 그랬다.
        #   사장님이 틀을 고른 것은 "그 틀로 바꿔달라"는 뜻이다.
        one = len(want) == 1
        tmpl_line = (
            "\n★쓸 문장틀(구조만 빌려라 — **{빈칸}은 이 대본의 소재로 채워 쓰고, 중괄호를 "
            "그대로 남기지 마라**): " + " / ".join('"%s"' % x for x in want)
            + ("\n  ★★이 틀로 **갈아끼우는 것**이 목적이다. 지금 이 칸에 적힌 문장이 다른 틀을 "
               "쓰고 있어도 **그건 버리고 위 틀로 바꿔라**. 위 틀의 뼈대가 결과 문장에 "
               "반드시 보여야 한다." if one else "")
            + "\n  틀의 **특징 어구**(예: '…한테 욕 바가지로 먹을 뻔했어요')는 살리되, "
              "앞머리와 살은 이 대본 소재에 맞게 새로 써라. 틀을 통째로 베끼지 마라.")

    # ★`_MIX_PROMPT`를 쓰지 않는다(2026-08-17 사장님 제보로 수정 — 미끼 칸에 대본 전체가
    #   들어갔다). 그 프롬프트는 **"약 30초 분량의 새 대본 초안을 만들어라 … 0초 훅 → …
    #   → 끝 CTA"** 라고 지시하고 헌장(`_STORY_RULES_CORE`)에 CTA 규칙까지 들어 있다.
    #   뒤에 "한 줄만 다시 쓴다"를 덧붙여도 **앞의 '대본 한 편을 써라'가 그대로 살아 있어서**
    #   모델이 훅 칸 하나에 문제제기·시연·증거·CTA를 전부 담았다(실측: 5줄짜리 훅 +
    #   아래 칸들과 내용 중복 + "댓글에 '카메라' 남겨주시면"까지).
    #   ★한 칸만 쓸 때 필요한 것은 **재료(무엇에 대한 대본인가)뿐**이고, '대본을 통째로
    #     써라'는 지시는 해롭다. 그래서 재료 블록만 직접 가져다 쓴다.
    #   (`_style_extra`·`voice_block`·`facts_block`은 표현·사실 재료라 그대로 둔다)
    base = (
        "너는 한국 쇼핑 숏폼 대본 작가다. 지금 **이미 완성된 대본 한 편**이 있고,\n"
        "그중 **딱 한 칸(한두 문장)만** 다시 쓰는 일을 한다.\n"
        "★새 대본을 쓰는 게 아니다. 훅부터 CTA까지 다 쓰지 마라 — **그 칸 하나만** 쓴다.\n\n"
        "[이 대본의 재료 — 무엇에 대한 영상인지 알기 위한 참고자료다]\n"
        + _mix_source_block((sources or [])[:SOURCE_MAX])
        + (("\n\n" + bank_context) if bank_context else "")
        + _style_extra()
        + (("\n" + facts_block) if facts_block else "")
        + "\n\n[현재 대본 — 이 중 ★표시한 칸 하나만 바꾼다]\n" + "\n".join(ctx)
        + "\n\n[다시 쓸 칸] role=\"%s\" — %s" % (role, bank_assemble._sanitize(descs.get(role, "")))
        + tmpl_line
        # ★"2~3문장씩"을 여기선 요구하지 않는다 — 그 지시는 대본 **전체**를 채울 때 것이고,
        #   한 칸만 다시 쓸 때 붙이면 짧아야 할 훅까지 부풀어 힘이 죽는다(실측).
        # ★상한을 처음부터 숫자로 준다(2026-08-22). 종전엔 "안팎"만 말해 첫 시도가 자주
        #   넘쳤고, 재시도 3회를 다 태워 502로 끝났다(사장님: "바꾸면 너무 길어진다").
        #   판정이 쓰는 값(_beat_len_cap)과 **같은 수**를 보여준다 — 여기서 다른 수를 말하면
        #   지킨 문장이 벌받는다(0순위-B).
        + (("\n★분량: **%d자 안팎, 많아도 %d자**(공백 제외). 지금 이 칸과 비슷한 길이로 써라. "
            "길게 늘이지 마라 — 이 칸이 길어지면 대본 전체 호흡이 무너지고 아래 칸과 내용이 겹친다. "
            "문장은 **한 문장**이 기본이다."
            % (per, int(_beat_len_cap(per)))) if per else "")
        + bank_assemble.voice_block(style)
        + "\n\n★반드시 지켜라:\n"
          "- **이 칸의 역할만** 하라. 다른 칸이 할 말(문제제기·시연·증거·CTA)을 여기에 끌어오지 마라.\n"
          "- 앞뒤 칸이 **이미 한 말을 되풀이하지 마라**. 자연스럽게 이어지기만 하면 된다.\n"
          "- 댓글 유도(CTA)는 마지막 칸 몫이다. 그 칸이 아니면 **CTA를 쓰지 마라**.\n"
          "- 지금 이 칸에 적혀 있던 문장과도 **다르게** 써라.\n"
          "출력은 {\"text\": \"...\"} 하나만. 그 칸의 대사만 넣어라. role은 돌려주지 마라."
    )

    extra, tries, out = "", [], ""
    for _ in range(BEAT_REGEN_TRIES + 1):
        data = _call_json(base + extra, _BEAT_SCHEMA)
        out = ((data or {}).get("text") or "").strip()
        if not out:
            break
        # ★중괄호가 남으면 실패다 — 그게 이 기능을 만든 이유다.
        left = "{" in out or "}" in out
        # 틀을 고른 경우에만 준수를 본다(자유 재생성이면 판정 없음 = 통과).
        ok_t = (not want) or script_gate.template_matches(out, want)
        # ★원래 문장과 똑같이 나오면 **실패로 친다**(2026-08-17 실측). 사장님이 [바꾸기]를
        #   눌렀는데 한 글자도 안 바뀌면 화면상 '먹통'이다 — 기능이 도는지조차 알 수 없다.
        #   실제로 원래 문장이 이미 그 틀을 쓰고 있을 때 모델이 그대로 되돌려줬다.
        same = bool(prev_text) and script_gate.norm(out) == script_gate.norm(prev_text)
        # ★칸 하나가 대본 전체를 삼키는 것을 막는다(2026-08-17 사장님 제보로 추가).
        #   미끼 칸에 문제제기·시연·증거·CTA가 통째로 들어와 5줄이 됐다. 프롬프트로
        #   부탁만 해서는 안 된다 — **판정해서 되돌려야** 고쳐진다(게이트와 같은 사상).
        n_out = beat_len(out)
        too_long = bool(per) and n_out > _beat_len_cap(per)
        # CTA는 마지막 칸 몫이다. 다른 칸이 댓글 유도를 하면 그 칸의 역할을 벗어난 것이다.
        cta_role = roles[-1] if roles else ""
        stole_cta = (role != cta_role) and ("남겨주" in script_gate.norm(out))
        tries.append({"chars": n_out,
                      "fails": ([] if ok_t else ["문장틀"]) + (["빈칸"] if left else [])
                               + (["그대로"] if same else []) + (["길이"] if too_long else [])
                               + (["CTA침범"] if stole_cta else [])})
        if ok_t and not left and not same and not too_long and not stole_cta:
            break
        # ★재작성 지시는 **무엇을 어겼는지 그대로** 보여준다(2026-08-15 게이트와 같은 사상:
        #   부탁이 아니라 되돌리기). 실측(2026-08-17)에서 "틀을 살려라"만으로는 2/4가 계속
        #   실패했다 — 모델이 어느 어구를 빠뜨렸는지 모르기 때문이다. 지켜야 할 어구를
        #   콕 집어 주면 고칠 수 있다.
        extra = ("\n\n[재작성 지시 — 방금 네가 쓴 것은 아래를 어겼다. 그대로 고쳐 다시 써라]\n"
                 "  방금 쓴 문장: \"%s\"\n" % out)
        if not ok_t:
            # 빈칸을 뺀 **원문 조각**을 보여준다 — `_chunks`는 공백을 지운 판정용이라
            # 그대로 보여주면 "욕바가지로먹을뻔했어요"처럼 읽기 나쁘다.
            need = [p.strip() for p in re.split(r"\{[^}]*\}", want[0] if want else "")
                    if len(p.strip()) >= 3]
            extra += ("- 위 문장틀을 **안 썼다**. 반드시 아래 어구가 문장 안에 그대로 보여야 한다:\n"
                      + "".join("    · \"%s\"\n" % w for w in need)
                      + "  (어구 사이는 이 대본 소재로 채워라. 어미는 바꿔도 된다)\n")
        if left:
            extra += ("- **중괄호가 그대로 남았다**. `{가족}`·`{장소}` 같은 자리는 이 대본의 "
                      "실제 소재로 바꿔 써야 한다(예: `{가족}` → `엄마`). 중괄호를 출력하지 마라.\n")
        if same:
            extra += ("- 원래 있던 문장을 **그대로 돌려줬다**. 사용자는 '바꿔달라'고 누른 것이다. "
                      "같은 뜻이라도 표현·어순·시작하는 말을 확실히 다르게 써라.\n")
        if too_long:
            # ★상한을 **숫자로** 알려준다(2026-08-22). 종전엔 "%d자 안팎"만 말해서 모델이
            #   어디까지가 통과인지 몰랐고, 재시도해도 또 길게 써서 3회를 다 태우고 502가 났다.
            #   판정이 쓰는 값(_beat_len_cap)을 그대로 보여줘야 고칠 수 있다.
            extra += ("- **너무 길다(%d자). 이 칸은 %d자 안팎, 많아도 %d자를 넘기지 마라.** "
                      "대본 전체를 쓰지 마라 — 이 칸 하나의 대사만 써라. 다른 칸이 할 말은 빼고, "
                      "곁가지 수식어를 덜어내 한 문장으로 줄여라.\n"
                      % (n_out, per, int(_beat_len_cap(per))))
        if stole_cta:
            extra += ("- **댓글 유도(CTA)를 여기에 썼다.** CTA는 마지막 '%s' 칸 몫이다. "
                      "이 칸에서는 빼라.\n" % cta_role)
    # ★조용히 반쪽을 주지 않는다 — 중괄호가 남았거나, 한 글자도 안 바뀌었거나, 칸 하나가
    #   대본 전체를 삼킨 결과는 실패로 돌려보내 화면이 "다시 시도"를 말하게 한다.
    #   성공인 척하고 화면에 꽂는 게 제일 나쁘다(사장님이 5줄짜리 훅을 그대로 받았다).
    if not out or "{" in out or "}" in out:
        return None
    if prev_text and script_gate.norm(out) == script_gate.norm(prev_text):
        return None
    _n = beat_len(out)          # 재시도 루프와 **같은 함수**로 잰다(0순위-B)
    if per and _n > _beat_len_cap(per):
        return None
    if roles and role != roles[-1] and "남겨주" in script_gate.norm(out):
        return None
    return {"text": out, "template": picked, "role": role,
            "matched": (not want) or script_gate.template_matches(out, want), "tries": tries}


def generate_by_styles(sources, styles, target_seconds=30, bank_context="", facts_block="",
                       reasons=None, seed=""):
    """스타일 목록(보통 2개) → 각 1안. 실패한 스타일은 건너뛴다(하나라도 나오면 화면은 산다).

    facts_block은 그대로 흘려보낸다 — 빈 값이면 기존 경로(회귀 0).

    reasons: 리스트를 주면 **실패 사유를 담아 돌려준다**(2026-08-22 추가).
      종전엔 사유가 `print`로만 나가서 호출부(app.py)가 "왜 0개인지" 알 길이 없었고,
      화면에는 원인과 무관하게 늘 "키 소진 또는 응답 오류"가 떴다 — 키가 멀쩡한데도
      사장님이 키 회복을 기다리며 재시도만 반복하게 만든 문구다.
      **주지 않으면 종전과 완전히 동일하게 동작한다**(기본값 None = 회귀 0).
    """
    out = []
    for st in styles or []:
        note = {} if reasons is not None else None
        try:
            d = generate_one_style(sources, st, target_seconds, bank_context, facts_block,
                                   seed=seed, note=note)
        except Exception as e:      # noqa: BLE001 — 한 스타일 실패로 나머지를 죽이지 않는다
            print(f"generate_by_styles 실패(style={st.get('id')}): {e}")
            if reasons is not None:
                reasons.append({"style": st.get("name") or st.get("id"),
                                "kind": type(e).__name__, "detail": str(e)[:200]})
            d = None
        if d and d.get("beats"):
            out.append(d)
        elif reasons is not None:
            # 예외 없이 빈손 = 키가 없거나·소진·응답오류·게이트 반ней. _call_json이 note에
            # 적어준 사유를 그대로 올린다(없으면 '빈손'으로만 표시).
            reasons.append({"style": st.get("name") or st.get("id"),
                            "kind": (note or {}).get("reason") or "empty",
                            "keys": (note or {}).get("keys"),
                            "detail": (note or {}).get("detail") or ""})
    return out


def _elem_lines(structure, elem_modes, category_lookup):
    """요소별 지시 라인 생성. elem_modes: {element_key: mode_string}, mode_string은
    "keep"(원본유지) / "free"(AI 자유즉흥) / "random"(학습된 카테고리 중 랜덤) /
    "category:<label>"(특정 카테고리 지정) 중 하나(2026-07-13, 4단 모드).
    category_lookup: {element: [{"label","description"}, ...]} — Store.get_element_options()
    형태. 지정/랜덤 모드인데 옵션이 없으면 free로 자동 폴백."""
    _STRUCT_KEY = {"hook": "hook_type"}  # analyze_structure 출력 필드명과 매핑
    lines = []
    for key, label in ELEM_LABELS.items():
        struct_key = _STRUCT_KEY.get(key, key)
        if key == "characters":
            chs = structure.get("characters") or []
            val = ", ".join(f"{c.get('who')}({c.get('role')})" for c in chs) or "없음"
        elif key == "devices":
            devs = structure.get("devices") or []
            val = ", ".join(str(d) for d in devs if str(d).strip()) or "없음"
        else:
            val = structure.get(struct_key) or "(원본에 없음)"

        mode = elem_modes.get(key, "keep")
        options = category_lookup.get(key) or []

        if mode == "keep":
            lines.append(f"- {label}: 유지 → 원본과 같은 강점 살려라 [{val}]")
            continue
        if mode == "random" and options:
            mode = "category:" + random.choice(options)["label"]
        if mode.startswith("category:") and options:
            wanted = mode.split(":", 1)[1]
            opt = next((o for o in options if o["label"] == wanted), None)
            if opt:
                lines.append(
                    f"- {label}: 반드시 '{opt['label']}' 유형으로 — {opt['description']} "
                    f"(원본[{val}]과 달라도 됨, 이 카테고리 안에서 자연스럽게)")
                continue
        # free 모드이거나, category/random인데 옵션이 없으면 자유즉흥으로 폴백
        lines.append(f"- {label}: 변형(자유 즉흥) → 원본[{val}]과 다르게 더 참신하게 바꿔라")
    return "\n".join(lines)


def _pickup_hook_directive(seed_hook, subject=""):
    """픽업영상 대본 — 훅 지시문(2026-08-26 사장님 "훅도 터지는 영상이니 변형해서").

    ★원본 훅 문장을 **그대로 보여준다**(사장님이 (B)안으로 확정). 문형 재현율이 가장 높다.
      대신 메모리 `참고훅주입_베끼기숫자창작`의 교훈을 그대로 반영한다 —
      "베끼지 마라" 한 줄로는 안 막히고 **실패 예시를 박아야** 걸린다.
    ⚠️여기 문구와 판정(pickup_script.hook_ok)이 두 벌이 되면 어긋난다.
      문구는 '무엇을 원하는지', 판정은 '지켰는지'다 — 어긴 결과는 호출부가 재작성을 건다.
    """
    subj = (subject or "").strip()
    lines = [
        "- 훅: **아래 원본 훅의 '문형'을 그대로 지켜라** — 문형이란 문장의 뼈대다.",
        "    원본 훅: 「" + (seed_hook or "").strip() + "」",
        "    ↳ 이 뼈대(호칭 + 대상 + 강조어 + ~하지 마세요 류)를 유지하되 **문장은 새로 써라.**",
    ]
    if subj:
        lines.append("    ↳ 소재는 원본과 같은 '" + subj + "'를 유지한다(제품군을 바꾸지 마라).")
    lines += [
        "    ★금지(실패 예시 — 이대로 쓰면 반려된다):",
        "      · 원본 훅을 그대로/거의 그대로 복사 → 「" + (seed_hook or "").strip() + "」 (X)",
        "      · 문형을 버리고 다른 말투로 → 「세상에, 그거 끊은 우리 엄마가…」 (X)",
        "      · 원본에 없는 숫자·통계 지어내기 → 「3주만에 30퍼센트 감소」 (X)",
    ]
    return "\n".join(lines)


def generate_variations(structure, full_text, elem_modes, category_lookup, mode="remake",
                        my_topic="", subject="", n=3, max_key_tries=3, bank_context="",
                        seed_hook=""):
    """구조+대본을 재료로 요소별 모드 지시에 맞춰 초안 리스트 반환. 실패/무키면 [].

    mode: "remake"(원본 소재 고정, 표현만 재작성) 또는 "transplant"(구조만 빌려 내 주제로).
    구버전 "A"/"B"도 하위호환으로 각각 remake/transplant에 매핑된다.
    """
    if not comment_gen.SHORTS_GEMINI_KEYS or not (full_text or "").strip():
        return []
    n = max(1, min(int(n or 3), 5))
    mode = {"A": "remake", "B": "transplant"}.get(mode, mode)  # 구버전 하위호환
    if mode == "transplant" and (my_topic or "").strip():
        topic_line = (f"주제: 구조만 빌리고 아래 '내 주제/제품'에 맞춰 새로 써라."
                      f"\n내 주제/제품: {my_topic.strip()}")
    else:
        subj = (subject or "").strip()
        subj_line = f"\n소재(고정): {subj}" if subj else ""
        topic_line = (
            "주제: 아래 원본의 '소재'를 그대로 유지한 리메이크다. 원본의 제품·사실·장면·정보는 "
            "바꾸지 말고, 표현(훅 문장·어휘·문장 순서·말투)만 새로 써서 원문을 그대로 베끼지 않게 "
            "(중복 회피) 리라이트하라. 없던 내용이나 다른 제품을 지어내지 마라." + subj_line)
    seconds = 30
    words = max(15, round(seconds * 2.3))
    _elems = _elem_lines(structure or {}, elem_modes, category_lookup)
    # ★픽업영상 대본(2026-08-26) — seed_hook이 오면 훅 줄만 '문형 지정' 지시로 갈아끼운다.
    #   안 오면 종전 그대로라 회귀 0(호출부가 안 보내면 아무 일도 없다).
    #   _elem_lines가 만든 훅 줄("- 훅: 유지 → …[경고형]")은 **유형만** 전달해서
    #   실측 4안 중 2안이 문형을 버렸다 — 그래서 원본 문장을 직접 싣는다.
    if (seed_hook or "").strip():
        _elems = "\n".join(
            [l for l in _elems.split("\n") if not l.startswith("- 훅:")]
            + [_pickup_hook_directive(seed_hook, subject)])
    prompt = (_GEN_PROMPT.format(
        full_text=full_text[:3000], elems=_elems,
        topic_line=topic_line, n=n, seconds=seconds, words=words,
        bank=("\n\n" + bank_context) if bank_context else "")
        + _style_extra())   # ★채널 스타일(2026-08-05)
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return []
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            return _verify_and_fix(json.loads(resp.text).get("drafts", []))
        except Exception as e:  # noqa: BLE001 — 생성 실패는 치명적 아님(빈 리스트)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki, key_vault.retry_delay_seconds(e), exc=e)
                continue
            return []
    return []


_REFINE_SCHEMA = {
    "type": "object",
    "properties": {"script": {"type": "string"}},
    "required": ["script"],
}

_REWRITE_PROMPT = """너는 한국 쇼핑 숏폼 대본 작가다. 아래 대본을 지시에 맞춰 통째로
다시 써라(구어체 나레이션, 0초 훅부터 끝 CTA까지 흐름은 유지).

[원본 대본]
{script}

[지시]
{instruction}

[반드시 지킬 대본 원칙]
""" + _STORY_RULES_CORE + """

다음 JSON으로만 출력: {{"script": "다시 쓴 전체 대본"}}"""

_PARTIAL_PROMPT = """너는 한국 쇼핑 숏폼 대본 작가다. 아래 대본에서 지정된 부분만
지시대로 바꿔라. 지정된 부분 밖은 토씨 하나 그대로 유지해라.

[원본 대본 전체]
{script}

[바꿀 부분]
{selected}

[지시]
{instruction}

바꾸는 부분도 전체 스토리(인과 사슬·훅에서 끝까지 이어지는 하나의 이야기)와 자연스럽게
이어지게 하라. 단 지정된 부분 밖은 토씨 하나 건드리지 마라.

다음 JSON으로만 출력: {{"script": "수정된 전체 대본(바뀐 부분만 반영, 나머지는 원본 그대로)"}}"""


def _refine(prompt, max_key_tries=3):
    if not comment_gen.SHORTS_GEMINI_KEYS:
        return ""
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return ""
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_REFINE_SCHEMA),
            )
            return json.loads(resp.text).get("script", "")
        except Exception as e:  # noqa: BLE001 — 재생성 실패는 치명적 아님(빈 문자열)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki, key_vault.retry_delay_seconds(e), exc=e)
                continue
            return ""
    return ""


def refine_draft_rewrite(script_text, instruction, max_key_tries=3):
    """대본 전체를 지시문에 맞춰 다시 쓴다. 실패/무키면 ""."""
    return _refine(_REWRITE_PROMPT.format(script=script_text, instruction=instruction), max_key_tries)


def refine_draft_partial(script_text, selected_text, instruction, max_key_tries=3):
    """선택한 부분만 지시문에 맞춰 바꾸고 나머지는 유지. 실패/무키면 ""."""
    return _refine(
        _PARTIAL_PROMPT.format(script=script_text, selected=selected_text, instruction=instruction),
        max_key_tries)


# ---- P5 자기검증 루프: 초안 3축 판정(인과·훅→끝·CTA) 후 미달만 1회 자동 보정 ----

_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "idx": {"type": "integer"},
                    "causality_ok": {"type": "boolean"},
                    "hook_to_end_ok": {"type": "boolean"},
                    "cta_ok": {"type": "boolean"},
                    "fix_instruction": {"type": "string"},
                },
                "required": ["idx", "causality_ok", "hook_to_end_ok", "cta_ok",
                             "fix_instruction"],
            },
        }
    },
    "required": ["verdicts"],
}

_JUDGE_PROMPT = """너는 한국 쇼핑 숏폼 대본 품질 검수자다. 아래 초안들을 초안별로
3가지 축으로 엄격히 판정하라.

[초안들]
{drafts}

판정 축:
1. causality_ok — 인과·상관관계가 말이 되나? 각 문장이 앞 문장에서 자연스럽게
   이어지나. 근거 없는 효능 비약, 뜬금없는 소재 점프가 있으면 실패.
2. hook_to_end_ok — 훅에서 던진 궁금증/문제/이야기가 끝까지 끊기지 않고 이어져
   해소되나. 훅 따로 본문 따로면 실패. 인물이나 사건이 중간에 바뀌면 실패.
3. cta_ok — 마지막이 행동유도(CTA) 문장으로 끝나고, 그 CTA가 본문 이야기와
   인과로 이어지나. 댓글 키워드형이면 'OO 남겨주세요'의 키워드가 실제로 명시돼
   있어야 통과.

하나라도 실패면 fix_instruction에 무엇을 어떻게 고칠지 구체적 수정 지시를
한국어 1~2문장으로 써라. 전부 통과면 fix_instruction은 빈 문자열.
idx는 초안 번호(0부터). JSON만 출력."""

_FIX_SCHEMA = {
    "type": "object",
    "properties": {"hook": {"type": "string"}, "script": {"type": "string"}},
    "required": ["hook", "script"],
}

_FIX_PROMPT = """너는 한국 쇼핑 숏폼 대본 작가다. 아래 대본이 검수에서 지적받았다.
지적을 고쳐 통째로 다시 써라. 구어체 나레이션, 원래 분량(약 {words}단어) 유지.

[대본]
{script}

[검수 지적]
{instruction}

규칙:
""" + _STORY_RULES_CORE + """
다음 JSON으로만 출력: {{"hook": "첫 훅 한 줄", "script": "다시 쓴 전체 대본"}}"""


def _verify_and_fix(drafts, seconds=20):
    """초안들을 3축(인과·훅→끝·CTA) 판정하고 미달 초안만 1회 재작성.
    판정 1콜 + 미달 수 만큼 수정 콜. 판정 실패 시 원본 그대로(fail-open) —
    검증 루프가 생성 기능을 죽이면 안 된다."""
    if not drafts:
        return drafts
    words = max(15, round(seconds * 2.3))
    block = "\n\n".join(f"[초안 {i}]\n{d.get('script', '')}" for i, d in enumerate(drafts))
    verdicts = _call_json(_JUDGE_PROMPT.format(drafts=block), _JUDGE_SCHEMA).get("verdicts", [])
    for v in verdicts:
        i = v.get("idx")
        if not isinstance(i, int) or not (0 <= i < len(drafts)):
            continue
        if v.get("causality_ok") and v.get("hook_to_end_ok") and v.get("cta_ok"):
            continue
        instruction = ((v.get("fix_instruction") or "").strip()
                       or "인과가 끊긴 부분을 잇고 마지막을 본문과 이어지는 CTA로 끝내라.")
        fixed = _call_json(
            _FIX_PROMPT.format(script=drafts[i].get("script", ""),
                               instruction=instruction, words=words), _FIX_SCHEMA)
        if (fixed.get("script") or "").strip():
            drafts[i]["script"] = fixed["script"].strip()
            drafts[i]["hook"] = (fixed.get("hook") or drafts[i].get("hook") or "").strip()
            drafts[i]["applied"] = ((drafts[i].get("applied") or "") + " · 검수 후 자동 보정").strip(" ·")
    # 대본 품질 주석 + 정렬 — 재미강도(D14 강한장치) 있고 대화체 자연스러운 초안을 앞으로.
    # 하드 재생성 대신 정렬로: 추천안([0])이 최고 품질이 되고, 약한 초안도 선택지로 남는다.
    from shopping_shorts import tone_score
    for d in drafts:
        sc = d.get("script", "")
        d["fun"] = tone_score.fun_intensity(sc)
        d["tone"] = round(tone_score.score_conversational(sc)["score"], 3)
    drafts.sort(key=lambda d: (d.get("fun", {}).get("has_strong", False), d.get("tone", 0)),
                reverse=True)
    return drafts


_SUBJECT_SCHEMA = {
    "type": "object",
    "properties": {"subject": {"type": "string"}},
    "required": ["subject"],
}

_SUBJECT_PROMPT = """다음 한국 쇼핑 숏폼 대본이 다루는 '소재'(무엇에 관한 영상인지 —
제품/장면/주제)를 한 줄 명사구로만 요약해라. 말투·훅 방식·기법이 아니라 '무엇'인지만.
예: "무선 가습기 물때 청소".

[대본]
{full_text}

다음 JSON으로만 출력: {{"subject": "소재 한 줄"}}"""


def detect_subject(full_text, max_key_tries=3):
    """원본 대본 원문에서 '소재 한 줄'을 Gemini로 요약. 실패/무키/빈입력이면 ""."""
    if not comment_gen.SHORTS_GEMINI_KEYS or not (full_text or "").strip():
        return ""
    prompt = _SUBJECT_PROMPT.format(full_text=full_text[:3000])
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return ""
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SUBJECT_SCHEMA),
            )
            return (json.loads(resp.text).get("subject", "") or "").strip()
        except Exception as e:  # noqa: BLE001 — 감지 실패는 치명적 아님(빈 문자열)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki, key_vault.retry_delay_seconds(e), exc=e)
                continue
            return ""
    return ""
