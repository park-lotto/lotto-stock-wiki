"""11-06 삼현정 #10009·#10010: 회원 PC 절전이 실행기 일(계획·렌더)을 재워 끊음 — 실행기가 도는 동안 절전 막기(runner_ops.keep_awake 한 곳)."""
import sys
import types

from tools.calcopy.hybrid import runner_ops as R


def test_windows_sets_execution_state(monkeypatch):
    calls = []
    fake = types.SimpleNamespace(windll=types.SimpleNamespace(kernel32=types.SimpleNamespace(SetThreadExecutionState=lambda f: calls.append(f) or 1)))
    monkeypatch.setitem(sys.modules, "ctypes", fake)
    assert R.keep_awake("win32") == "win"
    assert calls and calls[0] & 0x80000000 and calls[0] & 0x1 and not calls[0] & 0x2   # 화면 끄기는 허용(ES_DISPLAY_REQUIRED 아님)


def test_mac_runs_caffeinate_tied_to_pid(monkeypatch):
    seen = {}
    monkeypatch.setattr(R.subprocess, "Popen", lambda args, **k: seen.setdefault("a", args))
    assert R.keep_awake("darwin") == "mac"
    assert seen["a"][:3] == ["caffeinate", "-i", "-w"]


def test_main_calls_keep_awake():
    import inspect
    assert "keep_awake()" in inspect.getsource(R.main)
