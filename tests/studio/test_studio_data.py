# tests/studio/test_studio_data.py
from pathlib import Path
import scripts.studio_data as sd

def test_parses_scenario_md(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "scenario_2026-06-28.md").write_text(
        "# 2026-06-28 시장 시나리오\n\n"
        "## 오늘의 한 줄\n반도체 강세 지속, 외인 순매수 유입\n\n"
        "## 주도 섹터\n- 반도체\n- 조선\n\n"
        "## 시나리오\n- 코스피 강보합 출발 예상\n- 대장주 중심 순환매\n",
        encoding="utf-8")
    monkeypatch.setattr(sd, "OUT_DIR", out)
    data = sd.get_briefing_data("2026-06-28")
    assert data["date"] == "2026-06-28"
    assert "반도체" in data["headline"]
    assert "반도체" in data["lead_sectors"]
    assert len(data["lines"]) >= 1
    assert data["source"] == "scenario_2026-06-28.md"

def test_missing_file_returns_defaults(tmp_path, monkeypatch):
    out = tmp_path / "out"; out.mkdir()
    monkeypatch.setattr(sd, "OUT_DIR", out)
    data = sd.get_briefing_data("2026-01-01")
    assert data["date"] == "2026-01-01"
    assert data["headline"] == ""
    assert data["lead_sectors"] == []
