import json
import sqlite3
from shopping_shorts.store import Store


def test_prev_comments_empty(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.prev_comments("abc") is None  # 이력 없으면 None

def test_save_and_prev(tmp_path):
    s = Store(tmp_path / "t.db")
    # 1차 수집
    s.save_run("2026-07-08", [
        {"shortcode": "abc", "username": "u1", "comments": 600, "delta": 0},
    ])
    # 다음 수집 시 직전값 조회
    assert s.prev_comments("abc") == 600
    # 2차 수집
    s.save_run("2026-07-09", [
        {"shortcode": "abc", "username": "u1", "comments": 1400, "delta": 800},
    ])
    assert s.prev_comments("abc") == 1400  # 가장 최근값

def test_prev_deltas_for_acceleration(tmp_path):
    s = Store(tmp_path / "t.db")
    s.save_run("2026-07-08", [{"shortcode": "x", "username": "u", "comments": 200, "delta": 200}])
    s.save_run("2026-07-09", [{"shortcode": "x", "username": "u", "comments": 500, "delta": 300}])
    assert s.prev_delta("x") == 300  # 직전 Δ (가속 계산용)

def test_comment_drafts_roundtrip(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.get_drafts("sc1") == []
    s.save_drafts("sc1", ["댓글A", "댓글B", "댓글C"])
    assert s.get_drafts("sc1") == ["댓글A", "댓글B", "댓글C"]
    s.save_drafts("sc1", ["새댓글"])
    assert s.get_drafts("sc1") == ["새댓글"]

def test_drafts_bulk_map(tmp_path):
    s = Store(tmp_path / "t.db")
    s.save_drafts("a", ["x"])
    s.save_drafts("b", ["y", "z"])
    m = s.drafts_map(["a", "b", "c"])
    assert m["a"] == ["x"] and m["b"] == ["y", "z"]
    assert m.get("c", []) == []

def test_commented_mark_and_query(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.commented_set() == set()
    s.mark_commented("sc1")
    s.mark_commented("sc1")
    s.mark_commented("sc2")
    assert s.commented_set() == {"sc1", "sc2"}

def test_saved_mark_and_query(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.saved_set() == set()
    s.mark_saved("sc1")
    s.mark_saved("sc1")
    s.mark_saved("sc2")
    assert s.saved_set() == {"sc1", "sc2"}

def test_last_run_empty(tmp_path):
    s = Store(tmp_path / "t.db")
    items, collected_at = s.load_last_run()
    assert items == []
    assert collected_at is None

def test_last_run_roundtrip(tmp_path):
    s = Store(tmp_path / "t.db")
    data = [{"shortcode": "a", "name": "채널", "thumbnail": "t.jpg", "comments": 5}]
    s.save_last_run(data, "2026-07-09T10:00:00")
    items, collected_at = s.load_last_run()
    assert items == data
    assert collected_at == "2026-07-09T10:00:00"

def test_last_run_overwrites(tmp_path):
    s = Store(tmp_path / "t.db")
    s.save_last_run([{"shortcode": "a"}], "t1")
    s.save_last_run([{"shortcode": "b"}, {"shortcode": "c"}], "t2")
    items, collected_at = s.load_last_run()
    assert len(items) == 2
    assert collected_at == "t2"


def test_save_and_get_source_analysis(tmp_path):
    s = Store(tmp_path / "t.db")
    s.save_source_analysis(
        "sc1",
        keywords={"ko": ["바닥 청소"], "en": ["floor cleaner"], "zh": ["地板清洁剂"]},
        frame_paths=["/tmp/f1.jpg", "/tmp/f2.jpg"],
        analyzed_at="2026-07-09T00:00:00Z",
    )
    result = s.get_source_analysis("sc1")
    assert result["keywords"]["ko"] == ["바닥 청소"]
    assert result["frame_paths"] == ["/tmp/f1.jpg", "/tmp/f2.jpg"]


def test_get_source_analysis_missing_returns_none(tmp_path):
    s = Store(tmp_path / "t.db")
    assert s.get_source_analysis("nope") is None


def test_save_and_get_candidates(tmp_path):
    s = Store(tmp_path / "t.db")
    ids = s.save_candidates("sc1", "youtube", [
        {"url": "https://youtu.be/a", "title": "제목1", "thumbnail": "t1.jpg"},
        {"url": "https://youtu.be/b", "title": "제목2", "thumbnail": "t2.jpg"},
    ])
    assert len(ids) == 2
    candidates = s.get_candidates("sc1")
    assert len(candidates) == 2
    assert candidates[0]["platform"] == "youtube"
    assert candidates[0]["similarity_score"] is None
    assert candidates[0]["source_lang"] is None  # source_lang 안 준 경우


def test_save_candidates_stores_source_lang(tmp_path):
    """검색에 쓰인 언어를 저장해 해외원본/국내재편집 배지 판단에 쓴다(2026-07-10)."""
    s = Store(tmp_path / "t.db")
    s.save_candidates("sc1", "tiktok", [
        {"url": "https://tiktok.com/a", "title": "t", "thumbnail": "", "source_lang": "en"},
    ])
    candidates = s.get_candidates("sc1")
    assert candidates[0]["source_lang"] == "en"


def test_update_candidate_score(tmp_path):
    s = Store(tmp_path / "t.db")
    ids = s.save_candidates("sc1", "youtube", [{"url": "u", "title": "t", "thumbnail": ""}])
    s.update_candidate_score(ids[0], 0.87)
    candidates = s.get_candidates("sc1")
    assert candidates[0]["similarity_score"] == 0.87


def test_save_to_pool_and_pool_items(tmp_path):
    s = Store(tmp_path / "t.db")
    ids = s.save_candidates("sc1", "youtube", [{"url": "u", "title": "t", "thumbnail": ""}])
    s.save_to_pool("sc1", ids[0])
    pool = s.pool_items()
    assert len(pool) == 1
    assert pool[0]["origin_shortcode"] == "sc1"
    assert pool[0]["url"] == "u"
