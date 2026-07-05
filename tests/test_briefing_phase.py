# tests/test_briefing_phase.py
import datetime as dt
from briefing_phase import session_phase

def test_weekend_saturday():
    assert session_phase(dt.datetime(2026, 7, 4, 14, 0)) == "weekend"   # 토요일

def test_premarket():
    assert session_phase(dt.datetime(2026, 7, 6, 7, 45)) == "premarket"  # 월 07:45 (미국장 마감 직후)

def test_premarket_nxt():
    assert session_phase(dt.datetime(2026, 7, 6, 8, 20)) == "premarket_nxt"  # 월 08:20 (NXT)

def test_intraday():
    assert session_phase(dt.datetime(2026, 7, 6, 11, 0)) == "intraday"   # 월 11:00

def test_afterhours():
    assert session_phase(dt.datetime(2026, 7, 6, 16, 0)) == "afterhours"  # 월 16:00 (마감 후)

def test_afterhours_night():
    assert session_phase(dt.datetime(2026, 7, 6, 19, 0)) == "afterhours_night"  # 월 19:00 (야간선물+나스닥프리장)

def test_closed_after_20():
    assert session_phase(dt.datetime(2026, 7, 6, 20, 30)) == "closed"    # 월 20:30

def test_early_morning_is_closed():
    assert session_phase(dt.datetime(2026, 7, 6, 6, 0)) == "closed"      # 월 06:00 (프리마켓 이전)
