import sys, sqlite3
from pathlib import Path
from datetime import datetime

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_collect import recent_news_headlines, recent_market_atoms, recent_topick_mentions


def test_recent_news_headlines_none_returns_empty():
    assert recent_news_headlines(None) == []


def test_recent_news_headlines_flattens_sector_and_stock_news():
    data = {"sectors": [
        {"news": [{"title": "반도체 훈풍"}, {"title": "메모리 가격 상승"}],
         "stocks": [{"news": [{"title": "삼성전자 목표가 상향"}]}]},
        {"news": [{"title": "2차전지 조정"}], "stocks": []},
    ]}
    out = recent_news_headlines(data, limit=10)
    assert "반도체 훈풍" in out
    assert "삼성전자 목표가 상향" in out
    assert "2차전지 조정" in out


def test_recent_news_headlines_respects_limit():
    data = {"sectors": [{"news": [{"title": f"뉴스{i}"} for i in range(20)], "stocks": []}]}
    assert len(recent_news_headlines(data, limit=3)) == 3


def _mk_atoms_db(tmp_path):
    db_path = str(tmp_path / "atoms.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE atoms (
        id TEXT PRIMARY KEY, date TEXT, signal TEXT, asset_level TEXT,
        content TEXT, source_name TEXT, created_at TEXT)""")
    today = datetime.now().strftime("%Y-%m-%d")
    rows = [
        ("a1", today, "bullish", "sector", "반도체 강세 지속", "src", "2026-07-03T09:10:00"),
        ("a2", today, "neutral", "stock", "무관한 잡담", "src", "2026-07-03T09:11:00"),
        ("a3", today, "risk", "market", "코스닥 급락 위험", "src", "2026-07-03T09:12:00"),
        ("a4", "2020-01-01", "bullish", "market", "옛날 원자", "src", "2020-01-01T09:00:00"),
    ]
    conn.executemany("INSERT INTO atoms VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return db_path


def test_recent_market_atoms_filters_signal_and_date(tmp_path):
    db_path = _mk_atoms_db(tmp_path)
    out = recent_market_atoms(db_path, limit=10)
    assert "반도체 강세 지속" in out
    assert "코스닥 급락 위험" in out
    assert "무관한 잡담" not in out
    assert "옛날 원자" not in out


def test_recent_market_atoms_respects_limit(tmp_path):
    db_path = _mk_atoms_db(tmp_path)
    out = recent_market_atoms(db_path, limit=1)
    assert len(out) == 1


def test_recent_market_atoms_closes_connection_on_query_failure(tmp_path, monkeypatch):
    """쿼리가 실패해도(테이블 없음 등) conn.close()가 실제로 호출됐는지 검증.
    파일락 방식은 SQLite SELECT가 기본적으로 락을 안 잡아서 버그 있는 코드에서도
    통과해버려 신뢰 불가 — sqlite3.connect를 가로채서 진짜 커넥션 객체가
    닫혔는지(닫힌 커넥션에 쿼리하면 ProgrammingError) 직접 확인한다."""
    import sqlite3 as _sqlite3
    import briefing_collect

    db_path = str(tmp_path / "broken.db")
    conn = _sqlite3.connect(db_path)
    conn.execute("CREATE TABLE not_atoms (x TEXT)")
    conn.commit()
    conn.close()

    captured = {}
    real_connect = _sqlite3.connect

    def _spy_connect(*args, **kwargs):
        c = real_connect(*args, **kwargs)
        captured["conn"] = c
        return c

    monkeypatch.setattr(briefing_collect.sqlite3, "connect", _spy_connect)

    out = briefing_collect.recent_market_atoms(db_path, limit=5)
    assert out == []

    assert "conn" in captured, "recent_market_atoms가 sqlite3.connect를 호출하지 않음"
    with pytest.raises(_sqlite3.ProgrammingError):
        captured["conn"].execute("SELECT 1")


from briefing_collect import pick_notable_movers, recent_atoms_for_stock


def test_pick_notable_movers_sorts_by_abs_change_rate():
    rank_pop = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    rank_amt = [{"code": "000660", "name": "SK하이닉스", "price": 200000, "change_rate": -4.7},
                {"code": "005380", "name": "현대차", "price": 200000, "change_rate": 0.5}]
    out = pick_notable_movers(rank_pop, rank_amt, None, n=4)
    assert [m["name"] for m in out] == ["삼성전자", "SK하이닉스", "현대차"]


def test_pick_notable_movers_dedups_by_name():
    rank_pop = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    rank_amt = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    out = pick_notable_movers(rank_pop, rank_amt, None, n=4)
    assert len(out) == 1


def test_pick_notable_movers_respects_limit_n():
    rank_pop = [{"code": str(i), "name": f"종목{i}", "price": 1000, "change_rate": float(i)}
                for i in range(10)]
    out = pick_notable_movers(rank_pop, [], None, n=3)
    assert len(out) == 3


def test_pick_notable_movers_attaches_matching_news_reason():
    rank_pop = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    news_feed_data = {"sectors": [{"news": [], "stocks": [
        {"code": "005930", "name": "삼성전자", "news": [{"title": "메모리 가격 반등 소식"}]}]}]}
    out = pick_notable_movers(rank_pop, [], news_feed_data, n=4)
    assert out[0]["news_reason"] == "메모리 가격 반등 소식"


def test_pick_notable_movers_no_match_leaves_reason_none():
    rank_pop = [{"code": "005930", "name": "삼성전자", "price": 70000, "change_rate": 6.8}]
    out = pick_notable_movers(rank_pop, [], None, n=4)
    assert out[0]["news_reason"] is None


def test_recent_atoms_for_stock_filters_by_asset_name(tmp_path):
    import sqlite3
    from datetime import datetime
    db_path = str(tmp_path / "atoms.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE atoms (
        id TEXT PRIMARY KEY, date TEXT, asset TEXT, content TEXT, created_at TEXT)""")
    today = datetime.now().strftime("%Y-%m-%d")
    conn.executemany("INSERT INTO atoms VALUES (?,?,?,?,?)", [
        ("a1", today, "삼성전자", "메모리 가격 반등", "2026-07-03T09:10:00"),
        ("a2", today, "SK하이닉스", "무관한 원자", "2026-07-03T09:11:00"),
        ("a3", "2020-01-01", "삼성전자", "옛날 원자", "2020-01-01T09:00:00"),
    ])
    conn.commit(); conn.close()

    out = recent_atoms_for_stock(db_path, "삼성전자", limit=5)
    assert out == ["메모리 가격 반등"]


