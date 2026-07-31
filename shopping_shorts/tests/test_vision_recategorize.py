"""비전태그 기반 재분류 — 2026-07-31 '카테고리가 뒤죽박죽' 제보의 처방.

뿌리: 캡션이 100% 비어(429 회피로 릴스 상세조회 off) 분류가 채널명만 보게 됐고,
채널명에 장르를 도배한 채널의 영상이 통째로 한 카테고리로 몰렸다.
"""
import pytest

from shopping_shorts import vision_tagging
from shopping_shorts.store import Store


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    Store(p)          # 스키마 생성
    return p


def _item(sc, name, category, thumb="http://x/t.jpg"):
    return {"shortcode": sc, "name": name, "category": category, "thumbnail": thumb, "caption": ""}


def test_channel_name_genre_spam_is_fixed_by_vision(db):
    """★제보 재현: '홈새댁홈 | 레시피•꿀팁' 채널의 살림템 영상이 레시피로 분류돼 있다.
    비전태그(화면에 실제로 보이는 것)를 넣으면 홈템으로 교정된다."""
    Store(db).save_vision_tags("A1", "수납 정리함", ["수납", "정리", "주방"])
    items = [_item("A1", "홈새댁홈 | 레시피•꿀팁", "레시피")]

    changed = vision_tagging.recategorize_by_vision(items, db)

    assert changed == 1
    assert items[0]["category"] == "홈템"       # 채널명(레시피) 아니라 화면(수납·정리)을 따른다


def test_cooking_video_on_home_channel_is_fixed_too(db):
    """반대 방향도 된다: 살림 채널이 올린 요리 영상 → 레시피."""
    Store(db).save_vision_tags("B2", "감자조림", ["요리", "레시피", "반찬"])
    items = [_item("B2", "일분살림 | 30대 엄마의 요리 & 살림꿀팁", "홈템")]

    assert vision_tagging.recategorize_by_vision(items, db) == 1
    assert items[0]["category"] == "레시피"


def test_no_vision_tag_leaves_category_untouched(db):
    """태그 없는 항목은 손대지 않는다 — 더 나빠지지 않는 게 원칙."""
    items = [_item("C3", "아무채널", "기타")]
    assert vision_tagging.recategorize_by_vision(items, db) == 0
    assert items[0]["category"] == "기타"


def test_empty_vision_text_leaves_category_untouched(db):
    """subject·keywords가 다 비면 분류 근거가 없으므로 그대로 둔다."""
    Store(db).save_vision_tags("D4", "", [])
    items = [_item("D4", "아무채널", "기타")]
    assert vision_tagging.recategorize_by_vision(items, db) == 0
    assert items[0]["category"] == "기타"


def test_same_result_reports_no_change(db):
    """이미 맞는 카테고리면 changed=0 — 불필요한 재저장을 막는다."""
    Store(db).save_vision_tags("E5", "감자조림", ["요리", "레시피"])
    items = [_item("E5", "까리레시피", "레시피")]
    assert vision_tagging.recategorize_by_vision(items, db) == 0


def test_vision_text_joins_subject_and_keywords():
    assert vision_tagging.vision_text({"subject": "감자칩", "keywords": ["감자", "간식"]}) \
        == "감자칩 감자 간식"
    assert vision_tagging.vision_text({"subject": "", "keywords": []}) == ""


def test_tag_new_items_skips_already_tagged(db, monkeypatch):
    """이미 태그가 있으면 Gemini를 다시 부르지 않는다(비용 가드)."""
    Store(db).save_vision_tags("F6", "이미있음", ["태그"])
    calls = []
    from shopping_shorts import video_analysis
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda u: calls.append(u) or b"img")
    monkeypatch.setattr(video_analysis, "subject_tags_vision",
                        lambda img, cap: {"subject": "새것", "keywords": ["ㅋ"]})

    tagged = vision_tagging.tag_new_items([_item("F6", "채널", "기타")], db)

    assert tagged == 0 and calls == []       # 호출 0건


def test_tag_new_items_respects_cap(db, monkeypatch):
    """1회 상한을 넘으면 초과분은 다음 수집으로 미룬다."""
    from shopping_shorts import video_analysis
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda u: b"img")
    monkeypatch.setattr(video_analysis, "subject_tags_vision",
                        lambda img, cap: {"subject": "x", "keywords": ["y"]})
    items = [_item(f"G{i}", "채널", "기타") for i in range(5)]

    assert vision_tagging.tag_new_items(items, db, cap=2) == 2


# ── 배선 자물쇠: 크론 스크립트가 실제로 후속을 부르는가 ──────────────────
# 함수만 테스트하면 '함수는 맞는데 아무도 안 부른다'(이번 사고의 정확한 형태)를 못 잡는다.
def test_cron_script_calls_tagging_and_recategorize(tmp_path, monkeypatch):
    import scripts.daily_instagram_collect as cron
    from shopping_shorts import vision_tagging as vt

    db = tmp_path / "c.db"
    Store(db)
    monkeypatch.setattr(cron, "DB_PATH", db)
    monkeypatch.setattr(cron.service, "collect", lambda platform=None: [_item("Z9", "채널", "기타")])
    monkeypatch.setattr(cron.Store(db).__class__, "heavy_job_active", lambda self: False)

    called = {}
    monkeypatch.setattr(vt, "tag_new_items", lambda items, p, **k: called.setdefault("tag", True) or 1)
    monkeypatch.setattr(vt, "recategorize_by_vision", lambda items, p: called.setdefault("recat", True) or 0)

    assert cron.main() == 0
    assert called.get("tag") and called.get("recat"), "크론이 후속(태깅·재분류)을 안 부른다"


# ── 채널 카테고리 지정(2026-07-31) — 폴백이지 덮어쓰기가 아니다 ───────────
def test_channel_pin_applies_when_no_vision_tag(db):
    """태그 없는 영상은 사장님이 못 박은 채널 카테고리를 따른다."""
    Store(db).set_channel_category("chan_a", "가전")
    items = [{"shortcode": "P1", "username": "chan_a", "name": "채널", "category": "기타"}]
    assert vision_tagging.apply_channel_category(items, db) == 1
    assert items[0]["category"] == "가전"


def test_vision_tag_beats_channel_pin(db):
    """★핵심 규칙: 화면분석이 있으면 채널 지정을 이긴다.
    채널 고정이 이기면 그 채널의 다른 장르 영상까지 몰려 애초 문제로 되돌아간다."""
    s = Store(db)
    s.set_channel_category("chan_a", "가전")
    s.save_vision_tags("P2", "감자조림", ["요리", "반찬"])
    items = [{"shortcode": "P2", "username": "chan_a", "name": "채널", "category": "레시피"}]
    assert vision_tagging.apply_channel_category(items, db) == 0   # 손 안 댐
    assert items[0]["category"] == "레시피"


def test_pin_unset_returns_to_auto(db):
    """지정 해제하면 폴백이 사라진다(자동판정으로 되돌아감)."""
    s = Store(db)
    s.set_channel_category("chan_a", "가전")
    s.set_channel_category("chan_a", "")
    items = [{"shortcode": "P3", "username": "chan_a", "name": "채널", "category": "기타"}]
    assert vision_tagging.apply_channel_category(items, db) == 0
    assert items[0]["category"] == "기타"


def test_pin_matches_username_case_and_at_insensitively(db):
    Store(db).set_channel_category("@ChanB", "뷰티")
    items = [{"shortcode": "P4", "username": "chanb", "name": "채널", "category": "기타"}]
    assert vision_tagging.apply_channel_category(items, db) == 1
    assert items[0]["category"] == "뷰티"
