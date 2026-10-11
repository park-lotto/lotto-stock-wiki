"""후기 게시판·무료 자료실 — 저장(관제 179). 표 3개: 글 · 첨부 · 닉네임.

판단은 여기 없다(board.py). 여기는 읽고 쓰기만 한다.
연결은 Store._conn() 을 빌린다 — WAL·busy_timeout 설정이 한 곳에 있다(0순위-B).
"""
import sqlite3
import threading
from datetime import datetime, timezone

from shopping_shorts.store import Store

_ready = set()
_lock = threading.Lock()
_POST_FIELDS = ("title", "body", "status", "pinned", "approved_at")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def ensure(db_path):
    key = str(db_path)
    if key in _ready:
        return
    with _lock:
        if key in _ready:
            return
        with Store(db_path)._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS board_post (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board TEXT NOT NULL,
                    author_cid INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    consent INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    approved_at TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_board_post ON board_post(board, pinned, id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS board_file (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    orig_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    hidden INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_board_file ON board_file(post_id, id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS board_nick (
                    cid INTEGER PRIMARY KEY,
                    nickname TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
            """)
        _ready.add(key)


def _conn(db_path):
    ensure(db_path)
    return Store(db_path)._conn()


def _rows(c, q, args=()):
    c.row_factory = sqlite3.Row
    return [dict(r) for r in c.execute(q, args).fetchall()]


# ── 닉네임 ───────────────────────────────────────────────────────────────
def nick_get(db, cid):
    with _conn(db) as c:
        r = c.execute("SELECT nickname FROM board_nick WHERE cid=?", (int(cid),)).fetchone()
        return r[0] if r else None


def nick_set(db, cid, nick):
    """정하거나 바꾼다. 남이 쓰는 이름이면 False."""
    with _conn(db) as c:
        try:
            c.execute("INSERT INTO board_nick(cid, nickname, created_at) VALUES(?,?,?) "
                      "ON CONFLICT(cid) DO UPDATE SET nickname=excluded.nickname",
                      (int(cid), nick, _now()))
        except sqlite3.IntegrityError:
            return False
    return True


def nick_map(db, cids):
    cids = sorted({int(x) for x in cids})
    if not cids:
        return {}
    with _conn(db) as c:
        q = "SELECT cid, nickname FROM board_nick WHERE cid IN (%s)" % ",".join("?" * len(cids))
        return {r[0]: r[1] for r in c.execute(q, cids).fetchall()}


# ── 글 ──────────────────────────────────────────────────────────────────
def post_add(db, board, cid, title, body, status, consent):
    now = _now()
    with _conn(db) as c:
        cur = c.execute(
            "INSERT INTO board_post(board, author_cid, title, body, status, consent, "
            "created_at, updated_at, approved_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (board, int(cid), title, body, status, 1 if consent else 0, now, now,
             now if status == "approved" else None))
        return cur.lastrowid


def post_get(db, post_id):
    with _conn(db) as c:
        rows = _rows(c, "SELECT * FROM board_post WHERE id=?", (int(post_id),))
        return rows[0] if rows else None


def post_list(db, board):
    """고정 먼저 → 최신 순. 누가 볼 수 있는지는 부르는 쪽이 board.can_view 로 거른다."""
    with _conn(db) as c:
        return _rows(c, "SELECT * FROM board_post WHERE board=? ORDER BY pinned DESC, id DESC",
                     (board,))


def post_list_status(db, status):
    with _conn(db) as c:
        return _rows(c, "SELECT * FROM board_post WHERE status=? ORDER BY id DESC", (status,))


def post_update(db, post_id, **fields):
    bad = set(fields) - set(_POST_FIELDS)
    if bad:
        raise ValueError("고칠 수 없는 칸: %s" % sorted(bad))
    if not fields:
        return
    sets = ", ".join("%s=?" % k for k in fields) + ", updated_at=?"
    with _conn(db) as c:
        c.execute("UPDATE board_post SET %s WHERE id=?" % sets,
                  [*fields.values(), _now(), int(post_id)])


def post_delete(db, post_id):
    """글과 첨부 행을 지우고, 디스크에서 지워야 할 파일 이름을 돌려준다."""
    with _conn(db) as c:
        names = [r[0] for r in c.execute(
            "SELECT stored_name FROM board_file WHERE post_id=?", (int(post_id),)).fetchall()]
        c.execute("DELETE FROM board_file WHERE post_id=?", (int(post_id),))
        c.execute("DELETE FROM board_post WHERE id=?", (int(post_id),))
    return names


# ── 첨부 ─────────────────────────────────────────────────────────────────
def file_add(db, post_id, kind, orig_name, stored_name, size, hidden=0):
    with _conn(db) as c:
        cur = c.execute(
            "INSERT INTO board_file(post_id, kind, orig_name, stored_name, size, hidden, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (int(post_id), kind, orig_name, stored_name, int(size), 1 if hidden else 0, _now()))
        return cur.lastrowid


def file_get(db, file_id):
    with _conn(db) as c:
        rows = _rows(c, "SELECT * FROM board_file WHERE id=?", (int(file_id),))
        return rows[0] if rows else None


def file_delete(db, file_id):
    with _conn(db) as c:
        c.execute("DELETE FROM board_file WHERE id=?", (int(file_id),))


def files_of(db, post_id):
    with _conn(db) as c:
        return _rows(c, "SELECT * FROM board_file WHERE post_id=? ORDER BY id", (int(post_id),))


def files_of_many(db, post_ids):
    post_ids = [int(x) for x in post_ids]
    if not post_ids:
        return {}
    out = {p: [] for p in post_ids}
    with _conn(db) as c:
        q = "SELECT * FROM board_file WHERE post_id IN (%s) ORDER BY id" % ",".join("?" * len(post_ids))
        for r in _rows(c, q, post_ids):
            out[r["post_id"]].append(r)
    return out


def used_bytes(db):
    with _conn(db) as c:
        return int(c.execute("SELECT COALESCE(SUM(size), 0) FROM board_file").fetchone()[0])
