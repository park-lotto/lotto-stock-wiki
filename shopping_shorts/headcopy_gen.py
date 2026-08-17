"""확정 대본 → 헤드카피(고정카피) 후보 4개.

★생성 배관을 새로 만들지 않는다 — script_generate._call_json을 그대로 쓴다(키풀
로테이션·소진키 마킹·fail-open이 이미 검증된 코드다, 0순위-B).

⚠️ _call_json은 실패해도 {}를 돌려준다(fail-open). 그래서 여기서 **빈 리스트**로
정규화하고, "못 뽑았다"의 표시는 호출부(화면)가 한다 — 조용히 빈 카드를 띄우면
사장님이 고장인지 준비중인지 구분 못 한다.
"""
from shopping_shorts.script_generate import _call_json

_MAX_LEN = 40          # 헤드카피는 화면에 크게 박히는 한 줄 — 길면 줄이 무너진다
_WANT = 4

_SCHEMA = {
    "type": "object",
    "properties": {
        "copies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "text": {"type": "string"}},
                "required": ["label", "text"],
            },
        }
    },
    "required": ["copies"],
}

_PROMPT = """너는 쇼츠 영상의 **헤드카피**(영상 위에 크게 박히는 한 줄)를 쓴다.

아래 대본을 읽고 서로 **결이 다른** 후보 4개를 써라.
- 짧은 훅형: 궁금하게 만드는 짧은 한 방
- 숫자형: 숫자를 넣어 구체적으로
- 반전형: 예상과 다른 사실
- 질문형: 보는 사람에게 묻는다

규칙:
- 각 문구는 **{maxlen}자 이내**, 한 줄. 마침표로 끝내지 마라.
- 대본에 **없는 사실을 지어내지 마라**(가격·수치·효능을 새로 만들지 않는다).
- 이모지·해시태그·따옴표를 넣지 마라.

[대본]
{script}
"""


def suggest(script, want=_WANT):
    """대본 → [{label, text}] (최대 want개). 실패·무키·빈 대본이면 **빈 리스트**."""
    s = (script or "").strip()
    if not s:
        return []                      # 재료가 없으면 부르지 않는다(빈 재료로 지어낸다)
    data = _call_json(_PROMPT.format(script=s[:4000], maxlen=_MAX_LEN), _SCHEMA) or {}
    copies = data.get("copies") if isinstance(data, dict) else None
    if not isinstance(copies, list):
        copies = []
    out, seen = [], set()
    for c in copies:
        if not isinstance(c, dict):
            continue
        text = c.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if not text or len(text) > _MAX_LEN or text in seen:
            continue
        label = c.get("label")
        label = label.strip() if isinstance(label, str) else ""
        seen.add(text)
        out.append({"label": label or "제안", "text": text})
        if len(out) >= want:
            break
    return out
