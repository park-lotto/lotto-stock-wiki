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


def _c(r, kw):
    return next(f["count"] for f in r["funnel"] if kw in f["step"])


def test_funnel_stage_counts():
    r = select(_data(), th={"mode":"strict"}, rs={}, sortino={"names":[],"sectors":[]})
    assert _c(r, "전체") == 4
    assert _c(r, "빈집") == 2            # A,B (C pct↑, D osc없음)
    assert _c(r, "재료") == 3            # up>down: A,C,D (B는 하향)
    assert _c(r, "게이트") == 1          # strict=빈집 AND 컨센: A만


def test_funnel_selects_only_vacuum_and_up():
    r = select(_data(), th={"mode":"strict"}, rs={}, sortino={"names":[],"sectors":[]})
    names = [c["name"] for c in r["candidates"]]
    assert names == ["빈집상향"]


def test_funnel_candidate_has_reason():
    r = select(_data(), th={"mode":"strict"}, rs={}, sortino={"names":[],"sectors":[]})
    c = r["candidates"][0]
    assert c["vacuum_pct"] == 10.0
    assert c["tp_up"] == 5
    assert "빈집" in c["reason"] and "컨센" in c["reason"]


def test_rs_leader_sorted_first_and_flagged():
    # 주도주(RS) 매칭 종목이 먼저, is_leader 플래그 + 3M 표시
    rs = {"빈집상향": {"m1": 10.0, "m3": 50.0, "sector": "반도체"}}
    data = {
        "date": "2026-07-02",
        "stocks": {
            "A": {"name": "빈집상향", "osc": {"pct": 20.0}, "tp": {"up_count": 2, "down_count": 0}},
            "X": {"name": "비주도빈집", "osc": {"pct": 5.0}, "tp": {"up_count": 9, "down_count": 0}},
        },
    }
    r = select(data, th={"mode":"strict"}, rs=rs, sortino={"names":[],"sectors":[]})
    names = [c["name"] for c in r["candidates"]]
    assert names[0] == "빈집상향"          # 주도주 우선(비주도가 빈집·컨센 강해도)
    assert r["candidates"][0]["is_leader"] is True
    assert r["candidates"][0]["rs_m3"] == 50.0
    assert r["candidates"][1]["is_leader"] is False


def test_require_leader_filters_non_leaders():
    rs = {"빈집상향": {"m3": 50.0}}
    data = {"date": "d", "stocks": {
        "A": {"name": "빈집상향", "osc": {"pct": 20.0}, "tp": {"up_count": 2, "down_count": 0}},
        "X": {"name": "비주도", "osc": {"pct": 5.0}, "tp": {"up_count": 3, "down_count": 0}},
    }}
    r = select(data, th={"require_leader": True, "mode":"strict"}, rs=rs, sortino={"names":[],"sectors":[]})
    assert [c["name"] for c in r["candidates"]] == ["빈집상향"]


def test_sortino_match_flags_and_boosts():
    # 소라티노 상위(이름 or 섹터)면 sortino_match + 상단 정렬
    rs = {"소라섹터주": {"m3": 5.0, "sector": "은행"}}
    sortino = {"names": ["직접소라주"], "sectors": ["은행"]}
    data = {"date": "d", "stocks": {
        "A": {"name": "소라섹터주", "osc": {"pct": 30.0}, "tp": {"up_count": 1, "down_count": 0}},  # 섹터 은행 매칭
        "B": {"name": "직접소라주", "osc": {"pct": 30.0}, "tp": {"up_count": 1, "down_count": 0}},  # 이름 직접 매칭
        "C": {"name": "일반빈집", "osc": {"pct": 2.0}, "tp": {"up_count": 9, "down_count": 0}},     # 강하지만 소라티노 무관
    }}
    r = select(data, th={"mode":"strict"}, rs=rs, sortino=sortino)
    by = {c["name"]: c for c in r["candidates"]}
    assert by["소라섹터주"]["sortino_match"] is True   # 섹터 매칭
    assert by["직접소라주"]["sortino_match"] is True   # 이름 매칭
    assert by["일반빈집"]["sortino_match"] is False
    assert r["candidates"][0]["name"] in ("소라섹터주", "직접소라주")  # 소라티노 우선 정렬


def test_threshold_override_widens():
    # 빈집 임계값을 90으로 올리면 C(pct 80)도 빈집에 포함
    r = select(_data(), th={"vacuum_pct_max": 90.0, "mode":"strict"}, rs={}, sortino={"names":[],"sectors":[]})
    assert _c(r, "빈집") == 3                 # A,B,C
    names = [c["name"] for c in r["candidates"]]
    assert "수급유입" in names               # C도 컨센상향이라 선정


def test_his_mode_requires_leading():
    # his 모드: 주도(RS or 소라티노) 없으면 빈집·컨센 강해도 탈락
    rs = {"주도주": {"m3": 30.0, "sector": "반도체"}}
    data = {"date": "d", "stocks": {
        "A": {"name": "주도주", "osc": {"pct": 20.0}, "tp": {"up_count": 1, "down_count": 0}},
        "B": {"name": "비주도강빈집", "osc": {"pct": 1.0}, "tp": {"up_count": 9, "down_count": 0}},
    }}
    r = select(data, th={"mode": "his"}, rs=rs, sortino={"names": [], "sectors": []})
    assert [c["name"] for c in r["candidates"]] == ["주도주"]  # 비주도강빈집 탈락
