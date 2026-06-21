# pipeline/atoms/test_telegram_fanout.py
import json
from pathlib import Path
import pytest
import pipeline.atoms.stock_resolve as sr
from pipeline.atoms.telegram_questionnaire import (
    questionnaire_to_atoms_tg, _event_key, _strength,
)


@pytest.fixture(autouse=True)
def _temp_logs(tmp_path, monkeypatch):
    """운영 로그 격리 — UNMATCHED·FOREIGN_UNMAPPED 둘 다 tmp로."""
    monkeypatch.setattr(sr, "UNMATCHED_LOG", tmp_path / "unmatched.log")
    monkeypatch.setattr(sr, "FOREIGN_UNMAPPED_LOG", tmp_path / "foreign_unmapped.log")
    yield


FIX = json.loads((Path(__file__).parent / "fixtures" / "tg_spike.json").read_text(encoding="utf-8"))


def _by_channel(name):
    return next(x["result"] for x in FIX if x["channel"] == name)


def test_foreign_stock_routed_to_mapped_sector():
    # 마이크론(외국·DRAM) → 반도체 섹터 컨텍스트 원자 (드롭 아님)
    q = {"stocks": [{"name": "마이크론", "signal": "bull",
                     "reason": "슈퍼사이클", "ts": "10:00", "quote": "마이크론 10배"}]}
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집",
            "type": "stock_tips", "trust": "C"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    fgn = [a for a in atoms if a["asset_level"] == "sector" and a["sector"] == "반도체"]
    assert fgn, "마이크론이 반도체 섹터 원자로 라우팅돼야"
    assert "마이크론" in fgn[0]["content"]
    # 종목원자로는 안 들어감
    assert not any(a["asset_level"] == "stock" and a["asset"] == "마이크론" for a in atoms)


def test_apple_routed_to_two_sectors():
    # 애플 → 반도체 + IT 둘 다
    q = {"stocks": [{"name": "애플", "signal": "neutral",
                     "reason": "메모리 가격압박", "ts": "11:00", "quote": "애플 인정"}]}
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집",
            "type": "stock_tips", "trust": "C"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    secs = {a["sector"] for a in atoms if a["asset_level"] == "sector"}
    assert "반도체" in secs and "IT" in secs


def test_unmapped_foreign_english_logged(tmp_path, monkeypatch):
    # 매핑에도 codemap에도 없는 영문 외국주 → foreign_unmapped 로그
    monkeypatch.setattr(sr, "FOREIGN_UNMAPPED_LOG", tmp_path / "fu.log")
    q = {"stocks": [{"name": "ZZZCorp", "signal": "neutral",
                     "reason": "x", "ts": "09:00", "quote": "q"}]}
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집",
            "type": "stock_tips", "trust": "C"}
    questionnaire_to_atoms_tg(q, meta)
    assert (tmp_path / "fu.log").exists()
    assert "ZZZCorp" in (tmp_path / "fu.log").read_text(encoding="utf-8")


