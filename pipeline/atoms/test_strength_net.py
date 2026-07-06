import pipeline.atoms.strength_net as sn

def test_trust_tier_disclosure_is_green():
    assert sn.trust_tier({"source_type": "공시", "source_trust": "A"}) == "🟢"

def test_trust_tier_news_is_green():
    assert sn.trust_tier({"source_type": "news", "source_trust": "B"}) == "🟢"

def test_trust_tier_telegram_is_yellow():
    assert sn.trust_tier({"source_type": "telegram", "source_trust": "C"}) == "🟡"

def test_trust_tier_unknown_source_defaults_blue():
    assert sn.trust_tier({"source_type": "misc", "source_trust": "D"}) == "🔵"

def _fake_query(atoms_by_asset):
    def q(asset=None, days=None, active_only=True):
        return atoms_by_asset.get(asset, [])
    return q

def test_attribute_mover_finds_bullish_atom():
    mover = {"name": "가온칩스", "code": "399720", "sector": "반도체", "rate": 12.3}
    atoms = {"가온칩스": [
        {"id": "a1", "content": "296억 ASIC 계약 공시", "signal": "bullish",
         "source_type": "공시", "source_name": "DART", "source_trust": "A", "strength_score": 5},
    ]}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query(atoms))
    assert r["attributed"] is True
    assert r["status"] == "attributed"
    assert r["priority"] == 1
    assert r["trust"] == "🟢"
    assert r["atom_ids"] == ["a1"]
    assert r["flag"] is None

def test_attribute_mover_unattributed_when_no_atom():
    mover = {"name": "무이슈주", "code": "000000", "sector": "기타", "rate": 9.9}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query({}))
    assert r["attributed"] is False
    assert r["status"] == "unattributed"
    assert r["priority"] == 0
    assert r["issue"] is None
    assert r["flag"] == "⚠️ 원인 미상 강세 — 추적 요망"

def test_attribute_mover_ignores_neutral_atoms():
    mover = {"name": "보합주", "code": "111111", "sector": "기타", "rate": 8.0}
    atoms = {"보합주": [
        {"id": "n1", "content": "정기 IR", "signal": "neutral",
         "source_type": "news", "source_name": "X", "source_trust": "C", "strength_score": 1},
    ]}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query(atoms))
    assert r["attributed"] is False

def test_attribute_mover_picks_highest_strength_atom():
    mover = {"name": "다중주", "code": "222222", "sector": "기타", "rate": 7.0}
    atoms = {"다중주": [
        {"id": "w", "content": "약한 뉴스", "signal": "bullish",
         "source_type": "news", "source_name": "N", "source_trust": "C", "strength_score": 2},
        {"id": "s", "content": "강한 공시", "signal": "bullish",
         "source_type": "공시", "source_name": "DART", "source_trust": "A", "strength_score": 5},
    ]}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query(atoms))
    assert r["issue"] == "강한 공시"
    assert r["atom_ids"][0] == "s"

def test_scan_movers_never_drops_any_mover():
    movers = [
        {"name": "A", "code": "1", "sector": "s", "rate": 5.0},
        {"name": "B", "code": "2", "sector": "s", "rate": 9.0},
    ]
    results = sn.scan_movers(movers, days=3, query_fn=_fake_query({}))
    assert len(results) == len(movers)  # 침묵 금지: 하나도 누락 안 됨

def test_rank_results_unattributed_pinned_to_top():
    results = [
        {"name": "attr", "rate": 20.0, "priority": 1},
        {"name": "miss1", "rate": 6.0, "priority": 0},
        {"name": "miss2", "rate": 15.0, "priority": 0},
    ]
    ranked = sn.rank_results(results)
    assert [r["name"] for r in ranked] == ["miss2", "miss1", "attr"]
    # 미귀속이 등락률 낮아도 귀속보다 위. 미귀속 내부는 rate 내림차순.
