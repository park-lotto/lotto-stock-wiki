import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "pipeline" / "atoms" / "atoms.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_TG_COLUMNS = [
    ("stance_key", "TEXT"),
    ("mention_channels", "TEXT"),
    ("mention_count", "INTEGER DEFAULT 1"),
    ("msg_ts", "TEXT"),
]


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    migrate_db()


def migrate_db():
    """기존 DB에 텔레그램 필드 멱등 추가 (이미 있으면 무시)."""
    conn = get_conn()
    for name, decl in _TG_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE atoms ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass  # 이미 존재
    conn.commit()
    conn.close()


def insert_atom(atom: dict) -> str:
    a = dict(atom)
    if isinstance(a.get("relations"), list):
        a["relations"] = json.dumps(a["relations"], ensure_ascii=False)
    a.setdefault("created_at", datetime.now().isoformat())
    a.setdefault("stance_key", None)
    a.setdefault("mention_count", 1)
    a.setdefault("msg_ts", None)
    mc = a.get("mention_channels")
    a["mention_channels"] = json.dumps(mc, ensure_ascii=False) if isinstance(mc, list) else mc
    conn = get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO atoms
        (id, date, source_type, source_name, source_trust, raw_file,
         layer, sector, asset, asset_level,
         signal, event_type, magnitude, content_type, strength_score,
         validity_type, validity_until, is_active,
         content, relations, created_at,
         stance_key, mention_channels, mention_count, msg_ts)
        VALUES
        (:id, :date, :source_type, :source_name, :source_trust, :raw_file,
         :layer, :sector, :asset, :asset_level,
         :signal, :event_type, :magnitude, :content_type, :strength_score,
         :validity_type, :validity_until, :is_active,
         :content, :relations, :created_at,
         :stance_key, :mention_channels, :mention_count, :msg_ts)
        """,
        a,
    )
    conn.commit()
    conn.close()
    return a["id"]


def query_atoms(
    sector: Optional[str] = None,
    signal: Optional[str] = None,
    asset: Optional[str] = None,
    layer: Optional[str] = None,
    days: int = 7,
    limit: int = 50,
    active_only: bool = True,
) -> list[dict]:
    conditions = ["date >= date('now', ? || ' days')"]
    params: list = [f"-{days}"]

    if active_only:
        conditions.append("is_active = 1")
    if sector:
        conditions.append("sector = ?")
        params.append(sector)
    if signal:
        conditions.append("signal = ?")
        params.append(signal)
    if asset:
        conditions.append("asset LIKE ?")
        params.append(f"%{asset}%")
    if layer:
        conditions.append("layer = ?")
        params.append(layer)

    sql = (
        f"SELECT * FROM atoms WHERE {' AND '.join(conditions)} "
        f"ORDER BY date DESC, strength_score DESC LIMIT ?"
    )
    params.append(limit)
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("relations"):
            try:
                d["relations"] = json.loads(d["relations"])
            except (json.JSONDecodeError, TypeError):
                d["relations"] = []
        else:
            d["relations"] = []
        result.append(d)
    return result


def expire_atoms() -> int:
    conn = get_conn()
    conn.execute(
        """
        UPDATE atoms
        SET is_active = 0, updated_at = ?
        WHERE validity_until IS NOT NULL
          AND validity_until < date('now')
          AND is_active = 1
        """,
        [datetime.now().isoformat()],
    )
    count = conn.total_changes
    conn.commit()
    conn.close()
    return count


def get_atom_count(active_only: bool = False) -> int:
    conn = get_conn()
    sql = "SELECT COUNT(*) FROM atoms"
    if active_only:
        sql += " WHERE is_active = 1"
    count = conn.execute(sql).fetchone()[0]
    conn.close()
    return count
