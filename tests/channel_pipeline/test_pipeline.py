import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from scripts.channel_pipeline.models import Claim, WikiDecision, PipelineState


@pytest.fixture
def run_date():
    return "2026-06-04"


@pytest.fixture
def mock_claims():
    return [
        Claim(
            id="tg_001", channel="telegram", source="태린이아빠",
            content="HBM4 협상 본격화", claim_type="fact",
            sector="반도체", tickers=["SK하이닉스"], direction="bullish",
        ),
    ]


@pytest.fixture
def mock_decisions():
    return [
        WikiDecision(
            claim_id="tg_001", action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 협상 본격화 (태린이아빠/텔레그램)",
        ),
    ]


def test_load_state_new(tmp_path):
    from scripts.channel_pipeline.pipeline import load_state
    state = load_state("2026-06-04", base_dir=tmp_path)
    assert state.run_date == "2026-06-04"
    assert state.step == "pending"


def test_save_and_load_state(tmp_path):
    from scripts.channel_pipeline.pipeline import load_state, save_state
    state = PipelineState(
        run_date="2026-06-04", step="A_done",
        claims_file="pipeline/20260604/claims.json",
    )
    save_state(state, base_dir=tmp_path)
    loaded = load_state("2026-06-04", base_dir=tmp_path)
    assert loaded.step == "A_done"
    assert loaded.claims_file == "pipeline/20260604/claims.json"


@pytest.mark.asyncio
async def test_pipeline_dry_run(tmp_path, run_date, mock_claims, mock_decisions, tmp_wiki):
    from scripts.channel_pipeline.pipeline import run_pipeline

    briefing_path = tmp_path / "out" / f"briefing_{run_date.replace('-','')}.html"
    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_path.write_text("<html>test</html>", encoding="utf-8")

    with patch("scripts.channel_pipeline.pipeline.get_manifest",
               return_value={"telegram": [], "blog": [], "report": [], "yt": []}), \
         patch("scripts.channel_pipeline.pipeline.can_run",
               return_value=(True, 0.01, "테스트 $0.01")), \
         patch("scripts.channel_pipeline.pipeline.agent_a.run",
               new_callable=AsyncMock, return_value=mock_claims), \
         patch("scripts.channel_pipeline.pipeline.agent_b.run",
               return_value=mock_decisions), \
         patch("scripts.channel_pipeline.pipeline.agent_d.run",
               return_value=briefing_path):

        state = await run_pipeline(
            run_date, base_dir=tmp_path, wiki_root=tmp_wiki, dry_run=True,
        )
        assert state.step == "done"
        assert state.claims_file is not None
        assert state.decisions_file is not None


@pytest.mark.asyncio
async def test_pipeline_agent_a_failure(tmp_path, run_date, tmp_wiki):
    from scripts.channel_pipeline.pipeline import run_pipeline

    with patch("scripts.channel_pipeline.pipeline.get_manifest",
               return_value={"telegram": [], "blog": [], "report": [], "yt": []}), \
         patch("scripts.channel_pipeline.pipeline.can_run",
               return_value=(True, 0.01, "테스트")), \
         patch("scripts.channel_pipeline.pipeline.agent_a.run",
               new_callable=AsyncMock, side_effect=RuntimeError("API 오류")):

        state = await run_pipeline(run_date, base_dir=tmp_path, wiki_root=tmp_wiki)
        assert state.step == "failed"
        assert "Agent A" in state.error


@pytest.mark.asyncio
async def test_pipeline_resume(tmp_path, run_date, mock_claims, mock_decisions, tmp_wiki):
    from scripts.channel_pipeline.pipeline import run_pipeline, save_state

    # A 단계 완료 상태 미리 저장
    pd = tmp_path / "pipeline" / run_date.replace("-", "")
    pd.mkdir(parents=True, exist_ok=True)
    claims_path = pd / "claims.json"
    claims_path.write_text(
        json.dumps([c.model_dump() for c in mock_claims], ensure_ascii=False),
        encoding="utf-8",
    )
    pre_state = PipelineState(
        run_date=run_date, step="A_done",
        claims_file=str(claims_path.relative_to(tmp_path)),
    )
    save_state(pre_state, base_dir=tmp_path)

    briefing_path = tmp_path / "out" / f"briefing_{run_date.replace('-','')}.html"
    briefing_path.parent.mkdir(parents=True, exist_ok=True)
    briefing_path.write_text("<html>test</html>", encoding="utf-8")

    with patch("scripts.channel_pipeline.pipeline.get_manifest",
               return_value={"telegram": [], "blog": [], "report": [], "yt": []}), \
         patch("scripts.channel_pipeline.pipeline.can_run",
               return_value=(True, 0.01, "테스트")), \
         patch("scripts.channel_pipeline.pipeline.agent_a.run",
               new_callable=AsyncMock) as mock_a, \
         patch("scripts.channel_pipeline.pipeline.agent_b.run",
               return_value=mock_decisions), \
         patch("scripts.channel_pipeline.pipeline.agent_d.run",
               return_value=briefing_path):

        state = await run_pipeline(
            run_date, base_dir=tmp_path, wiki_root=tmp_wiki,
            dry_run=True, resume=True,
        )
        assert state.step == "done"
        mock_a.assert_not_called()  # resume이라 A 재실행 안 함
