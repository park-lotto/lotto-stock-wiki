import json
import pytest
from datetime import date

import pipeline.atoms.db as db_module
from pipeline.atoms.db import init_db, insert_atom
import pipeline.people.registry as registry_module
import pipeline.people.brain_view as bv


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    # 원자 DB 격리
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "atoms.db")
    init_db()
    # 레지스트리 격리 (temp people.json)
    reg = {"테스트채널": {"display": "테스트채널", "sources": ["테스트채널"],
                       "trust": "B", "tracking_since": "2026-06-01",
                       "brain_page": "brain.md"}}
    reg_path = tmp_path / "people.json"
    reg_path.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(registry_module, "_REGISTRY_PATH", reg_path)
    # 골격 MD 격리
    monkeypatch.setattr(bv, "_ROOT", tmp_path)
    (tmp_path / "brain.md").write_text(
        "# 테스트채널 — 브레인\n## 1. 철학\n수급빈집.\n\n"
        "## 5. 라이브\n<!-- AUTO:live_stance -->\nX\n<!-- /AUTO:live_stance -->\n",
        encoding="utf-8",
    )


def _atom(**kw):
    base = {"id": "a1", "date": date.today().isoformat(),
            "source_type": "telegram", "source_name": "테스트채널", "source_trust": "B",
            "raw_file": "r.md", "layer": "L5", "sector": "반도체", "asset": "삼성전자",
            "asset_level": "stock", "signal": "bullish", "event_type": "news",
            "magnitude": "minor", "content_type": "opinion", "strength_score": 3,
            "validity_type": "permanent", "validity_until": None,
            "is_active": 1, "content": "비중 확대.", "relations": []}
    base.update(kw)
    return base


def test_list_people_counts_stances():
    insert_atom(_atom(id="s1", stance_key="테스트채널|반도체"))
    insert_atom(_atom(id="s2", stance_key=None))
    people = bv.list_people()
    assert len(people) == 1
    p = people[0]
    assert p["name"] == "테스트채널"
    assert p["stance_count"] == 1          # stance_key 있는 것만
    assert p["has_skeleton"] is True
    assert p["latest_date"] == date.today().isoformat()


def test_person_view_splits_stance_and_log():
    insert_atom(_atom(id="s1", stance_key="테스트채널|반도체", content="긍정: 확대"))
    insert_atom(_atom(id="f1", stance_key=None, content_type="fact", content="사실 발언"))
    v = bv.person_view("테스트채널")
    assert len(v["live_stance"]) == 1
    assert v["live_stance"][0]["content"] == "긍정: 확대"
    assert len(v["speech_log"]) == 2       # 발언 로그는 stance 여부 무관 전체
    assert "수급빈집" in v["skeleton_md"]    # 골격 §1~4 (첫 AUTO 마커 이전)
    assert "AUTO:live_stance" not in v["skeleton_md"]  # 자동 섹션은 제외


def test_three_buckets_by_asset_level():
    insert_atom(_atom(id="mk", asset_level="market", content="시장 조정 우려"))
    insert_atom(_atom(id="mc", asset_level="macro", content="달러 강세"))
    insert_atom(_atom(id="me", asset_level="method", content="이평선 이탈 시 축소"))
    insert_atom(_atom(id="st", asset_level="stock", asset="삼성전자", content="삼전 비중 축소"))
    insert_atom(_atom(id="se", asset_level="sector", sector="반도체", content="반도체 빈집"))
    assert len(bv.market_insight("테스트채널")) == 2       # market + macro
    assert len(bv.methods("테스트채널")) == 1              # method
    assert len(bv.materials("테스트채널")) == 2            # stock + sector


def test_materials_query_filters_by_stock():
    insert_atom(_atom(id="s1", asset_level="stock", asset="삼성전자", content="삼전 얘기"))
    insert_atom(_atom(id="s2", asset_level="stock", asset="SK하이닉스", content="하닉 얘기"))
    got = bv.materials("테스트채널", query="삼성전자")
    assert len(got) == 1
    assert got[0]["asset"] == "삼성전자"


def test_recent_mentioned_assets_tokenizes():
    insert_atom(_atom(id="m1", asset_level="stock", asset="삼성전자"))
    insert_atom(_atom(id="m2", asset_level="stance", asset="삼성전자, 하이닉스"))
    insert_atom(_atom(id="m3", asset_level="stock", asset="티에스이"))
    got = bv._recent_mentioned_assets("테스트채널", days=7)
    assert "삼성전자" in got and "하이닉스" in got and "티에스이" in got


def test_match_substring():
    assert bv._match("삼성전자", "삼성전자")
    assert bv._match("삼성전자", "삼성전자, 하이닉스")
    assert not bv._match("삼성전자", "SK하이닉스")


def test_routine_today_none_when_no_routine():
    # 루틴 파일 없는 채널이면 None (무거운 로드 전에 반환)
    assert bv.routine_today("루틴없는채널") is None


def test_person_view_unknown_raises():
    with pytest.raises(KeyError):
        bv.person_view("없는채널")


def test_skeleton_md_absent_returns_empty(monkeypatch):
    # brain_page 파일이 없으면 빈 문자열
    monkeypatch.setattr(bv, "_ROOT", bv._ROOT)  # 유지
    cfg = {"brain_page": "없는파일.md"}
    assert bv._skeleton_md(cfg) == ""
    assert bv._skeleton_md({}) == ""
