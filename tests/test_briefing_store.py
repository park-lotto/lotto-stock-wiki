import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_store import load_briefing, append_briefing_item, set_insight


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


def test_load_briefing_missing_file_includes_null_insight(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    d = load_briefing(p)
    assert d["insight"] is None


def test_load_briefing_backward_compat_with_items_only_file(tmp_path):
    """기존(이번 태스크 전) 파일은 insight 키가 아예 없다 — 읽을 때 None으로 채워져야 함."""
    p = tmp_path / "market_briefing.json"
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    p.write_text(json.dumps({"date": today, "items": [
        {"ts": "09:00", "severity": "gray", "headline": "테스트", "body": None, "kind": "raw_alert"}
    ]}), encoding="utf-8")
    d = load_briefing(str(p))
    assert d["insight"] is None
    assert len(d["items"]) == 1


def test_set_insight_writes_without_touching_items(tmp_path):
    p = str(tmp_path / "market_briefing.json")
    append_briefing_item(p, {"ts": "09:00", "severity": "gray",
                              "headline": "속보", "body": None, "kind": "raw_alert"})
    insight_obj = {"ts": "11:50", "comment": "오늘 코스피 급락 후 반등",
                   "movers": "삼성전자, SK하이닉스"}
    d = set_insight(p, insight_obj)
    assert d["insight"] == insight_obj
    assert len(d["items"]) == 1
    with open(p, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["insight"] == insight_obj
    assert len(on_disk["items"]) == 1


def test_set_insight_resets_on_new_day_like_items(tmp_path):
    p = tmp_path / "market_briefing.json"
    stale = {"date": "2020-01-01", "insight": {"ts": "09:00", "comment": "옛날", "movers": "x"},
             "items": [{"ts": "09:00", "severity": "gray", "headline": "옛날꺼",
                        "body": None, "kind": "raw_alert"}]}
    p.write_text(json.dumps(stale), encoding="utf-8")
    d = set_insight(str(p), {"ts": "09:00", "comment": "오늘", "movers": "y"})
    assert d["insight"]["comment"] == "오늘"
    assert d["items"] == []
