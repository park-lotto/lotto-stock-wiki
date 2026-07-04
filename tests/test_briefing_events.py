from briefing_events import (build_snapshot, detect_flow, detect_index,
                             detect_nq, detect_decouple, detect_sector, detect_all)


def _mf():
    return {
        "J_price": {"price": 8088.0, "change_rate": 5.76},
        "Q_price": {"price": 868.0, "change_rate": 0.19},
        "J_investor": {"외인": -220000, "기관": 440000},   # 백만원
        "Q_investor": {"외인": -20200, "기관": -103700},
        "J_prog": {"합계": -936700}, "Q_prog": {"합계": -92200},
        "NQ": {"change_rate": 1.10},
    }


# ── T2: build_snapshot ──────────────────────────────
def test_build_snapshot_shape():
    bars = [{"t": "090000", "price": 8000.0}, {"t": "094500", "price": 7950.0},
            {"t": "140000", "price": 8088.0}]
    snap = build_snapshot(_mf(), [{"name": "반도체", "avg_rate": 3.4, "stocks": []}],
                          bars, bars, ts="14:00")
    assert snap["idx"]["J"]["price"] == 8088.0
    assert snap["idx"]["J"]["rate"] == 5.76
    assert snap["hi_lo"]["J"]["day_high"] == 8088.0
    assert snap["hi_lo"]["J"]["day_low"] == 7950.0
    assert snap["inv"]["J"]["외인"] == -220000
    assert snap["prog"]["J"] == -936700
    assert snap["nq"]["rate"] == 1.10
    assert snap["sect"]["반도체"] == 3.4


def test_build_snapshot_missing_fields_safe():
    snap = build_snapshot({}, [], [], [], ts="09:00")
    assert snap["idx"]["J"]["price"] == 0
    assert snap["hi_lo"]["J"]["day_high"] == 0
    assert snap["sect"] == {}


# ── T3: detect_flow ─────────────────────────────────
def _snap(inv_j_ext=0, prog_j=0):
    return {"ts": "11:00",
            "inv": {"J": {"외인": inv_j_ext, "기관": 0}, "Q": {"외인": 0, "기관": 0}},
            "prog": {"J": prog_j, "Q": 0}}


def test_investor_sign_flip_fires():
    prev = _snap(inv_j_ext=-50000)
    curr = _snap(inv_j_ext=+40000)
    evs = detect_flow(prev, curr)
    assert any(e["type"] == "investor_flip" and e["market"] == "J" for e in evs)


def test_investor_flip_too_small_ignored():
    prev = _snap(inv_j_ext=-50000)
    curr = _snap(inv_j_ext=+10000)
    assert not any(e["type"] == "investor_flip" for e in detect_flow(prev, curr))


def test_investor_first_run_silent():
    assert detect_flow(None, _snap(inv_j_ext=+40000)) == []


def test_prog_jump_fires():
    prev = _snap(prog_j=0)
    curr = _snap(prog_j=+60000)
    assert any(e["type"] == "prog_shift" for e in detect_flow(prev, curr))


def test_prog_small_move_ignored():
    prev = _snap(prog_j=0)
    curr = _snap(prog_j=+10000)
    assert not any(e["type"] == "prog_shift" for e in detect_flow(prev, curr))


# ── T4: detect_index ────────────────────────────────
def _isnap(price, hi, lo):
    return {"ts": "11:00", "idx": {"J": {"price": price, "rate": 0}, "Q": {"price": 0, "rate": 0}},
            "hi_lo": {"J": {"day_high": hi, "day_low": lo}, "Q": {"day_high": 0, "day_low": 0}}}


def test_index_new_high():
    prev = _isnap(8000, 8000, 7900)
    curr = _isnap(8010, 8010, 7900)
    assert any(e["type"] == "index_newhigh" for e in detect_index(prev, curr, {}))


def test_index_rebound_once_per_leg():
    leg = {}
    prev = _isnap(7900, 8000, 7900)
    curr = _isnap(7948, 8000, 7900)
    first = detect_index(prev, curr, leg)
    assert any(e["type"] == "index_rebound" for e in first)
    again = detect_index(curr, _isnap(7950, 8000, 7900), leg)
    assert not any(e["type"] == "index_rebound" for e in again)


def test_index_first_run_silent():
    assert detect_index(None, _isnap(8000, 8000, 7900), {}) == []


# ── T5: detect_nq / detect_decouple / detect_sector ──
def test_nq_delta_fires():
    prev = {"nq": {"rate": 0.2}}
    curr = {"nq": {"rate": 0.7}}
    assert any(e["type"] == "nq_move" for e in detect_nq(prev, curr))


def test_decouple_opposite_slope():
    j_bars = [{"price": 8000}, {"price": 7990}, {"price": 7980}]
    nq_bars = [100.0, 100.3, 100.6]
    evs = detect_decouple(j_bars, nq_bars)
    assert any(e["type"] == "decouple" for e in evs)


def test_sector_surge_with_drivers():
    prev = {"sect": {"반도체": 1.0}}
    curr = {"sect": {"반도체": 3.2}}
    full = [{"name": "반도체", "avg_rate": 3.2,
             "stocks": [{"name": "한미반도체", "change_rate": 8.2, "price": 100},
                        {"name": "이수페타시스", "change_rate": 6.1, "price": 100}]}]
    evs = detect_sector(prev, curr, full)
    surge = [e for e in evs if e["type"] == "sector_surge"]
    assert surge and surge[0]["sector"] == "반도체"
    assert surge[0]["top_movers"][0]["name"] == "한미반도체"


def test_sector_no_change_silent():
    assert detect_sector({"sect": {"반도체": 3.0}}, {"sect": {"반도체": 3.1}}, []) == []


# ── T6: detect_all (페이즈게이팅 + 쿨다운) ────────────
def _full_snap(**kw):
    return {"ts": "11:00",
            "idx": {"J": {"price": kw.get("jp", 8000), "rate": 0}, "Q": {"price": 800, "rate": 0}},
            "hi_lo": {"J": {"day_high": kw.get("jh", 8000), "day_low": kw.get("jl", 7900)},
                      "Q": {"day_high": 800, "day_low": 790}},
            "inv": {"J": {"외인": kw.get("jext", 0), "기관": 0}, "Q": {"외인": 0, "기관": 0}},
            "prog": {"J": 0, "Q": 0}, "nq": {"rate": kw.get("nq", 0)},
            "sect": kw.get("sect", {})}


def test_detect_all_cooldown_blocks_repeat():
    st = {"cooldown": {}, "leg": {}}
    prev = _full_snap(jext=-50000)
    curr = _full_snap(jext=+40000)
    first = detect_all(prev, curr, [], [], [], "intraday", st)
    assert any(e["type"] == "investor_flip" for e in first)
    second = detect_all(curr, _full_snap(jext=-40000), [], [], [], "intraday", st)
    assert not any(e["type"] == "investor_flip" for e in second)


def test_detect_all_weekend_skips_flow():
    st = {"cooldown": {}, "leg": {}}
    prev = _full_snap(jext=-50000)
    curr = _full_snap(jext=+40000)
    evs = detect_all(prev, curr, [], [], [], "weekend", st)
    assert not any(e["type"] == "investor_flip" for e in evs)
