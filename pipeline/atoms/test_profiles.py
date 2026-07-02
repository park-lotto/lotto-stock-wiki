import json
import tempfile
from pathlib import Path

from pipeline.atoms import profiles


def test_youtube_channel_profile_returns_none_when_field_missing(monkeypatch):
    fake_registry = {"업사이클": {"trust": "B", "url": "https://x"}}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "youtube_registry.json"
        p.write_text(json.dumps(fake_registry, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(profiles, "_YOUTUBE_REGISTRY_PATH", p)
        profiles._YOUTUBE_REGISTRY_CACHE.clear()
        assert profiles.youtube_channel_profile("업사이클") is None


def test_youtube_channel_profile_returns_tagged_value(monkeypatch):
    fake_registry = {"어떤채널": {"trust": "B", "url": "https://x", "profile": "데이트레이딩"}}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "youtube_registry.json"
        p.write_text(json.dumps(fake_registry, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(profiles, "_YOUTUBE_REGISTRY_PATH", p)
        profiles._YOUTUBE_REGISTRY_CACHE.clear()
        assert profiles.youtube_channel_profile("어떤채널") == "데이트레이딩"


def test_youtube_channel_profile_unknown_channel_returns_none(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "youtube_registry.json"
        p.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(profiles, "_YOUTUBE_REGISTRY_PATH", p)
        profiles._YOUTUBE_REGISTRY_CACHE.clear()
        assert profiles.youtube_channel_profile("존재안함") is None


def test_daytrading_atoms_maps_slots_into_structured_fields():
    q = {
        "trades": [
            {"name": "삼성전자", "entry_price": "71000", "stop_loss": "69500",
             "target_price": "75000", "hold_period": "2~3일",
             "chart_pattern": "20일선 지지 후 반등", "sector": "반도체",
             "quote": "71000원 부근에서 분할매수 진입"}
        ]
    }
    meta = {"date": "2026-07-02", "channel": "테스트채널", "source_type": "youtube",
            "trust": "B", "raw_file": "x.md"}
    from pipeline.atoms.profiles import daytrading_atoms
    atoms = daytrading_atoms(q, meta)
    assert len(atoms) == 1
    a = atoms[0]
    assert a["asset"] == "삼성전자"
    assert a["source_type"] == "youtube"
    import json
    sf = json.loads(a["structured_fields"])
    assert sf["entry_price"] == "71000"
    assert sf["stop_loss"] == "69500"
    assert sf["target_price"] == "75000"
    assert sf["hold_period"] == "2~3일"
    assert sf["chart_pattern"] == "20일선 지지 후 반등"


def test_daytrading_atoms_skips_entry_without_name():
    q = {"trades": [{"name": "", "entry_price": "1000"}]}
    meta = {"date": "2026-07-02", "channel": "테스트채널", "source_type": "youtube",
            "trust": "B", "raw_file": "x.md"}
    from pipeline.atoms.profiles import daytrading_atoms
    assert daytrading_atoms(q, meta) == []
