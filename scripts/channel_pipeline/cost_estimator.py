"""
channel_pipeline/cost_estimator.py — 일비용 추정 및 예산 가드
목표: $0.06/일 이하. 하드스톱: $0.08
"""

from __future__ import annotations
from pathlib import Path

# 모델별 가격 ($/1M 토큰, 2026-06 기준)
PRICES = {
    "gemini-2.5-flash":  {"in": 0.15,  "out": 0.60},
    "claude-sonnet-4-6": {"in": 3.00,  "out": 15.0},
    "claude-haiku-4-5":  {"in": 0.25,  "out": 1.25},
}

DAILY_BUDGET_USD = 0.060
HARD_STOP_USD    = 0.080

# 파일당 평균 토큰 추정 (경험치)
AVG_TOKENS = {
    "telegram": 2_000,
    "blog":     3_000,
    "report":   1_500,
    "yt":       1_000,
}


def _cost(model: str, in_tok: int, out_tok: int) -> float:
    p = PRICES[model]
    return (in_tok * p["in"] + out_tok * p["out"]) / 1_000_000


def estimate_A(manifest: dict[str, list[str]]) -> float:
    """Gemini Flash — 원문 분류"""
    total_in = sum(len(files) * AVG_TOKENS[ch] for ch, files in manifest.items())
    total_out = int(total_in * 0.15)   # 출력은 입력의 15% 수준
    return _cost("gemini-2.5-flash", total_in, total_out)


def estimate_B(num_claims: int) -> float:
    """Sonnet — 채널 간 토론 (클레임 50개 기준)"""
    in_tok  = min(num_claims, 50) * 200 + 2_000   # 클레임당 ~200 토큰 + 시스템
    out_tok = min(num_claims, 50) * 150
    return _cost("claude-sonnet-4-6", in_tok, out_tok)


def estimate_C1(num_candidates: int) -> float:
    """Sonnet — wiki 승격 결정"""
    in_tok  = num_candidates * 1_500 + 2_000
    out_tok = num_candidates * 300
    return _cost("claude-sonnet-4-6", in_tok, out_tok)


def estimate_D(num_decisions: int) -> float:
    """Haiku — wiki 파일 업데이트"""
    in_tok  = num_decisions * 500 + 1_000
    out_tok = num_decisions * 100
    return _cost("claude-haiku-4-5", in_tok, out_tok)


def estimate_E() -> float:
    """Haiku — HTML 브리핑 생성"""
    return _cost("claude-haiku-4-5", 4_000, 2_000)


def total_estimate(manifest: dict[str, list[str]]) -> float:
    num_files = sum(len(v) for v in manifest.values())
    num_claims = num_files * 3       # 파일당 평균 3개 클레임
    num_candidates = max(1, num_claims // 10)
    num_decisions = max(1, num_candidates // 2)

    return (
        estimate_A(manifest)
        + estimate_B(num_claims)
        + estimate_C1(num_candidates)
        + estimate_D(num_decisions)
        + estimate_E()
    )


def can_run(manifest: dict[str, list[str]]) -> tuple[bool, float, str]:
    """(실행 가능 여부, 예상 비용, 사유)"""
    cost = total_estimate(manifest)

    if cost > HARD_STOP_USD:
        return False, cost, f"예상 비용 ${cost:.3f} > 하드스톱 ${HARD_STOP_USD}"
    if cost > DAILY_BUDGET_USD:
        return True, cost, f"⚠️ 예산 초과 ${cost:.3f} > ${DAILY_BUDGET_USD} (계속 진행)"
    return True, cost, f"✅ 예상 비용 ${cost:.3f}"


def reduce_scope(manifest: dict[str, list[str]]) -> dict[str, list[str]]:
    """비용 초과 시 범위 축소: blog 제거 → report 최신 10건으로 제한"""
    reduced = dict(manifest)
    cost = total_estimate(reduced)

    if cost > HARD_STOP_USD:
        reduced["blog"] = []
        cost = total_estimate(reduced)

    if cost > HARD_STOP_USD:
        reduced["report"] = sorted(reduced["report"])[-10:]

    return reduced
