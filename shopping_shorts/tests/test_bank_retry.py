"""부품은행 흡수 실패 재큐 + 지수 백오프 (2026-07-24).

503으로 놓친 상위영상이 다음 수집 때 상위권 밖으로 밀려도 유실되지 않게, url당 1행으로
재큐에 담아 백오프 시점에 재투입한다. fail_count 상한 초과 시 폐기(영구불량 방어)."""
import pytest

from shopping_shorts import pattern_bank
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


# ── 저장소 계층 ──
def test_upsert_then_due_respects_backoff(store):
    store.bank_retry_upsert("u1", '{"url":"u1","caption":"가나다"}', "collect", "503", now=1000.0)
    # 1차 실패 백오프 = 30분(1800s). 1000+1800=2800 이후에만 due.
    assert store.bank_retry_due(now=1000.0) == []                 # 아직 이르다
    due = store.bank_retry_due(now=2801.0)
    assert len(due) == 1 and due[0]["url"] == "u1" and due[0]["caption"] == "가나다"


def test_upsert_bumps_and_doubles_backoff(store):
    store.bank_retry_upsert("u1", '{"url":"u1"}', "collect", "e", now=0.0)     # fc1 → +1800
    store.bank_retry_upsert("u1", '{"url":"u1"}', "collect", "e", now=0.0)     # fc2 → +3600
    assert store.bank_retry_due(now=1801.0) == []                # fc2라 3600 뒤에만
    assert len(store.bank_retry_due(now=3601.0)) == 1


def test_dropped_after_max_fails(store):
    for _ in range(7):                                           # 상한 6 초과
        store.bank_retry_upsert("u1", '{"url":"u1"}', "collect", "e", now=0.0)
    assert store.bank_retry_due(now=10 ** 9) == []               # 폐기됨
    with store._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM bank_retry").fetchone()[0] == 0


def test_clear_removes(store):
    store.bank_retry_upsert("u1", '{"url":"u1"}', "collect", "e", now=0.0)
    store.bank_retry_clear("u1")
    assert store.bank_retry_due(now=10 ** 9) == []


# ── 흡수 루프 통합 ──
def _run(store, items, ingest_fn, now):
    return pattern_bank.ingest_collected(
        store, items, top_n=10, min_kr=1, ingest_fn=ingest_fn,
        call=None, perf_fn=lambda it: 1, now=now)


def test_failure_enqueues_and_success_clears(store):
    item = {"url": "vid1", "caption": "가나다라마", "score": 9}

    # 1) 빈 결과(503) → 재큐된다
    _run(store, [item], ingest_fn=lambda *a, **k: {}, now=1000.0)
    assert len(store.bank_retry_due(now=1_000_000.0)) == 1

    # 2) 백오프 시점에 자동 재투입 → 이번엔 성공 → 재큐에서 제거
    ok = lambda *a, **k: {"source_id": 7, "added": 1, "buckets": {"hook": ["훅"]}}
    rep = _run(store, [], ingest_fn=ok, now=1_000_000.0)   # 새 items 없어도 due가 처리됨
    assert rep["added_sources"] == 1                       # 재큐 항목이 실제로 흡수됨
    assert store.bank_retry_due(now=1_000_000_000.0) == [] # 성공 → 큐 비움


def test_exception_also_enqueues(store):
    item = {"url": "vid2", "caption": "가나다라마"}

    def boom(*a, **k):
        raise RuntimeError("upload 503")

    _run(store, [item], ingest_fn=boom, now=0.0)
    assert len(store.bank_retry_due(now=10 ** 9)) == 1


def test_no_url_item_not_enqueued(store):
    item = {"caption": "가나다라마"}                         # url 없음 → 재큐 대상 아님
    _run(store, [item], ingest_fn=lambda *a, **k: {}, now=0.0)
    assert store.bank_retry_due(now=10 ** 9) == []
