# -*- coding: utf-8 -*-
"""실행기 감시(사장님 10-26 "가만히 있으면 한없이 진행되는 게 제일 문제") — runner_ops.run_do 가
① 진행 신호 없이 멈춘 일을 stall 초 안에 '시간 초과'로 끝내고 하위 프로그램을 끈다 ② 예산 초과도 끝낸다
③ 파일이 자라는(받기·렌더) 일은 멈춤으로 보지 않는다 ④ 진행 줄(progress.json)에 '무엇을 하는 중 n/m'."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import runner_ops as R  # noqa: E402


def _hang(W, d):          # 진행 신호 없이 하위 프로그램이 오래 도는 일(10-26 run3 원본 받기처럼)
    subprocess.run([sys.executable, "-c", "import time; time.sleep(60)"])
    return {"ok": True}


def _grow(W, d):          # 파일이 자라며 오래 걸리는 일(받기·렌더) — 멈춤 아님
    f = Path(W) / "grow.bin"
    for _ in range(8):
        with open(f, "ab") as fh:
            fh.write(b"x" * 1000)
        time.sleep(0.4)
    return {"ok": True}


def _busy_child(W, d):     # 파일도 안 쓰고 진행 신호도 없지만 하위 프로그램이 CPU 를 쓰며 일하는 중(10-26 run4 계획 199초)
    subprocess.run([sys.executable, "-c", "import time\nt=time.time()\nwhile time.time()-t<4: pass"])
    return {"ok": True}


def _steps(W, d):
    for i in range(3):
        R.progress(W, "원본 후보 조사", i + 1, 3)
        time.sleep(0.1)
    return {"ok": True}


def test_stalled_job_ends_and_child_killed(tmp_path, monkeypatch):
    monkeypatch.setitem(R.CMDS, "hang", _hang)
    t0 = time.time()
    out = R.run_do(tmp_path, [{"id": "h", "cmd": "hang"}], log=lambda s: None, stall=1.5)
    took = time.time() - t0
    assert out["h"].get("timed_out") and "시간 초과" in out["h"]["error"], out
    assert took < 15, took                       # 60초 잠든 하위 프로그램을 기다리지 않는다
    assert not [p for p in R._CHILDREN if p.poll() is None]


def test_budget_over_ends(tmp_path, monkeypatch):
    monkeypatch.setitem(R.CMDS, "hang", _hang)
    out = R.run_do(tmp_path, [{"id": "h", "cmd": "hang", "budget": 1}], log=lambda s: None, stall=100)
    assert out["h"].get("timed_out") and "예산" in out["h"]["error"]


def test_growing_files_are_progress(tmp_path, monkeypatch):
    monkeypatch.setitem(R.CMDS, "grow", _grow)
    out = R.run_do(tmp_path, [{"id": "g", "cmd": "grow"}], log=lambda s: None, stall=1.5)
    assert out["g"] == {"ok": True}


def test_progress_file_has_n_of_m(tmp_path, monkeypatch):
    monkeypatch.setitem(R.CMDS, "steps", _steps)
    out = R.run_do(tmp_path, [{"id": "s", "cmd": "steps"}], log=lambda s: None, stall=5)
    assert out["s"] == {"ok": True}
    p = json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))
    assert p["what"] == "원본 후보 조사" and p["n"] == 3 and p["m"] == 3


def test_every_budget_covers_measured_max():
    """예산이 실측 최장보다 짧으면 정상 일을 끊는다 — 근거 숫자(주석)와 같이 묶어 둔다."""
    measured_max = {"bench": 802, "origin_get": 273, "origin_probe": 146, "render": 701, "download": 665, "screen": 282, "check": 150}
    for k, v in measured_max.items():
        assert max(R.BUDGET_FLOOR, R.BUDGET.get(k, R.BUDGET_DEFAULT)) >= v, (k, v)
    for k in ("plan", "asr_spans", "orig_heard", "coupang"):   # 10-26 run4: plan·asr_spans 120.2초가 정상이었다(바닥 120초가 끊음)
        assert max(R.BUDGET_FLOOR, R.BUDGET.get(k, R.BUDGET_DEFAULT)) >= 300, k


def test_cpu_busy_child_is_progress(tmp_path, monkeypatch):
    monkeypatch.setitem(R.CMDS, "busy", _busy_child)
    out = R.run_do(tmp_path, [{"id": "b", "cmd": "busy"}], log=lambda s: None, stall=1.5)
    assert out["b"] == {"ok": True}, out


def _beating(W, d):         # 예산보다 오래 걸리지만 진행 신호를 내며 일하는 중(계획의 30초 박동처럼)
    for i in range(6):
        R.progress(W, "장면 맞추기")
        time.sleep(0.5)
    return {"ok": True}


def test_over_budget_but_progressing_is_not_cut(tmp_path, monkeypatch):
    monkeypatch.setitem(R.CMDS, "beat", _beating)
    out = R.run_do(tmp_path, [{"id": "b", "cmd": "beat", "budget": 1.5}], log=lambda s: None, stall=1.0)
    assert out["b"] == {"ok": True}, out
