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
    except Exception:
        return []
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT content FROM atoms
               WHERE date = ? AND (signal IN ('bullish','bearish','catalyst','risk')
                                    OR asset_level = 'market')
               ORDER BY created_at DESC LIMIT ?""",
            (today, limit),
        ).fetchall()
        return [r["content"] for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def pick_notable_movers(rank_pop: list, rank_amt: list, news_feed_data: dict | None,
                          n: int = 4) -> list[dict]:
    """market_flow 순위 데이터에서 오늘 특징적으로 움직인 종목 상위 n개.
    news_feed_data가 있으면 같은 종목명의 뉴스 제목을 이유로 붙인다(없으면 None —
    종합층 프롬프트가 이유 없다고 명시하거나 수급 관점으로 설명하게 됨)."""
    stock_news: dict[str, str] = {}
    if news_feed_data:
        for sector in news_feed_data.get("sectors") or []:
            for stock in sector.get("stocks") or []:
                name = stock.get("name")
                news_list = stock.get("news") or []
                if name and news_list and news_list[0].get("title"):
                    stock_news[name] = news_list[0]["title"]

    seen: dict[str, dict] = {}
    for item in (rank_pop or []) + (rank_amt or []):
        name = item.get("name")
        if not name or name in seen:
            continue
        seen[name] = {
            "name": name,
            "change_rate": item.get("change_rate", 0.0),
            "news_reason": stock_news.get(name),
        }

    ranked = sorted(seen.values(), key=lambda m: abs(m["change_rate"]), reverse=True)
    return ranked[:n]


def recent_atoms_for_stock(db_path: str, stock_name: str, limit: int = 1) -> list[str]:
    """특정 종목명을 오늘자 원자(asset 컬럼)에서 매칭 — 텔레그램/리포트/유튜브에서
    그 종목을 언급한 최신 원자. recent_market_atoms와 같은 연결관리 패턴."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(db_path)
    except Exception:
        return []
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT content FROM atoms
               WHERE date = ? AND asset = ?
               ORDER BY created_at DESC LIMIT ?""",
            (today, stock_name, limit),
        ).fetchall()
        return [r["content"] for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def recent_topick_mentions(db_path: str, limit: int = 2) -> list[dict]:
    """오늘자 리포트/뉴스 원자 중 '탑픽' 언급된 것 — 종목명+내용. 없으면 빈 리스트.
    recent_market_atoms/recent_atoms_for_stock과 같은 연결관리 패턴."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(db_path)
    except Exception:
        return []
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT asset, content FROM atoms
               WHERE date = ? AND content LIKE '%탑픽%'
                     AND source_type IN ('report', 'news')
                     AND asset IS NOT NULL AND asset != ''
               ORDER BY created_at DESC LIMIT ?""",
            (today, limit),
        ).fetchall()
        return [{"asset": r["asset"], "content": r["content"]} for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
