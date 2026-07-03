import json
from scripts.goal_loop import quality

def test_critique_parses_pass():
    fake = lambda p: json.dumps({"pass": True, "issues": []})
    r = quality.critique({"headline": "삼성전자 8조 투자, 매수 우위"}, fake)
    assert r["pass"] is True and r["issues"] == []

def test_critique_parses_fail():
    fake = lambda p: json.dumps({"pass": False, "issues": ["수치 없음", "양면론"]})
    r = quality.critique({"headline": "시장은 혼조세"}, fake)
    assert r["pass"] is False and "양면론" in r["issues"]

def test_critique_bad_json_defaults_fail():
    r = quality.critique({"headline": "x"}, lambda p: "not json")
    assert r["pass"] is False

def test_revise_returns_dict():
    revised = quality.revise({"headline": "혼조"}, ["수치 없음"],
                             lambda p: json.dumps({"headline": "코스피 -1.2%, 반도체 +3%"}))
    assert revised["headline"].startswith("코스피")
