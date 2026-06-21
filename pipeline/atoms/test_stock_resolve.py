"""Test stock resolution: alias → code, unmatched korean logging."""
from pathlib import Path
from pipeline.atoms.stock_resolve import resolve_stock, UNMATCHED_LOG


def test_alias_then_code():
    r = resolve_stock("삼전", date="2026-06-19", channel="태린이아빠 주식투자")
    assert r["name"] == "삼성전자"
    assert r["code"] == "005930"
    assert r["is_korean"] is True
    assert r["matched"] is True


def test_foreign_stock_not_korean():
    r = resolve_stock("마이크론", date="2026-06-19", channel="하나반도체")
    assert r["is_korean"] is False
    assert r["matched"] is False


def test_unmatched_korean_is_logged():
    # 한글인데 codemap에 없는 가짜 종목 → 로그 기록
    if UNMATCHED_LOG.exists():
        UNMATCHED_LOG.unlink()
    r = resolve_stock("듣보종목가나다", date="2026-06-19", channel="잠실개미고급수집")
    assert r["matched"] is False
    assert UNMATCHED_LOG.exists()
    txt = UNMATCHED_LOG.read_text(encoding="utf-8")
    assert "듣보종목가나다" in txt
    assert "잠실개미고급수집" in txt
