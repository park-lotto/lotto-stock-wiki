"""
channel_pipeline/agent_A.py — Gemini Flash: 채널 원문 분류·필터·팩트-의견 분리

실행:
    python -m scripts.channel_pipeline.agent_A --date 2026-06-04
"""

from __future__ import annotations
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import google.generativeai as genai

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from channel_pipeline.models import Claim, ChannelClaims

MODEL_NAME = "gemini-2.5-flash"
MAX_CHARS_PER_FILE = 8_000     # 파일당 최대 전달 글자수
BATCH_SIZE = 5                 # 한 번 API 호출당 파일 수

SYSTEM_PROMPT = """당신은 한국 주식 투자 정보 분류 전문가입니다.
주어진 텍스트에서 투자 관련 클레임을 추출하고 JSON 배열로 반환하세요.

규칙:
1. content_verbatim: 원문 핵심 부분 그대로 보존 (최대 400자, 절대 의역 금지)
2. fact_component: 수치·날짜·공시·데이터 등 검증 가능한 부분만
3. opinion_component: 전망·판단·예측 등 주관적 부분
4. claim_type: fact(수치·공시), data(차트·통계), opinion(전망·판단), prediction(미래예측)
5. direction: bullish(매수관점), bearish(매도관점), neutral(중립)
6. needs_verification: fact/data도 출처 불명확하면 true
7. 주식 무관 내용(일상·광고 등)은 추출하지 말 것
8. 출력은 JSON 배열만. 다른 텍스트 절대 금지.

출력 형식 예시:
[
  {
    "claim_id": "tg_001",
    "claim_type": "fact",
    "sector": "반도체",
    "tickers": ["SK하이닉스", "000660"],
    "content_verbatim": "HBM4 계약 가격 협상이 2026년 2분기부터 본격화될 것으로 예상",
    "fact_component": "HBM4 계약 가격 협상 2026년 2Q 본격화 예상 (TrendForce)",
    "opinion_component": "가격이 큰 폭으로 상승할 가능성",
    "direction": "bullish",
    "time_horizon": "longterm",
    "confidence_signal": "high",
    "needs_verification": false,
    "keywords": ["HBM4", "계약가격", "TrendForce"]
  }
]"""


def _setup_gemini() -> genai.GenerativeModel:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)


def _read_file_content(path: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        return text[:MAX_CHARS_PER_FILE]
    except Exception as e:
        return f"[파일 읽기 오류: {e}]"


def _parse_claims(raw: str, channel: str, source_file: str,
                  channel_source: str, id_offset: int) -> list[Claim]:
    """Gemini 응답 파싱 → Claim 리스트"""
    # JSON 블록 추출
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        return []

    try:
        items = json.loads(match.group())
    except json.JSONDecodeError:
        return []

    prefix = {"telegram": "tg", "blog": "bl", "report": "rp", "yt": "yt"}[channel]
    claims = []
    for i, item in enumerate(items):
        try:
            claim = Claim(
                claim_id=f"{prefix}_{id_offset + i:03d}",
                source_file=source_file,
                channel=channel,
                channel_source=channel_source,
                claim_type=item.get("claim_type", "opinion"),
                sector=item.get("sector"),
                tickers=item.get("tickers", []),
                content_verbatim=item.get("content_verbatim", ""),
                fact_component=item.get("fact_component", ""),
                opinion_component=item.get("opinion_component", ""),
                direction=item.get("direction", "neutral"),
                time_horizon=item.get("time_horizon"),
                confidence_signal=item.get("confidence_signal", "medium"),
                needs_verification=item.get("needs_verification", True),
                keywords=item.get("keywords", []),
            )
            claims.append(claim)
        except Exception:
            continue
    return claims


def _extract_channel_source(file_path: str, channel: str) -> str:
    name = Path(file_path).stem
    parts = name.split("_")
    if len(parts) >= 2:
        return parts[1]
    return channel


async def _process_batch(model: genai.GenerativeModel, channel: str,
                          batch: list[str], id_offset: int) -> list[Claim]:
    """파일 배치를 Gemini에 전달, 클레임 리스트 반환"""
    combined = ""
    for fp in batch:
        source = _extract_channel_source(fp, channel)
        content = _read_file_content(fp)
        combined += f"\n\n=== [{source}] {Path(fp).name} ===\n{content}"

    prompt = f"다음 {channel} 채널 내용을 분석하세요:\n{combined}"

    for attempt in range(3):
        try:
            resp = await asyncio.to_thread(model.generate_content, prompt)
            raw = resp.text or ""
            claims = []
            offset = id_offset
            for fp in batch:
                src = _extract_channel_source(fp, channel)
                file_claims = _parse_claims(raw, channel, fp, src, offset)
                claims.extend(file_claims)
                offset += len(file_claims)
            return claims
        except Exception as e:
            if attempt == 2:
                print(f"[Agent A] 배치 실패 ({channel}): {e}")
                return []
            await asyncio.sleep(10 ** attempt)
    return []


async def _process_channel(model: genai.GenerativeModel, channel: str,
                            files: list[str]) -> list[Claim]:
    if not files:
        return []

    all_claims: list[Claim] = []
    for i in range(0, len(files), BATCH_SIZE):
        batch = files[i:i + BATCH_SIZE]
        claims = await _process_batch(model, channel, batch, len(all_claims))
        all_claims.extend(claims)
        print(f"  [{channel}] {i+len(batch)}/{len(files)} 파일 처리 → {len(claims)}개 클레임")

    return all_claims


async def run(manifest: dict[str, list[str]], run_date: str) -> ChannelClaims:
    """Agent A 메인 실행"""
    print(f"[Agent A] Gemini Flash 분류 시작 — {run_date}")
    model = _setup_gemini()

    tasks = {
        ch: _process_channel(model, ch, files)
        for ch, files in manifest.items()
    }

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    channels: dict[str, list[Claim]] = {}
    total = 0
    for ch, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            print(f"  [{ch}] 오류: {result}")
            channels[ch] = []
        else:
            channels[ch] = result
            total += len(result)

    print(f"[Agent A] 완료 — 총 {total}개 클레임 추출")

    return ChannelClaims(
        run_date=run_date,
        channels={ch: [c.model_dump() for c in v] for ch, v in channels.items()},
        processing_stats={
            "total_claims": total,
            "by_channel": {ch: len(v) for ch, v in channels.items()},
            "model": MODEL_NAME,
        },
    )


def save(result: ChannelClaims, pipeline_dir: Path) -> Path:
    out = pipeline_dir / "A_claims.json"
    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(f"[Agent A] 저장: {out}")
    return out


if __name__ == "__main__":
    import argparse
    from channel_pipeline.file_manifest import get_manifest

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    manifest = get_manifest(args.date)
    result = asyncio.run(run(manifest, args.date))

    out_dir = ROOT / "pipeline" / args.date.replace("-", "")
    out_dir.mkdir(parents=True, exist_ok=True)
    save(result, out_dir)
