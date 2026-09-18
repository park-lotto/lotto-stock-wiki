"""확정 대본 → 헤드카피(고정카피) 후보 4개.

★생성 배관을 새로 만들지 않는다 — script_generate._call_json을 그대로 쓴다(키풀
로테이션·소진키 마킹·fail-open이 이미 검증된 코드다, 0순위-B).

⚠️ _call_json은 실패해도 {}를 돌려준다(fail-open). 그래서 여기서 **빈 리스트**로
정규화하고, "못 뽑았다"의 표시는 호출부(화면)가 한다 — 조용히 빈 카드를 띄우면
사장님이 고장인지 준비중인지 구분 못 한다.
"""
import json

from shopping_shorts.script_generate import _call_json
from shopping_shorts.template_copy import EVEN_SHOPPING

_LEGACY_SUBLINE_LEN = 32   # 카나리 밖(고객)의 종전 보조제목 한도 — 2026-09-17 이전 동작 그대로


def _support_max():
    """보조제목 한도 — 관리자 카나리에서만 장면꾸미기 슬롯 계약(22자)을 쓴다(2026-09-18)."""
    from shopping_shorts import canary
    return EVEN_SHOPPING.support_max if canary.on() else _LEGACY_SUBLINE_LEN

_MAX_LEN = 26          # ★썸네일 문구는 두 줄이 전부다(2026-08-18). 40자였을 땐 화면에서 4줄로
_LINE_LEN = 13         #   무너져 문단처럼 보였다 — 두 줄 x 13자를 넘기지 않는다.
_WANT = 4
_WHY_LEN = 80          # ★이유문은 카드 밑에 한 줄로 깔린다(썸네일 제목 추천과 같은 모양).
                       #   길어지면 카드가 문단이 돼 고르기가 더 어려워진다.
_FAMILIES = {"generic", "youtube_reveal", "instagram_story", "demo_direct"}
_DEFAULT_FAMILY = "youtube_reveal"
_PAIRED_FAMILIES = {"youtube_reveal", "instagram_story", "demo_direct"}

_SCHEMA = {
    "type": "object",
    "properties": {
        "copies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "text": {"type": "string"},
                               "why": {"type": "string"},
                               "subline": {"type": "string"},
                               "upload_title": {"type": "string"}},
                "required": ["label", "text", "why"],
            },
        }
    },
    "required": ["copies"],
}

_PROMPT = """너는 쇼츠 영상의 **헤드카피**(영상 위에 크게 박히는 썸네일 문구)를 쓴다.

아래 대본을 읽고 서로 **결이 다른** 후보 4개를 써라.
- 짧은 훅형: 궁금하게 만드는 짧은 한 방
- 숫자형: 숫자를 넣어 구체적으로
- 반전형: 예상과 다른 사실
- 질문형: 보는 사람에게 묻는다

규칙:
- ★**딱 두 줄**로 써라. 두 줄 사이에 줄바꿈(\\n)을 하나만 넣는다.
- 각 줄은 **{linelen}자 이내**(공백 포함), 전체 {maxlen}자 이내.
- 줄을 어절 중간에서 끊지 마라 — 한 줄만 읽어도 말이 되게 끊어라.
- 마침표로 끝내지 마라. 이모지·해시태그·따옴표를 넣지 마라.
- 대본에 **없는 사실을 지어내지 마라**(가격·수치·효능을 새로 만들지 않는다).

각 후보마다 **why**도 함께 써라:
- why: 어떤 훅 장치를 썼고 왜 스크롤이 멈추는지 **한 줄로**({whylen}자 이내).
- 문구를 그대로 옮겨 적지 마라 — **왜 먹히는지**를 말해라.

좋은 예:
  text: 첫 줄 "네일샵 10만원" / 둘째 줄 "아끼는 셀프 꿀팁"  (사이에 줄바꿈 하나)
  why:  "구체적 금액으로 손해 회피 심리를 건드려 클릭을 유도했습니다"

[대본]
{script}
"""

