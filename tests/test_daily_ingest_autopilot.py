import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import daily_ingest_autopilot as auto


def test_process_channel_skips_when_already_diagnosed_today():
    state = {"ch1": {"first_detected": "2026-07-05", "diagnosed_dates": ["2026-07-05"],
                      "latest_outcome": "escalated", "last_seen": "2026-07-05"}}
    with patch("daily_ingest_autopilot.diagnose_mod.diagnose") as mock_diagnose:
        alerts = auto.process_channel("ch1", {"status": "stale"}, state, "12:10", "2026-07-05")
    mock_diagnose.assert_not_called()
    assert alerts == []


def test_process_channel_escalates_when_diagnosis_is_unfixable():
    state = {}
    with patch("daily_ingest_autopilot.diagnose_mod.read_log_tail", return_value=""), \
         patch("daily_ingest_autopilot.diagnose_mod.diagnose") as mock_diagnose:
        mock_diagnose.return_value = {
            "root_cause": "플랫폼 제한", "target": "unfixable",
            "target_files": [], "fix_plan": "", "requires_destructive_action": False,
        }
        alerts = auto.process_channel("ch1", {"status": "never_synced"}, state, "12:10", "2026-07-05")
    assert state["ch1"]["latest_outcome"] == "escalated"
    assert "사람 판단 필요" in alerts[0]


def test_process_channel_escalates_when_destructive_action_required():
    state = {}
    with patch("daily_ingest_autopilot.diagnose_mod.read_log_tail", return_value=""), \
         patch("daily_ingest_autopilot.diagnose_mod.diagnose") as mock_diagnose, \
         patch("daily_ingest_autopilot.fix_mod.apply_fix") as mock_apply:
        mock_diagnose.return_value = {
            "root_cause": "r", "target": "local", "target_files": ["a.py"],
            "fix_plan": "delete stale rows", "requires_destructive_action": True,
        }
        alerts = auto.process_channel("ch1", {"status": "stale"}, state, "12:10", "2026-07-05")
    mock_apply.assert_not_called()
    assert state["ch1"]["latest_outcome"] == "escalated"


def test_process_channel_auto_fixes_local_target_end_to_end():
    state = {}
    with patch("daily_ingest_autopilot.diagnose_mod.read_log_tail", return_value=""), \
         patch("daily_ingest_autopilot.diagnose_mod.diagnose") as mock_diagnose, \
         patch("daily_ingest_autopilot.fix_mod.apply_fix") as mock_apply, \
         patch("daily_ingest_autopilot.fix_mod.changed_files", return_value=["pipeline/atoms/foo.py"]), \
         patch("daily_ingest_autopilot.run_pytest_check", return_value={"ok": True, "failed_tests": []}), \
         patch("daily_ingest_autopilot.deploy_mod.deploy_local", return_value="abc123"), \
         patch("daily_ingest_autopilot.deploy_mod.health_check", return_value=True), \
         patch("daily_ingest_autopilot.deploy_mod.append_wiki_log") as mock_log:
        mock_diagnose.return_value = {
            "root_cause": "r", "target": "local", "target_files": ["pipeline/atoms/foo.py"],
            "fix_plan": "fix timeout", "requires_destructive_action": False,
        }
        mock_apply.return_value = {"done": True, "summary": "타임아웃 상향"}
        alerts = auto.process_channel("ch1", {"status": "stale"}, state, "12:10", "2026-07-05")
    assert "ch1" not in state  # auto_fixed는 채널 항목만 상태에서 제거됨(메타키 _daily_stats는 남음)
    assert "자동수정 완료" in alerts[0]
    mock_log.assert_called_once()
    assert "ch1" in mock_log.call_args[0][1]


def test_process_channel_escalates_and_rolls_back_when_healthcheck_fails():
    state = {}
    with patch("daily_ingest_autopilot.diagnose_mod.read_log_tail", return_value=""), \
         patch("daily_ingest_autopilot.diagnose_mod.diagnose") as mock_diagnose, \
         patch("daily_ingest_autopilot.fix_mod.apply_fix") as mock_apply, \
         patch("daily_ingest_autopilot.fix_mod.changed_files", return_value=["pipeline/atoms/foo.py"]), \
         patch("daily_ingest_autopilot.run_pytest_check", return_value={"ok": True, "failed_tests": []}), \
         patch("daily_ingest_autopilot.deploy_mod.deploy_local", return_value="abc123"), \
         patch("daily_ingest_autopilot.deploy_mod.health_check", return_value=False), \
         patch("daily_ingest_autopilot.deploy_mod.rollback_local") as mock_rollback:
        mock_diagnose.return_value = {
            "root_cause": "r", "target": "local", "target_files": ["pipeline/atoms/foo.py"],
            "fix_plan": "fix timeout", "requires_destructive_action": False,
        }
        mock_apply.return_value = {"done": True, "summary": "s"}
        alerts = auto.process_channel("ch1", {"status": "stale"}, state, "12:10", "2026-07-05")
    mock_rollback.assert_called_once_with(str(auto.ROOT), "abc123", ["pipeline/atoms/foo.py"])
    assert state["ch1"]["latest_outcome"] == "escalated"
    assert "롤백" in alerts[0]


