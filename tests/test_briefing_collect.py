import sys, sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_collect import recent_news_headlines, recent_market_atoms


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
