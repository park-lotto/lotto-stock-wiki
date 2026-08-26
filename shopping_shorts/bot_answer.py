"""카톡 답변봇 — 자료를 프롬프트로 만들어 모델에 한 번 묻는다.

★모델 교체 지점을 **이 파일 하나**로 묶는다(0순위-B). 나중에 클로드로 바꾸면
  `_call`만 갈아끼우면 되고 라우트·검색·저장소는 안 건드린다.
★제미니로 시작하는 이유는 품질이 아니라 **비용**이다 — 오픈채팅방은 누가 몇 번
  물을지 통제가 안 돼서, 유료 API를 열어두면 장난 100번이 그대로 과금된다.
"""
from shopping_shorts.script_generate import _call_json

_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
}

_PROMPT = """너는 '숏템메이커' 고객 문의에 답하는 상담원이다.

[반드시 지켜라]
- 아래 [자료]에 있는 내용만으로 답하라. **자료에 없는 것은 절대 지어내지 마라.**
- 자료로 답할 수 없으면 answer를 빈 문자열("")로 두어라.
- 카톡 말풍선이라 짧게, 2~4문장으로. 존댓말.
- 링크가 자료에 있으면 그대로 옮겨라(주소를 지어내지 마라).

[자료]
{material}

[질문]
{question}
"""


def _call(prompt):
    """모델 한 번. 실패·키소진은 {}로 온다(fail-open).

    ★교체 지점 — 클로드로 바꾸려면 이 함수만 고친다."""
    return _call_json(prompt, _SCHEMA)


def build_prompt(question, hits):
    material = "\n\n".join(
        "Q. %s\nA. %s" % (h.get("question", ""), h.get("answer", "")) for h in hits)
    return _PROMPT.format(material=material, question=question)


def answer(question, hits):
    """자료 기반 답변 문자열. **자료가 없거나 모델이 못 답하면 None**.

    None이면 호출부가 "확인해서 알려드릴게요"로 간다 — 지어내지 않는다.
    """
    if not hits:
        return None                       # ★자료 없이는 모델을 부르지도 않는다
    data = _call(build_prompt(question, hits)) or {}
    text = (data.get("answer") or "").strip()
    if not text:
        return None                       # 모델이 "못 답하겠다"고 한 경우도 여기
    # 근거 표시 — 틀렸을 때 어디가 틀렸는지 사장님이 바로 안다
    return "%s\n\n\U0001F4CE %s" % (text, hits[0].get("question", ""))
