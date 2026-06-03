"""
channel_pipeline/agent_B.py — Claude Sonnet: 채널 간 교차검증·반박·토론

Sonnet이 하는 일:
  - 같은 종목/테마에 대한 여러 채널 주장 교차검증
  - 논리적 반박 생성
  - 충돌·합의 판정
  - wiki 승격 후보 선별
"""

from __future__ import annotations
import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import anthropic

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from channel_pipeline.models import Argument, Debate, DebateResult
from channel_pipeline import trust_tracker

MODEL = "claude-sonnet-4-6"
MAX_CLAIMS_PER_CALL = 20   # Sonnet 1회 호출당 처리 클레임 수

SYSTEM_PROMPT = """당신은 한국 주식 정보 교차검증 전문가입니다.
여러 채널(텔레그램·블로그·증권사리포트·유튜브)의 클레임을 비교하여 토론을 생성하세요.

규칙:
1. 같은 종목/테마에 대한 서로 다른 주장을 debate로 묶으세요
2. 팩트 근거(수치·공시·데이터) 있는 주장 = logic_strength: strong
3. 단순 의견/추측 = logic_strength: weak
4. 시간지평 불일치(단기 기술적 vs 장기 펀더멘털)는 별도 명시
5. channel_trust_delta: 팩트 기반으로 맞을 가능성 높은 채널 +1, 틀릴 가능성 -1
6. wiki_promotion_candidate: 새 정보 or 중요 충돌만 true (단순 반복 false)
7. 단일 채널 클레임(교차 대상 없음)도 중요하면 debate에 포함 (단독 주장)
8. 출력은 JSON 배열만. 다른 텍스트 절대 금지.

출력 형식:
[
  {
    "debate_id": "dbt_001",
    "topic": "SK하이닉스 HBM4 수급 전망",
    "tickers": ["SK하이닉스", "000660"],
    "sector": "반도체",
    "claim_ids": ["rp_012", "tg_003"],
    "consensus": "partial",
    "bullish_arguments": [
      {
        "claim_id": "rp_012",
        "channel": "report",
        "channel_source": "NH투자증권",
        "argument": "HBM4 독점 공급 구조 확인, TP 3,100,000원 상향",
        "logic_strength": "strong",
        "fact_basis": true
      }
    ],
    "bearish_arguments": [
      {
        "claim_id": "tg_003",
        "channel": "telegram",
        "channel_source": "태린이아빠",
        "argument": "10일선 이탈, 단기 차익매물 주의",
        "logic_strength": "weak",
        "fact_basis": false
      }
    ],
    "contradiction_detected": true,
    "contradiction_note": "리포트(장기 펀더멘털) vs 텔레그램(단기 기술적) — 시간지평 불일치",
    "sonnet_verdict": "agree_with_bullish",
    "verdict_reason": "NH 리포트 근거(TP 상향+HBM4 독점)가 팩트 기반. 단기 기술적 신호는 매수 타이밍 조정용.",
    "wiki_promotion_candidate": true,
    "channel_trust_delta": {"report_NH투자증권": 1, "telegram_태린이아빠": 0}
  }
]"""


def _group_by_ticker(claims_data: dict) -> dict[str, list[dict]]:
    """종목·섹터별로 클레임 묶기"""
    groups: dict[str, list[dict]] = defaultdict(list)

    for channel, claims in claims_data.items():
        for claim in claims:
            tickers = claim.get("tickers", [])
            sector = claim.get("sector", "")

            if tickers:
                for ticker in tickers[:2]:   # 최대 2개 종목키
                    groups[ticker].append(claim)
            elif sector:
                groups[f"SECTOR_{sector}"].append(claim)
            else:
                groups["GENERAL"].append(claim)

    return dict(groups)


def _build_prompt(ticker: str, claims: list[dict]) -> str:
    claims_text = json.dumps(claims, ensure_ascii=False, indent=2)
    return f"""종목/테마: {ticker}
관련 클레임 목록:
{claims_text}

위 클레임들을 교차검증하여 debate JSON을 생성하세요."""


