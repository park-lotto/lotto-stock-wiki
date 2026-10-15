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


from shopping_shorts import calcopy_board as B
import pytest


def test_slug_of_korean_handle_and_channel_id():
    assert B.slug_of("https://www.youtube.com/@%EC%8D%B0%ED%92%80%EB%8B%A4") == "썰풀다"
    assert B.slug_of("https://www.youtube.com/channel/UCL12SCB2y7J-KX0_ghAf-xQ") == "UCL12SCB2y7J-KX0_ghAf-xQ"
    with pytest.raises(ValueError):
        B.slug_of("아무말")


def test_add_update_style_roundtrip(tmp_path):
    def bad(url):
        raise RuntimeError("키 없음")
    c = B.add_channel("https://www.youtube.com/@썰풀다", tags=["썰"], resolver=bad, data_dir=tmp_path)
    assert c["status"] == "후보" and "키 없음" in c["resolve_error"]   # 수치 실패는 저장을 막지 않고 드러낸다
    with pytest.raises(ValueError):
        B.add_channel("https://www.youtube.com/@썰풀다", data_dir=tmp_path)
    B.update_channel("썰풀다", {"status": "진행", "memo": "m"}, data_dir=tmp_path)
    with pytest.raises(ValueError):
        B.update_channel("썰풀다", {"status": "엉뚱"}, data_dir=tmp_path)
    B.set_style("썰풀다", "역할극형", rename="역할극", confirmed=True, data_dir=tmp_path)
    d = B._store_load(tmp_path)["썰풀다"]
    assert d["status"] == "진행" and d["styles"]["역할극형"] == {**d["styles"]["역할극형"], "rename": "역할극", "confirmed": True}


def test_detail_applies_human_style(tmp_path):
    root = tmp_path / "repo"; ch = root / "channel" / "x"; ch.mkdir(parents=True)
    (ch / "갈래.json").write_text(json.dumps({"styles": [{"name": "A형", "n": 1, "views_median": 5, "views_max": 5,
                                                          "from_labels": [], "ids": ["v1"]}]}), encoding="utf-8")
    (ch / "1차분석_편별.json").write_text(json.dumps([{"id": "v1", "views": 5, "title": "t", "voice": "TTS"}]), encoding="utf-8")
    B.set_style("x", "A형", rename="에이", confirmed=True, data_dir=tmp_path)
    d = B.detail("x", root=root, data_dir=tmp_path)
    assert d["styles"][0]["label"] == "에이" and d["styles"][0]["confirmed"] and d["styles"][0]["videos"][0]["id"] == "v1"
