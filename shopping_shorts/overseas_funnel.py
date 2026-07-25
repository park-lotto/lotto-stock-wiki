"""해외HOT 무료 깔때기 — 형식 하드컷·관련성 게이트·'안터진' 조회수 상한. 순수함수라
overseas_hot_jobs에서 조합해 쓰고 단위테스트가 쉽다. (설계 §4 STAGE1·2, §5 상한)"""

BLOCK_WORDS = ("dance", "prank", "storytime", "story time", "lip sync", "lipsync",
               "giveaway", "sub for sub", "follow me", "asmr",
               # CN AI애니·창작툴 스팸(가전/도구에 #动画创作工具 픽사풍 카툰이 섞여옴, 실측 2026-07-26)
               "动画", "动漫", "创作工具")

DEFAULT_VIEW_CEILING = 3_000_000   # 이미 터진 것 제외(설계 §5). 국가감이라 튜닝대상.
SHORTFORM_MAX_SECS = 120           # 이보다 길면 롱폼으로 보고 컷(꿀템 숏폼만). 길이불명은 통과.


def passes_format(item):
    """재생 URL과 video_id가 있어야 통과."""
    return bool(item.get("url")) and bool(item.get("video_id"))


def passes_shortform(item, max_secs=SHORTFORM_MAX_SECS):
    """숏폼만 통과 — 길이(초)가 상한 초과면 컷. 길이불명(None)은 통과(과필터 방지)."""
    d = item.get("duration")
    if d is None:
        return True
    try:
        return int(d) <= max_secs
    except (TypeError, ValueError):
        return True


def passes_relevance(item, allow_words):
    """제목에 카테고리 허용어 ≥1 있고 차단어 없으면 통과. 허용어 대소문자 무시."""
    title = (item.get("title") or "")
    low = title.lower()
    if any(b in low for b in BLOCK_WORDS):
        return False
    if not allow_words:
        return True
    return any(w.lower() in low for w in allow_words)


def under_view_ceiling(item, ceiling=DEFAULT_VIEW_CEILING):
    """조회수가 상한 이하여야 '아직 안 터진'. 조회수 0/미제공(CN)은 통과(상한 판단 불가)."""
    v = int(item.get("views") or 0)
    return v == 0 or v <= ceiling
