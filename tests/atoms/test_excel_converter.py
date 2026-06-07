import pytest
import pandas as pd
from pipeline.atoms.excel_converter import oscillator_to_atoms, consensus_to_atoms


@pytest.fixture
def oscillator_excel(tmp_path):
    df = pd.DataFrame({
        "종목명": ["SK하이닉스", "삼성전자", "에코프로"],
        "오실레이터": [73.0, -20.0, 5.0],
    })
    path = tmp_path / "oscillator.xlsx"
    df.to_excel(path, index=False)
    return str(path)


@pytest.fixture
def consensus_excel(tmp_path):
    df = pd.DataFrame({
        "종목명": ["삼성전자", "LG에너지솔루션"],
        "섹터": ["반도체", "2차전지"],
        "컨센변화": ["+15%", "-8%"],
        "TP": ["100000", "450000"],
    })
    path = tmp_path / "consensus.xlsx"
    df.to_excel(path, index=False)
    return str(path)


def test_positive_oscillator_is_bullish(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    sk = next(a for a in atoms if a["asset"] == "SK하이닉스")
    assert sk["signal"] == "bullish"
    assert sk["event_type"] == "supply"
    assert "73" in sk["content"]


def test_negative_oscillator_is_bearish(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    samsung = next(a for a in atoms if a["asset"] == "삼성전자")
    assert samsung["signal"] == "bearish"


def test_oscillator_above_50_is_major(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    sk = next(a for a in atoms if a["asset"] == "SK하이닉스")
    assert sk["magnitude"] == "major"


def test_oscillator_validity_is_one_week(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    assert all(a["validity_until"] == "2026-06-14" for a in atoms)
    assert all(a["validity_type"] == "date" for a in atoms)


def test_oscillator_content_type_is_data(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    assert all(a["content_type"] == "data" for a in atoms)


def test_oscillator_source_trust_is_a(oscillator_excel):
    atoms = oscillator_to_atoms(oscillator_excel, "2026-06-07")
    assert all(a["source_trust"] == "A" for a in atoms)


def test_consensus_positive_is_bullish(consensus_excel):
    atoms = consensus_to_atoms(consensus_excel, "2026-06-07")
    samsung = next(a for a in atoms if a["asset"] == "삼성전자")
    assert samsung["signal"] == "bullish"
    assert samsung["event_type"] == "consensus"


def test_consensus_negative_is_bearish(consensus_excel):
    atoms = consensus_to_atoms(consensus_excel, "2026-06-07")
    lg = next(a for a in atoms if a["asset"] == "LG에너지솔루션")
    assert lg["signal"] == "bearish"
