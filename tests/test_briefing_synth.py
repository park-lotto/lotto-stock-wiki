import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from briefing_synth import (
    build_briefing_prompt, parse_briefing_response,
    build_insight_prompt, parse_insight_response
)


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


def test_build_insight_prompt_returns_none_without_index_shape():
    assert build_insight_prompt(None, [], []) is None


def test_build_insight_prompt_includes_shape_and_movers():
    shape = {"open": 7650.0, "low": 7550.0, "low_t": "10:30",
              "high": 7890.0, "high_t": "11:50", "current": 7877.0}
    movers = [{"name": "삼성전자", "change_rate": 6.8, "news_reason": "메모리 가격 반등"},
              {"name": "SK하이닉스", "change_rate": 4.7, "news_reason": None}]
    prompt = build_insight_prompt(shape, movers, ["오늘 시장 코멘트"])
    assert "7550.0" in prompt and "10:30" in prompt
    assert "삼성전자" in prompt and "메모리 가격 반등" in prompt
    assert "SK하이닉스" in prompt and "이유 데이터 없음" in prompt
    assert "오늘 시장 코멘트" in prompt


def test_parse_insight_response_valid():
    text = "코멘트: 오늘 코스피가 급락 후 반도체 대형주 중심으로 반등했습니다."
    d = parse_insight_response(text)
    assert "급락 후" in d["comment"]
    assert "movers" not in d


def test_parse_insight_response_no_longer_requires_movers_marker():
    """특징종목 마커는 더 이상 파싱 대상이 아니다 — 코멘트만 있으면 통과."""
    text = "코멘트: 오늘 코스피가 급락 후 반등했습니다.\n특징종목: 삼성전자, SK하이닉스"
    d = parse_insight_response(text)
    assert d["comment"] == "오늘 코스피가 급락 후 반등했습니다."


def test_parse_insight_response_missing_marker_returns_none():
    assert parse_insight_response("그냥 아무말") is None


def test_parse_insight_response_empty_returns_none():
    assert parse_insight_response("") is None