def test_sector_korean_stock_only():
    # 하나반도체: SK하이닉스(한국)는 종목원자, 마이크론/ARM(외국)은 종목원자 X
    q = _by_channel("하나반도체")
    meta = {"date": "2026-06-19", "channel": "하나반도체", "type": "sector",
            "sector": "반도체", "trust": "B"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    stock_atoms = [a for a in atoms if a["asset_level"] == "stock"]
    names = {a["asset"] for a in stock_atoms}
    assert "SK하이닉스" in names
    assert "ARM" not in names and "마이크론" not in names
    # 섹터 원자는 1개 존재
    assert any(a["asset_level"] == "sector" for a in atoms)


def test_insight_produces_stance_and_method():
    q = _by_channel("태린이아빠 주식투자")
    meta = {"date": "2026-06-19", "channel": "태린이아빠 주식투자", "type": "insight", "trust": "B"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    # 방법론 원자
    assert any(a["asset_level"] == "method" for a in atoms)
    # 스탠스 원자는 stance_key 보유
    stance = [a for a in atoms if a.get("stance_key")]
    assert len(stance) >= 1
    assert "|" in stance[0]["stance_key"]  # "채널|대상" 형식


def test_stock_tips_quote_in_content():
    # 종목 원자 content에 quote(원문)가 들어가야 (comment 아님)
    q = _by_channel("잠실개미고급수집")
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집", "type": "stock_tips", "trust": "C"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    sk = [a for a in atoms if a["asset"] == "SK하이닉스"]
    assert sk and ("머스크" in sk[0]["content"] or "회동" in sk[0]["content"])


def test_event_key_groups_same_fact():
    k1 = _event_key("미국-이란 MOU 체결")
    k2 = _event_key("미국 이란 MOU 체결!!")
    assert k1 == k2  # 구두점·공백 무시 정규화


def test_strength_caps_at_4():
    assert _strength("B", "fact", mention_count=10) <= 4
    assert _strength("C", "stance", mention_count=1) >= 1


def test_report_relay_korean_yes_foreign_no():
    """report_relay: 한국주(삼성전자)는 종목원자 생성, 외국주(마이크론)는 생성 안 됨."""
    q = {
        "reports": [
            {"stock": "삼성전자", "broker": "한화", "rating": "BUY",
             "tp": "100000", "ts": "09:00", "quote": "목표가 상향"},
            {"stock": "마이크론", "broker": "한화", "rating": "BUY",
             "tp": "150", "ts": "09:05", "quote": "AI 수혜"},
        ],
        "quote": "반도체 업황 개선세",
    }
    meta = {"date": "2026-06-19", "channel": "신한리서치",
            "type": "report_relay", "trust": "B"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    stock_atoms = [a for a in atoms if a["asset_level"] == "stock"]
    names = {a["asset"] for a in stock_atoms}
    # 한국주는 종목원자 생성
    assert "삼성전자" in names
    # 외국주는 종목원자 없음
    assert "마이크론" not in names
    # content에 broker / 목표가 흔적 포함
    se_atom = next(a for a in stock_atoms if a["asset"] == "삼성전자")
    assert "한화" in se_atom["content"] or "100000" in se_atom["content"]


def test_stock_tips_quote_takes_priority_over_reason():
    """stock_tips: quote와 reason이 다를 때 quote가 content에 포함되고 reason은 포함 안 됨."""
    q = {
        "stocks": [
            {"name": "삼성전자", "signal": "bull",
             "reason": "리즌텍스트ABC", "ts": "10:00", "quote": "인용텍스트XYZ"},
        ],
        "news_items": [],
        "quote": "시장 전반 긍정",
    }
    meta = {"date": "2026-06-19", "channel": "테스트채널",
            "type": "stock_tips", "trust": "B"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    stock_atoms = [a for a in atoms if a["asset_level"] == "stock"]
    assert stock_atoms, "삼성전자 종목원자가 생성되어야 함"
    content = stock_atoms[0]["content"]
    # quote 우선: 인용텍스트XYZ 포함, 리즌텍스트ABC 미포함
    assert "인용텍스트XYZ" in content
    assert "리즌텍스트ABC" not in content


def test_korean_stock_gets_hint_sector():
    # stock_tips 한국주가 "기타" 아닌 hint 섹터를 받는다
    q = {"stocks": [{"name": "삼성전자", "signal": "bull", "reason": "x",
                     "ts": "10:00", "quote": "q", "sector": "반도체"}]}
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집",
            "type": "stock_tips", "trust": "C"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    sams = [a for a in atoms if a["asset"] == "삼성전자" and a["asset_level"] == "stock"]
    assert sams and sams[0]["sector"] == "반도체"


def test_unmapped_foreign_with_hint_preserved():
    # map에 없는 외국주라도 hint로 섹터 컨텍스트 원자 생성 (손실 X)
    q = {"stocks": [{"name": "ZZZChip", "signal": "bull", "reason": "신규칩",
                     "ts": "10:00", "quote": "q", "sector": "반도체"}]}
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집",
            "type": "stock_tips", "trust": "C"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    fgn = [a for a in atoms if a["asset_level"] == "sector" and a["sector"] == "반도체"]
    assert fgn and "ZZZChip" in fgn[0]["content"]


def test_sector_atom_uses_sector_name_when_no_meta_sector():
    # 블로그처럼 meta에 sector 없고 q에 sector_name 있으면 그걸로 (기타 아님)
    q = {"sector_name": "바이오", "sector_view": "부정",
         "points": ["코스닥 승강제"], "events": [{"fact": "10월 시행", "ts": None, "quote": "q"}]}
    meta = {"date": "2026-06-21", "channel": "pokara61", "type": "sector",
            "source_type": "blog", "trust": "B"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    secs = [a for a in atoms if a["asset_level"] == "sector"]
    assert secs and all(a["sector"] == "바이오" for a in secs)
