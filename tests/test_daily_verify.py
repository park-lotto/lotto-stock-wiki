import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from unittest.mock import patch, MagicMock

from daily_verify import (
    count_today_files, weekday_average, check_crawl_freshness,
    run_pytest_check, check_service_health,
    render_verify_card, load_verify_history, save_verify_counts,
)


def test_count_today_files_flat_pattern(tmp_path):
    d = tmp_path / "telegram"
    d.mkdir()
    (d / "2026-07-03_주식픽.md").write_text("x", encoding="utf-8")
    (d / "2026-07-03_그로스리서치.md").write_text("x", encoding="utf-8")
    (d / "2026-07-02_주식픽.md").write_text("x", encoding="utf-8")
    assert count_today_files(str(tmp_path), "telegram", "2026-07-03") == 2


def test_count_today_files_subfolder_pattern(tmp_path):
    d = tmp_path / "news" / "2026-07-03"
    d.mkdir(parents=True)
    (d / "a.md").write_text("x", encoding="utf-8")
    (d / "b.md").write_text("x", encoding="utf-8")
    assert count_today_files(str(tmp_path), "news", "2026-07-03") == 2


def test_count_today_files_missing_returns_zero(tmp_path):
    assert count_today_files(str(tmp_path), "report", "2026-07-03") == 0


def test_weekday_average_computes_from_matching_weekday_only():
    # 2026-07-03(금)=weekday 4. 같은 금요일 표본만 평균에 들어가야 함.
    history = {
        "2026-06-19": {"telegram": 10},  # 금
        "2026-06-26": {"telegram": 20},  # 금
        "2026-06-20": {"telegram": 999},  # 토(다른 요일, 제외돼야 함)
    }
    avg = weekday_average(history, "telegram", weekday=4, weeks=4)
    assert avg == 15.0


def test_weekday_average_returns_none_when_no_samples():
    assert weekday_average({}, "telegram", weekday=4, weeks=4) is None


def test_check_crawl_freshness_flags_source_below_30pct_of_average(tmp_path):
    d = tmp_path / "telegram"
    d.mkdir()
    (d / "2026-07-03_a.md").write_text("x", encoding="utf-8")  # 오늘 1건
    history = {"2026-06-26": {"telegram": 10}}  # 지난주 같은 요일 10건 -> 평균 10
    alerts = check_crawl_freshness(str(tmp_path), ["telegram"], history, "2026-07-03")
    assert len(alerts) == 1
    assert alerts[0]["source"] == "telegram"
    assert alerts[0]["level"] == "orange"


def test_check_crawl_freshness_skips_when_no_history_yet(tmp_path):
    d = tmp_path / "telegram"
    d.mkdir()
    alerts = check_crawl_freshness(str(tmp_path), ["telegram"], {}, "2026-07-03")
    assert alerts == []


def test_run_pytest_check_parses_failed_test_names():
    fake_output = (
        b"===== FAILURES =====\n"
        b"FAILED tests/test_a.py::test_one - AssertionError\n"
        b"FAILED tests/test_b.py::test_two - ValueError\n"
    )
    with patch("daily_verify.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout=fake_output, stderr=b"")
        result = run_pytest_check("/fake/root")
    assert result["ok"] is False
    assert result["failed_tests"] == [
        "tests/test_a.py::test_one", "tests/test_b.py::test_two"]


def test_run_pytest_check_ok_when_returncode_zero():
    with patch("daily_verify.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        result = run_pytest_check("/fake/root")
    assert result == {"ok": True, "failed_tests": []}


def test_run_pytest_check_exception_is_not_an_alert():
    with patch("daily_verify.subprocess.run", side_effect=Exception("timeout")):
        result = run_pytest_check("/fake/root")
    assert result["ok"] is True
    assert "측정 실패" in result["error"]


def test_check_service_health_active_no_restart():
    with patch("daily_verify.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"active\n", stderr=b"")
        result = check_service_health("stockbrain")
    assert result == {"active": True, "restarted": False}
    assert mock_run.call_count == 1   # is-active만 호출, restart는 안 함


def test_check_service_health_inactive_triggers_restart_attempt():
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "is-active" in cmd and len(calls) == 1:
            return MagicMock(returncode=3, stdout=b"inactive\n", stderr=b"")
        if "restart" in cmd:
            return MagicMock(returncode=0, stdout=b"", stderr=b"")
        return MagicMock(returncode=0, stdout=b"active\n", stderr=b"")  # 재확인
    with patch("daily_verify.subprocess.run", side_effect=fake_run):
        result = check_service_health("stockbrain")
    assert result == {"active": True, "restarted": True}
    assert calls[0] == ["systemctl", "is-active", "stockbrain"]
    assert calls[1] == ["sudo", "systemctl", "restart", "stockbrain"]


def test_render_verify_card_all_ok_is_one_line():
    card = render_verify_card("2026-07-03", [], {"ok": True, "failed_tests": []},
                               {"active": True, "restarted": False})
    assert card.startswith("✅")
    assert "\n" not in card


def test_render_verify_card_shows_freshness_alert():
    card = render_verify_card(
        "2026-07-03",
        [{"source": "telegram", "today": 1, "avg": 10.0, "level": "orange"}],
        {"ok": True, "failed_tests": []}, {"active": True, "restarted": False})
    assert "⚠️" in card
    assert "telegram" in card


def test_render_verify_card_shows_pytest_failures():
    card = render_verify_card(
        "2026-07-03", [],
        {"ok": False, "failed_tests": ["tests/test_a.py::test_one"]},
        {"active": True, "restarted": False})
    assert "test_one" in card


def test_render_verify_card_shows_service_restart():
    card = render_verify_card(
        "2026-07-03", [], {"ok": True, "failed_tests": []},
        {"active": True, "restarted": True})
    assert "재시작" in card


def test_save_and_load_verify_history_roundtrip(tmp_path):
    path = str(tmp_path / "hist.json")
    save_verify_counts(path, "2026-07-03", {"telegram": 5, "news": 10})
    hist = load_verify_history(path)
    assert hist["2026-07-03"] == {"telegram": 5, "news": 10}


def test_save_verify_counts_keeps_only_14_days(tmp_path):
    path = str(tmp_path / "hist.json")
    for i in range(1, 20):
        save_verify_counts(path, f"2026-06-{i:02d}", {"telegram": i})
    hist = load_verify_history(path)
    assert len(hist) == 14
