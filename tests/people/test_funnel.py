from pipeline.people.funnel import select


def _data():
    return {
        "date": "2026-07-02",
        "stocks": {
            # 빈집(pct 낮음) + 컨센 상향 → 선정
            "A": {"name": "빈집상향", "osc": {"pct": 10.0, "trend": "빈집"},
                  "tp": {"dir": "상향", "up_count": 5, "down_count": 0}},
            # 빈집이지만 컨센 하향 → 탈락
            "B": {"name": "빈집하향", "osc": {"pct": 12.0, "trend": "빈집"},
                  "tp": {"dir": "하향", "up_count": 0, "down_count": 3}},
            # 컨센 상향이지만 빈집 아님(pct 높음) → 탈락
            "C": {"name": "수급유입", "osc": {"pct": 80.0, "trend": "유입"},
                  "tp": {"dir": "상향", "up_count": 4, "down_count": 0}},
            # osc 없음 → 탈락
            "D": {"name": "데이터없음", "tp": {"dir": "상향", "up_count": 2}},
        },
    }


def test_funnel_stage_counts():
    r = select(_data())
    counts = {f["step"].split()[0]: f["count"] for f in r["funnel"]}
    assert r["funnel"][0]["count"] == 4      # 전체
    assert r["funnel"][1]["count"] == 2      # 빈집(A,B; C는 pct 높음, D는 osc 없음)
    assert r["funnel"][2]["count"] == 1      # 컨센상향(A만; B는 하향)


def test_funnel_selects_only_vacuum_and_up():
    r = select(_data())
    names = [c["name"] for c in r["candidates"]]
    assert names == ["빈집상향"]


def test_funnel_candidate_has_reason():
    r = select(_data())
    c = r["candidates"][0]
    assert c["vacuum_pct"] == 10.0
    assert c["tp_up"] == 5
    assert "수급빈집" in c["reason"] and "컨센상향" in c["reason"]


def test_threshold_override_widens():
    # 빈집 임계값을 90으로 올리면 C(pct 80)도 빈집에 포함
    r = select(_data(), th={"vacuum_pct_max": 90.0})
    assert r["funnel"][1]["count"] == 3      # A,B,C
    names = [c["name"] for c in r["candidates"]]
    assert "수급유입" in names               # C도 컨센상향이라 선정
