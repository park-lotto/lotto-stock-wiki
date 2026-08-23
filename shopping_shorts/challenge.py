"""1기 챌린지 — 순수 판정 로직.

DB도 HTTP도 모른다. 여기 있는 함수는 값만 받아 값만 돌려준다.
그래야 규칙이 한 곳에만 존재하고(0순위-B), 테스트가 DB 없이 즉시 돈다.
"""
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def kst_day(dt=None):
    """UTC 시각 → 한국 날짜 문자열 'YYYY-MM-DD'.

    ★하루 2영상의 '하루'가 여기서 정해진다. 저장 시점에 한 번 불러
    컬럼에 넣고, 조회할 때 다시 계산하지 않는다 — 계산이 두 군데 있으면
    언젠가 어긋난다(0순위-B).
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%Y-%m-%d")


def in_period(day, start, end):
    """day가 챌린지 기간 안인가. 전부 'YYYY-MM-DD' 문자열(사전순=시간순).

    start/end가 비어 있으면 그쪽 끝은 열어둔다 — 사장님이 아직 기간을
    설정하지 않았다고 해서 멤버 제출이 막히면 안 된다.
    """
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True
