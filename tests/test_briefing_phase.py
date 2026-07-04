# tests/test_briefing_phase.py
import datetime as dt
from briefing_phase import session_phase

def test_weekend_saturday():
    assert session_phase(dt.datetime(2026, 7, 4, 14, 0)) == "weekend"   # 토요일

def test_premarket():
    assert session_phase(dt.datetime(2026, 7, 6, 8, 20)) == "premarket"  # 월 08:20

def test_intraday():
    assert session_phase(dt.datetime(2026, 7, 6, 11, 0)) == "intraday"   # 월 11:00

def test_closed():
    assert session_phase(dt.datetime(2026, 7, 6, 16, 0)) == "closed"     # 월 16:00

def test_early_morning_is_closed():
    assert session_phase(dt.datetime(2026, 7, 6, 6, 0)) == "closed"      # 월 06:00 (장전 이전)
