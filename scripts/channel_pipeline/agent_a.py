from __future__ import annotations
import asyncio
import json
import os
import re
from pathlib import Path
from scripts.channel_pipeline.models import Claim

MODEL = "gemini-3-flash-preview"
MAX_CHARS = 8_000
BATCH_SIZE = 5

# confidence가 low인 클레임은 Agent B에서 skip 우선 처리
CONFIDENCE_DROP_THRESHOLD = "low"

SYSTEM_PROMPT = """당신은 한국 주식 투자 정보 분류 전문가입니다.
주어진 텍스트에서 투자 관련 클레임을 추출해 JSON 배열로만 반환하세요.

=== 분류 규칙 ===
1. content: 원문 핵심 그대로 보존 (400자 max, 절대 의역·요약 금지)
2. claim_type:
   - fact: 수치·날짜·공시·실적 등 검증 가능한 사실
   - opinion: "~할 것이다" "~로 본다" 등 주관적 판단·전망
   - prediction: 구체적 미래 수치 예측 ("Q3에 ~% 성장")
3. direction: bullish(매수관점) | bearish(매도관점) | neutral(중립·정보성)
4. confidence: high(명확한 근거 있음) | medium(개연성 있음) | low(근거 불명확·추측)
5. conflict_candidate: 같은 배치 내 다른 출처와 direction이 상반되면 true
6. 주식 무관 내용(일상·광고·자기홍보) → 추출하지 말 것

=== 판단 기준 ===
- "SK하이닉스 목표가 250,000원 → 300,000원 상향" → fact, bullish, high
- "반도체 업황 하반기 개선 전망" → opinion, bullish, medium
- "내년 HBM 시장 50% 성장할 것" → prediction, bullish, low (추측성)
- "오늘 점심 먹었어요" → 추출 안 함

=== Few-shot 예시 ===
입력: "[태린이아빠] SK하이닉스 HBM4 고객사 승인 완료. 2분기부터 본격 공급 시작. 판가는 HBM3E 대비 20% 프리미엄 적용 예상"
출력:
[
  {
    "claim_type": "fact",
    "sector": "반도체",
    "tickers": ["SK하이닉스", "000660"],
    "content": "SK하이닉스 HBM4 고객사 승인 완료. 2분기부터 본격 공급 시작",
    "direction": "bullish",
    "confidence": "high",
    "conflict_candidate": false
  },
  {
    "claim_type": "prediction",
    "sector": "반도체",
    "tickers": ["SK하이닉스"],
    "content": "HBM4 판가 HBM3E 대비 20% 프리미엄 적용 예상",
    "direction": "bullish",
    "confidence": "medium",
    "conflict_candidate": false
  }
]

입력: "[KB증권] HBM 공급 과잉 우려. 2026년 하반기 가격 조정 불가피"
출력:
[
  {
    "claim_type": "opinion",
    "sector": "반도체",
    "tickers": ["SK하이닉스", "삼성전자"],
    "content": "HBM 공급 과잉 우려. 2026년 하반기 가격 조정 불가피",
    "direction": "bearish",
    "confidence": "medium",
    "conflict_candidate": true
  }
]

JSON 배열만 출력. 다른 텍스트 절대 금지."""


def _setup():
    import google.generativeai as genai
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise EnvironmentError("GEMINI_API_KEY 미설정")
    genai.configure(api_key=key)
    return genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)


def _parse(raw: str, channel: str, source: str, id_offset: int) -> list[Claim]:
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    prefix = {"telegram": "tg", "blog": "bl", "report": "rp", "yt": "yt"}.get(channel, "xx")
    claims = []
    for i, item in enumerate(items):
        try:
            claims.append(Claim(
                id=f"{prefix}_{id_offset + i:03d}",
                channel=channel,
                source=source,
                content=item.get("content", ""),
                claim_type=item.get("claim_type", "opinion"),
                sector=item.get("sector"),
                tickers=item.get("tickers", []),
                direction=item.get("direction", "neutral"),
                confidence=item.get("confidence", "medium"),
                conflict_candidate=item.get("conflict_candidate", False),
            ))
        except Exception:
            continue
    return claims


def _source_from_path(path: str) -> str:
    name = Path(path).stem
    parts = name.split("_")
    return parts[1] if len(parts) >= 2 else "unknown"


async def _process_channel(model, channel: str, files: list[str]) -> list[Claim]:
    if not files:
        return []
    all_claims: list[Claim] = []
    for i in range(0, len(files), BATCH_SIZE):
        batch = files[i:i + BATCH_SIZE]
        combined = ""
        for fp in batch:
            source = _source_from_path(fp)
            text = Path(fp).read_text(encoding="utf-8", errors="ignore")[:MAX_CHARS]
            combined += f"\n\n=== [{source}] {Path(fp).name} ===\n{text}"
        prompt = f"다음 {channel} 채널 내용을 분석하세요:\n{combined}"
        for attempt in range(3):
            try:
                resp = await asyncio.to_thread(model.generate_content, prompt)
                batch_claims = _parse(
                    resp.text or "", channel,
                    _source_from_path(batch[0]), len(all_claims),
                )
                all_claims.extend(batch_claims)
                print(f"  [{channel}] {min(i + BATCH_SIZE, len(files))}/{len(files)} → {len(batch_claims)}개")
                break
            except Exception as e:
                if attempt == 2:
                    print(f"  [{channel}] 배치 실패: {e}")
                else:
                    await asyncio.sleep(2 ** attempt)
    return all_claims


async def run(manifest: dict[str, list[str]]) -> list[Claim]:
    model = _setup()
    tasks = {ch: _process_channel(model, ch, files) for ch, files in manifest.items()}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    claims: list[Claim] = []
    for ch, result in zip(tasks.keys(), results):
        if isinstance(result, list):
            claims.extend(result)
        else:
            print(f"  [{ch}] 오류: {result}")
    print(f"[Agent A] 완료 — {len(claims)}개 클레임")
    return claims


def save(claims: list[Claim], path: Path) -> None:
    path.write_text(
        json.dumps([c.model_dump() for c in claims], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
