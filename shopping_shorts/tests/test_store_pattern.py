"""부품은행 Phase0 T1 — pattern_source/pattern_item/spine 스키마·메서드(TDD).

핵심은 add_pattern_item의 dedup: 같은 (bucket, canonical)이면 새 행을 만들지 않고
freq+1 & source_ids append(중복 없이). "한스푼이 가루↔액체로 섞이는" 사고를
막던 다축 설계의 부품 버전 — 같은 문구는 한 행에 빈도로 쌓인다.
"""
import pytest
from shopping_shorts.store import PATTERN_BUCKETS, Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_add_source_returns_id(store):
    sid = store.add_pattern_source("manual", "http://x", "본문", product_category="홈템",
                                   category_source="user", perf={"views": 100},
                                   structure={"a": 1})
    assert isinstance(sid, int) and sid > 0


def test_add_item_and_list_defaults(store):
    iid = store.add_pattern_item("hook", "이거 절대 하지 마세요")
    assert isinstance(iid, int)
    items = store.list_pattern_items(bucket="hook")
    assert len(items) == 1
    it = items[0]
    assert it["id"] == iid
    assert it["text"] == "이거 절대 하지 마세요"
    assert it["bucket"] == "hook"
    assert it["status"] == "pending"
    assert it["freq"] == 1
    assert it["is_negative"] == 0
    assert it["slot_role"] is None


def test_dedup_same_bucket_canonical(store):
    """공백만 다른 문구 → 같은 canonical → 한 행, freq=2, source 둘 다."""
    s1 = store.add_pattern_source("manual", "", "t1")
    s2 = store.add_pattern_source("manual", "", "t2")
    a = store.add_pattern_item("hook", "알고보니  대박", source_id=s1)
    b = store.add_pattern_item("hook", "알고보니 대박", source_id=s2)
    assert a == b
    items = store.list_pattern_items(bucket="hook")
    assert len(items) == 1
    assert items[0]["freq"] == 2
    assert set(items[0]["source_ids"]) == {s1, s2}


def test_dedup_no_duplicate_source_id(store):
    """같은 source로 두 번 → freq는 오르되 source_ids엔 한 번만."""
    s1 = store.add_pattern_source("manual", "", "t1")
    store.add_pattern_item("hook", "같은문구", source_id=s1)
    store.add_pattern_item("hook", "같은문구", source_id=s1)
    it = store.list_pattern_items(bucket="hook")[0]
    assert it["freq"] == 2
    assert it["source_ids"] == [s1]


def test_different_bucket_same_text_not_deduped(store):
    store.add_pattern_item("hook", "좋아요")
    store.add_pattern_item("cta", "좋아요")
    assert len(store.list_pattern_items(bucket="hook")) == 1
    assert len(store.list_pattern_items(bucket="cta")) == 1


def test_status_change_and_filter(store):
    iid = store.add_pattern_item("cta", "댓글 달아주세요")
    store.set_pattern_item_status(iid, "approved")
    assert [x["id"] for x in store.list_pattern_items(status="approved")] == [iid]
    assert store.list_pattern_items(status="pending") == []


def test_edit_item(store):
    iid = store.add_pattern_item("adverb", "진짜")
    store.edit_pattern_item(iid, text="완전", tags=["강조"], note="메모")
    it = store.list_pattern_items(bucket="adverb")[0]
    assert it["text"] == "완전"
    assert it["tags"] == ["강조"]
    assert it["note"] == "메모"


def test_list_order_by_freq(store):
    store.add_pattern_item("price", "A")
    store.add_pattern_item("price", "B")
    store.add_pattern_item("price", "B")  # dedup → freq 2
    rows = store.list_pattern_items(bucket="price", order_by="freq")
    assert rows[0]["text"] == "B"


def test_negative_filter(store):
    store.add_pattern_item("hook", "정상")
    store.add_pattern_item("hook", "반려문", is_negative=1)
    assert len(store.list_pattern_items(bucket="hook", is_negative=0)) == 1
    negs = store.list_pattern_items(bucket="hook", is_negative=1)
    assert len(negs) == 1 and negs[0]["is_negative"] == 1


def test_spine_crud(store):
    sp = store.add_spine("이모복수극", situation_type="갈등형",
                         character_roles=["나", "이모"],
                         beat_chain=["훅", "전개", "반전"],
                         emotion_arc="분노→통쾌", appeal="공감",
                         fit_categories=["홈템"])
    assert isinstance(sp, int)
    spines = store.list_spines()
    assert spines[0]["name"] == "이모복수극"
    assert spines[0]["beat_chain"] == ["훅", "전개", "반전"]
    assert spines[0]["character_roles"] == ["나", "이모"]
    assert spines[0]["fit_categories"] == ["홈템"]
    assert spines[0]["status"] == "pending"
    store.set_spine_status(sp, "approved")
    assert [s["id"] for s in store.list_spines(status="approved")] == [sp]
    assert store.list_spines(status="pending") == []


def test_bucket_counts(store):
    store.add_pattern_item("hook", "h1")
    h2 = store.add_pattern_item("hook", "h2")
    store.set_pattern_item_status(h2, "approved")
    store.add_pattern_item("hook", "neg", is_negative=1)  # 네거티브는 카운트 제외
    counts = store.pattern_bucket_counts()
    assert set(counts.keys()) == set(PATTERN_BUCKETS)
    assert counts["hook"] == {"pending": 1, "approved": 1, "rejected": 0}
    assert counts["cta"] == {"pending": 0, "approved": 0, "rejected": 0}
