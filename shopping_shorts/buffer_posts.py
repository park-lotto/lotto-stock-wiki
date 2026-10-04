"""Buffer 예약 장부 — "이 영상을 이 채널에 이미 예약했나"를 **여기 한 곳**이 정한다.

★왜 생겼나 (2026-10-04, 관제 114 — 고객 340 유튜브·인스타에 같은 영상이 2개씩)
  예약 요청은 부를 때마다 Buffer에 새 게시물을 만들었고, 서버는 무엇을 예약했는지
  **아무것도 적지 않았다**. 그래서 ①같은 영상을 다시 눌러도 막을 근거가 없었고
  (실측: job c2e762780e08 이 5분 간격으로 같은 채널·같은 시각에 두 번)
  ②한 채널만 실패해 다시 누르면 이미 성공한 채널이 또 예약됐고
  ③예약을 취소하려 해도 우리가 게시물 id를 몰라 Buffer에 가서 지워야 했다.

★판단의 주인 (0순위-C)
  - 중복인가        → already_scheduled()
  - 취소할 수 있나   → cancel()
  화면·app은 이 둘을 **부른다**. 같은 판단을 다른 곳에 다시 적지 마라.

★장부만 믿지 않는다
  고객이 Buffer에서 직접 지우거나 시간을 옮길 수 있다. 그래서 판단 직전에 Buffer에
  **지금 상태를 물어** 장부를 맞춘다(sync). 못 물어봤으면(네트워크) 장부를 그대로 둔다 —
  '없다'(BufferNotFound)와 '못 물어봤다'를 섞으면 살아 있는 예약을 지워진 것으로 적는다.
"""

import logging
import sqlite3
import time

from shopping_shorts import buffer_api

log = logging.getLogger(__name__)

# 취소할 수 있는 상태. sending(올리는 중)·sent(올라감)는 Buffer에서 지워도
# SNS에 남으므로 '취소됐다'고 말하면 거짓이다.
_CANCELLABLE = ("scheduled", "draft", "needs_approval", "error")


