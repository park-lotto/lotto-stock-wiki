import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from autopilot_diagnose import build_prompt, parse_diagnosis, diagnose, read_log_tail


def test_build_prompt_includes_channel_status_and_log():
    prompt = build_prompt(
        "그로쓰리서치특징주",
        {"status": "never_synced", "days_stale": None, "latest_date": None},
        "some crawler log line")
    assert "그로쓰리서치특징주" in prompt
    assert "never_synced" in prompt
    assert "some crawler log line" in prompt


def test_parse_diagnosis_extracts_json_with_defaults():
    raw = 'blah {"root_cause": "x", "target": "local"} trailing'
    d = parse_diagnosis(raw)
    assert d["target"] == "local"
    assert d["requires_destructive_action"] is False
    assert d["fix_plan"] == ""
    assert d["target_files"] == []


def test_parse_diagnosis_preserves_explicit_true_destructive_flag():
    raw = '{"root_cause": "x", "target": "local", "requires_destructive_action": true}'
    d = parse_diagnosis(raw)
    assert d["requires_destructive_action"] is True


def test_parse_diagnosis_rejects_invalid_target():
    raw = '{"root_cause": "x", "target": "something_else"}'
    assert parse_diagnosis(raw) is None


def test_parse_diagnosis_returns_none_for_garbage():
    assert parse_diagnosis("no json here") is None


def test_diagnose_calls_claude_with_disallowed_tools_and_parses_result():
    envelope = json.dumps({"result": '{"root_cause": "r", "target": "unfixable"}'})
    with patch("autopilot_diagnose.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=envelope)
        result = diagnose("ch", {"status": "stale", "days_stale": 3}, "", cwd="/fake")
    assert result["target"] == "unfixable"
    called = mock_run.call_args[0][0]
    idx = called.index("--disallowedTools")
    assert called[idx + 1] == "Edit,Write,NotebookEdit,Bash"


def test_diagnose_returns_none_on_subprocess_failure():
    with patch("autopilot_diagnose.subprocess.run", side_effect=Exception("timeout")):
        result = diagnose("ch", {"status": "stale"}, "", cwd="/fake")
    assert result is None


def test_read_log_tail_returns_last_n_lines(tmp_path):
    log = tmp_path / "service.log"
    log.write_text("\n".join(f"line{i}" for i in range(200)), encoding="utf-8")
    tail = read_log_tail(str(log), lines=5)
    assert "line199" in tail
    assert "line0" not in tail


def test_read_log_tail_missing_file_returns_empty(tmp_path):
    assert read_log_tail(str(tmp_path / "nope.log")) == ""
