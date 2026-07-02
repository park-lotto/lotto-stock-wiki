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
