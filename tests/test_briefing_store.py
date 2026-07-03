import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_store import load_briefing, append_briefing_item


def test_load_briefing_missing_file_returns_empty_today(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    from datetime import datetime
    d = load_briefing(p)
    assert d["date"] == datetime.now().strftime("%Y-%m-%d")
    assert d["items"] == []


def test_append_briefing_item_writes_and_prepends(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    item1 = {"ts": "09:00", "severity": "gray", "headline": "첫 항목", "body": None, "kind": "raw_alert"}
    item2 = {"ts": "09:05", "severity": "red", "headline": "두번째", "body": "설명", "kind": "ai_brief"}
    append_briefing_item(p, item1)
    d = append_briefing_item(p, item2)
    assert [x["headline"] for x in d["items"]] == ["두번째", "첫 항목"]
    with open(p, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert [x["headline"] for x in on_disk["items"]] == ["두번째", "첫 항목"]


def test_append_briefing_item_caps_at_200(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    for i in range(205):
        d = append_briefing_item(p, {"ts": "09:00", "severity": "gray",
                                      "headline": f"item{i}", "body": None, "kind": "raw_alert"})
    assert len(d["items"]) == 200
    assert d["items"][0]["headline"] == "item204"   # 최신이 맨 앞


def test_append_briefing_item_resets_on_new_day(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    stale = {"date": "2020-01-01", "items": [
        {"ts": "09:00", "severity": "gray", "headline": "옛날꺼", "body": None, "kind": "raw_alert"}]}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(stale, f, ensure_ascii=False)
    d = append_briefing_item(p, {"ts": "09:00", "severity": "gray",
                                  "headline": "오늘꺼", "body": None, "kind": "raw_alert"})
    assert len(d["items"]) == 1
    assert d["items"][0]["headline"] == "오늘꺼"
