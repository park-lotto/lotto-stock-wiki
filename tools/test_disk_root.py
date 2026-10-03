"""관제 107 — C 디스크가 계속 차던 뿌리 둘의 시험.
① 예약 작업 명령(win_schedule.task_command)이 한글·띄어쓰기 경로에서 **cmd 로 실제로 돌아** 로그를 남긴다
   (옛 `\\"` 따옴표는 cd 에서 죽어 04:40 C→D 이동·매시간 라이브 실측이 한 번도 안 돌았다).
② 게이트 시험 임시 폴더(Temp\\gate_child_<pid>*)는 끝나면 지워지고, 죽은 게이트의 잔해는 finish 청소가 지운다.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_gate  # noqa: E402
import track  # noqa: E402
import win_schedule  # noqa: E402

win = pytest.mark.skipif(os.name != "nt", reason="cmd.exe 는 윈도에만")


def _sched_env():
    # 작업 스케줄러처럼 기본 환경으로 띄운다 — Git Bash 에서 물려받은 긴 PATH 로 cmd 를 띄우면 시작에만 1~2분 걸렸다(실측 81~134초, 기본 환경 0.11초)
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "COMSPEC", "TEMP", "TMP", "USERPROFILE") if k in os.environ}
    env["PATH"] = os.path.join(os.environ.get("SystemRoot", r"C:\WINDOWS"), "system32")
    return env


def _repo_with_script(tmp_path):
    repo = tmp_path / "로또의 주식 시험"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools" / "hello.py").write_text("import os;print('ran in', os.getcwd())\n", encoding="utf-8")
    return repo


@win
def test_task_command_really_runs_under_cmd(tmp_path):
    repo = _repo_with_script(tmp_path)
    log = repo / "관제 로그.log"
    cmd = win_schedule.task_command(repo, ["tools\\hello.py"], log, python=sys.executable)
    # 작업 스케줄러는 /TR 문자열을 그대로 명령줄로 띄운다 — 같은 문자열을 그대로 실행
    r = subprocess.run(cmd, capture_output=True, env=_sched_env(), timeout=60)
    assert r.returncode == 0, r.stderr
    assert log.exists() and "ran in" in log.read_text(encoding="utf-8", errors="replace")


@win
def test_old_backslash_quote_form_fails(tmp_path):
    # 고치기 전 모양이 실제로 실패함을 남긴다(이 시험이 무언가를 잡는다는 증거)
    repo = _repo_with_script(tmp_path)
    log = repo / "old.log"
    old = 'cmd /c "cd /d \\"%s\\" && \\"%s\\" tools\\hello.py >> \\"%s\\" 2>&1"' % (repo, sys.executable, log)
    subprocess.run(old, capture_output=True, env=_sched_env(), timeout=60)
    assert not log.exists()


def test_clean_gate_temp_only_that_pid(tmp_path):
    for n in ("gate_child_12", "gate_child_12_finish_queue", "gate_child_123"):
        (tmp_path / n).mkdir()
        (tmp_path / n / "big.bin").write_bytes(b"x" * 10)
    (tmp_path / "gate_child_12_finish.lock").write_text("")
    gone = merge_gate.clean_gate_temp(12, tmp_root=tmp_path)
    assert sorted(gone) == ["gate_child_12", "gate_child_12_finish.lock", "gate_child_12_finish_queue"]
    assert (tmp_path / "gate_child_123").exists()


def test_dead_gate_temp_swept_live_kept(tmp_path, monkeypatch):
    for n in ("gate_child_111", "gate_child_111_finish_queue", "gate_child_222", "gate_child_%d" % os.getpid()):
        (tmp_path / n).mkdir()
    monkeypatch.setattr(track, "_pid_alive", lambda pid: pid == 222)
    gone = track._clean_dead_gate_temp(tmp_root=tmp_path)
    assert sorted(gone) == ["gate_child_111", "gate_child_111_finish_queue"]
    assert (tmp_path / "gate_child_222").exists()                       # 살아 있는 게이트
    assert (tmp_path / ("gate_child_%d" % os.getpid())).exists()      # 나 자신


def test_run_cleans_its_own_temp(tmp_path, monkeypatch):
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    code = "import tempfile,os;open(os.path.join(tempfile.gettempdir(),'pytest_junk.bin'),'wb').write(b'x'*1000)"
    rc, _ = merge_gate._run([sys.executable, "-c", code], tmp_path)
    assert rc == 0
    assert not list(tmp_path.glob("gate_child_%d*" % os.getpid()))
