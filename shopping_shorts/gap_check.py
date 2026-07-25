"""해외 발굴 항목의 국내 선점여부 뱃지 — 유튜브에서 제목을 검색해 결과에 한국어
제목의 재편집본이 이미 있으면 '이미유입', 없으면 '🔥선점가능', 검색 실패면 '미확인'.

필터가 아니라 참고 뱃지다(최종판단은 사람 — 설계 §5.5). 검색은 영어 원제목으로 하되
결과 제목에 한글이 섞였는지로 국내 유입을 추정한다(완벽하진 않음, 뱃지 용도라 충분).
YouTube Data API 무료쿼터(search.list=100유닛) 보호를 위해 호출부에서 배치당 상위 N개만
검사한다(여기선 단건만 판정)."""
import re
from shopping_shorts import youtube_search

_HANGUL = re.compile(r"[가-힣]")


def _has_korean(text):
    return bool(_HANGUL.search(text or ""))


def gap_badge(title, min_korean=1):
    """제목 → '🔥선점가능' | '이미유입' | '미확인'.

    유튜브 검색 결과 제목 중 한글 포함이 min_korean개 이상이면 이미유입으로 본다.
    빈 제목·검색 실패(쿼터 소진 등)는 '미확인'."""
    q = (title or "").strip()
    if not q:
        return "미확인"
    try:
        results = youtube_search.search(q, max_results=10)
    except Exception:
        return "미확인"
    korean = sum(1 for r in results if _has_korean(r.get("title")))
    return "이미유입" if korean >= min_korean else "🔥선점가능"
