from pipeline.atoms.calendar_ingest import (
    event_to_atom, _confidence, _entity_scope, _map_kind,
)


def test_confidence_tiers():
    assert _confidence(True, 1, True) == 1        # 확정
    assert _confidence(False, 3, True) == 2       # 여러 소스
    assert _confidence(False, 1, True) == 3        # 단일 소스
    assert _confidence(False, 1, False) == 4       # 날짜 애매


def test_entity_scope():
    assert _entity_scope("삼성전자", "실적발표") == "domestic"
    assert _entity_scope("마이크론", "실적발표") == "foreign"
    assert _entity_scope(None, "금통위") == "policy"


def test_map_kind():
    assert _map_kind("실적발표") == "실적발표"
    assert _map_kind("금통위") == "정책"
    assert _map_kind("기타") == "트리거"


def test_event_to_atom_domestic_stock():
    ev = {"date": "2026-07-08", "company": "삼성전자", "event": "2Q 잠정실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "가이던스 주목",
          "confirmed": True}
    a = event_to_atom(ev, sector="반도체", gen_date="2026-07-04")
    assert a["event_type"] == "event"
    assert a["signal"] == "catalyst"
    assert a["validity_type"] == "date"
    assert a["event_date"] == "2026-07-08"
    assert a["validity_until"] == "2026-07-08"
    assert a["sector"] == "반도체"
    assert a["asset"] == "삼성전자"
    assert a["asset_level"] == "stock"
    sf = a["structured_fields"]
    assert sf["event_kind"] == "실적발표"
    assert sf["entity_scope"] == "domestic"
    assert sf["event_form"] == "point"
    assert sf["affected_stocks"] == ["삼성전자"]
    assert sf["confidence"] == 1
    assert sf["confirmed"] is True


def test_event_to_atom_id_is_deterministic():
    ev = {"date": "2026-07-08", "company": "삼성전자", "event": "2Q 잠정실적",
          "type": "실적발표", "importance": "[HIGH]", "desc": "", "confirmed": True}
    a1 = event_to_atom(ev, "반도체", "2026-07-04")
    a2 = event_to_atom(ev, "반도체", "2026-07-04")
    assert a1["id"] == a2["id"]
