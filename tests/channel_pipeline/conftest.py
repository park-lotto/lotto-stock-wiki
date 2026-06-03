import pytest
from pathlib import Path


@pytest.fixture
def tmp_wiki(tmp_path):
    """임시 wiki 디렉토리 생성 — stock 파일 포함"""
    stock_dir = tmp_path / "wiki" / "L5_섹터" / "반도체" / "stock"
    stock_dir.mkdir(parents=True)
    stock_file = stock_dir / "stock_SK하이닉스.md"
    stock_file.write_text(
        "# SK하이닉스\n\n## 기본 정보\n테스트\n\n## 최신 이벤트\n- [2026-05-01] 기존 이벤트\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def sample_claims():
    from scripts.channel_pipeline.models import Claim
    return [
        Claim(
            id="tg_001",
            channel="telegram",
            source="태린이아빠",
            content="HBM4 계약 가격 협상 2분기 본격화",
            claim_type="fact",
            sector="반도체",
            tickers=["SK하이닉스", "000660"],
            direction="bullish",
            conflict_candidate=False,
        ),
        Claim(
            id="rp_001",
            channel="report",
            source="KB증권",
            content="HBM4 공급 과잉 우려로 가격 하락 가능",
            claim_type="opinion",
            sector="반도체",
            tickers=["SK하이닉스"],
            direction="bearish",
            conflict_candidate=True,
        ),
    ]


@pytest.fixture
def sample_decisions():
    from scripts.channel_pipeline.models import WikiDecision
    return [
        WikiDecision(
            claim_id="tg_001",
            action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 계약 가격 협상 2분기 본격화 (태린이아빠/텔레그램)",
        ),
        WikiDecision(
            claim_id="rp_001",
            action="flag",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 공급 과잉 우려 (KB증권/리포트)",
            conflict_note="태린이아빠(bullish)와 방향 상충",
        ),
    ]
