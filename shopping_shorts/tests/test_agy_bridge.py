import json
import pytest
from pathlib import Path
from tools.calcopy.engine import agy


@pytest.fixture(autouse=True)
def _fake_find(monkeypatch):
    monkeypatch.setattr(agy, "find", lambda: "agy")


class FakeRun:
    def __init__(self, outs): self.outs, self.calls = list(outs), []
    def __call__(self, args, **kw):
        self.calls.append(args)
        out = self.outs.pop(0)
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()

def _resp(text): return json.dumps({"status": "SUCCESS", "response": text})

def test_ask_video_parses_json_and_uses_plan_mode(tmp_path):
    v = tmp_path / "v360.mp4"; v.write_bytes(b"x")
    run = FakeRun([_resp('{"cuts":[0,1.5]}')])
    r = agy.ask_video(v, "컷 시작 초", {"type": "object"}, run=run)
    assert r["answer"] == {"cuts": [0, 1.5]}
    a = run.calls[0]
    assert "--mode" in a and a[a.index("--mode") + 1] == "plan"      # 명령 실행 권한 없음
    assert "--add-dir" in a and a[-2] == "-p"                         # -p 는 맨 끝(앞에 두면 다음 플래그를 질문으로 먹는다 — 11-04 실측)

def test_ask_video_retries_once_then_errors(tmp_path):
    v = tmp_path / "v.mp4"; v.write_bytes(b"x")
    run = FakeRun([_resp("모르겠어요"), _resp("")])
    r = agy.ask_video(v, "q", {"type": "object"}, run=run)
    assert "error" in r and len(run.calls) == 2

def test_logged_in_false_when_status_not_success():
    run = FakeRun([json.dumps({"status": "UNAUTHENTICATED"})])
    assert agy.logged_in(run=run) is False


def test_agy_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(agy, "find", lambda: None)
    assert agy.ask_video(tmp_path / "v.mp4", "q", {}) == {"error": "agy_missing"}
    assert agy.logged_in() is False

def test_timeout_no_retry(tmp_path):
    import subprocess
    calls = []
    def run(args, **kw):
        calls.append(args); raise subprocess.TimeoutExpired(args, 1)
    r = agy.ask_video(tmp_path / "v.mp4", "q", {}, run=run)
    assert r == {"error": "agy_timeout"} and len(calls) == 1
    assert agy.logged_in(run=run) is False

def test_oserror_becomes_error(tmp_path):
    def run(args, **kw): raise FileNotFoundError("x")
    assert agy.ask_video(tmp_path / "v.mp4", "q", {}, run=run) == {"error": "agy_run_failed:FileNotFoundError"}

def test_codefence_answer_parsed(tmp_path):
    run = FakeRun([_resp('```json\n{"a": 1}\n```')])
    assert agy.ask_video(tmp_path / "v.mp4", "q", {}, run=run)["answer"] == {"a": 1}
