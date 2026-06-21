import pytest
from pipeline.atoms.verify_telegram import verify_telegram_quotes, _all_quotes


def test_quote_present_no_flag():
    q = {"stocks": [{"name": "SK하이닉스", "quote": "최태원 회장 머스크 회동"}]}
    md = "오늘 뉴스: 최태원 회장 머스크 회동 예정이라고 한다."
    assert verify_telegram_quotes(q, md) == []


def test_quote_absent_flagged():
    q = {"stocks": [{"name": "X", "quote": "존재하지 않는 완전히 다른 문장입니다"}]}
    md = "전혀 다른 내용"
    flags = verify_telegram_quotes(q, md)
    assert any(f["code"] == "TG_QUOTE_NOT_FOUND" for f in flags)


def test_all_quotes_collects_nested():
    q = {"events": [{"quote": "a문장"}], "quote": "b문장",
         "stance": [{"quote": "c문장"}]}
    qs = set(_all_quotes(q))
    assert {"a문장", "b문장", "c문장"} <= qs
