"""SerpApi 월한도 키 로테이션 공용 판정(2026-07-26).

무료 플랜은 계정당 월 100회뿐이라 한 키가 소진되면 렌즈검색이 429로 통째로
막힌다. config.SERPAPI_KEYS(_N 넘버링 풀)를 순서대로 시도하다가, 현재 키가
월 한도를 소진한 신호를 받으면 다음 키로 넘어간다 — 이 신호 판정을 여기서
한 곳에 둔다(lens_discover·product_identify가 공유). 실제 requests.get 호출은
각 모듈에 남긴다(테스트가 모듈별 requests를 패치하기 때문)."""


def is_exhausted(status_code, data):
    """이 키를 버리고 다음 키로 넘어가야 하는가.

    - 429: SerpApi가 월/분 한도 소진 시 주는 상태코드(다음 키 시도).
    - 401: 잘못된/비활성 키(다음 키에 기회를 준다).
    - 본문 error 문자열에 'run out of searches'가 있으면 소진(상태코드가 200이어도).
    그 외(정상 200, 또는 400 같은 요청오류)는 로테이션 대상이 아니다."""
    if status_code in (401, 429):
        return True
    err = (data.get("error", "") if isinstance(data, dict) else "") or ""
    err = err.lower()
    return "run out of searches" in err or "ran out of searches" in err
