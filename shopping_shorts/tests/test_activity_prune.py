import time
from datetime import datetime, timezone, timedelta

from shopping_shorts.store import Store


def _day(now, ago):
    return (datetime.fromtimestamp(now, timezone.utc) - timedelta(days=ago)).strftime("%Y-%m-%d")


def test_prune_activity_removes_old_keeps_recent(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("u", "pw12")
    now = int(time.time())
    s.record_activity(cid, "old", now - 40 * 86400)      # 40일 전 → 삭제 대상
    s.record_activity(cid, "recent", now - 5 * 86400)    # 5일 전 → 유지
    s.record_access(cid, "1.1.1.1", "ua", _day(now, 40))
    s.record_access(cid, "1.1.1.1", "ua", _day(now, 5))

    n_act, n_acc = s.prune_activity(keep_days=30, now_ts=now)

    assert n_act == 1 and n_acc == 1
    assert [a["action"] for a in s.recent_activity(cid, 12)] == ["recent"]
    assert s.access_summary(cid, "1970-01-01")["ips"] == 1   # 최근 접속만 남음


def test_prune_activity_noop_when_all_recent(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("u", "pw12")
    now = int(time.time())
    s.record_activity(cid, "a", now - 1 * 86400)
    s.record_access(cid, "1.1.1.1", "ua", _day(now, 1))

    n_act, n_acc = s.prune_activity(keep_days=30, now_ts=now)

    assert n_act == 0 and n_acc == 0
    assert len(s.recent_activity(cid, 12)) == 1
