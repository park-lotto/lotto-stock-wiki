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


def passes_relevance(item, allow_words=None):
    """차단어(잡영상·스팸·AI애니)가 제목에 있으면 컷. 그 외는 통과.

    ★주제 적합성은 '그 카테고리 키워드로 검색해 나온 결과'라는 사실이 이미 보장한다.
    허용어(완전구절) 재매칭을 요구했더니 제목이 "kitchen finds"·"kitchen upgrades"처럼
    구절과 안 맞는 멀쩡한 꿀템이 74% 버려졌다(실측 2026-07-26, 반응 24만짜리 포함).
    그래서 허용어 요구는 폐기하고 차단어만 건다. allow_words는 호환용(미사용)."""
    low = (item.get("title") or "").lower()
    return not any(b in low for b in BLOCK_WORDS)


def under_view_ceiling(item, ceiling=DEFAULT_VIEW_CEILING):
    """조회수가 상한 이하여야 '아직 안 터진'. 조회수 0/미제공(CN)은 통과(상한 판단 불가)."""
    v = int(item.get("views") or 0)
    return v == 0 or v <= ceiling


def passes_caption_clutter(item):
    """큰 자막/텍스트 오버레이가 썸네일 대부분을 가리면 컷(video_analysis.text_level_vision 판정).

    현재 해외HOT 파이프라인에서는 미사용(2026-07-29) — 실측(반응 1만+ 29건 중 자막없음
    0건)에서 heavy 대부분이 인기 영상이라 여기서 컷하면 손해였다. 판정(text_level)은
    계속 매기되, 거르는 건 화면 "자막 없는 것만" 토글로 옮겼다. 함수·테스트는 유지."""
    return item.get("text_level") != "heavy"


CAPTION_RANK = {"none": 0, "light": 1}


def caption_rank(item):
    """자막 적을수록 앞(0=none, 1=light, 2=heavy·미판정).

    정렬 1차키로는 미사용(2026-07-29 되돌림 — 실측에서 인기 영상을 밀어냈다).
    화면 필터·뱃지용으로만 쓴다. 미판정을 2로 두는 건 '모르는 것을 light보다
    앞세우지 않기' 위해서다."""
    return CAPTION_RANK.get(item.get("text_level"), 2)