def _conn(db_path):
    c = sqlite3.connect(db_path, timeout=15.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=15000")
    c.execute("""
        CREATE TABLE IF NOT EXISTS buffer_posts (
            post_id      TEXT PRIMARY KEY,
            customer_id  INTEGER NOT NULL,
            job_id       TEXT NOT NULL,
            channel_id   TEXT NOT NULL,
            due_at       TEXT NOT NULL DEFAULT '',
            share_now    INTEGER NOT NULL DEFAULT 0,
            status       TEXT NOT NULL DEFAULT 'scheduled',
            link         TEXT NOT NULL DEFAULT '',
            created_at   INTEGER NOT NULL,
            gone_at      INTEGER NOT NULL DEFAULT 0
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_buffer_posts_job "
              "ON buffer_posts(customer_id, job_id)")
    return c


def record(db_path, customer_id, job_id, channel_id, post_id, due_at="", share_now=False):
    """예약이 **성공한 뒤** 적는다. 실패한 것은 적지 않는다."""
    with _conn(db_path) as c:
        c.execute(
            "INSERT OR REPLACE INTO buffer_posts"
            "(post_id, customer_id, job_id, channel_id, due_at, share_now, status, created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (str(post_id), int(customer_id), str(job_id), str(channel_id), str(due_at or ""),
             1 if share_now else 0, "sent" if share_now else "scheduled", int(time.time())))


def _rows(db_path, customer_id, job_id):
    with _conn(db_path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM buffer_posts WHERE customer_id=? AND job_id=? AND gone_at=0"
            " ORDER BY created_at", (int(customer_id), str(job_id)))]


def sync(db_path, key, customer_id, job_id):
    """이 작업의 살아 있는 예약 목록. Buffer에 지금 상태를 물어 장부를 맞춘 뒤 돌려준다.

    → [{post_id, channel_id, due_at, status, link, share_now, cancellable}]
    """
    out = []
    for r in _rows(db_path, customer_id, job_id):
        try:
            live = buffer_api.post_status(key, r["post_id"])
        except buffer_api.BufferNotFound:
            # Buffer에서 지워졌다 → 더는 '예약됨'이 아니다.
            with _conn(db_path) as c:
                c.execute("UPDATE buffer_posts SET gone_at=? WHERE post_id=?",
                          (int(time.time()), r["post_id"]))
            continue
        except buffer_api.BufferError as e:
            # 못 물어봤다 — 장부에 적힌 대로 보여준다(지워진 것으로 치지 않는다).
            log.warning("buffer 상태 조회 실패 post=%s: %s", r["post_id"], e)
            live = None
        if live:
            r["status"] = live["status"] or r["status"]
            r["due_at"] = live["dueAt"] or r["due_at"]
            r["link"] = live["link"] or r["link"]
            with _conn(db_path) as c:
                c.execute("UPDATE buffer_posts SET status=?, due_at=?, link=? WHERE post_id=?",
                          (r["status"], r["due_at"], r["link"], r["post_id"]))
        out.append({"post_id": r["post_id"], "channel_id": r["channel_id"],
                    "due_at": r["due_at"], "status": r["status"], "link": r["link"],
                    "share_now": bool(r["share_now"]),
                    "cancellable": r["status"] in _CANCELLABLE})
    return out


def already_scheduled(db_path, key, customer_id, job_id, channel_ids):
    """★중복 판정의 주인. 고른 채널 중 **이 영상이 이미 걸려 있는** 채널.

    → {channel_id: [예약 dict, …]}  (없으면 빈 dict)
    예약 대기뿐 아니라 이미 올라간 것(sent)도 중복이다 — 같은 영상이 한 채널에
    두 번 올라가는 것이 고객이 겪은 사고다. Buffer에서 지워진 것은 sync가 걸러낸다.
    """
    want = set(str(c) for c in channel_ids)
    out = {}
    for p in sync(db_path, key, customer_id, job_id):
        if p["channel_id"] in want:
            out.setdefault(p["channel_id"], []).append(p)
    return out


class CancelError(Exception):
    """취소하지 못했다. message는 고객에게 그대로 보여준다."""


def cancel(db_path, key, customer_id, post_id):
    """★취소 판정의 주인. 내 예약이고 아직 안 올라갔을 때만 Buffer에서 지운다."""
    with _conn(db_path) as c:
        r = c.execute("SELECT * FROM buffer_posts WHERE post_id=? AND customer_id=?",
                      (str(post_id), int(customer_id))).fetchone()
    if not r:
        raise CancelError("내 예약이 아닙니다.")

    def _gone():
        with _conn(db_path) as c:
            c.execute("UPDATE buffer_posts SET gone_at=? WHERE post_id=?",
                      (int(time.time()), str(post_id)))

    try:
        live = buffer_api.post_status(key, str(post_id))
    except buffer_api.BufferNotFound:
        _gone()                       # 이미 Buffer에서 지워져 있다 — 취소된 것과 같다
        return
    except buffer_api.BufferError as e:
        raise CancelError(str(e))
    if live["status"] not in _CANCELLABLE:
        with _conn(db_path) as c:
            c.execute("UPDATE buffer_posts SET status=?, link=? WHERE post_id=?",
                      (live["status"], live["link"], str(post_id)))
        raise CancelError("이미 올라간 게시물이라 취소할 수 없습니다. 해당 SNS에서 직접 지워 주세요."
                          if live["status"] == "sent" else
                          "지금 올리는 중이라 취소할 수 없습니다. 올라간 뒤 해당 SNS에서 지워 주세요.")
    try:
        buffer_api.delete_post(key, str(post_id))
    except buffer_api.BufferNotFound:
        pass
    except buffer_api.BufferError as e:
        raise CancelError(str(e))
    _gone()
