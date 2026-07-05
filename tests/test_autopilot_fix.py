import sys
import json
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from autopilot_fix import (
    build_prompt, parse_fix_result, apply_fix, changed_files,
    snapshot_mtimes, changed_relative_paths, within_file_cap,
)


def test_build_prompt_includes_target_files_and_plan():
    diagnosis = {"root_cause": "r", "target_files": ["a.py", "b.py"], "fix_plan": "p"}
    prompt = build_prompt("ch1", diagnosis)
    assert "a.py, b.py" in prompt
    assert "p" in prompt


def test_build_prompt_handles_empty_target_files():
    diagnosis = {"root_cause": "r", "target_files": [], "fix_plan": "p"}
    prompt = build_prompt("ch1", diagnosis)
    assert "명시 안 됨" in prompt


def test_parse_fix_result_extracts_json():
    d = parse_fix_result('done. {"done": true, "summary": "fixed timeout"}')
    assert d["done"] is True
    assert d["summary"] == "fixed timeout"


def test_parse_fix_result_returns_none_for_garbage():
    assert parse_fix_result("no json") is None


def test_apply_fix_disallows_bash_and_parses_result():
    envelope = json.dumps({"result": '{"done": true, "summary": "s"}'})
    with patch("autopilot_fix.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=envelope)
        result = apply_fix("ch1", {"root_cause": "r", "target_files": [], "fix_plan": "p"},
                            cwd="/fake")
    assert result["done"] is True
    called = mock_run.call_args[0][0]
    idx = called.index("--disallowedTools")
    assert called[idx + 1] == "Bash"


def test_apply_fix_returns_none_on_failure():
    with patch("autopilot_fix.subprocess.run", side_effect=Exception("x")):
        result = apply_fix("ch1", {"root_cause": "r", "target_files": [], "fix_plan": "p"},
                            cwd="/fake")
    assert result is None


def test_changed_files_parses_git_status_porcelain():
    with patch("autopilot_fix.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=" M pipeline/atoms/foo.py\n?? scratch.txt\n")
        files = changed_files("/repo")
    assert files == ["pipeline/atoms/foo.py", "scratch.txt"]


def test_snapshot_and_changed_relative_paths_detect_modification(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("v1", encoding="utf-8")
    before = snapshot_mtimes(str(tmp_path), ["a.py", "missing.py"])
    future = time.time() + 5
    os.utime(f, (future, future))
    changed = changed_relative_paths(str(tmp_path), ["a.py", "missing.py"], before)
    assert changed == ["a.py"]


def test_within_file_cap_true_at_boundary():
    assert within_file_cap(["a", "b", "c"], cap=3) is True


def test_within_file_cap_false_over_boundary():
    assert within_file_cap(["a", "b", "c", "d"], cap=3) is False
