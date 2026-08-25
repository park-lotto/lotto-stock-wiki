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


#: 한 번에 AI에게 먹이는 자료 개수. 자료가 1,000개로 늘어도 이 수는 안 변한다.
TOP_N = 5
#: 이 점수 미만이면 "근거 없음"으로 본다 → 호출부가 AI를 안 부른다.
MIN_SCORE = 2

_WORD = re.compile(r"[0-9A-Za-z가-힣]+")


def _words(text):
    """2글자 이상 낱말만. 1글자는 아무 데나 걸려 잡음이 된다."""
    return {w for w in _WORD.findall(text or "") if len(w) >= 2}


def _score(question_words, item):
    """겹치는 낱말 수. 질문·태그가 본문보다 무겁다(제목이 곧 주제다)."""
    q = _words(item.get("question")) | _words(item.get("tags"))
    a = _words(item.get("answer"))
    return len(question_words & q) * 2 + len(question_words & a)


def search(question, items, room):
    """질문에 맞는 자료 TOP_N개. 근거가 약하면 **빈 리스트**를 준다.

    ★빈 리스트가 이 설계의 핵심이다 — 호출부는 빈 손이면 AI를 아예 안 부르고
      "확인해서 알려드릴게요"로 간다. 자료 밖을 지어내는 걸 여기서 막는다.
    """
    qw = _words(question)
    if not qw:
        return []
    scored = []
    for it in items or []:
        # 방 전용 자료는 그 방에서만 보인다(체험단 자료가 문의방으로 새면 안 된다)
        r = it.get("room") or "공통"
        if r != "공통" and r != room:
            continue
        s = _score(qw, it)
        if s >= MIN_SCORE:
            # 그 방 전용 자료를 공통보다 앞세운다(체험단방에선 챌린지가 먼저)
            scored.append((s + (1 if r == room else 0), it))
    scored.sort(key=lambda x: -x[0])
    return [it for _, it in scored[:TOP_N]]
