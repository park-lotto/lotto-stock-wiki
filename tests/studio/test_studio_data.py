# tests/studio/test_studio_data.py
from pathlib import Path
import scripts.studio_data as sd

# daily_scenario 실제 출력 형식(이모지 섹션)을 그대로 본뜬 fixture
REAL_FORMAT = """━━━ 2026-06-28 시장 브리핑 ━━━

📌 오늘 핵심
• 돈이 반도체에서 신기술 섹터로 옮겨가는 움직임이 보여.
• AI 기판과 휴머노이드 성장 기대감이 커.

🔴 강세 종목
종목명        TP·수치          핵심 이유
LG이노텍      TP 200만 (+상향) AI 기판 수요 커서
현대모비스    TP 120만 (+60%) 휴머노이드 성장 기대
선익시스템    71,600원         8세대 장비 개발로

🔵 리스크 종목
종목명        수치             이유
삼성SDI       TP ▼ 531,000     전기차 판매 감소

💡 시나리오
강세: 신기술 수요가 늘면 관련 종목으로 돈이 몰릴 수 있어.
약세: 패시브 펀드 조정으로 변동성이 커질 수 있어.

🎯 오늘 한 줄
신기술 수혜주 관심, 변동성 주의해.
"""


def test_parses_real_emoji_format(tmp_path, monkeypatch):
    out = tmp_path / "out"; out.mkdir()
    (out / "scenario_2026-06-28.md").write_text(REAL_FORMAT, encoding="utf-8")
    monkeypatch.setattr(sd, "OUT_DIR", out)
    data = sd.get_briefing_data("2026-06-28")

    assert data["date"] == "2026-06-28"
    # 🎯 오늘 한 줄 → headline
    assert data["headline"] == "신기술 수혜주 관심, 변동성 주의해."
    assert data["market_mood"] == data["headline"]
    # 🔴 강세 종목명만 추출(헤더행 '종목명' 제외)
    assert "LG이노텍" in data["lead_sectors"]
    assert "현대모비스" in data["lead_sectors"]
    assert "종목명" not in data["lead_sectors"]
    # 📌 오늘 핵심 불릿이 lines로(• 제거)
    assert any("신기술" in ln for ln in data["lines"])
    assert all(not ln.startswith("•") for ln in data["lines"])
    assert data["source"] == "scenario_2026-06-28.md"


def test_headline_falls_back_to_core_when_no_one_liner(tmp_path, monkeypatch):
    out = tmp_path / "out"; out.mkdir()
    (out / "scenario_2026-06-28.md").write_text(
        "📌 오늘 핵심\n• 핵심 한 줄이야.\n", encoding="utf-8")
    monkeypatch.setattr(sd, "OUT_DIR", out)
    data = sd.get_briefing_data("2026-06-28")
    assert data["headline"] == "핵심 한 줄이야."


def test_missing_file_returns_defaults(tmp_path, monkeypatch):
    out = tmp_path / "out"; out.mkdir()
    monkeypatch.setattr(sd, "OUT_DIR", out)
    data = sd.get_briefing_data("2026-01-01")
    assert data["date"] == "2026-01-01"
    assert data["headline"] == ""
    assert data["lead_sectors"] == []
    assert data["source"] == ""