_YOUTUBE_REVEAL_PROMPT = """너는 이븐쇼핑류 유튜브 쇼츠의 **첫 후킹 제목 세트**를 쓴다.

아래 대본에서 서로 다른 후보 4개를 써라. 각 후보는 반드시 한 세트다.
- upload_title: 업로드용 결과형 제목. 제품명보다 먼저 큰 결과·사건을 말한다.
- text: 영상 상단 큰 제목. 정확히 두 줄이며 3인칭 관찰자 화법을 쓴다.
- subline: 큰 제목 아래 흰 띠 문구. 정체를 보조 제목에서 공개하지 말고 질문·미스터리로 남긴다.
- why: 어떤 후킹 장치인지 한 줄로 설명한다.

전개 규칙:
- 큰 제목은 ‘누가/무엇을 어떻게 바꿨는가’라는 결과를 먼저 보여준다.
- 나라·천재·개발자·돈방석·주문 폭주·업계 반응은 후킹을 위해 자유롭게 각색해도 된다.
- 단, 제품의 정체·작동 방식·핵심 효능은 대본과 다른 물건으로 바꾸지 않는다.
- 마지막 재후킹에서 공개할 최강 장점은 subline에 미리 쓰지 않는다.
- text는 두 줄, 각 줄 {linelen}자 이내, 전체 {maxlen}자 이내다.
- subline은 {supportlen}자 이내, upload_title은 50자 이내다.
- 마침표·이모지·해시태그·따옴표를 쓰지 않는다.

좋은 세트 예:
  upload_title: "칼질 포기자를 살린 한국 천재의 발명품"
  text: "칼질 포기자를 살린\n한국 천재의 발명품"
  subline: "텀블러처럼 생긴 주방도구의 정체?"
  why: "큰 결과를 먼저 던지고 제품 정체는 흰 띠에서도 숨겼습니다"

[대본]
{script}
"""

_INSTAGRAM_STORY_PROMPT = """너는 인스타 릴스의 **관계썰 제목 세트**를 쓴다.

아래 대본에서 서로 다른 후보 4개를 써라. 각 후보는 반드시 한 세트다.
- upload_title: 업로드용 제목. 사람·관계·상황·반전 전조를 자연스럽게 잇는다.
- text: 영상 상단 큰 제목. 정확히 두 줄이며 대화하듯 자연스러운 관계 사건으로 연다.
- subline: 큰 제목 아래 보조문구. 다음 상황이 궁금해지는 목격담이나 질문을 쓴다.
- why: 어떤 관계썰 장치인지 한 줄로 설명한다.

전개 규칙:
- 가족·손님·친구·직장 동료처럼 대본에 어울리는 사람과 상황을 먼저 놓는다.
- '~했다는데', '~했더니', '알고 보니'처럼 썰을 이어가는 말투를 자유롭게 쓴다.
- 관계 갈등이나 반전은 흥미롭게 각색해도 되지만 제품 정체·작동 방식·핵심 효능은 바꾸지 않는다.
- 마지막 재후킹에서 공개할 최강 장점은 subline에 미리 쓰지 않는다.
- text는 두 줄, 각 줄 {linelen}자 이내, 전체 {maxlen}자 이내다.
- subline은 {supportlen}자 이내, upload_title은 50자 이내다.
- 이모지·해시태그·따옴표를 쓰지 않는다.

[대본]
{script}
"""

_DEMO_DIRECT_PROMPT = """너는 제품을 직접 보여주는 쇼츠의 **시연형 제목 세트**를 쓴다.

아래 대본에서 서로 다른 후보 4개를 써라. 각 후보는 반드시 한 세트다.
- upload_title: 업로드용 제목. 제품·행동·효과가 한눈에 이해되게 쓴다.
- text: 영상 상단 큰 제목. 정확히 두 줄이며 사용 행동과 결과를 바로 말한다.
- subline: 큰 제목 아래 보조문구. 사용법·비교·핵심 기능 중 하나를 짧게 받친다.
- why: 어떤 시연 장치인지 한 줄로 설명한다.

전개 규칙:
- 제품 정체를 숨기지 말고 화면에서 보이는 행동과 효익을 먼저 설명한다.
- 사용 전후, 시간 절약, 번거로움 해결처럼 대본에서 확인되는 변화에 집중한다.
- 대본에 없는 가족 갈등·천재 개발자·해외 품절 같은 서사를 억지로 만들지 않는다.
- 제품 정체·작동 방식·핵심 효능은 대본과 다르게 바꾸지 않는다.
- text는 두 줄, 각 줄 {linelen}자 이내, 전체 {maxlen}자 이내다.
- subline은 {supportlen}자 이내, upload_title은 50자 이내다.
- 마침표·이모지·해시태그·따옴표를 쓰지 않는다.

[대본]
{script}
"""

_FAMILY_PROMPTS = {
    "youtube_reveal": _YOUTUBE_REVEAL_PROMPT,
    "instagram_story": _INSTAGRAM_STORY_PROMPT,
    "demo_direct": _DEMO_DIRECT_PROMPT,
}


def normalize_family(value):
    """외부 입력을 아는 문구 계열 하나로 정규화한다."""
    return value if value in _FAMILIES else _DEFAULT_FAMILY


