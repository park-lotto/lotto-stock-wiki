"""Test stock resolution: alias → code, unmatched korean logging, foreign sector map."""
from pathlib import Path
import pytest
import pipeline.atoms.stock_resolve as sr
from pipeline.atoms.stock_resolve import resolve_stock, foreign_sectors


@pytest.fixture(autouse=True)
def _temp_log(tmp_path, monkeypatch):
    """Isolate test unmatched log to temp path to preserve real log."""
    monkeypatch.setattr(sr, "UNMATCHED_LOG", tmp_path / "unmatched.log")
    yield


def test_foreign_sectors_single():
    assert foreign_sectors("마이크론") == ["반도체"]
    assert foreign_sectors("TSMC") == ["반도체"]


def test_foreign_sectors_multi():
    assert foreign_sectors("애플") == ["반도체", "IT"]


def test_foreign_sectors_paren_stripped():
    # 비셰이(VSH) → 괄호 제거 후 비셰이 매칭
    assert foreign_sectors("비셰이(VSH)") == ["전력"]


def test_foreign_sectors_unknown_empty():
    assert foreign_sectors("ZZZCorp") == []
    assert foreign_sectors("") == []


def test_skip_log_suppresses_unmatched(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "UNMATCHED_LOG", tmp_path / "u.log")
    resolve_stock("마이크론", date="2026-06-19", channel="x", skip_log=True)
    assert not (tmp_path / "u.log").exists()  # skip_log이면 기록 안 함


def test_alias_then_code():
    r = resolve_stock("삼전", date="2026-06-19", channel="태린이아빠 주식투자")
    assert r["name"] == "삼성전자"
    assert r["code"] == "005930"
    assert r["is_korean"] is True
    assert r["matched"] is True


def test_hangul_foreign_unmatched():
    """한글 음차 외국주(마이크론)는 한글이라 logged, is_korean=True but matched=False."""
    r = resolve_stock("마이크론", date="2026-06-19", channel="하나반도체")
    assert r["is_korean"] is True  # 한글 포함 → looks_korean=True
    assert r["matched"] is False


def test_english_ticker_not_logged():
    """순수 영문 티커(AAPL)는 로그에 기록 안 됨."""
    r = resolve_stock("AAPL", date="2026-06-19", channel="미국주식")
    assert r["is_korean"] is False  # 한글 없음 → looks_korean=False
    assert r["matched"] is False
    # 로그 파일이 없거나 AAPL 미포함
    log_path = sr.UNMATCHED_LOG
    assert not log_path.exists() or "AAPL" not in log_path.read_text(encoding="utf-8")


def test_unmatched_korean_is_logged():
    # 한글인데 codemap에 없는 가짜 종목 → 로그 기록
    r = resolve_stock("듣보종목가나다", date="2026-06-19", channel="잠실개미고급수집")
    assert r["matched"] is False
    assert sr.UNMATCHED_LOG.exists()
    txt = sr.UNMATCHED_LOG.read_text(encoding="utf-8")
    assert "듣보종목가나다" in txt
    assert "잠실개미고급수집" in txt
