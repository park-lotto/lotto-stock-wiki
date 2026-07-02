import pytest
from pipeline.people.persona import decide_verdict


def test_verdict_toppick_leading_and_vacuum():
    assert decide_verdict(leading=True, vac=True, up_ok=False) == "탑픽 후보"
    assert decide_verdict(leading=True, vac=False, up_ok=True) == "탑픽 후보"


def test_verdict_interest_leading_only():
    assert decide_verdict(leading=True, vac=False, up_ok=False).startswith("관심")


def test_verdict_watch_vacuum_consensus_no_lead():
    assert decide_verdict(leading=False, vac=True, up_ok=True).startswith("관망")


def test_verdict_out_of_scope():
    assert decide_verdict(leading=False, vac=False, up_ok=False).startswith("그의 기준 밖")
    assert decide_verdict(leading=False, vac=True, up_ok=False).startswith("그의 기준 밖")


from pipeline.people.persona import decide_posture


def test_posture_defensive():
    assert decide_posture(bull=1, bear=5, has_cash=True, has_defensive=False).startswith("방어")
    assert decide_posture(bull=0, bear=3, has_cash=False, has_defensive=True).startswith("방어")


def test_posture_aggressive():
    assert decide_posture(bull=8, bear=1, has_cash=False, has_defensive=False).startswith("공격")


def test_posture_neutral():
    # 강세지만 방어 트리거 있으면 중립
    assert decide_posture(bull=8, bear=1, has_cash=False, has_defensive=True).startswith("중립")
    assert decide_posture(bull=3, bear=3, has_cash=False, has_defensive=False).startswith("중립")


# 범용 스키마: 데이터파일 없는 채널은 발언 기반 판정
import json
from datetime import date
import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, insert_atom
import pipeline.people.registry as registry_module
from pipeline.people import persona


@pytest.fixture
def verbal_only(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "atoms.db")
    init_db()
    reg = {"발언채널": {"display": "발언채널", "sources": ["발언채널"], "trust": "C"}}  # data_files 없음
    p = tmp_path / "people.json"
    p.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(registry_module, "_REGISTRY_PATH", p)


def _atom(**kw):
    base = {"id": "a1", "date": date.today().isoformat(), "source_type": "telegram",
            "source_name": "발언채널", "source_trust": "C", "raw_file": "r.md", "layer": "L6",
            "sector": "반도체", "asset": "삼성전자", "asset_level": "stock", "signal": "bullish",
            "event_type": "news", "magnitude": "minor", "content_type": "opinion",
            "strength_score": 3, "validity_type": "permanent", "validity_until": None,
            "is_active": 1, "content": "삼성전자 좋게 본다", "relations": []}
    base.update(kw); return base


def test_verbal_channel_uses_own_atoms(verbal_only):
    insert_atom(_atom(signal="bullish", content="삼성전자 반등 기대"))
    v = persona.stock_verdict("발언채널", "삼성전자")
    assert v["found_in_data"] is False           # 데이터 지표 안 씀
    assert v["verdict"] == "긍정적"                # 발언 신호 기반
    assert any("삼성전자 반등" in r for r in v["reason"])


def test_verbal_channel_unknown_stock(verbal_only):
    v = persona.stock_verdict("발언채널", "없는종목")
    assert v["verdict"] == "자료 없음"