def two_lines(text):
    """무슨 일이 있어도 **두 줄**로 만든다.

    ★프롬프트만 믿으면 안 된다 — AI가 한 줄로 뱉는 날이 반드시 온다. 그러면 화면에서
      제멋대로 4줄로 쪼개져(실측 '똥손도 샵/퀄리티 내는/다이소의/의외의 정체') 썸네일이 아니라
      문단이 된다. 그래서 받는 쪽에서 어절 경계로 접어 고정한다.
    """
    t = " ".join((text or "").split("\n"))
    words = t.split()
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    # 두 줄 길이가 가장 비슷해지는 어절 경계에서 자른다(한쪽만 길면 썸네일이 안 예쁘다)
    total = len(t)
    best, best_gap = 1, None
    for i in range(1, len(words)):
        left = len(" ".join(words[:i]))
        gap = abs(left - (total - left))
        if best_gap is None or gap < best_gap:
            best, best_gap = i, gap
    return " ".join(words[:best]) + "\n" + " ".join(words[best:])


def suggest(script, want=_WANT, family=_DEFAULT_FAMILY):
    """대본 → [{label, text}] (최대 want개). 실패·무키·빈 대본이면 **빈 리스트**."""
    s = (script or "").strip()
    if not s:
        return []                      # 재료가 없으면 부르지 않는다(빈 재료로 지어낸다)
    family = normalize_family(family)
    paired = family in _PAIRED_FAMILIES
    maxlen = EVEN_SHOPPING.hook_total_max if paired else _MAX_LEN
    # 두 줄 모두 둘째 줄 한도(10자)로 받는다 — 모델이 어느 줄에 긴 말을 넣을지 몰라 좁은 쪽에 맞춘다.
    linelen = EVEN_SHOPPING.hook2_line_max if paired else _LINE_LEN
    prompt = _FAMILY_PROMPTS.get(family, _PROMPT)
    def clean(data):
        copies = data.get("copies") if isinstance(data, dict) else None
        copies = copies if isinstance(copies, list) else []
        out, seen = [], set()
        for c in copies:
            if not isinstance(c, dict):
                continue
            text = c.get("text")
            text = text.strip() if isinstance(text, str) else ""
            if not text or len(text) > maxlen:
                continue
            # ★접은 **뒤에** 중복을 본다. 접기 전 문자열로 검사하고 접은 걸 저장하면
            #   같은 문구가 두 번 통과한다(실측: 테스트 test_dedupes_identical_text가 잡음).
            text = two_lines(text)     # 두 줄 고정은 여기 한 곳(화면에서 또 접지 않는다)
            if paired and any(len(line) > linelen for line in text.split("\n")):
                continue              # 실제 틀에서 좌우가 잘리는 문구는 후보로 내지 않는다
            if text in seen:
                continue
            label = c.get("label")
            label = label.strip() if isinstance(label, str) else ""
            why = c.get("why")
            why = why.strip() if isinstance(why, str) else ""
            seen.add(text)
            item = {"label": label or "제안", "text": text, "why": why[:_WHY_LEN]}
            if paired:
                subline = c.get("subline")
                upload_title = c.get("upload_title")
                if isinstance(subline, str) and subline.strip():
                    clean_subline = " ".join(subline.split())
                    if _support_max() == _LEGACY_SUBLINE_LEN:
                        item["subline"] = clean_subline[:_LEGACY_SUBLINE_LEN]   # 고객: 종전 32자 자르기
                    elif len(clean_subline) > _support_max():
                        continue                                              # 카나리: 22자 계약, 초과 후보 제외
                    else:
                        item["subline"] = clean_subline
                if isinstance(upload_title, str) and upload_title.strip():
                    item["upload_title"] = upload_title.strip()[:50]
            out.append(item)
            if len(out) >= want:
                break
        return out

    data = _call_json(prompt.format(script=s[:4000], maxlen=maxlen,
                                    linelen=linelen, supportlen=_support_max(),
                                    whylen=_WHY_LEN), _SCHEMA) or {}
    out = clean(data)
    # 실측: 모델이 "11자 이내"를 보고도 12~15자로 네 후보를 전부 써서 결과가 0개가 됐다.
    # 안전폭을 풀지 않고, 받은 세트의 뜻은 유지한 채 길이만 한 번 압축한다.
    raw = data.get("copies") if isinstance(data, dict) else None
    if paired and not out and isinstance(raw, list) and raw:
        retry_prompt = f"""다음 제목 세트는 화면 폭 규칙을 어겼다.
각 후보의 text만 정확히 두 줄로 다시 압축하라. 각 줄은 공백 포함 {linelen}자 이내,
전체는 줄바꿈 포함 {maxlen}자 이내다. subline은 {_support_max()}자 이내로 줄이고
upload_title·why의 의미는 유지하라.
JSON 스키마대로 copies를 반환하라.

[원래 후보]
{json.dumps(raw, ensure_ascii=False)}
"""
        out = clean(_call_json(retry_prompt, _SCHEMA) or {})
    return out
