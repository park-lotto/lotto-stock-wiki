"""매일 영상 점검(daily_video_audit.py) 테스트 — 어긋나면 쪽지, 깨끗하면 닫기, 못 돌리면 조용히 넘기지 않기."""
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import daily_video_audit as dva
import video_gate as vg
from test_video_gate import _JOB_BAD, _JOB_OK, _report, _sum

CFG = vg.load_config()
NOW = datetime(2026, 9, 27, 4, 30, tzinfo=timezone(timedelta(hours=9)))


def _db(tmp_path, rows):
    p = tmp_path / "ref.db"
    con = sqlite3.connect(p)
    con.execute("create table mix_jobs (job_id text, preview_status text, updated_at text)")
    con.executemany("insert into mix_jobs values (?,?,?)", rows)
    con.commit()
    con.close()
    return str(p)


def _iso(delta_h):
    return (datetime.now(timezone.utc) - timedelta(hours=delta_h)).isoformat()


def test_pick_jobs_uses_iso_window_and_ready_only(tmp_path):
    db = _db(tmp_path, [("new1", "ready", _iso(1)), ("new2", "ready", _iso(20)), ("old", "ready", _iso(30)),
                        ("notready", "building", _iso(1))])
    assert dva.pick_jobs(db, 24, 10) == ["new1", "new2"]
    assert dva.pick_jobs(db, 24, 1) == ["new1"]


def _fake_runner(report, crash="", rc=0):
    def run(ids, work, timeout):
        work.mkdir(parents=True, exist_ok=True)
        (work / "report.txt").write_text(report, encoding="utf-8")
        (work / ("eye_%s.jpg" % ids[0])).write_bytes(b"jpg")
        if crash:
            (work / "crash.txt").write_text(crash, encoding="utf-8")
        return rc, "log"
    return run


def _go(tmp_path, report="", free=57, rows=None, **kw):
    al = dva._Alerter(dry_run=True, printer=lambda s: None)
    db = _db(tmp_path, rows if rows is not None else [("62ed6bf66eb9", "ready", _iso(1))])
    rc = dva.run_audit(jobs=10, hours=24, out_root=tmp_path / "audit", tmp_root=tmp_path / "tmp", alerter=al, cfg=CFG,
                       printer=lambda s: None, runner=_fake_runner(report, **kw), free_gb=free, db_path=db, now=NOW)
    return rc, al.calls


def test_clean_day_resolves(tmp_path):
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 2)))
    assert rc == 0 and calls == [("resolve",)]
    day = tmp_path / "audit" / "2026-09-27"
    assert (day / "report.txt").exists() and (day / "eye_62ed6bf66eb9.jpg").exists() and (day / "summary.json").exists()
    assert not list((tmp_path / "tmp").glob("video_audit_*")), "임시 폴더(영상)는 지워야 한다"


def test_scene_mismatch_raises_customer_alert(tmp_path):
    rc, calls = _go(tmp_path, _report([_JOB_OK, _JOB_BAD], _sum(18, 3)))
    assert rc == 1
    kind, title, detail, grade, sig = calls[0]
    assert kind == "raise" and "다른 장면 3칸" in title and "09-27" in title and grade == "고객영향"
    assert "7bbb00000001" in detail, "쪽지에 어느 작업인지 있어야 한다"


def test_shift_ratio_over_limit_raises_ops_alert(tmp_path):
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 5)))
    assert rc == 1 and calls[0][0] == "raise" and calls[0][3] == "운영주의"


def test_low_disk_alerts_instead_of_silently_skipping(tmp_path):
    rc, calls = _go(tmp_path, "", free=5)
    assert rc == 2 and calls[0][0] == "raise" and "디스크" in calls[0][1]


def test_tool_crash_alerts(tmp_path):
    rc, calls = _go(tmp_path, "", crash="Traceback\nImportError: x", rc=0)
    assert rc == 2 and calls[0][0] == "raise" and "못 돌림" in calls[0][1]


def test_no_jobs_is_quiet(tmp_path):
    rc, calls = _go(tmp_path, "", rows=[])
    assert rc == 3 and calls == []


def test_dry_run_and_pytest_never_touch_ops_alert(tmp_path, monkeypatch):
    import types
    boom = types.SimpleNamespace(raise_alert=lambda *a, **k: (_ for _ in ()).throw(AssertionError("발송됨")),
                                 resolve_kind=lambda *a, **k: (_ for _ in ()).throw(AssertionError("닫힘")))
    monkeypatch.setitem(sys.modules, "shopping_shorts.ops_alert", boom)
    al = dva._Alerter(dry_run=False, printer=lambda s: None)       # dry-run 이 아니어도 pytest 안이면 막힌다
    al.resolve()
    al.raise_("t", "d", grade="운영주의", signature="s", cooldown_sec=1, todo="")


def test_crash_after_clean_looking_report_still_alerts(tmp_path):
    """report 가 멀쩡해 보여도 도구가 예외로 끝났거나 rc≠0 이면 '깨끗'으로 닫지 않는다."""
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0)), crash="Traceback\nKeyError: x")
    assert rc == 2 and calls[0][0] == "raise"
    (tmp_path / "b").mkdir()
    rc, calls = _go(tmp_path / "b", _report([_JOB_OK], _sum(10, 0)), rc=124)
    assert rc == 2 and calls[0][0] == "raise"
