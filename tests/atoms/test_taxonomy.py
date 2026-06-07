from pipeline.atoms.taxonomy import (
    SIGNAL_TYPES, EVENT_TYPES, ASSET_LEVELS,
    CONTENT_TYPES, SECTOR_LIST
)

def test_signal_types_complete():
    assert "bullish" in SIGNAL_TYPES
    assert "bearish" in SIGNAL_TYPES
    assert "conflict" in SIGNAL_TYPES

def test_no_duplicates():
    assert len(SIGNAL_TYPES) == len(set(SIGNAL_TYPES))
    assert len(EVENT_TYPES) == len(set(EVENT_TYPES))

def test_sector_list_has_major_sectors():
    for sector in ["반도체", "조선", "로봇", "방산"]:
        assert sector in SECTOR_LIST
