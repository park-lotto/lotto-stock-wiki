"""라이브 DB 읽기 전용 연결 — 잠금 대기 2초, 쓰기 금지 PRAGMA. 실패는 호출자가 회색으로 다룬다."""
import sqlite3
from shopping_shorts.config import DB_PATH as LIVE_DB


def ro_connect(path=LIVE_DB):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    conn.execute("PRAGMA query_only=1")
    conn.row_factory = sqlite3.Row
    return conn
