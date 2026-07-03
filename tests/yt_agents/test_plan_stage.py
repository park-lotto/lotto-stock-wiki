import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.yt_agents import plan_stage


def test_run_plan_stage_yields_done_on_first_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_stage, "OUT", tmp_path)

    with patch("scripts.yt_agents.plan_stage.agent_plan.run", return_value="# 기획서\n내용") as m_run, \
         patch("scripts.yt_agents.plan_stage.agent_plan.qc", return_value={"total": 8, "passed": True, "feedback": ""}):
        events = list(plan_stage.run_plan_stage("반도체 조정", references=[], pipeline_id="test123"))

    types = [e["type"] for e in events]
    assert "step" in types
    assert types[-1] == "done"
    done = events[-1]
    assert done["qc_score"] == 8
    assert done["plan_text"] == "# 기획서\n내용"
    m_run.assert_called_once()

    # state.json 기록 확인
    state_file = tmp_path / "yt_pipeline_test123" / "state.json"
    assert state_file.exists()
    import json
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["steps"]["plan"]["status"] == "done"
    assert state["steps"]["plan"]["qc_score"] == 8


def test_run_plan_stage_retries_until_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_stage, "OUT", tmp_path)

    qc_results = [
        {"total": 5, "passed": False, "feedback": "레퍼런스 인용 부족"},
        {"total": 8, "passed": True, "feedback": ""},
    ]
    with patch("scripts.yt_agents.plan_stage.agent_plan.run", return_value="# 기획서") as m_run, \
         patch("scripts.yt_agents.plan_stage.agent_plan.qc", side_effect=qc_results):
        events = list(plan_stage.run_plan_stage("아이디어", references=[], pipeline_id="test456"))

    running_events = [e for e in events if e["type"] == "step" and "qc_score" in e]
    assert len(running_events) == 2
    assert running_events[0]["qc_score"] == 5
    assert running_events[1]["qc_score"] == 8
    assert events[-1]["qc_score"] == 8
    assert m_run.call_count == 2
    # 두번째 호출은 feedback을 받아야 함
    assert "레퍼런스 인용 부족" in m_run.call_args_list[1].kwargs["feedback"]


def test_format_references_includes_title_and_pct():
    refs = [{"title": "미장 폭락 5%", "channel_title": "3protv", "view_pct_above_avg": 210.0}]
    text = plan_stage._format_references(refs)
    assert "미장 폭락 5%" in text
    assert "3protv" in text
    assert "+210%" in text


def test_format_references_empty_list_returns_empty_string():
    assert plan_stage._format_references([]) == ""
