import pytest
from scripts.channel_pipeline.models import Claim, WikiDecision, PipelineState


def test_claim_defaults():
    c = Claim(
        id="tg_001", channel="telegram", source="태린이아빠",
        content="테스트", claim_type="fact",
    )
    assert c.tickers == []
    assert c.direction == "neutral"
    assert c.conflict_candidate is False
    assert c.sector is None


def test_claim_invalid_channel():
    with pytest.raises(Exception):
        Claim(id="x", channel="twitter", source="s", content="c", claim_type="fact")


def test_claim_invalid_direction():
    with pytest.raises(Exception):
        Claim(id="x", channel="telegram", source="s", content="c",
              claim_type="fact", direction="sideways")


def test_wiki_decision_defaults():
    d = WikiDecision(claim_id="tg_001", action="skip")
    assert d.wiki_file == ""
    assert d.section == "## 최신 이벤트"
    assert d.conflict_note is None


def test_wiki_decision_invalid_action():
    with pytest.raises(Exception):
        WikiDecision(claim_id="x", action="delete")


def test_pipeline_state_defaults():
    s = PipelineState(run_date="2026-06-04")
    assert s.step == "pending"
    assert s.claims_file is None
    assert s.decisions_file is None
    assert s.error is None


def test_pipeline_state_step_transition():
    s = PipelineState(run_date="2026-06-04", step="A_done")
    assert s.step == "A_done"
