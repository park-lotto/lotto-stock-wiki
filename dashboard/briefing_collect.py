"""브리핑 종합층 입력 재료 수집 — 기존 news_feed/atoms.db를 읽기만, 신규 크롤링 없음."""
import sqlite3
from datetime import datetime


def recent_news_headlines(news_feed_data: dict | None, limit: int = 5) -> list[str]:
    if not news_feed_data:
        return []
    out = []
    for sector in news_feed_data.get("sectors") or []:
        for n in sector.get("news") or []:
            if n.get("title"):
                out.append(n["title"])
        for stock in sector.get("stocks") or []:
            for n in stock.get("news") or []:
                if n.get("title"):
                    out.append(n["title"])
    return out[:limit]


def recent_market_atoms(db_path: str, limit: int = 5) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT content FROM atoms
               WHERE date = ? AND (signal IN ('bullish','bearish','catalyst','risk')
                                    OR asset_level = 'market')
               ORDER BY created_at DESC LIMIT ?""",
            (today, limit),
        ).fetchall()
        conn.close()
        return [r["content"] for r in rows]
    except Exception:
        return []
