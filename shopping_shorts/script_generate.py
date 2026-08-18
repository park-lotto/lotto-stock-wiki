"""S급 대본의 구조를 빌려 새 20초 대본 초안 생성 — 유지/변형 토글 + 모드 remake/transplant.

위키의 검증된 뼈대(주변인물·발상전환·전개방식·훅·어필포인트·말투)를 재료로,
사용자가 각 요소를 '유지/변형' 지정하면 그에 맞춰 Gemini가 여러 초안을 만든다.
- 모드 remake: 원본 소재 그대로 유지, 표현(훅·문장·순서·말투)만 새로 써서 중복 회피 리라이트.
- 모드 transplant: 구조만 빌려 사용자가 준 '내 주제/제품'에 이식.
(구버전 A→remake / B→transplant 하위호환.)
전용 키풀(comment_gen) 재사용. 실패/무키면 [].
"""
import json
import random
import re

from google.genai import types

from shopping_shorts import comment_gen
from pipeline.atoms import key_vault

_MODEL = comment_gen._MODEL

# produce 대본생성(우리믹스)은 comment_gen 전용키(1개, 쉽게 소진) 대신
# key_vault 공유풀을 캐스케이드로 쓴다 — 배치된 예비키(general→ingest→embed→briefing)를
# 전부 활용해 소진 사고를 피한다(2026-07-13).
_GEN_GROUP = "general"


def _style_extra():
    """채널 스타일 블록(style_profiles, 2026-08-05). 실패해도 생성을 죽이지 않는다."""
    try:
        from shopping_shorts import style_profiles
        return style_profiles.style_block()
    except Exception:
        return ""


def _call_json(prompt, schema):
    """key_vault 캐스케이드 키풀로 JSON 1콜. 소진키는 마킹하고 다음 키로.
    무키·전부실패면 {} (호출부는 반드시 빈 dict 허용 — fail-open)."""
    keys = key_vault.get_live_keys_cascade(_GEN_GROUP)
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
                continue
            if key_vault.is_quota_error(e):
                continue  # 순간 rate limit — 다음 키로
            return {}
    return {}


