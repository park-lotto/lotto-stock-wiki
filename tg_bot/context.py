"""고객 메시지에서 조사에 필요한 정보를 뽑는다.

★순수 함수만 둔다 — 네트워크·텔레그램을 모른다. 그래야 테스트가 빠르고 정확하다.
"""
import re

# 주소 안의 job / job_id 파라미터. 둘 다 실제로 쓰인다(produce.html은 job_id를 쓰고,
# 사람이 손으로 줄여 job=로 적는 경우도 있다).
_JOB = re.compile(r"[?&]job(?:_id)?=([A-Za-z0-9_-]+)")
_URL = re.compile(r"https?://[^\s<>\"]+")


def extract(text):
    """메시지 → {"job_id": str|None, "urls": [str], "text": str}"""
    s = (text or "").strip()
    m = _JOB.search(s)
    return {
        "job_id": m.group(1) if m else None,
        "urls": _URL.findall(s),
        "text": s,
    }
