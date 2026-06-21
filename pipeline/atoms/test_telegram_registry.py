"""Test telegram registry channel_info, is_excluded, resolve_alias."""
from pipeline.atoms.telegram_registry import channel_info, is_excluded, resolve_alias


def test_sector_channel():
    info = channel_info("하나반도체")
    assert info["type"] == "sector"
    assert info["sector"] == "반도체"
    assert info["trust"] == "B"


def test_market_channel_no_sector():
    info = channel_info("대신시황")
    assert info["type"] == "market"
    assert info.get("sector") is None


def test_unregistered_returns_none():
    assert channel_info("듣보채널") is None


def test_excluded_channels():
    assert is_excluded("리포트요약") is True
    assert is_excluded("투경현황") is True
    assert is_excluded("하나반도체") is False


def test_alias_resolution():
    assert resolve_alias("삼전") == "삼성전자"
    assert resolve_alias("하이닉스") == "SK하이닉스"
    assert resolve_alias("LG엔솔") == "LG에너지솔루션"  # 대소문자 무시
    assert resolve_alias("미등록종목") == "미등록종목"     # 없으면 원본
