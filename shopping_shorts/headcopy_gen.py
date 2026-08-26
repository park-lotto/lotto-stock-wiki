"""확정 대본 → 헤드카피(고정카피) 후보 4개.

★생성 배관을 새로 만들지 않는다 — script_generate._call_json을 그대로 쓴다(키풀
로테이션·소진키 마킹·fail-open이 이미 검증된 코드다, 0순위-B).

⚠️ _call_json은 실패해도 {}를 돌려준다(fail-open). 그래서 여기서 **빈 리스트**로
정규화하고, "못 뽑았다"의 표시는 호출부(화면)가 한다 — 조용히 빈 카드를 띄우면
사장님이 고장인지 준비중인지 구분 못 한다.
"""
from shopping_shorts.script_generate import _call_json

_MAX_LEN = 26          # ★썸네일 문구는 두 줄이 전부다(2026-08-18). 40자였을 땐 화면에서 4줄로
_LINE_LEN = 13         #   무너져 문단처럼 보였다 — 두 줄 x 13자를 넘기지 않는다.
_WANT = 4
_WHY_LEN = 80          # ★이유문은 카드 밑에 한 줄로 깔린다(썸네일 제목 추천과 같은 모양).
                       #   길어지면 카드가 문단이 돼 고르기가 더 어려워진다.

_SCHEMA = {
    "type": "object",
    "properties": {
        "copies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "text": {"type": "string"},
                               "why": {"type": "string"}},
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


def suggest(script, want=_WANT):
    """대본 → [{label, text}] (최대 want개). 실패·무키·빈 대본이면 **빈 리스트**."""
    s = (script or "").strip()
    if not s:
        return []                      # 재료가 없으면 부르지 않는다(빈 재료로 지어낸다)
    data = _call_json(_PROMPT.format(script=s[:4000], maxlen=_MAX_LEN,
                                     linelen=_LINE_LEN, whylen=_WHY_LEN), _SCHEMA) or {}
    copies = data.get("copies") if isinstance(data, dict) else None
    if not isinstance(copies, list):
        copies = []
    out, seen = [], set()
    for c in copies:
        if not isinstance(c, dict):
            continue
        text = c.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if not text or len(text) > _MAX_LEN:
            continue
        # ★접은 **뒤에** 중복을 본다. 접기 전 문자열로 검사하고 접은 걸 저장하면
        #   같은 문구가 두 번 통과한다(실측: 테스트 test_dedupes_identical_text가 잡음).
        text = two_lines(text)         # 두 줄 고정은 여기 한 곳(화면에서 또 접지 않는다)
        if text in seen:
            continue
        label = c.get("label")
        label = label.strip() if isinstance(label, str) else ""
        # ★why가 없어도 죽지 않는다 — 옛 캐시·구버전 응답이 그대로 올 수 있다.
        why = c.get("why")
        why = why.strip() if isinstance(why, str) else ""
        seen.add(text)
        out.append({"label": label or "제안", "text": text, "why": why[:_WHY_LEN]})
        if len(out) >= want:
            break
    return out
