"""카톡 답변봇 — 순수 판정 로직(DB·HTTP를 모른다).

★왜 따로 두나: 이 파일은 DB도 네트워크도 안 건드려서 **테스트가 DB 없이 돈다**.
  challenge.py가 같은 이유로 이 구조다.
"""
import re

#: 카톡 말풍선에서 안 잘리는 길이. 넘으면 우리가 먼저 자른다.
MAX_REPLY = 900

#: 호출어 — "!질문 ..." 또는 "!..." 둘 다 받는다(외우기 쉬운 쪽이 이긴다).
#: ★"질문" 뒤에 공백이 없으면(예: "!질문답") 키워드로 안 먹고 그대로 질문 취급한다
#: — 그래서 키워드는 "뒤에 공백 또는 끝"일 때만 벗겨낸다.
_CMD = re.compile(r"^\s*!\s*(?:질문(?:\s+|$))?(.*)$", re.S)

#: 돈·계정 관련 — AI를 아예 안 거치고 사람에게 넘긴다(잘못 답하면 분쟁).
_SENSITIVE = ("환불", "결제", "계좌", "입금", "카드", "청구", "요금제", "해지", "탈퇴")


def parse_command(text):
    """'!질문 ...' → 질문 문자열. 호출이 아니면 None."""
    m = _CMD.match(text or "")
    if not m:
        return None
    q = m.group(1).strip()
    return q or None


def is_sensitive(question):
    """돈·계정 질문인가 — True면 AI를 안 부르고 사람 연결로 간다."""
    q = question or ""
    return any(w in q for w in _SENSITIVE)


def trim(text):
    """카톡 길이에 맞춘다. 넘치면 잘라내고 말줄임표."""
    t = (text or "").strip()
    if len(t) <= MAX_REPLY:
        return t
    return t[:MAX_REPLY - 1].rstrip() + "…"
