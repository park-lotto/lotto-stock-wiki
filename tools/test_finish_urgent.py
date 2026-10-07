# -*- coding: utf-8 -*-
"""병합 급행(관제 157) — 급행 finish 는 main 을 예약하고, 보통 finish 는 급행 push 전에 push 하지 않는다.

진짜 프로세스 3개(급행1 + 보통2)를 임시 git 저장소에서 동시에 띄워 origin/main 의 병합 순서를 본다.
급행의 시험이 가장 느려도(8초 vs 1초) 급행이 먼저 들어가야 한다.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import track  # noqa: E402
from test_track import repo, _git  # noqa: E402,F401  (픽스처 재사용)
from test_finish_speed import _make_track_commit  # noqa: E402

TOOLS = Path(__file__).resolve().parent

_DRIVER = r'''
import os, sys, time
sys.path.insert(0, sys.argv[1])
import track, merge_gate, video_gate
repo, name, urgent, delay = sys.argv[2], sys.argv[3], sys.argv[4] == "1", float(sys.argv[5])

class G:
    def _s(self):
        return {"compile_ok": True, "import_ok": True, "pytest_rc": 0, "failed": [], "import_out": "", "pytest_out": ""}
    def snapshot_light(self, cwd=None, **kw): return self._s()
    def snapshot(self, cwd=None, **kw):
        time.sleep(delay); return self._s()
    def baseline_warnings(self, b): return []
    def compare(self, b, a): return merge_gate.compare(b, a)
    def rerun_ids(self, cwd, ids, **kw): return set()

track._known_main_failures = lambda *a, **k: set()
# 시험 자원을 2칸씩만 — 셋이 동시에 시험한다(실제로도 영상 관문·시험은 줄 밖에서 겹친다)
track._gate_target_workers = lambda free_mb: 2
ok = lambda stage, br: video_gate.GateResult(True, False, "")
from pathlib import Path
kw = dict(repo=Path(repo), gate=G(), video_gate=ok)
try:
    rc = track.finish(name, urgent=urgent, **kw)
except TypeError:                      # 급행을 모르는 옛 판본
    rc = track.finish(name, **kw)
print("RC", rc)
'''


def _merge_order(repo):
    origin = repo.parent / "origin.git"
    out = _git(origin, "log", "main", "--first-parent", "--reverse", "--format=%s")
    return [ln for ln in out.splitlines() if "track/" in ln]


def test_급행이_먼저_push_보통은_보류(repo, tmp_path):
    for n, f in (("급행", "u.py"), ("보통1", "a.py"), ("보통2", "b.py")):
        _make_track_commit(repo, n, fname=f, body="X = 1\n")
    drv = tmp_path / "driver.py"
    drv.write_text(_DRIVER, encoding="utf-8")
    env = dict(os.environ, TRACK_FINISH_LOCK=str(tmp_path / "lk" / "f.lock"), PYTHONIOENCODING="utf-8",
               TRACK_URGENT_WAIT_MAX="120", TRACK_PRECHECK="0")
    env.pop("PYTEST_CURRENT_TEST", None)
    (tmp_path / "lk").mkdir()
    procs = []

    def go(name, urgent, delay):
        log = open(tmp_path / ("%s.log" % name), "wb")
        procs.append((name, log, subprocess.Popen(
            [sys.executable, str(drv), str(TOOLS), str(repo), name, "1" if urgent else "0", str(delay)],
            cwd=str(repo), env=env, stdout=log, stderr=subprocess.STDOUT)))
    go("급행", True, 8)
    time.sleep(1.5)                    # 급행이 예약할 시간
    go("보통1", False, 1)
    go("보통2", False, 1)
    for name, log, p in procs:
        p.wait(300)
        log.close()
    logs = {n: (tmp_path / ("%s.log" % n)).read_text(encoding="utf-8", errors="replace") for n, _, _ in procs}
    for n, _, p in procs:
        assert p.returncode == 0, "%s 실패:\n%s" % (n, logs[n][-3000:])
    order = _merge_order(repo)
    assert len(order) == 3, order
    assert "track/급행" in order[0], "급행이 먼저 들어가지 못했다: %s" % order
    assert "[급행 보류]" in logs["보통1"] + logs["보통2"], "보통 finish 가 보류 로그를 남기지 않았다"


def test_급행_예약표는_끝나면_지워지고_죽은_표는_무시(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    with track._urgent_reservation():
        assert track._live_urgent(exclude_self=False)
    assert not track._live_urgent(exclude_self=False)
    d = track._urgent_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s_%d_%d" % (track._queue_rank(urgent=True), 999999, 1))).write_text("", encoding="utf-8")   # 죽은 pid
    assert not track._live_urgent(exclude_self=False)
    assert track._wait_for_urgent(max_s=1) is False


def test_급행_대기는_상한_뒤_경보하고_진행(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TRACK_FINISH_LOCK", str(tmp_path / "f.lock"))
    monkeypatch.setattr(track, "_live_urgent", lambda exclude_self=True: ["x"])
    monkeypatch.setattr(track.time, "sleep", lambda s: None)
    assert track._wait_for_urgent(max_s=0) is True
    assert "[경보]" in capsys.readouterr().out


def test_줄_순서는_급행이_먼저_같은_등급은_선착순():
    a = track._queue_rank(urgent=False)
    b = track._queue_rank(urgent=True)
    c = track._queue_rank(urgent=True)
    assert sorted([a, c, b]) == [b, c, a]
    # 옛 꼴 번호표(<ns>_<pid>_<id>)도 읽는다 — 보통 등급
    assert track._ticket_key("%020d_%d_%d" % (5, 12, 3)) == ((1, 5), 12)
    assert track._ticket_key("0_%020d_%d_%d" % (7, 12, 3)) == ((0, 7), 12)


def test_한글_경로_diff_는_이스케이프되지_않는다(repo):
    (repo / "관제").mkdir(exist_ok=True)
    (repo / "관제" / "카드.json").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "한글")
    names = track._diff_names(repo, "HEAD~1", "HEAD")
    assert names == ["관제/카드.json"], names
    assert all(track._is_non_code(n) for n in names)


def test_pipeline_데이터는_비코드_py는_코드():
    assert track._is_non_code("pipeline/dashboard_log.json")
    assert not track._is_non_code("pipeline/atoms/query.py")
    assert not track._is_non_code("shopping_shorts/app.py")
    assert not track._is_non_code("tools/track.py")


def test_code_key_는_pipeline_데이터에_안_흔들린다(repo):
    (repo / "pipeline").mkdir()
    (repo / "pipeline" / "x.py").write_text("A = 1\n", encoding="utf-8")
    (repo / "pipeline" / "d.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "p")
    k1 = track._code_key(repo)
    (repo / "pipeline" / "d.json").write_text('{"a": 1}', encoding="utf-8")
    _git(repo, "commit", "-am", "data")
    assert track._code_key(repo) == k1
    (repo / "pipeline" / "x.py").write_text("A = 2\n", encoding="utf-8")
    _git(repo, "commit", "-am", "code")
    assert track._code_key(repo) != k1


def test_재시도_상한은_20퍼센트():
    import inspect
    assert inspect.signature(track._retry_test_subset).parameters["half"].default == 0.2


def test_finish_report_는_이름이_다른_로그를_건너뛰고_등급_보류를_낸다(tmp_path, capsys):
    import finish_report
    (tmp_path / "sched_test.log").write_text("x\n", encoding="utf-8")          # 종전엔 None.groups() 로 크래시
    p = tmp_path / "보통1_20261007_120000.log"
    p.write_text("\n".join([
        "12:00:01 등급: 보통",
        "12:01:00 게이트 실행 중 (병합된 상태 · 줄 밖)...",
        "12:05:00 [급행 보류] 급행 finish 1건이 main 을 예약 중 — push 를 미룬다(상한 40분)",
        "12:09:00 검사 끝 — 줄에 선다(줄 안에선 커밋·push 만)",
        "12:10:00 ✅ main에 병합 완료 — push됨.",
    ]) + "\n", encoding="utf-8")
    assert finish_report.parse(tmp_path / "sched_test.log") is None
    r = finish_report.parse(p)
    assert r["등급"] == "보통" and r["보류"] == 1 and round(r["push분"]) == 10
    assert finish_report.main(["--dir", str(tmp_path)]) == 0
    assert "보통1" in capsys.readouterr().out
