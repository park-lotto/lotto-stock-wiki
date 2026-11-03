# -*- coding: utf-8 -*-
"""#3558 — 설치본 내장 파이썬엔 ensurepip·pip 가 없다(build_win slim_python). 무료 자막 지우기 설치는 그때 --without-pip 로 가상환경을 만들고 pip 를 따로 깐다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.free_subclean import engine as E  # noqa: E402


def test_install_without_ensurepip_bootstraps_pip(tmp_path, monkeypatch):
    calls, boot = [], []
    monkeypatch.setattr(E, "HOME", tmp_path)
    monkeypatch.setattr(E, "py_path", lambda: tmp_path / "v" / "python.exe")
    monkeypatch.setattr(E, "_has", lambda py, mod: False)            # ensurepip 없음 · 새 가상환경에 pip 없음

    def run(cmd, **k):
        calls.append([str(c) for c in cmd])
        if "venv" in cmd:
            (tmp_path / "v").mkdir(); (tmp_path / "v" / "python.exe").write_text("")
        class R: returncode, stdout, stderr = 1, "", "no gpu"
        return R()
    monkeypatch.setattr(E.subprocess, "run", run)
    monkeypatch.setattr(E, "_bootstrap_pip", lambda log=print: boot.append(1))
    (tmp_path / "big-lama.pt").write_text("")
    E.install(log=lambda *_: None)
    assert "--without-pip" in calls[0] and boot == [1]


def test_build_keeps_ensurepip():
    src = (ROOT / "installer" / "win" / "build_win.py").read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if l.startswith("PY_DROP_DIRS"))
    assert "ensurepip" not in line
