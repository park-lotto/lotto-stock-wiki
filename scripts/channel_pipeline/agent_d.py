from __future__ import annotations
import json
import os
from pathlib import Path
from anthropic import Anthropic
from scripts.channel_pipeline.models import Claim, WikiDecision

ROOT = Path(__file__).parent.parent.parent
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """한국 주식 아침 브리핑 HTML 작성자입니다.
클레임과 wiki 결정을 바탕으로 간결하고 읽기 좋은 완전한 HTML 파일을 작성하세요.

구조:
1. 헤더: 날짜 + 채널 수 + 클레임 수 요약
2. 🔴 주목 클레임: conflict_candidate=true 쌍 (bullish vs bearish 대비 표시)
3. 📋 채널별 주요 클레임 (action=append/flag 된 것만, 채널별 섹션)
4. 📈 언급 종목 요약 테이블 (종목명 | 방향 | 출처 수)

스타일 요구사항:
- 다크 테마 (배경 #1a1a2e, 텍스트 #e0e0e0)
- 모바일 친화적 (max-width 800px, padding 16px)
- bullish = 초록색, bearish = 빨간색, neutral = 회색
- 이모지 적극 활용
- 완전한 HTML 문서 (<!DOCTYPE html> 포함)"""


def run(
    claims: list[Claim],
    decisions: list[WikiDecision],
    run_date: str,
    out_dir: Path | None = None,
) -> Path:
    if out_dir is None:
        out_dir = ROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"briefing_{run_date.replace('-', '')}.html"

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    payload = {
        "run_date": run_date,
        "claims": [c.model_dump() for c in claims],
        "decisions": [d.model_dump() for d in decisions],
    }
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"다음 데이터로 아침 브리핑 HTML을 작성하세요:\n"
                f"{json.dumps(payload, ensure_ascii=False)}"
            ),
        }],
    )
    html = response.content[0].text
    if not html.strip().startswith("<!DOCTYPE") and not html.strip().startswith("<html"):
        html = f"<!DOCTYPE html><html><body>{html}</body></html>"
    out_path.write_text(html, encoding="utf-8")
    print(f"[Agent D] 브리핑 저장: {out_path.name}")
    return out_path


def save_fallback(claims: list[Claim], run_date: str, out_dir: Path | None = None) -> Path:
    """API 실패 시 최소 HTML 생성"""
    if out_dir is None:
        out_dir = ROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"briefing_{run_date.replace('-', '')}.html"
    rows = "".join(
        f"<tr><td>{c.source}</td><td>{c.channel}</td><td>{c.content[:80]}</td>"
        f"<td style='color:{'green' if c.direction == 'bullish' else 'red' if c.direction == 'bearish' else 'gray'}'>"
        f"{c.direction}</td></tr>"
        for c in claims
    )
    html = (
        f'<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{run_date} 브리핑</title>"
        f"<style>body{{background:#1a1a2e;color:#e0e0e0;font-family:sans-serif;padding:16px}}"
        f"table{{width:100%;border-collapse:collapse}}td{{padding:8px;border-bottom:1px solid #333}}</style>"
        f"</head><body>"
        f"<h1>📊 {run_date} 채널 브리핑 (fallback)</h1>"
        f"<table><tr><th>출처</th><th>채널</th><th>내용</th><th>방향</th></tr>{rows}</table>"
        f"</body></html>"
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path
