# tests/nlm_bridge/test_notebook_calls.py
import json
from scripts import nlm_bridge as nb


def test_create_notebook_parses_json_id(monkeypatch):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=90, _auth_retry=True:
                        (True, json.dumps({"id": "abc-123"}), ""))
    r = nb.create_notebook("[골루프] 아침브리핑 2026-07-03")
    assert r["ok"] is True and r["notebook_id"] == "abc-123"


def test_create_notebook_fails_returns_error(monkeypatch):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=90, _auth_retry=True:
                        (False, "", "Authentication expired"))
    r = nb.create_notebook("x")
    assert r["ok"] is False and "로그인" in r["error"]


def test_add_source_file(monkeypatch):
    calls = {}
    def fake(args, timeout=90, _auth_retry=True):
        calls["args"] = args
        return True, "", ""
    monkeypatch.setattr(nb, "_run_nlm", fake)
    r = nb.add_source_file("nb1", "/tmp/x.md", "제목")
    assert r["ok"] is True
    assert calls["args"] == ["source", "add", "nb1", "--file", "/tmp/x.md", "--title", "제목"]


def test_notebook_query_parses_answer(monkeypatch):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=180, _auth_retry=True:
                        (True, json.dumps({"answer": "본문", "conversation_id": "c1"}), ""))
    r = nb.notebook_query("nb1", "질문")
    assert r["ok"] is True and r["answer"] == "본문" and r["conversation_id"] == "c1"


def test_notebook_query_fails(monkeypatch):
    monkeypatch.setattr(nb, "_run_nlm", lambda args, timeout=180, _auth_retry=True:
                        (False, "", "timeout"))
    r = nb.notebook_query("nb1", "질문")
    assert r["ok"] is False and r["answer"] == ""


def test_add_source_urls_empty_lists_short_circuits(monkeypatch):
    def fail_if_called(args, timeout=90, _auth_retry=True):
        raise AssertionError("_run_nlm must not be called when both url lists are empty")
    monkeypatch.setattr(nb, "_run_nlm", fail_if_called)
    r = nb.add_source_urls("nb1", [], [])
    assert r == {"ok": True, "error": ""}


def test_add_source_urls_builds_args_and_returns_ok(monkeypatch):
    calls = {}
    def fake(args, timeout=90, _auth_retry=True):
        calls["args"] = args
        return True, "", ""
    monkeypatch.setattr(nb, "_run_nlm", fake)
    r = nb.add_source_urls("nb1", ["https://youtu.be/abc"], ["https://example.com/x"])
    assert calls["args"] == [
        "source", "add", "nb1",
        "--youtube", "https://youtu.be/abc",
        "--url", "https://example.com/x",
    ]
    assert r == {"ok": True, "error": ""}


def test_create_report_no_artifact_returns_ready_false(monkeypatch, tmp_path):
    def fake(args, timeout=90, _auth_retry=True):
        if args[0] == "report":
            return True, "", ""
        if args[0] == "studio":
            return True, json.dumps([]), ""
        if args[0] == "download":
            return False, "", "no artifact"
        return True, "", ""
    monkeypatch.setattr(nb, "_run_nlm", fake)
    monkeypatch.setattr(nb.time, "sleep", lambda s: None)   # 폴링 대기 skip
    r = nb.create_report("nb1", out_dir=str(tmp_path))
    assert r["ok"] is True and r["ready"] is False and r["markdown"] == ""
