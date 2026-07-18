"""픽로그 스토어 — 사장님이 고르고 버린 것을 append-only로 남긴다(스펙 §7, 트랙1).

목적: 트랙7 LLM 심사의 취향 예시 + B전환 승인률 지표의 원천. 여기선 append·조회·격리만 잠근다.
"""
import pytest

from shopping_shorts.store import LEGACY_CUSTOMER_ID, Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_append_returns_row_id_and_reads_back(store):
    eid = store.log_pick_event("S2", picked="초안2", candidates=["초안1", "초안2", "초안3"])
    assert isinstance(eid, int) and eid > 0
    rows = store.list_pick_events()
    assert len(rows) == 1
    r = rows[0]
    assert r["stage"] == "S2"
    assert r["picked"] == "초안2"
    assert r["candidates"] == ["초안1", "초안2", "초안3"]
    assert r["ts"]                       # 시각이 찍힌다


def test_dict_payloads_are_json_roundtripped(store):
    store.log_pick_event("S7", picked={"idx": 3}, rejected=[0, 1, 2, 4],
                         edit_diff={"before": "x", "after": "y"})
    r = store.list_pick_events()[0]
    # 서버가 저장할 때 JSON으로 감쌌어도, 조회 땐 원래 타입으로 돌아온다
    assert r["picked"] == {"idx": 3}
    assert r["rejected"] == [0, 1, 2, 4]
    assert r["edit_diff"] == {"before": "x", "after": "y"}


def test_plain_string_picked_stays_string(store):
    store.log_pick_event("S6", picked="임팩트옐로")
    assert store.list_pick_events()[0]["picked"] == "임팩트옐로"


def test_nullable_fields_default_none(store):
    store.log_pick_event("S3")
    r = store.list_pick_events()[0]
    assert r["job_id"] is None
    assert r["candidates"] is None
    assert r["picked"] is None
    assert r["rejected"] is None
    assert r["edit_diff"] is None


def test_recent_first(store):
    store.log_pick_event("S2", picked="a")
    store.log_pick_event("S2", picked="b")
    picks = [r["picked"] for r in store.list_pick_events()]
    assert picks == ["b", "a"]           # 최근이 먼저


def test_filter_by_stage_and_limit(store):
    for s in ("S2", "S3", "S2", "S7"):
        store.log_pick_event(s)
    assert len(store.list_pick_events(stage="S2")) == 2
    assert len(store.list_pick_events(limit=2)) == 2


def test_customer_isolation(store):
    store.log_pick_event("S2", picked="고객0", customer_id=LEGACY_CUSTOMER_ID)
    store.log_pick_event("S2", picked="고객7", customer_id=7)
    rows = store.list_pick_events(customer_id=LEGACY_CUSTOMER_ID)
    assert [r["picked"] for r in rows] == ["고객0"]


def test_job_id_bridge_is_optional(store):
    store.log_pick_event("S3", picked="mix", job_id="job-9")
    assert store.list_pick_events()[0]["job_id"] == "job-9"


def test_migration_on_reopened_db(tmp_path):
    """기존 DB에 새로 붙어도 생긴다 — 서버 DB는 이미 여러 테이블이 들어있다."""
    p = tmp_path / "old.db"
    Store(p)
    s2 = Store(p)                        # CREATE IF NOT EXISTS라 재오픈이 안 깨져야
    s2.log_pick_event("S8", picked="seo")
    assert s2.list_pick_events()[0]["picked"] == "seo"


def test_does_not_touch_mix_jobs(store):
    """픽로그는 파이프라인 테이블을 오염시키지 않는다."""
    store.log_pick_event("S3", picked="mix", job_id="job-1")
    with store._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM mix_jobs").fetchone()[0] == 0
