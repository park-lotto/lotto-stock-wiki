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

def test_tiktok_daily_count_starts_at_zero_and_bumps(tmp_path):
    """하루 수집 횟수: 처음 0, bump할 때마다 1씩 증가한 새 값 반환(남용 방지 카운터)."""
    s = Store(tmp_path / "t.db")
    assert s.tiktok_daily_count(1, "2026-07-14") == 0
    assert s.bump_tiktok_daily(1, "2026-07-14") == 1
    assert s.bump_tiktok_daily(1, "2026-07-14") == 2
    assert s.tiktok_daily_count(1, "2026-07-14") == 2


def test_tiktok_daily_count_isolated_by_customer_and_day(tmp_path):
    """카운터는 (고객, 날짜)별로 격리 — 다른 고객·다른 날짜는 서로 영향 없음."""
    s = Store(tmp_path / "t.db")
    s.bump_tiktok_daily(1, "2026-07-14")
    s.bump_tiktok_daily(1, "2026-07-14")
    assert s.tiktok_daily_count(2, "2026-07-14") == 0   # 다른 고객
    assert s.tiktok_daily_count(1, "2026-07-15") == 0   # 다른 날짜
    assert s.tiktok_daily_count(1, "2026-07-14") == 2


def test_tiktok_month_spend_accumulates(tmp_path):
    """월 예산 누적: 처음 0.0, add할 때마다 누적 달러 반환. 월 경계는 키가 달라 자동 리셋."""
    s = Store(tmp_path / "t.db")
    assert s.tiktok_month_spend("2026-07") == 0.0
    assert s.add_tiktok_spend("2026-07", 0.05) == 0.05
    assert round(s.add_tiktok_spend("2026-07", 0.10), 2) == 0.15
    assert s.tiktok_month_spend("2026-08") == 0.0   # 새 달 = 새 예산
    assert round(s.tiktok_month_spend("2026-07"), 2) == 0.15


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


def test_save_script_with_category_and_structure_backfill(tmp_path):
    from shopping_shorts.store import Store
    s = Store(tmp_path / "t.db")
    s.save_script("SC1", {"full_text": "안녕하세요 대본", "segments": []}, category="레시피")
    got = s.get_extract("SC1")
    assert got["full_text"] == "안녕하세요 대본"
    assert got["category"] == "레시피"
    assert got["structure"] is None  # 아직 구조분석 전

    missing = s.extracts_missing_structure(limit=10)
    assert any(m["shortcode"] == "SC1" and m["category"] == "레시피" for m in missing)

    s.save_extract_structure("SC1", {"hook_type": "경고형", "tone": "친근한 수다체"})
    got2 = s.get_extract("SC1")
    assert got2["structure"]["hook_type"] == "경고형"
    missing2 = s.extracts_missing_structure(limit=10)
    assert not any(m["shortcode"] == "SC1" for m in missing2)


def test_save_script_without_category_is_backward_compatible(tmp_path):
    from shopping_shorts.store import Store
    s = Store(tmp_path / "t2.db")
    s.save_script("SC2", {"full_text": "카테고리 없이", "segments": []})
    got = s.get_extract("SC2")
    assert got["category"] is None
    assert got["full_text"] == "카테고리 없이"


def test_element_raw_values_extracts_characters_and_plain_fields(tmp_path):
    from shopping_shorts.store import Store
    s = Store(tmp_path / "t3.db")
    s.save_script("SC1", {"full_text": "t1"}, category="레시피")
    s.save_extract_structure("SC1", {
        "hook_type": "경고형",
        "characters": [{"who": "엄마", "role": "엄마가 알려준 노하우"}, {"who": "언니", "role": "언니네 집 팁"}],
        "tone": "친근한 반말",
    })
    s.save_script("SC2", {"full_text": "t2"}, category="레시피")
    s.save_extract_structure("SC2", {"hook_type": "반전형", "characters": [], "tone": ""})

    chars = s.element_raw_values("레시피", "characters")
    assert chars == ["엄마가 알려준 노하우", "언니네 집 팁"]

    hooks = s.element_raw_values("레시피", "hook")
    assert hooks == ["경고형", "반전형"]

    tones = s.element_raw_values("레시피", "tone")
    assert tones == ["친근한 반말"]  # 빈 문자열은 제외


def test_element_category_stats_roundtrip(tmp_path):
    from shopping_shorts.store import Store
    s = Store(tmp_path / "t4.db")
    cats = [{"label": "가족관계", "description": "d1", "examples": ["e1", "e2"]},
            {"label": "전문가", "description": "d2", "examples": ["e3"]}]
    s.save_element_category_stats("레시피", "characters", cats)

    opts = s.get_element_options("레시피")
    assert [c["label"] for c in opts["characters"]] == ["가족관계", "전문가"]
    assert opts.get("tone", []) == []  # 아직 저장 안 한 요소는 빈 리스트

    detail = s.get_category_detail("레시피", "characters", "전문가")
    assert detail["description"] == "d2"
    assert detail["examples"] == ["e3"]

    # 재계산은 기존 값을 덮어쓴다(누적 아님)
    s.save_element_category_stats("레시피", "characters", [
        {"label": "지인동료", "description": "d3", "examples": []}])
    opts2 = s.get_element_options("레시피")
    assert [c["label"] for c in opts2["characters"]] == ["지인동료"]


def test_distinct_extract_categories(tmp_path):
    from shopping_shorts.store import Store
    s = Store(tmp_path / "t5.db")
    s.save_script("SC1", {"full_text": "t"}, category="레시피")
    s.save_script("SC2", {"full_text": "t"}, category="뷰티")
    s.save_script("SC3", {"full_text": "t"}, category="레시피")
    s.save_script("SC4", {"full_text": "t"})  # category 없음 — 제외
    assert sorted(s.distinct_extract_categories()) == ["레시피", "뷰티"]
