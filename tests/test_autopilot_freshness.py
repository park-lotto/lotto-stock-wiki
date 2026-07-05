import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from autopilot_freshness import (
    latest_dates_by_channel, classify_channel, check_all_channels, anomalies_only,
)


def _resolve(name):
    mapping = {"독학주식첵터정리": "독학주식", "그로스리서치": "그로스리서치",
               "하나차이나": "하나차이나"}
    return mapping.get(name)


def test_latest_dates_by_channel_matches_display_name_prefix(tmp_path):
    (tmp_path / "2026-07-04_독학주식첵터정리.md").write_text("x", encoding="utf-8")
    (tmp_path / "2026-07-05_독학주식첵터정리.md").write_text("x", encoding="utf-8")
    latest = latest_dates_by_channel(str(tmp_path), _resolve)
    assert latest["독학주식"] == "2026-07-05"


def test_latest_dates_by_channel_ignores_unresolved_display_names(tmp_path):
    (tmp_path / "2026-07-05_듣보채널.md").write_text("x", encoding="utf-8")
    assert latest_dates_by_channel(str(tmp_path), _resolve) == {}


def test_classify_channel_never_synced_when_no_raw_file():
    result = classify_channel("그로쓰리서치특징주", None, "2026-07-05")
    assert result["status"] == "never_synced"
    assert result["days_stale"] is None


def test_classify_channel_stale_beyond_default_threshold():
    result = classify_channel("실시간주식뉴스", "2026-07-03", "2026-07-05")
    assert result["status"] == "stale"
    assert result["days_stale"] == 2


def test_classify_channel_ok_within_threshold():
    result = classify_channel("하나차이나", "2026-07-04", "2026-07-05")
    assert result["status"] == "ok"
    assert result["days_stale"] == 1


def test_classify_channel_respects_custom_freshness_days():
    result = classify_channel("주공고급수집", "2026-07-01", "2026-07-05", freshness_days=5)
    assert result["status"] == "ok"  # gap=4 <= 5


def test_check_all_channels_skips_excluded(tmp_path):
    config = {"하나차이나": {}, "투경현황": {}}
    (tmp_path / "2026-07-05_하나차이나.md").write_text("x", encoding="utf-8")
    results = check_all_channels(str(tmp_path), config, _resolve, "2026-07-05",
                                  excluded={"투경현황"})
    assert [r["channel"] for r in results] == ["하나차이나"]


def test_check_all_channels_uses_config_freshness_days(tmp_path):
    config = {"주공고급수집": {"freshness_days": 5}}
    (tmp_path / "2026-07-01_주공고급수집.md").write_text("x", encoding="utf-8")

    def resolve(name):
        return "주공고급수집" if name == "주공고급수집" else None

    results = check_all_channels(str(tmp_path), config, resolve, "2026-07-05")
    assert results[0]["status"] == "ok"


def test_anomalies_only_filters_ok():
    results = [
        {"channel": "a", "status": "ok"},
        {"channel": "b", "status": "stale"},
        {"channel": "c", "status": "never_synced"},
    ]
    assert [r["channel"] for r in anomalies_only(results)] == ["b", "c"]
