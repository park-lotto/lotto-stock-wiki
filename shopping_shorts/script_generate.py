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
    return "\n\n".join(lines)


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
