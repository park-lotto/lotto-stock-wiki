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

def test_coverage_metrics_basic():
    results = [
        {"status": "attributed"}, {"status": "attributed"},
        {"status": "unattributed"},
    ]
    m = sn.coverage_metrics(results, input_count=3)
    assert m["total"] == 3
    assert m["attributed"] == 2
    assert m["unattributed"] == 1
    assert abs(m["coverage_rate"] - (2/3)) < 1e-9
    assert m["silent_miss"] == 0  # 입력=출력이면 침묵 누락 0

def test_coverage_metrics_detects_silent_miss():
    results = [{"status": "attributed"}]  # 입력 2개인데 결과 1개 = 누락 발생
    m = sn.coverage_metrics(results, input_count=2)
    assert m["silent_miss"] == 1  # 규칙 위반 감지

# --- Task 5: movers_from_heatmap (실제 build_heatmap 중첩 형태) ---

def _heatmap(sectors):
    return {"sectors": sectors, "updated_at": "09:05:00", "source": "x"}

def test_movers_from_heatmap_filters_by_min_rate():
    hm = _heatmap([
        {"name": "반도체", "avg_rate": 2.0, "stocks": [
            {"name": "강세주", "code": "1", "change_rate": 8.0, "price": 1000},
            {"name": "약세주", "code": "2", "change_rate": -1.0, "price": 500},
            {"name": "미미주", "code": "3", "change_rate": 1.0, "price": 700},
        ]},
    ])
    movers = sn.movers_from_heatmap(hm, min_rate=3.0)
    assert [m["name"] for m in movers] == ["강세주"]
    assert movers[0]["rate"] == 8.0
    assert movers[0]["sector"] == "반도체"

def test_movers_from_heatmap_excludes_zero_price():
    hm = _heatmap([
        {"name": "2차전지", "avg_rate": 5.0, "stocks": [
            {"name": "데이터없음주", "code": "9", "change_rate": 9.0, "price": 0},
        ]},
    ])
    assert sn.movers_from_heatmap(hm, min_rate=3.0) == []  # price 0 = 강세로 안 침

def test_movers_from_heatmap_dedupes_across_tiles_keeping_highest():
    hm = _heatmap([
        {"name": "테마A", "avg_rate": 4.0, "stocks": [
            {"name": "중복주", "code": "7", "change_rate": 5.0, "price": 100}]},
        {"name": "테마B", "avg_rate": 6.0, "stocks": [
            {"name": "중복주", "code": "7", "change_rate": 12.0, "price": 100}]},
    ])
    movers = sn.movers_from_heatmap(hm, min_rate=3.0)
    assert len(movers) == 1
    assert movers[0]["rate"] == 12.0  # 최고 등락률 타일 채택

def test_movers_from_heatmap_sorted_desc():
    hm = _heatmap([
        {"name": "s", "avg_rate": 5.0, "stocks": [
            {"name": "A", "code": "1", "change_rate": 4.0, "price": 100},
            {"name": "B", "code": "2", "change_rate": 11.0, "price": 100}]},
    ])
    movers = sn.movers_from_heatmap(hm, min_rate=3.0)
    assert [m["name"] for m in movers] == ["B", "A"]

# --- Task 3 (Phase2): 그래프-홉 귀속 ---

def test_attribute_mover_graph_hop_via_sector():
    mover = {"name": "가온칩스", "code": "1", "sector": "반도체", "rate": 10.0}
    atoms = {"SK하이닉스": [{"id": "h1", "content": "HBM 수급 강세", "signal": "bullish",
             "source_type": "news", "source_name": "N", "source_trust": "B", "strength_score": 3}]}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query(atoms),
                           related_fn=lambda name: ["SK하이닉스"] if name == "가온칩스" else [])
    assert r["attributed"] is True
    assert r["via"] == "SK하이닉스"
    assert r["trust"] == "🔵"
    assert "SK하이닉스" in r["issue"]
    assert r["priority"] == 1

def test_attribute_mover_graph_hop_none_still_unattributed():
    mover = {"name": "외톨이주", "code": "9", "sector": "기타", "rate": 8.0}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query({}),
                           related_fn=lambda name: [])
    assert r["status"] == "unattributed"
    assert r["priority"] == 0

def test_direct_attribution_still_wins_over_graph():
    mover = {"name": "직접주", "code": "2", "sector": "반도체", "rate": 9.0}
    atoms = {"직접주": [{"id": "d1", "content": "자체 대형수주", "signal": "bullish",
             "source_type": "공시", "source_name": "DART", "source_trust": "A", "strength_score": 5}]}
    r = sn.attribute_mover(mover, days=3, query_fn=_fake_query(atoms),
                           related_fn=lambda name: ["SK하이닉스"])
    assert r["attributed"] is True
    assert r.get("via") is None
    assert r["trust"] == "🟢"
