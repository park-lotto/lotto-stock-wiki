import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from daily_verify import count_today_files, weekday_average, check_crawl_freshness


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
