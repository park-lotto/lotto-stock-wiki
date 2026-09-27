"""매일 영상 점검(daily_video_audit.py) 테스트 — 어긋나면 쪽지, 깨끗하면 닫기, 못 돌리면 조용히 넘기지 않기."""
import sqlite3

import pytest
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


_CC_OK = "62ed6bf66eb9 칸3 컷R10/C10/E10 | 캡컷 불일치 0 {} | 내보내기 불일치 0 {}\n== 컷 10 · 캡컷 불일치 0 · 내보내기 불일치 0\n"


def _fake_cc(report=_CC_OK, crash="", rc=0, seen=None):
    def run(ids, work, timeout):
        if seen is not None:
            seen.append(list(ids))
        work.mkdir(parents=True, exist_ok=True)
        (work / "report.txt").write_text(report, encoding="utf-8")
        if crash:
            (work / "crash.txt").write_text(crash, encoding="utf-8")
        return rc, "cclog"
    return run


_AU_LINE = ("== 칸 %d · 나레이션 0.15초+ 오차 %d · 효과음 누락 0 · BGM 이상 0 · 음성-자막 0.15초+ 0 · 나레이션 못찾음 0"
            " · 효과음 타점0.10+ 0 · 길이 이상 0 · 렌더뒤음성바뀜 0 · 건너뜀 0 · 패킷 잉여 0.05초+ %d편 · 일정 지연 %d편 · 검출불일치 0칸   (…)")
_AU_OK = "j 칸10 …\n" + _AU_LINE % (10, 0, 0, 0) + "\n"


def _fake_au(report=_AU_OK, crash="", rc=0, seen=None):
    def run(n, work, timeout):
        if seen is not None:
            seen.append(n)
        work.mkdir(parents=True, exist_ok=True)
        (work / "report.txt").write_text(report, encoding="utf-8")
        if crash:
            (work / "crash.txt").write_text(crash, encoding="utf-8")
        return rc, "aulog"
    return run


def _go(tmp_path, report="", free=57, rows=None, cc=None, au=None, **kw):
    al = dva._Alerter(dry_run=True, printer=lambda s: None)
    db = _db(tmp_path, rows if rows is not None else [("62ed6bf66eb9", "ready", _iso(1))])
    rc = dva.run_audit(jobs=10, hours=24, out_root=tmp_path / "audit", tmp_root=tmp_path / "tmp", alerter=al, cfg=CFG,
                       printer=lambda s: None, runner=_fake_runner(report, **kw), free_gb=free, db_path=db, now=NOW,
                       cc_runner=cc or _fake_cc(), audio_runner=au or _fake_au())
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


def test_script_run_from_tools_dir_can_import_alert_channel(tmp_path):
    """systemd 처럼 `python3 tools/daily_video_audit.py` 로 띄워도(sys.path[0]=tools/) 쪽지 통로가 import 돼야 한다.
    2026-09-27: 라이브 첫 실행이 27분 점검 뒤 `from shopping_shorts import ops_alert` 에서 죽었다(경보·해제 둘 다 안 나감)."""
    import subprocess, sys as _sys
    repo = Path(__file__).resolve().parents[1]
    r = subprocess.run([_sys.executable, str(repo / "tools" / "daily_video_audit.py"), "--import-check"],
                       cwd=str(tmp_path), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    assert "IMPORT_OK" in r.stdout, r.stdout


# ── ⑤ 캡컷·내보내기 대조(2026-09-27) ─────────────────────────────────

def test_capcut_audit_runs_on_same_jobs_and_is_kept(tmp_path):
    seen = []
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 2)), cc=_fake_cc(seen=seen))
    assert rc == 0 and calls == [("resolve",)]
    assert seen == [["62ed6bf66eb9"]], "영상 비교와 같은 작업으로 돈다"
    day = tmp_path / "audit" / "2026-09-27"
    assert "== 컷 10" in (day / "capcut_report.txt").read_text(encoding="utf-8")
    import json
    assert json.loads((day / "summary.json").read_text(encoding="utf-8"))["capcut_summary"] == {
        "cuts": 10, "capcut": 0, "export": 0, "clean_missing": 0}
    assert not list((tmp_path / "tmp").glob("capcut_audit_*")), "대조 임시 폴더도 지운다"


def test_capcut_mismatch_raises_customer_alert(tmp_path):
    """★사보타주 기준: 영상 비교는 깨끗해도 ZIP 이 완성본과 다르면 쪽지가 나가야 한다."""
    bad = "62ed6bf66eb9 칸3 컷R10/C10/E10 | 캡컷 불일치 0 {} | 내보내기 불일치 4 {'clean': 4}\n== 컷 10 · 캡컷 불일치 0 · 내보내기 불일치 4\n"
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 2)), cc=_fake_cc(report=bad))
    assert rc == 1
    kind, title, detail, grade, sig = calls[0]
    assert kind == "raise" and "ZIP≠완성본 4컷" in title and grade == "고객영향"
    assert "[캡컷·ZIP] 62ed6bf66eb9" in detail and "내보내기 불일치 4컷" in detail


