# -*- coding: utf-8 -*-
"""서버 제미나이 창구가 429·SSH 로 교차 확인을 못 채우면 로컬 공용 풀로 모자란 모델만 채운다(10-18 다섯 편 동시 제작 — 작업자 손 우회 3번)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.engine import gemini_free as GF  # noqa: E402
from tools.calcopy.engine import gemini_server as G  # noqa: E402


def _fake_local(calls):
    def f(parts, prompt, tag="", models=None):
        calls.append(models[0])
        return {"text": "ok", "_model": models[0]}, None
    return f


def test_fills_only_missing_models(monkeypatch):
    calls = []
    monkeypatch.setattr(GF, "_ask_local", _fake_local(calls))
    monkeypatch.setattr(G, "_ssh_py", lambda *a, **k: {"runs": [[{"model": "m1", "json": {"text": "a"}}, {"model": "m2", "why": "429"}]]})
    r = G.ask_files([], "p", "text", models=("m1", "m2"), fallback=("m3",), cross_n=2)
    j = r["jobs"][0]
    assert calls == ["m2"] and j["cross_ok"] and j["ok_models"] == ["m1", "m2"]


def test_server_down_all_local(monkeypatch):
    calls = []
    monkeypatch.setattr(GF, "_ask_local", _fake_local(calls))
    monkeypatch.setattr(G, "_ssh_py", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("rc=255")))
    j = G.ask_files([], "p", "text", models=("m1", "m2"), fallback=(), cross_n=2)["jobs"][0]
    assert sorted(calls) == ["m1", "m2"] and j["cross_ok"] and any(f["model"] == "server" for f in j["failed"])


def test_no_fill_when_server_ok(monkeypatch):
    calls = []
    monkeypatch.setattr(GF, "_ask_local", _fake_local(calls))
    monkeypatch.setattr(G, "_ssh_py", lambda *a, **k: {"runs": [[{"model": "m1", "json": {}}, {"model": "m2", "json": {}}]]})
    assert G.ask_files([], "p", "text", models=("m1", "m2"), cross_n=2)["jobs"][0]["cross_ok"] and calls == []
