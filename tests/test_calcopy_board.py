import json
from shopping_shorts.calcopy_board import collect


def _w(root, slug, data):
    p = root / "channel" / slug
    p.mkdir(parents=True)
    (p / "calcopy.json").write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def test_collect_counts_and_current(tmp_path):
    _w(tmp_path, "a", {"name": "A", "steps": {"1": {"state": "done", "date": "2026-10-01"},
                                             "2": {"state": "blocked", "date": "2026-10-02"}}})
    d = collect(tmp_path)
    c = d["channels"][0]
    assert (c["done"], c["current"], c["blocked"], c["updated"]) == (1, "2", True, "2026-10-02")
    assert c["steps"]["7"]["state"] == "todo"


def test_collect_reports_broken_ledger(tmp_path):
    _w(tmp_path, "bad", "{not json")
    d = collect(tmp_path)
    assert d["channels"] == [] and d["errors"][0]["slug"] == "bad"


def test_unknown_state_becomes_todo(tmp_path):
    _w(tmp_path, "x", {"steps": {"1": {"state": "finished"}}})
    assert collect(tmp_path)["channels"][0]["steps"]["1"]["state"] == "todo"
