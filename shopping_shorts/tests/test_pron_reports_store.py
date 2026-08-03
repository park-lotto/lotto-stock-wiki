"""발음 제보함 Store(2026-07-22). 제보 저장→미처리 목록→처리됨 표시."""
import os, tempfile
from shopping_shorts.store import Store


def _store():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd)
    return Store(p)


def test_add_then_list():
    s = _store()
    rid = s.add_pron_report("좋은데요", "발음 이상", "2026-07-22T00:00:00+00:00")
    assert isinstance(rid, int)
    rows = s.list_pron_reports()
    assert len(rows) == 1
    assert rows[0]["text"] == "좋은데요" and rows[0]["comment"] == "발음 이상"
    assert rows[0]["id"] == rid


def test_resolve_hides_from_default_list():
    s = _store()
    rid = s.add_pron_report("가치", "", "2026-07-22T00:00:00+00:00")
    s.resolve_pron_report(rid)
    assert s.list_pron_reports() == []                     # 미처리만 기본
    assert len(s.list_pron_reports(include_resolved=True)) == 1


def test_list_newest_first():
    s = _store()
    a = s.add_pron_report("첫째", "", "2026-07-22T00:00:01+00:00")
    b = s.add_pron_report("둘째", "", "2026-07-22T00:00:02+00:00")
    ids = [r["id"] for r in s.list_pron_reports()]
    assert ids == [b, a]                                   # id DESC(최신 먼저)
