from briefing_weather import build_prompt, parse_result


def test_build_prompt_includes_events_and_story():
    p = build_prompt(
        facts={"J": {"rate": 5.76, "current": 8088}},
        events=[{"label": "외인 순매도→순매수 전환"}],
        story={"verdict": {"line": "약세 지속"}, "turning_points": []},
        news=["삼성전자 8조 기판 투자 공시"], phase="intraday")
    assert "외인 순매도→순매수 전환" in p
    assert "삼성전자 8조" in p
    assert "약세 지속" in p


def test_parse_result_valid_json():
    raw = '{"verdict":{"tone":"🟢위험선호","line":"외인 매수 유지"},"narrative":"...","new_turning_points":[{"ts":"11:20","label":"외인 전환","major":true}],"used_news_ids":["a1"]}'
    d = parse_result(raw)
    assert d["verdict"]["line"] == "외인 매수 유지"
    assert d["new_turning_points"][0]["ts"] == "11:20"


def test_parse_result_with_codefence():
    raw = '```json\n{"verdict":{"tone":"t","line":"l"},"narrative":"n","new_turning_points":[],"used_news_ids":[]}\n```'
    assert parse_result(raw)["verdict"]["line"] == "l"


def test_parse_result_garbage_returns_none():
    assert parse_result("모델이 그냥 문장으로 답함") is None