def test_recent_topick_mentions_filters_by_keyword_and_source_type(tmp_path):
    import sqlite3
    from datetime import datetime
    db_path = str(tmp_path / "atoms.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE atoms (
        id TEXT PRIMARY KEY, date TEXT, asset TEXT, content TEXT,
        source_type TEXT, created_at TEXT)""")
    today = datetime.now().strftime("%Y-%m-%d")
    conn.executemany("INSERT INTO atoms VALUES (?,?,?,?,?,?)", [
        ("a1", today, "삼성SDI", "2차전지 섹터리포트 탑픽 거론", "report", "2026-07-03T08:10:00"),
        ("a2", today, "한국전력", "시황리포트 탑픽 거론", "news", "2026-07-03T08:11:00"),
        ("a3", today, "SK하이닉스", "탑픽 아닌 그냥 코멘트", "telegram", "2026-07-03T08:12:00"),
        ("a4", today, "삼성전자", "무관한 원자", "report", "2026-07-03T08:13:00"),
        ("a5", "2020-01-01", "카카오", "옛날 탑픽 거론", "report", "2020-01-01T08:00:00"),
    ])
    conn.commit(); conn.close()

    out = recent_topick_mentions(db_path, limit=2)
    assert out == [
        {"id": "a2", "asset": "한국전력", "content": "시황리포트 탑픽 거론"},
        {"id": "a1", "asset": "삼성SDI", "content": "2차전지 섹터리포트 탑픽 거론"},
    ]


def test_recent_topick_mentions_empty_when_none_match(tmp_path):
    import sqlite3
    from datetime import datetime
    db_path = str(tmp_path / "atoms.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE atoms (
        id TEXT PRIMARY KEY, date TEXT, asset TEXT, content TEXT,
        source_type TEXT, created_at TEXT)""")
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO atoms VALUES (?,?,?,?,?,?)",
                 ("a1", today, "삼성전자", "무관한 원자", "report", "2026-07-03T08:10:00"))
    conn.commit(); conn.close()

    assert recent_topick_mentions(db_path, limit=2) == []
