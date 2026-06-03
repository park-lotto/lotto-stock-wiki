from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Claim(BaseModel):
    id: str
    channel: Literal["telegram", "blog", "report", "yt"]
    source: str
    content: str
    claim_type: Literal["fact", "opinion", "prediction"]
    sector: Optional[str] = None
    tickers: list[str] = Field(default_factory=list)
    direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    conflict_candidate: bool = False


class WikiDecision(BaseModel):
    claim_id: str
    action: Literal["append", "flag", "skip"]
    wiki_file: str = ""
    section: str = "## 최신 이벤트"
    line: str = ""
    conflict_note: Optional[str] = None


class PipelineState(BaseModel):
    run_date: str
    step: Literal["pending", "A_done", "B_done", "done", "failed"] = "pending"
    claims_file: Optional[str] = None
    decisions_file: Optional[str] = None
    error: Optional[str] = None
