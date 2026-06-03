"""
channel_pipeline/agent_E.py — Haiku: HTML 일일 브리핑 생성

debate 결과 + wiki 결정 → 아침 브리핑 HTML
"""

from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from channel_pipeline import trust_tracker

MODEL = "claude-haiku-4-5-20251001"
OUT_DIR = ROOT / "out"

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0a0a; color: #e0e0e0; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; padding: 28px 20px; max-width: 700px; margin: 0 auto; line-height: 1.6; }
.header { border-bottom: 1px solid #222; padding-bottom: 14px; margin-bottom: 20px; }
.date { color: #555; font-size: 11px; letter-spacing: 3px; margin-bottom: 4px; }
.title { font-size: 18px; font-weight: 700; color: #fff; }
.source { color: #444; font-size: 11px; margin-top: 3px; }
.section { margin-bottom: 24px; }
.section-label { font-size: 10px; letter-spacing: 4px; color: #00FFD0; margin-bottom: 10px; opacity: 0.8; }
.item { display: flex; gap: 10px; margin-bottom: 12px; align-items: flex-start; }
.tag { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; white-space: nowrap; flex-shrink: 0; margin-top: 2px; }
.tag-hot { background: #ff4444; color: #fff; }
.tag-up  { background: #1a3d31; color: #00FFD0; border: 1px solid #00FFD0; }
.tag-warn { background: #2d1f00; color: #FFB800; border: 1px solid #554000; }
.tag-conflict { background: #2d1500; color: #FF8C00; border: 1px solid #664000; }
.item-text { font-size: 13px; color: #ccc; }
.item-text strong { color: #fff; }
.mint { color: #00FFD0; font-weight: 700; }
.gray { color: #666; font-size: 12px; }
.trust-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.trust-chip { font-size: 11px; padding: 3px 10px; border-radius: 12px; background: #111; border: 1px solid #333; color: #aaa; }
.trust-chip.high { border-color: #00FFD0; color: #00FFD0; }
.trust-chip.low  { border-color: #554; color: #888; }
hr { border: none; border-top: 1px solid #1a1a1a; margin: 16px 0; }
.footer { color: #333; font-size: 10px; text-align: center; padding-top: 16px; border-top: 1px solid #1a1a1a; letter-spacing: 2px; }
"""


def _build_prompt(debates: list, decisions: list, trust_summary: list,
                  run_date: str) -> str:
    top_debates = [d for d in debates if d.get("wiki_promotion_candidate")][:8]
    conflicts = [d for d in debates if d.get("contradiction_detected")][:3]

    return f"""다음 채널 토론 결과로 아침 브리핑 HTML body 내용을 생성하세요.

날짜: {run_date}
주요 토론 ({len(top_debates)}개):
{json.dumps(top_debates, ensure_ascii=False, indent=2)[:3000]}

충돌 감지 ({len(conflicts)}개):
{json.dumps(conflicts, ensure_ascii=False, indent=2)[:1000]}

wiki 반영 결정 ({len(decisions)}개):
{json.dumps([d for d in decisions if d.get('action') != 'skip'][:5], ensure_ascii=False, indent=2)[:1000]}

채널 신뢰도:
{json.dumps(trust_summary[:5], ensure_ascii=False)}

아래 HTML 구조로 생성하세요. CSS 클래스는 위에 정의된 것만 사용.
섹션: 오늘의 핵심 / 섹터 강약 / wiki 반영 완료 / 충돌·주의 / 채널 신뢰도

각 항목은 .item 구조:
<div class="item">
  <span class="tag tag-hot">🔴 핵심</span>
  <div class="item-text"><strong>제목</strong><br><span class="gray">상세</span></div>
</div>

<body> 내용만 출력 (html/head/style 태그 제외). 다른 텍스트 금지."""


def run(debate_data: dict, decisions_data: dict, run_date: str) -> Path:
    """Agent E 메인 실행"""
    print(f"[Agent E] Haiku HTML 브리핑 생성 — {run_date}")
    client = anthropic.Anthropic()

    debates = debate_data.get("debates", [])
    decisions = decisions_data.get("wiki_updates", [])
    trust_summary = trust_tracker.get_summary()

    prompt = _build_prompt(debates, decisions, trust_summary, run_date)

    body_content = ""
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        body_content = resp.content[0].text
    except Exception as e:
        print(f"  [Agent E] Haiku 오류: {e} — 마크다운 폴백")
        body_content = _markdown_fallback(debates, decisions, run_date)

    date_display = datetime.strptime(run_date, "%Y-%m-%d").strftime("%Y · %m · %d")
    channel_count = len(set(
        c.get("channel_source", "")
        for d in debates
        for args in [d.get("bullish_arguments", []), d.get("bearish_arguments", [])]
        for c in args
    ))

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>채널 인사이트 브리핑 — {run_date}</title>
<style>{CSS}</style>
</head>
<body>
<div class="header">
  <div class="date">{date_display} · CHANNEL INTELLIGENCE</div>
  <div class="title">채널 종합 브리핑</div>
  <div class="source">토론: {len(debates)}건 · wiki 반영: {len([d for d in decisions if d.get('action') != 'skip'])}건 · 채널: {channel_count}개</div>
</div>

{body_content}

<div class="footer">STOCK BRAIN · 로또의 주식인사이트</div>
</body>
</html>"""

    OUT_DIR.mkdir(exist_ok=True)
    date_compact = run_date.replace("-", "")
    out_path = OUT_DIR / f"channel_briefing_{date_compact}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[Agent E] 저장: {out_path}")
    return out_path


def _markdown_fallback(debates: list, decisions: list, run_date: str) -> str:
    lines = [f'<div class="section"><div class="section-label">오늘의 핵심</div>']
    for d in debates[:5]:
        if d.get("wiki_promotion_candidate"):
            lines.append(f"""<div class="item">
  <span class="tag tag-up">📈</span>
  <div class="item-text"><strong>{d.get('topic','')}</strong><br>
  <span class="gray">{d.get('verdict_reason','')[:100]}</span></div>
</div>""")
    lines.append("</div>")
    return "\n".join(lines)
