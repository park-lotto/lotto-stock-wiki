import pytest
from pipeline.people.registry import load_registry, get_person, source_names


def test_load_registry_has_taerini():
    reg = load_registry()
    assert "태린이아빠" in reg


def test_get_person_returns_config():
    p = get_person("태린이아빠")
    assert p["trust"] == "B"
    assert p["brain_page"] == "wiki/people/태린이아빠.md"


def test_source_names_includes_telegram_and_youtube():
    names = source_names("태린이아빠")
    assert "태린이아빠 주식투자" in names   # 텔레그램
    assert "태린이아빠" in names            # 유튜브


def test_get_person_unknown_raises():
    with pytest.raises(KeyError):
        get_person("없는사람")
