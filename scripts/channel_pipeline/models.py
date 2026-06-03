"""
channel_pipeline/models.py — Pydantic 스키마 정의
채널 집계 파이프라인 전체에서 공유하는 데이터 모델
"""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ────────────────────────────────────────────
# Agent A 출력: 개별 클레임
# ────────────────────────────────────────────

class Claim(BaseModel):
    claim_id: str                                               # tg_001, bl_002, rp_003, yt_004
    source_file: str                                            # raw/inbox/telegram/...
    channel: Literal["telegram", "blog", "report", "yt"]
    channel_source: str                                         # 태린이아빠, KB증권, etc.
    claim_type: Literal["fact", "opinion", "prediction", "data"]
    sector: Optional[str] = None                                # 반도체, 조선, etc.
    tickers: list[str] = Field(default_factory=list)            # 종목코드 or 종목명
    content_verbatim: str                                       # 원문 그대로 (최대 500자)
    fact_component: str                                         # 팩트 부분만 추출
    opinion_component: str                                      # 의견/전망 부분
    direction: Literal["bullish", "bearish", "neutral"]
    time_horizon: Optional[Literal["intraday", "swing", "longterm"]] = None
    confidence_signal: Literal["high", "medium", "low"]
    needs_verification: bool = True
    keywords: list[str] = Field(default_factory=list)


class ChannelClaims(BaseModel):
    run_date: str
    channels: dict[str, list[Claim]] = Field(default_factory=dict)
    processing_stats: dict = Field(default_factory=dict)


# ────────────────────────────────────────────
# Agent B 출력: 채널 간 토론
# ────────────────────────────────────────────

class Argument(BaseModel):
    claim_id: str
    channel: str
    channel_source: str
    argument: str                                               # 논거 요약
    logic_strength: Literal["strong", "medium", "weak"]
    fact_basis: bool                                            # 수치/공시 기반 여부


class Debate(BaseModel):
    debate_id: str                                              # dbt_001
    topic: str                                                  # "SK하이닉스 HBM4 공급 이슈"
    tickers: list[str]
    sector: Optional[str] = None
    claim_ids: list[str]
    consensus: Literal["agree", "disagree", "partial"]
    bullish_arguments: list[Argument] = Field(default_factory=list)
    bearish_arguments: list[Argument] = Field(default_factory=list)
    contradiction_detected: bool = False
    contradiction_note: Optional[str] = None
    sonnet_verdict: str                                         # "agree_with_bullish" etc.
    verdict_reason: str
    wiki_promotion_candidate: bool = False
    channel_trust_delta: dict[str, int] = Field(default_factory=dict)  # 채널명: +1/-1


class DebateResult(BaseModel):
    run_date: str
    debates: list[Debate] = Field(default_factory=list)
    fallback_mode: bool = False
    summary: dict = Field(default_factory=dict)


# ────────────────────────────────────────────
# Agent C1 출력: wiki 승격 결정
# ────────────────────────────────────────────

class WikiDecision(BaseModel):
    decision_id: str                                            # dec_001
    debate_id: str
    action: Literal["update", "create", "flag", "skip"]
    target_file: str                                            # wiki/L5_섹터/.../stock_XX.md
    target_section: Optional[str] = None                       # ## 최신 이벤트
    content_to_append: Optional[str] = None                    # 실제 삽입할 마크다운 행
    conflict_with_existing: bool = False
    conflict_note: Optional[str] = None
    flag: Optional[str] = None                                 # "CONFLICT", "NEEDS_VERIFY"


class WikiDecisionResult(BaseModel):
    run_date: str
    wiki_updates: list[WikiDecision] = Field(default_factory=list)
    trust_updates: list[dict] = Field(default_factory=list)
    skip_reasons: list[dict] = Field(default_factory=list)


# ────────────────────────────────────────────
# 채널 신뢰도
# ────────────────────────────────────────────

class ChannelCallRecord(BaseModel):
    id: str
    date: str
    stock: str
    claim: str
    category: str
    status: Literal["pending", "verified", "expired"]
    resolution_date: Optional[str] = None
    actual_result: Optional[str] = None
    verdict: Optional[Literal["correct", "incorrect"]] = None
    tier_promoted: bool = False
    discussion_file: Optional[str] = None


class ChannelStats(BaseModel):
    display_name: str
    platform: str
    speciality: list[str] = Field(default_factory=list)
    grade: str = "C"
    stats: dict = Field(default_factory=lambda: {
        "total_calls": 0, "correct": 0, "incorrect": 0,
        "pending": 0, "accuracy_rate": 0.0
    })
    by_category: dict = Field(default_factory=dict)
    by_sector: dict = Field(default_factory=dict)
    calls: list[ChannelCallRecord] = Field(default_factory=list)


class ChannelReliability(BaseModel):
    version: str = "1.0"
    last_updated: str
    channels: dict[str, ChannelStats] = Field(default_factory=dict)
    grade_thresholds: dict = Field(default_factory=lambda: {
        "S":  {"min_accuracy": 0.85, "min_calls": 20},
        "A+": {"min_accuracy": 0.80, "min_calls": 15},
        "A-": {"min_accuracy": 0.75, "min_calls": 15},
        "B+": {"min_accuracy": 0.70, "min_calls": 10},
        "B-": {"min_accuracy": 0.60, "min_calls": 10},
        "C":  {"min_accuracy": 0.50, "min_calls": 5},
        "D":  {"min_accuracy": 0.00, "min_calls": 0},
    })


# ────────────────────────────────────────────
# Pipeline 상태
# ────────────────────────────────────────────

class StepStatus(BaseModel):
    status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"
    completed_at: Optional[str] = None
    error: Optional[str] = None


class PipelineState(BaseModel):
    schema_version: str = "channel_pipeline_state_v1"
    run_date: str
    pipeline_id: str
    steps: dict[str, StepStatus] = Field(default_factory=lambda: {
        "A_claims":  StepStatus(),
        "B_debate":  StepStatus(),
        "C1_wiki":   StepStatus(),
        "D_update":  StepStatus(),
        "E_html":    StepStatus(),
    })
    file_manifest: dict[str, list[str]] = Field(default_factory=lambda: {
        "telegram": [], "blog": [], "report": [], "yt": []
    })
    cost_estimate_usd: dict = Field(default_factory=dict)
