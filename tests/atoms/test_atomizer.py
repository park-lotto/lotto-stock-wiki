import pytest
from unittest.mock import MagicMock, patch
from pipeline.atoms.atomizer import atomize_text, _make_id, _calc_strength


def test_make_id_deterministic():
    id1 = _make_id("2026-06-07", "신한리서치", 0)
    id2 = _make_id("2026-06-07", "신한리서치", 0)
    assert id1 == id2
    assert id1.startswith("atom_")
    assert len(id1) == 17  # "atom_" + 12자


def test_make_id_unique_per_index():
    id0 = _make_id("2026-06-07", "신한리서치", 0)
    id1 = _make_id("2026-06-07", "신한리서치", 1)
    assert id0 != id1


def test_calc_strength_a_source_major():
    score = _calc_strength({"magnitude": "major"}, "A")
    assert score == 4  # 1 base + 2 trust_A + 1 major


def test_calc_strength_max_five():
    score = _calc_strength({"magnitude": "major"}, "A")
    assert score <= 5


def test_calc_strength_d_source_minor():
    score = _calc_strength({"magnitude": "minor"}, "D")
    assert score == 1  # 1 base only


@patch("pipeline.atoms.atomizer._client")
def test_atomize_text_returns_atoms(mock_client):
    mock_client.models.generate_content.return_value.text = '''[
        {
            "content": "브로드컴 AI 가이던스 -11.8% 미달.",
            "sector": "반도체",
            "asset": "브로드컴",
            "asset_level": "stock",
            "signal": "bearish",
            "event_type": "earnings",
            "magnitude": "major",
            "content_type": "fact",
            "validity_type": "permanent",
            "validity_until": null
        }
    ]'''

    atoms = atomize_text(
        text="브로드컴 AI 가이던스 -11.8% 미달.",
        source_type="telegram",
        source_name="신한리서치",
        source_trust="B",
        raw_file="raw/test.md",
        date="2026-06-07",
    )

    assert len(atoms) == 1
    a = atoms[0]
    assert a["signal"] == "bearish"
    assert a["sector"] == "반도체"
    assert a["source_trust"] == "B"
    assert a["content"] == "브로드컴 AI 가이던스 -11.8% 미달."
    assert a["id"].startswith("atom_")


@patch("pipeline.atoms.atomizer._client")
def test_atomize_text_preserves_content_exactly(mock_client):
    original = "원문 그대로 보존해야 한다. 절대 요약 금지."
    mock_client.models.generate_content.return_value.text = f'''[
        {{
            "content": "{original}",
            "sector": "기타", "asset": "테스트",
            "asset_level": "stock", "signal": "neutral",
            "event_type": "news", "magnitude": "minor",
            "content_type": "fact", "validity_type": "permanent",
            "validity_until": null
        }}
    ]'''

    atoms = atomize_text(
        text=original,
        source_type="news",
        source_name="테스트",
        source_trust="D",
        raw_file="raw/test.md",
        date="2026-06-07",
    )
    assert atoms[0]["content"] == original


@patch("pipeline.atoms.atomizer._client")
def test_atomize_text_invalid_json_raises(mock_client):
    mock_client.models.generate_content.return_value.text = "not valid json"
    with pytest.raises(ValueError, match="invalid JSON"):
        atomize_text(
            text="test", source_type="news", source_name="test",
            source_trust="D", raw_file="raw/test.md", date="2026-06-07",
        )


@patch("pipeline.atoms.atomizer._client")
def test_atomize_text_skips_empty_content(mock_client):
    mock_client.models.generate_content.return_value.text = '''[
        {"content": "", "sector": "기타", "asset": "X", "asset_level": "stock",
         "signal": "neutral", "event_type": "news", "magnitude": "minor",
         "content_type": "fact", "validity_type": "permanent", "validity_until": null},
        {"content": "유효한 원자 내용.", "sector": "반도체", "asset": "삼성",
         "asset_level": "stock", "signal": "bullish", "event_type": "news",
         "magnitude": "minor", "content_type": "fact", "validity_type": "permanent",
         "validity_until": null}
    ]'''
    atoms = atomize_text(
        text="test", source_type="news", source_name="test",
        source_trust="D", raw_file="raw/test.md", date="2026-06-07",
    )
    assert len(atoms) == 1
    assert atoms[0]["content"] == "유효한 원자 내용."
