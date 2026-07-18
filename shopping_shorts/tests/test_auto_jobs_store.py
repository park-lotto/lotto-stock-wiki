"""러너 상태 저장소 — auto_jobs(스펙 §7, 트랙4). 상태·원가·재개 스냅샷을 영속."""
import pytest
from shopping_shorts.store import LEGACY_CUSTOMER_ID, Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_create_defaults(store):
    jid = store.create_auto_job("J1")
    got = store.get_auto_job("J1")
    assert jid == "J1"
    assert got["status"] == "running"
    assert got["current_stage"] is None
    assert got["cost_krw"] == 0
    assert got["mode"] == "C"
    assert got["stage_results"] == {}


def test_partial_update_preserves(store):
    store.create_auto_job("J1")
    store.update_auto_job("J1", current_stage="S1", cost_krw=120.0)
    store.update_auto_job("J1", status="waiting_human")   # cost_krw 재전송 안 함
    got = store.get_auto_job("J1")
    assert got["status"] == "waiting_human"
    assert got["cost_krw"] == 120.0          # 보존
    assert got["current_stage"] == "S1"      # 보존


def test_stage_results_roundtrip(store):
    store.create_auto_job("J1")
    store.update_auto_job("J1", stage_results={"S1": {"output_ref": "abc", "score": 0.8}})
    assert store.get_auto_job("J1")["stage_results"]["S1"]["output_ref"] == "abc"


def test_mix_job_bridge_and_unsure_reason(store):
    store.create_auto_job("J1")
    store.update_auto_job("J1", mix_job_id="mix-9", unsure_reason="cost_cap")
    got = store.get_auto_job("J1")
    assert got["mix_job_id"] == "mix-9" and got["unsure_reason"] == "cost_cap"


def test_unknown_field_ignored_not_crash(store):
    store.create_auto_job("J1")
    store.update_auto_job("J1", bogus="x", status="done")   # 화이트리스트 밖은 무시
    assert store.get_auto_job("J1")["status"] == "done"


def test_list_recent_first_and_isolation(store):
    store.create_auto_job("J1", customer_id=LEGACY_CUSTOMER_ID)
    store.create_auto_job("J2", customer_id=7)
    store.create_auto_job("J3", customer_id=LEGACY_CUSTOMER_ID)
    rows = store.list_auto_jobs(customer_id=LEGACY_CUSTOMER_ID)
    assert [r["id"] for r in rows] == ["J3", "J1"]


def test_get_missing_none(store):
    assert store.get_auto_job("없음") is None


def test_migration_reopen(tmp_path):
    p = tmp_path / "old.db"
    Store(p)
    s2 = Store(p)
    s2.create_auto_job("J1")
    assert s2.get_auto_job("J1")["status"] == "running"
