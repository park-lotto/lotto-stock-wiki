import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from autopilot_deploy import (
    needs_service_restart, deploy_local, rollback_local,
    backup_remote_files, deploy_remote_crawler, rollback_remote_crawler, health_check,
    append_wiki_log,
)


def test_needs_service_restart_true_for_dashboard_path():
    assert needs_service_restart(["dashboard/server.py"]) is True


def test_needs_service_restart_true_for_server_py():
    assert needs_service_restart(["server.py"]) is True


def test_needs_service_restart_false_for_pipeline_path():
    assert needs_service_restart(["pipeline/atoms/telegram_questionnaire.py"]) is False


def test_deploy_local_commits_pushes_and_restarts_when_allowlisted():
    with patch("autopilot_deploy._run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
            MagicMock(returncode=0, stdout="abc123\n"),
            MagicMock(returncode=0),
        ]
        commit_hash = deploy_local("/repo", "msg", ["dashboard/server.py"])
    assert commit_hash == "abc123"
    assert mock_run.call_count == 5


def test_deploy_local_skips_restart_when_not_allowlisted():
    with patch("autopilot_deploy._run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0), MagicMock(returncode=0),
            MagicMock(returncode=0), MagicMock(returncode=0, stdout="abc123\n"),
        ]
        commit_hash = deploy_local("/repo", "msg", ["pipeline/atoms/foo.py"])
    assert commit_hash == "abc123"
    assert mock_run.call_count == 4


def test_deploy_local_returns_none_when_commit_fails():
    with patch("autopilot_deploy._run") as mock_run:
        mock_run.side_effect = [MagicMock(returncode=0), MagicMock(returncode=1)]
        assert deploy_local("/repo", "msg", []) is None


def test_backup_remote_files_copies_existing_files(tmp_path):
    crawler_root = tmp_path / "crawler"
    crawler_root.mkdir()
    (crawler_root / "a.py").write_text("original", encoding="utf-8")
    backup_root = tmp_path / "backups"
    backups = backup_remote_files(str(crawler_root), ["a.py"], str(backup_root))
    assert "a.py" in backups
    assert Path(backups["a.py"]).read_text(encoding="utf-8") == "original"


def test_rollback_remote_crawler_restores_backup_and_restarts(tmp_path):
    crawler_root = tmp_path / "crawler"
    crawler_root.mkdir()
    (crawler_root / "a.py").write_text("broken", encoding="utf-8")
    backup_file = tmp_path / "backup_a.py"
    backup_file.write_text("original", encoding="utf-8")
    with patch("autopilot_deploy._run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ok = rollback_remote_crawler(str(crawler_root), {"a.py": str(backup_file)})
    assert ok is True
    assert (crawler_root / "a.py").read_text(encoding="utf-8") == "original"


def test_health_check_true_when_active_immediately():
    with patch("autopilot_deploy._run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")
        assert health_check("stockbrain") is True
    assert mock_run.call_count == 1


def test_health_check_false_after_retries_exhausted():
    with patch("autopilot_deploy._run") as mock_run, patch("autopilot_deploy.time.sleep"):
        mock_run.return_value = MagicMock(returncode=3, stdout="inactive\n")
        assert health_check("stockbrain", retries=2, delay=0) is False
    assert mock_run.call_count == 2


def test_append_wiki_log_prepends_line(tmp_path):
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "log.md").write_text("- old entry\n", encoding="utf-8")
    append_wiki_log(str(tmp_path), "- 2026-07-05 — new entry")
    content = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert content == "- 2026-07-05 — new entry\n- old entry\n"


def test_append_wiki_log_creates_file_if_missing(tmp_path):
    (tmp_path / "wiki").mkdir()
    append_wiki_log(str(tmp_path), "- first entry")
    content = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert content == "- first entry\n"