def _generate_drafts(prompt):
    """key_vault 캐스케이드 키풀로 대본 초안 리스트 생성. 무키·전부실패면 []."""
    return _call_json(prompt, _SCHEMA).get("drafts", [])

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
    prompt = (_MIX_PROMPT.format(sources=_mix_source_block(sources[:3]), seconds=seconds, words=words, n=n,
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
                "properties": {"role": {"type": "string"}, "text": {"type": "string"}},
                "required": ["role", "text"],
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

def generate_one_style(sources, style, target_seconds=30, bank_context="", facts_block=""):
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
    head = bank_assemble.style_block(style, seconds=seconds)
    if not head:
        return None
    base = (_MIX_PROMPT.format(sources=_mix_source_block((sources or [])[:3]),
                               seconds=seconds, words=max(15, round(seconds * 2.3)), n=1,
                               bank=("\n\n" + bank_context) if bank_context else "")
            + _style_extra()
            + (("\n" + facts_block) if facts_block else "")
            + "\n\n" + head
            + "\n\n출력은 위 칸 순서대로 beats 배열 하나만. 각 원소는 {role, text}.")

    extra, tries, res, checks, full = "", [], None, [], ""
    for _ in range(STYLE_REWRITES + 1):
        data = _call_json(base + extra, _STYLE_SCHEMA)
        res = (data or {}).get("beats") or []
        if not res:
            break
        # ★facts_block을 게이트에도 넘긴다 — 재료를 줬으면 대본의 수치가 그 안에 있는지
        #   대조한다(지어낸 수치 차단). 안 줬으면 그 검사는 건너뛴다(회귀 0).
        # ★소재 일치도 함께 본다(2026-08-18) — 재료의 제품명을 그대로 넘긴다.
        #   product가 비면 그 검사는 건너뛴다(회귀 0).
        checks, full = script_gate.check(style, res, facts_text=facts_block,
                                         product=_sources_product(sources))
        tries.append({"chars": len(script_gate.norm(full)),
                      "fails": [c["name"] for c in checks if not c["ok"]]})
        if script_gate.passed(checks):
            break
        extra = script_gate.gate_feedback(checks)

    return {
        "style_id": style.get("id"), "style_name": style.get("name"),
        "beats": res or [], "script": full, "hook": (res or [{}])[0].get("text", ""),
        "checks": checks, "passed": script_gate.passed(checks), "tries": tries,
    }


_BEAT_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
}

BEAT_REGEN_TRIES = 2     # 틀 준수를 못 지켰을 때 다시 쓰는 횟수. generate_one_style과 같은 사상.
# 한 칸이 원래 길이의 몇 배까지 허용되나. 표현을 바꾸면 길이는 자연히 출렁이므로 넉넉히 두되,
# **대본 전체를 삼키는 폭주**(실측: 한 줄 훅 → 5줄)는 잡는다. 짧은 칸은 배수만으론 너무
# 빡빡해서 `+40자`와 큰 쪽을 쓴다(20자 칸이 30자가 되는 건 정상이다).
_BEAT_LEN_MAX = 1.8


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
    if not role or not style:
        return None
    roles = list(style.get("beat_roles") or [])
    if role not in roles:
        return None
    seconds = max(5, min(int(target_seconds or 30), 90))
    templates = (style.get("templates") or {}).get(role) or []
    # 고른 틀이 그 칸 것이 아니면 무시한다(클라이언트 값을 믿지 않는다 — work_id 사고와 같은 유형).
    picked = (template or "").strip()
    want = [picked] if picked and picked in templates else list(templates)

    descs = style.get("beat_descs") or dict(zip(roles, style.get("beat_chain") or []))
    # ★분량은 **지금 그 칸에 있던 문장 길이**에 맞춘다(2026-08-17 실측 수정).
    #   처음엔 전체 생성과 같은 '칸 평균'(chars_per_30s ÷ 칸수)을 줬는데, 한 칸만 다시 쓸
    #   때는 그게 틀렸다 — 칸마다 제 길이가 다르기 때문이다. 실측에서 한 문장짜리 훅이
    #   2~3문장으로 부풀어 **훅의 힘이 죽었다**(미끼는 짧아야 하는 칸이다).
    #   대본 전체 밀도는 나머지 칸이 그대로 있으므로 이 칸만 제자리를 지키면 유지된다.
    prev_text = next((str(b.get("text") or "") for b in (beats or [])
                      if isinstance(b, dict) and b.get("role") == role), "")
    per = len(prev_text.strip())
    if not per:     # 빈 칸을 채우는 경우에만 스타일 평균으로 되돌아간다
        chars = style.get("chars_per_30s") or 0
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
        + _mix_source_block((sources or [])[:3])
        + (("\n\n" + bank_context) if bank_context else "")
        + _style_extra()
        + (("\n" + facts_block) if facts_block else "")
        + "\n\n[현재 대본 — 이 중 ★표시한 칸 하나만 바꾼다]\n" + "\n".join(ctx)
        + "\n\n[다시 쓸 칸] role=\"%s\" — %s" % (role, bank_assemble._sanitize(descs.get(role, "")))
        + tmpl_line
        # ★"2~3문장씩"을 여기선 요구하지 않는다 — 그 지시는 대본 **전체**를 채울 때 것이고,
        #   한 칸만 다시 쓸 때 붙이면 짧아야 할 훅까지 부풀어 힘이 죽는다(실측).
        + (("\n★분량: **%d자 안팎**(지금 이 칸과 비슷한 길이로. 길게 늘이지 마라 — "
            "이 칸이 길어지면 대본 전체 호흡이 무너진다)." % per) if per else "")
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
        n_out = len(script_gate.norm(out))
        too_long = bool(per) and n_out > max(per * _BEAT_LEN_MAX, per + 40)
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
            extra += ("- **너무 길다(%d자). 이 칸은 %d자 안팎이어야 한다.** 대본 전체를 쓰지 마라 — "
                      "이 칸 하나의 대사만 써라. 다른 칸이 할 말은 빼라.\n" % (n_out, per))
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
    _n = len(script_gate.norm(out))
    if per and _n > max(per * _BEAT_LEN_MAX, per + 40):
        return None
    if roles and role != roles[-1] and "남겨주" in script_gate.norm(out):
        return None
    return {"text": out, "template": picked, "role": role,
            "matched": (not want) or script_gate.template_matches(out, want), "tries": tries}


def generate_by_styles(sources, styles, target_seconds=30, bank_context="", facts_block=""):
    """스타일 목록(보통 2개) → 각 1안. 실패한 스타일은 건너뛴다(하나라도 나오면 화면은 산다).

    facts_block은 그대로 흘려보낸다 — 빈 값이면 기존 경로(회귀 0)."""
    out = []
    for st in styles or []:
        try:
            d = generate_one_style(sources, st, target_seconds, bank_context, facts_block)
        except Exception as e:      # noqa: BLE001 — 한 스타일 실패로 나머지를 죽이지 않는다
            print(f"generate_by_styles 실패(style={st.get('id')}): {e}")
            d = None
        if d and d.get("beats"):
            out.append(d)
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


def generate_variations(structure, full_text, elem_modes, category_lookup, mode="remake",
                        my_topic="", subject="", n=3, max_key_tries=3, bank_context=""):
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
    prompt = (_GEN_PROMPT.format(
        full_text=full_text[:3000], elems=_elem_lines(structure or {}, elem_modes, category_lookup),
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
                comment_gen._mark_key_exhausted(ki)
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
                comment_gen._mark_key_exhausted(ki)
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
                comment_gen._mark_key_exhausted(ki)
                continue
            return ""
    return ""
