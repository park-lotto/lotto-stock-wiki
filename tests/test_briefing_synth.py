import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_synth import build_briefing_prompt, parse_briefing_response


def test_build_prompt_returns_none_when_nothing_to_report():
    assert build_briefing_prompt([], [], [], []) is None


def test_build_prompt_includes_alert_and_headline():
    alerts = [{"ts": "09:47", "metric": "J_change_rate", "from": -0.5, "to": -1.8,
               "label": "코스피 등락률"}]
    prompt = build_briefing_prompt(alerts, ["반도체 훈풍"], ["코스닥 급락 위험"], [])
    assert "코스피 등락률" in prompt
    assert "반도체 훈풍" in prompt
    assert "코스닥 급락 위험" in prompt


def test_build_prompt_includes_prior_headlines_for_context():
    prompt = build_briefing_prompt(
        [{"ts": "09:47", "metric": "x", "from": 0, "to": 1, "label": "y"}],
        [], [], ["직전 브리핑: 외국인 매도 전환"])
    assert "직전 브리핑: 외국인 매도 전환" in prompt


def test_parse_valid_response():
    text = "헤드라인: 코스닥 급락 전환\n본문: 코스닥이 오전 내내 완만하다가 갑자기 -4%대로 밀렸습니다."
    d = parse_briefing_response(text)
    assert d["headline"] == "코스닥 급락 전환"
    assert "완만하다가" in d["body"]


def test_parse_no_briefing_marker_returns_none():
    assert parse_briefing_response("브리핑 없음") is None


def test_parse_malformed_response_returns_none():
    assert parse_briefing_response("그냥 아무말") is None
