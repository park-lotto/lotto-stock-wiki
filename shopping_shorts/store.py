"""SQLite 수집 이력 저장소."""
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    shortcode TEXT NOT NULL,
                    username TEXT,
                    comments INTEGER,
                    delta INTEGER
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_shortcode ON snapshots(shortcode, id)")

    def prev_comments(self, shortcode):
        """가장 최근에 기록된 이 영상의 댓글수. 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT comments FROM snapshots WHERE shortcode=? ORDER BY id DESC LIMIT 1",
                (shortcode,),
            ).fetchone()
        return row[0] if row else None

    def prev_delta(self, shortcode):
        """가장 최근에 기록된 이 영상의 Δ. 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT delta FROM snapshots WHERE shortcode=? ORDER BY id DESC LIMIT 1",
                (shortcode,),
            ).fetchone()
        return row[0] if row else None

    def save_run(self, run_date, rows):
        """이번 수집 스냅샷 저장. rows: [{shortcode, username, comments, delta}]."""
        with self._conn() as c:
            c.executemany(
                "INSERT INTO snapshots(run_date, shortcode, username, comments, delta) "
                "VALUES(?,?,?,?,?)",
                [(run_date, r["shortcode"], r["username"], r["comments"], r["delta"]) for r in rows],
            )