async def _call_sonnet(client: anthropic.Anthropic, prompt: str) -> list[dict]:
    for attempt in range(2):
        try:
            resp = await asyncio.to_thread(
                client.messages.create,
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            return []
        except Exception as e:
            if attempt == 1:
                print(f"  [Agent B] Sonnet 오류: {e}")
                return []
            await asyncio.sleep(5)
    return []


async def _debate_group(client: anthropic.Anthropic, ticker: str,
                         claims: list[dict], debate_offset: int) -> list[Debate]:
    if not claims:
        return []

    # 단일 채널 클레임이고 wiki 승격 필요 없으면 스킵
    sources = set(c.get("channel_source", "") for c in claims)
    if len(sources) == 1 and len(claims) < 2:
        return []

    prompt = _build_prompt(ticker, claims[:MAX_CLAIMS_PER_CALL])
    raw_debates = await _call_sonnet(client, prompt)

    debates = []
    for i, d in enumerate(raw_debates):
        try:
            debate = Debate(
                debate_id=f"dbt_{debate_offset + i:03d}",
                topic=d.get("topic", ticker),
                tickers=d.get("tickers", [ticker]),
                sector=d.get("sector"),
                claim_ids=d.get("claim_ids", []),
                consensus=d.get("consensus", "partial"),
                bullish_arguments=[
                    Argument(**a) for a in d.get("bullish_arguments", [])
                ],
                bearish_arguments=[
                    Argument(**a) for a in d.get("bearish_arguments", [])
                ],
                contradiction_detected=d.get("contradiction_detected", False),
                contradiction_note=d.get("contradiction_note"),
                sonnet_verdict=d.get("sonnet_verdict", "neutral"),
                verdict_reason=d.get("verdict_reason", ""),
                wiki_promotion_candidate=d.get("wiki_promotion_candidate", False),
                channel_trust_delta=d.get("channel_trust_delta", {}),
            )
            debates.append(debate)
        except Exception as e:
            print(f"  [Agent B] Debate 파싱 오류: {e}")
    return debates


async def run(claims_data: dict, run_date: str) -> DebateResult:
    """Agent B 메인 실행"""
    print(f"[Agent B] Sonnet 교차검증 시작 — {run_date}")
    client = anthropic.Anthropic()

    groups = _group_by_ticker(claims_data)
    print(f"  종목/테마 그룹: {len(groups)}개")

    all_debates: list[Debate] = []
    tasks = []
    tickers = list(groups.keys())

    for ticker in tickers:
        tasks.append(_debate_group(client, ticker, groups[ticker], len(all_debates)))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, list):
            all_debates.extend(result)
        elif isinstance(result, Exception):
            print(f"  [Agent B] 그룹 오류: {result}")

    candidates = sum(1 for d in all_debates if d.wiki_promotion_candidate)
    print(f"[Agent B] 완료 — {len(all_debates)}개 토론, wiki 후보 {candidates}개")

    # 신뢰도 델타 수집
    trust_deltas = []
    for debate in all_debates:
        for ch_src, delta in debate.channel_trust_delta.items():
            if delta != 0:
                trust_deltas.append({
                    "channel_source": ch_src,
                    "delta": delta,
                    "debate_id": debate.debate_id,
                })

    trust = trust_tracker.load()
    trust_tracker.apply_deltas(trust, trust_deltas)

    return DebateResult(
        run_date=run_date,
        debates=[d.model_dump() for d in all_debates],
        summary={
            "total_debates": len(all_debates),
            "wiki_candidates": candidates,
            "contradictions": sum(1 for d in all_debates if d.contradiction_detected),
            "model": MODEL,
        },
    )


def save(result: DebateResult, pipeline_dir: Path) -> Path:
    out = pipeline_dir / "B_debate.json"
    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"[Agent B] 저장: {out}")
    return out