def test_capcut_audit_crash_or_missing_summary_alerts(tmp_path):
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 2)), cc=_fake_cc(report="", crash="Traceback\nX"))
    assert rc == 2 and calls[0][0] == "raise" and "캡컷·ZIP 대조를 끝까지 못 돌림" in calls[0][1]
    (tmp_path / "b").mkdir()
    rc, calls = _go(tmp_path / "b", _report([_JOB_OK], _sum(10, 0, 2)), cc=_fake_cc(report="x\n", rc=0))
    assert rc == 2 and calls[0][0] == "raise"


def test_ghost_raises_customer_alert_and_is_in_summary(tmp_path):
    """잔상(컷 가장자리 딴 장면)은 고객이 보는 결함 — 쪽지 제목·summary.json 에 실린다(2026-09-27)."""
    import json as _json
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, ghost=3, ghost_only=1)))
    assert rc == 1
    kind, title, detail, grade, sig = calls[0]
    assert kind == "raise" and "잔상 3프레임(화면에만 1)" in title and grade == "고객영향", (title, grade)
    sj = _json.loads((tmp_path / "audit" / "2026-09-27" / "summary.json").read_text(encoding="utf-8"))
    assert sj["ghost"] == {"frames": 3, "cuts": 3, "screen_only": 1, "short": 0}


def test_daily_summary_keeps_clean_missing(tmp_path):
    cc = "62ed6bf66eb9 칸3 컷R10/C10/E10 | 캡컷 불일치 0 {} | 내보내기 불일치 0 {}" + chr(10) + "== 컷 10 · 캡컷 불일치 0 · 내보내기 불일치 0 · 청소 미생성 1 job" + chr(10)
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 2)), cc=_fake_cc(report=cc))
    import json
    s = json.loads((tmp_path / "audit" / "2026-09-27" / "summary.json").read_text(encoding="utf-8"))
    assert s["capcut_summary"]["clean_missing"] == 1


@pytest.mark.parametrize("fn", ["_run_evf", "_run_cea"])
def test_daily_audit_scene_cache_under_work(tmp_path, monkeypatch, fn):
    """매일 점검의 비교 실행은 장면 전환 캐시를 자기 작업 폴더에 — 소재 옆(고객 폴더)에 쓰지 않는다."""
    import daily_video_audit as dva
    seen = {}

    class _P:
        returncode, stdout, stderr = 0, "", ""

    def fake_run(cmd, **kw):
        seen.update(kw.get("env") or {})
        return _P()
    monkeypatch.setattr(dva.subprocess, "run", fake_run)
    getattr(dva, fn)(["abc"], tmp_path / "w", 10)
    assert seen.get("SEG_SNAP_CACHE_DIR") == str(tmp_path / "w" / "snapcache"), seen.get("SEG_SNAP_CACHE_DIR")



# ── ⑥ 소리 대조(2026-09-27) — 고객이 받은 실제 완성본(효과음·인트로 포함) ─────────────────

def test_audio_audit_runs_and_is_kept(tmp_path):
    seen = []
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 2)), au=_fake_au(seen=seen))
    assert rc == 0 and calls == [("resolve",)]
    assert seen == [CFG["audit"]["audio_jobs"]]
    day = tmp_path / "audit" / "2026-09-27"
    assert "일정 지연 0편" in (day / "audio_report.txt").read_text(encoding="utf-8")
    import json
    assert json.loads((day / "summary.json").read_text(encoding="utf-8"))["audio_summary"]["delay"] == 0
    assert not list((tmp_path / "tmp").glob("audio_audit_*")), "소리 대조 임시 폴더도 지운다"


@pytest.mark.parametrize("n,s,d", [(2, 0, 0), (0, 1, 0), (0, 0, 3)])
def test_audio_mismatch_raises_customer_alert(tmp_path, n, s, d):
    """★사보타주 기준: 영상·캡컷은 깨끗해도 목소리가 화면과 어긋나면(나레이션·잉여·일정 지연) 쪽지가 나가야 한다."""
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 2)), au=_fake_au(report=_AU_LINE % (10, n, s, d) + "\n"))
    assert rc == 1
    raised = [c for c in calls if c[0] == "raise"]
    assert raised and "소리≠화면" in raised[0][1] and raised[0][3] == "고객영향", calls


def test_audio_audit_crash_or_missing_summary_alerts(tmp_path):
    rc, calls = _go(tmp_path, _report([_JOB_OK], _sum(10, 0, 2)), au=_fake_au(report="x\n"))
    assert rc == 2 and any("소리 대조를 끝까지 못 돌림" in c[1] for c in calls if c[0] == "raise"), calls
    (tmp_path / "b").mkdir()
    rc, calls = _go(tmp_path / "b", _report([_JOB_OK], _sum(10, 0, 2)), au=_fake_au(crash="Traceback", rc=1))
    assert rc == 2, calls