def test_process_channel_escalates_when_fix_diff_exceeds_cap():
    state = {}
    with patch("daily_ingest_autopilot.diagnose_mod.read_log_tail", return_value=""), \
         patch("daily_ingest_autopilot.diagnose_mod.diagnose") as mock_diagnose, \
         patch("daily_ingest_autopilot.fix_mod.apply_fix") as mock_apply, \
         patch("daily_ingest_autopilot.fix_mod.changed_files",
               return_value=["a.py", "b.py", "c.py", "d.py"]):
        mock_diagnose.return_value = {
            "root_cause": "r", "target": "local", "target_files": ["a.py"],
            "fix_plan": "p", "requires_destructive_action": False,
        }
        mock_apply.return_value = {"done": True, "summary": "s"}
        alerts = auto.process_channel("ch1", {"status": "stale"}, state, "12:10", "2026-07-05")
    assert state["ch1"]["latest_outcome"] == "escalated"
    assert "캡" in alerts[0]


def test_process_channel_restores_remote_crawler_backup_when_cap_exceeded():
    state = {}
    with patch("daily_ingest_autopilot.diagnose_mod.read_log_tail", return_value=""), \
         patch("daily_ingest_autopilot.diagnose_mod.diagnose") as mock_diagnose, \
         patch("daily_ingest_autopilot.deploy_mod.backup_remote_files", return_value={"crawlers/telegram_crawler.py": "/backup/path"}), \
         patch("daily_ingest_autopilot.fix_mod.apply_fix") as mock_apply, \
         patch("daily_ingest_autopilot.deploy_mod.rollback_remote_crawler") as mock_rollback:
        mock_diagnose.return_value = {
            "root_cause": "r", "target": "remote_crawler",
            "target_files": ["a.py", "b.py", "c.py", "d.py"],
            "fix_plan": "p", "requires_destructive_action": False,
        }
        mock_apply.return_value = {"done": True, "summary": "s"}
        alerts = auto.process_channel("ch1", {"status": "stale"}, state, "12:10", "2026-07-05")
    mock_rollback.assert_called_once_with(auto.CRAWLER_ROOT, {"crawlers/telegram_crawler.py": "/backup/path"})
    assert state["ch1"]["latest_outcome"] == "escalated"
    assert "캡" in alerts[0]


def test_run_slot_sends_healed_alert_when_channel_recovers():
    state = {"ch1": {"first_detected": "2026-07-03", "last_seen": "2026-07-04",
                      "diagnosed_dates": ["2026-07-03"], "latest_outcome": "escalated"}}
    with patch("daily_ingest_autopilot.state_mod.load_state", return_value=state), \
         patch("daily_ingest_autopilot.state_mod.save_state"), \
         patch("daily_ingest_autopilot._excluded_channels", return_value=set()), \
         patch("daily_ingest_autopilot._CHANNELS", {"ch1": {}}), \
         patch("daily_ingest_autopilot.freshness.check_all_channels",
               return_value=[{"channel": "ch1", "status": "ok", "days_stale": 0,
                              "latest_date": "2026-07-05"}]), \
         patch("daily_ingest_autopilot.send_telegram") as mock_send:
        alerts = auto.run_slot(slot_label="15:10")
    assert any("해결됨" in a for a in alerts)
    mock_send.assert_called()


def test_run_daily_summary_includes_open_escalations_and_sends_telegram():
    state = {
        "ch1": {"first_detected": "2026-07-03", "latest_outcome": "escalated"},
        "_daily_stats": {"date": "2026-07-05", "detected": 2, "auto_fixed": 1, "escalated": 1},
    }
    with patch("daily_ingest_autopilot.state_mod.load_state", return_value=state), \
         patch("daily_ingest_autopilot.run_pytest_check",
               return_value={"ok": True, "failed_tests": []}), \
         patch("daily_ingest_autopilot.check_service_health",
               return_value={"active": True, "restarted": False}), \
         patch("daily_ingest_autopilot.send_telegram") as mock_send:
        card = auto.run_daily_summary()
    assert "ch1" in card
    assert "1건 자동수정" in card
    mock_send.assert_called_once_with(card)


def test_main_dispatches_slot_flag():
    with patch("daily_ingest_autopilot.run_slot") as mock_slot:
        with patch("sys.argv", ["daily_ingest_autopilot.py", "--slot"]):
            auto.main()
    mock_slot.assert_called_once()


def test_main_dispatches_daily_summary_flag():
    with patch("daily_ingest_autopilot.run_daily_summary") as mock_summary:
        with patch("sys.argv", ["daily_ingest_autopilot.py", "--daily-summary"]):
            auto.main()
    mock_summary.assert_called_once()
