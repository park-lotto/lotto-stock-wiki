from __future__ import annotations
import asyncio
import json
import os
import re
from pathlib import Path
from scripts.channel_pipeline.models import Claim

MODEL = "gemini-2.5-flash"
MAX_CHARS = 8_000
BATCH_SIZE = 5

SYSTEM_PROMPT = """한국 주식 투자 정보 분류 전문가입니다.
주어진 텍스트에서 투자 관련 클레임을 추출해 JSON 배열로 반환하세요.

규칙:
1. content: 원문 핵심 그대로 보존 (400자 max, 의역 금지)
2. claim_type: fact(수치·공시·데이터), opinion(전망·판단), prediction(미래예측)
3. direction: bullish(매수관점) | bearish(매도관점) | neutral(중립)
4. conflict_candidate: 동일 배치 내 다른 채널과 방향 상충 가능성이 있으면 true
5. 주식 무관 내용(일상·광고) 제외
6. JSON 배열만 출력. 다른 텍스트 금지.

출력 형식:
[{"claim_type":"fact","sector":"반도체","tickers":["SK하이닉스"],"content":"원문","direction":"bullish","conflict_candidate":false}]"""


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
