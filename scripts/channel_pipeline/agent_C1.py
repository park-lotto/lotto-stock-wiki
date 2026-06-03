"""
channel_pipeline/agent_C1.py — Claude Sonnet: wiki 승격 최종 판단

Sonnet이 하는 일:
  - debate 결과 중 wiki_promotion_candidate=true 항목 심사
  - 기존 wiki와 충돌 여부 판단
  - 반영 위치·내용·액션 결정
  - ⚠️ 플래그 생성
"""

from __future__ import annotations
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from channel_pipeline.models import WikiDecision, WikiDecisionResult

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """당신은 한국 주식 분석 위키 편집장입니다.
debate 결과를 보고 어떤 내용을 wiki에 반영할지 최종 결정하세요.

규칙:
1. action="update": 기존 파일에 행 추가 (가장 일반적)
2. action="create": 종목 페이지 신규 생성 필요 시
3. action="flag": 기존 내용과 충돌 → ⚠️ 노트 추가, 덮어쓰기 금지
4. action="skip": 이미 wiki에 있는 내용, 또는 근거 불충분

target_section 값:
  - "## 최신 이벤트" — 종목 뉴스/이벤트
  - "## 증권사 컨센서스" — TP/레이팅 (증권사당 1행 덮어쓰기 원칙)
  - "## 채널 인사이트 [Tier 2]" — 미검증 채널 의견 (별도 섹션)
  - "## 지속 영향 이벤트" — 섹터 장기 영향 이슈

content_to_append 형식:
  - 최신이벤트: "YYYY-MM-DD | 내용 | 🔴/🟠/🟡 | 출처: {파일명}"
  - 컨센서스: "| {증권사} | {의견} | {TP} | {날짜} | {근거1줄} |"
  - 채널인사이트: "| {날짜} | @{채널} | {등급} | {주장 1줄} | ⏳ 미검증 | - |"

7일 롤링 규칙: 8일 이상 경과 데이터는 반영하지 않음
증권사 컨센서스: 동일 증권사 기존 행 삭제 후 신규 행 삽입

출력: JSON 배열만. 다른 텍스트 금지.

[
  {
    "decision_id": "dec_001",
    "debate_id": "dbt_001",
    "action": "update",
    "target_file": "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
    "target_section": "## 최신 이벤트",
    "content_to_append": "2026-06-04 | NH투자증권 TP 3,100,000원 상향 — HBM4 독점 공급 | 🔴 | 출처: rp_012",
    "conflict_with_existing": false,
    "conflict_note": null,
    "flag": null
  }
]"""


def _load_wiki_snippet(target_file: str, section: str, max_lines: int = 30) -> str:
    """wiki 파일에서 해당 섹션만 추출 (컨텍스트용)"""
    path = ROOT / target_file
    if not path.exists():
        return "(파일 없음 — 신규 생성 필요)"

    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.split("\n")

    in_section = False
    result = []
    for line in lines:
        if line.startswith("## ") and section in line:
            in_section = True
        elif line.startswith("## ") and in_section:
            break
        if in_section:
            result.append(line)
            if len(result) >= max_lines:
                result.append("... (생략)")
                break

    return "\n".join(result) if result else "(섹션 없음)"


def _infer_target_file(debate: dict) -> str:
    """debate에서 target_file 추론"""
    tickers = debate.get("tickers", [])
    sector = debate.get("sector", "")

    # 종목 코드 매핑 (자주 쓰이는 것)
    KNOWN_FILES = {
        "SK하이닉스": "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
        "삼성전자":   "wiki/L5_섹터/반도체/stock/stock_삼성전자.md",
        "삼성전기":   "wiki/L5_섹터/반도체/stock/stock_삼성전기.md",
        "LG이노텍":   "wiki/L5_섹터/반도체/stock/stock_LG이노텍.md",
    }

    for ticker in tickers:
        if ticker in KNOWN_FILES:
            return KNOWN_FILES[ticker]
        # 종목명으로 파일 탐색
        for path in (ROOT / "wiki").rglob(f"stock_{ticker}.md"):
            return str(path.relative_to(ROOT))

    # 섹터 수준
    if sector:
        sector_map = {
            "반도체": "wiki/L5_섹터/반도체/반도체index.md",
            "조선":   "wiki/L5_섹터/조선/조선index.md",
            "방산":   "wiki/L5_섹터/방산/방산index.md",
        }
        return sector_map.get(sector, f"wiki/L5_섹터/{sector}/{sector}index.md")

    return "wiki/외부인사이트/채널인사이트.md"


async def _decide_debate(client: anthropic.Anthropic, debate: dict,
                          offset: int) -> list[dict]:
    target_file = _infer_target_file(debate)
    section = "## 최신 이벤트"

    existing = _load_wiki_snippet(target_file, section)
    prompt = f"""다음 debate 결과를 wiki에 반영할지 결정하세요.

debate:
{json.dumps(debate, ensure_ascii=False, indent=2)}

현재 wiki 해당 섹션 ({target_file} / {section}):
{existing}

결정 JSON을 생성하세요. decision_id는 dec_{offset:03d}부터 순서대로."""

    for attempt in range(2):
        try:
            resp = await asyncio.to_thread(
                client.messages.create,
                model=MODEL,
                max_tokens=2048,
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
                print(f"  [Agent C1] Sonnet 오류: {e}")
                return []
            await asyncio.sleep(5)
    return []


async def run(debate_data: dict, run_date: str) -> WikiDecisionResult:
    """Agent C1 메인 실행"""
    print(f"[Agent C1] Sonnet wiki 승격 판단 시작 — {run_date}")
    client = anthropic.Anthropic()

    debates = debate_data.get("debates", [])
    candidates = [d for d in debates if d.get("wiki_promotion_candidate", False)]
    print(f"  wiki 후보: {len(candidates)}개 / 전체 {len(debates)}개")

    all_decisions = []
    tasks = []
    for i, debate in enumerate(candidates):
        tasks.append(_decide_debate(client, debate, len(all_decisions) + i))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, list):
            all_decisions.extend(result)
        elif isinstance(result, Exception):
            print(f"  [Agent C1] 오류: {result}")

    # WikiDecision 모델로 검증
    valid_decisions = []
    for d in all_decisions:
        try:
            valid_decisions.append(WikiDecision(**d))
        except Exception as e:
            print(f"  [Agent C1] 파싱 오류: {e}")

    updates = sum(1 for d in valid_decisions if d.action in ("update", "create"))
    flags   = sum(1 for d in valid_decisions if d.action == "flag")
    skips   = sum(1 for d in valid_decisions if d.action == "skip")

    print(f"[Agent C1] 완료 — update/create: {updates}, flag: {flags}, skip: {skips}")

    return WikiDecisionResult(
        run_date=run_date,
        wiki_updates=[d.model_dump() for d in valid_decisions],
        trust_updates=[],
        skip_reasons=[
            {"debate_id": d.debate_id, "reason": "action=skip"}
            for d in valid_decisions if d.action == "skip"
        ],
    )


def save(result: WikiDecisionResult, pipeline_dir: Path) -> Path:
    out = pipeline_dir / "C1_wiki_decisions.json"
    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"[Agent C1] 저장: {out}")
    return out
