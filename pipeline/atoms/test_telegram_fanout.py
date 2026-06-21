# pipeline/atoms/test_telegram_fanout.py
import json
from pathlib import Path
from pipeline.atoms.telegram_questionnaire import (
    questionnaire_to_atoms_tg, _event_key, _strength,
)

FIX = json.loads((Path(__file__).parent / "fixtures" / "tg_spike.json").read_text(encoding="utf-8"))


def _by_channel(name):
    return next(x["result"] for x in FIX if x["channel"] == name)


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
