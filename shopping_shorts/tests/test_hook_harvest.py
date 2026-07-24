"""훅 자동수확(P2) — 우승작 캡션/제목 첫 줄에서 훅 후보를 뽑아 hook 버킷 pending으로.
대본 전체가 없어도 훅 풀을 키운다('8개뿐' 근본 해소). 사람 승인 게이트가 품질 필터.
+ 훅 taxonomy: 타깃콜아웃('자~ OO하시는 분들')·충격·발견·극찬·경고·질문 유형 태깅.
"""
from shopping_shorts import hook_harvest as HH
from shopping_shorts.store import Store


# ---- 캡션 → 훅 후보 정제 ----

def test_clean_takes_first_line_drops_hashtags():
    cap = "이거 진짜 사길 잘했어요\n#다이소 #꿀템 #생활용품"
    assert HH.clean_hook_candidate(cap) == "이거 진짜 사길 잘했어요"


def test_clean_stops_at_inline_hashtag():
    assert HH.clean_hook_candidate("와 이거 대박이에요 #꿀템 #추천") == "와 이거 대박이에요"


def test_clean_rejects_too_short_or_no_korean():
    assert HH.clean_hook_candidate("#OOTD #daily") == ""
    assert HH.clean_hook_candidate("hi") == ""
    assert HH.clean_hook_candidate("") == ""


def test_clean_rejects_too_long():
    assert HH.clean_hook_candidate("가" * 60) == ""


def test_clean_strips_leading_emoji_and_space():
    assert HH.clean_hook_candidate("🔥🔥 이거 왜 이제 알았지") == "이거 왜 이제 알았지"


# ---- 훅 taxonomy ----

def test_classify_target_callout():
    assert HH.classify_hook("자~ 다이소 자주 쓰시는 분들 주목하세요") == "target_callout"
    assert HH.classify_hook("주부님들 이것만은 꼭 보세요") == "target_callout"


def test_classify_shock_discovery_warning_question():
    assert HH.classify_hook("와 이거 진짜 대박인데요") == "shock"
    assert HH.classify_hook("이걸 왜 이제 알았지") == "discovery"   # 헌장상 '뒤늦은 발견'
    assert HH.classify_hook("이거 저만 몰랐나요?") == "discovery"   # '몰랐'=발견 우선(헌장 매핑)
    assert HH.classify_hook("이거 절대 하지 마세요") == "warning"
    assert HH.classify_hook("이거 진짜 괜찮을까요?") == "question"  # 키워드 없고 물음 → 질문형


def test_classify_unknown_returns_none():
    assert HH.classify_hook("오늘 장 보러 갔어요") is None


# ---- 크롤 우승작에서 수확 ----

def _seed_last_run(store, platform, items):
    import json
    store.set_setting(f"last_run::{platform}",
                      json.dumps({"items": items, "collected_at": "2026-07-22"}))


def test_harvest_adds_pending_hooks_with_type(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    _seed_last_run(s, "instagram", [
        {"grade": "S", "shortcode": "a", "caption": "자~ 다이소 쓰시는 분들 주목하세요\n#다이소"},
        {"grade": "A", "shortcode": "b", "caption": "와 이거 진짜 대박인데요 #꿀템"},
        {"grade": "B", "shortcode": "c", "caption": "이건 등급 낮아 제외되는 훅"},
    ])
    n = HH.harvest_hooks_from_crawl(s, platforms=("instagram",))
    assert n == 2
    hooks = [h["text"] for h in s.list_pattern_items(bucket="hook")]
    assert "자~ 다이소 쓰시는 분들 주목하세요" in hooks
    assert "와 이거 진짜 대박인데요" in hooks
    assert "이건 등급 낮아 제외되는 훅" not in hooks   # 등급 B 제외
    # taxonomy 태그가 실렸는지
    callout = next(h for h in s.list_pattern_items(bucket="hook")
                   if h["text"].startswith("자~"))
    assert callout["tags"]["hook_type"] == "target_callout"
    # pending 상태(사람 승인 대기)
    assert callout["status"] == "pending"


def test_harvest_dedups_and_caps(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    _seed_last_run(s, "instagram", [
        {"grade": "S", "shortcode": "a", "caption": "와 이거 진짜 대박인데요"},
        {"grade": "S", "shortcode": "b", "caption": "와 이거 진짜 대박인데요"},  # 중복
    ])
    n = HH.harvest_hooks_from_crawl(s, platforms=("instagram",))
    hooks = [h for h in s.list_pattern_items(bucket="hook") if h["text"] == "와 이거 진짜 대박인데요"]
    assert len(hooks) == 1   # dedup(같은 canonical 1행)


def test_harvest_empty_platform_is_noop(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert HH.harvest_hooks_from_crawl(s, platforms=("instagram",)) == 0
