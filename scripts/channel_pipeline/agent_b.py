from __future__ import annotations
import json
import os
import re
from pathlib import Path
from anthropic import Anthropic
from scripts.channel_pipeline.models import Claim, WikiDecision

ROOT = Path(__file__).parent.parent.parent
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """당신은 한국 주식 wiki 에디터입니다.
채널들의 클레임을 검토해 wiki 업데이트 결정을 JSON 배열로 반환하세요.

규칙:
1. 각 클레임에 대해 action 결정:
   - append: wiki에 1줄 추가 (중요 팩트·의견)
   - flag: append + ⚠️ 충돌 주석 (다른 채널과 방향 상충)
   - skip: wiki 미반영 (중복·무관·노이즈)
   ** confidence=low 클레임은 skip 우선 처리. 단, 여러 채널에서 동일 방향이면 예외적으로 append 가능.
2. wiki_file: 정확한 상대경로 (wiki/L5_섹터/{섹터}/stock/stock_{종목}.md)
   - 섹터 폴더명은 한국어 그대로 (반도체, 조선, 전력기기, 방산, 2차전지ESS 등)
   - 종목 파일 없으면 신규 생성 경로 지정
3. line 형식: "- [YYYY-MM-DD] {내용 50자 이내} ({출처}/{채널})"
4. conflict_candidate=true 클레임 쌍은 반드시 교차 검토 → 두 클레임 모두 flag
5. 같은 종목 같은 날 동일 내용 중복 → skip
6. JSON 배열만 출력. 다른 텍스트 금지.

출력 형식:
[{"claim_id":"tg_001","action":"append","wiki_file":"wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md","section":"## 최신 이벤트","line":"- [2026-06-04] HBM4 협상 본격화 (태린이아빠/텔레그램)","conflict_note":null}]"""


def _wiki_tree() -> str:
    wiki_dir = ROOT / "wiki"
    if not wiki_dir.exists():
        return "(wiki 디렉토리 없음)"
    files = sorted(wiki_dir.rglob("*.md"))
    relevant = [
        str(f.relative_to(ROOT))
        for f in files
        if "stock_" in f.name or "sector_" in f.name
    ]
    return "\n".join(relevant[:200])


def run(claims: list[Claim], run_date: str) -> list[WikiDecision]:
    if not claims:
        return []
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    wiki_tree = _wiki_tree()
    claims_json = json.dumps([c.model_dump() for c in claims], ensure_ascii=False, indent=2)
    user_msg = (
        f"오늘 날짜: {run_date}\n\n"
        f"현재 wiki 파일 목록:\n{wiki_tree}\n\n"
        f"처리할 클레임:\n{claims_json}\n\n"
        "위 클레임들에 대한 WikiDecision 배열을 반환하세요."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = response.content[0].text
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    try:
        items = json.loads(match.group()) if match else []
    except Exception:
        items = []

    decisions: list[WikiDecision] = []
    for item in items:
        try:
            decisions.append(WikiDecision(
                claim_id=item.get("claim_id", ""),
                action=item.get("action", "skip"),
                wiki_file=item.get("wiki_file", ""),
                section=item.get("section", "## 최신 이벤트"),
                line=item.get("line", ""),
                conflict_note=item.get("conflict_note"),
            ))
        except Exception:
            continue
    print(f"[Agent B] 완료 — {len(decisions)}개 결정")
    return decisions


def save(decisions: list[WikiDecision], path: Path) -> None:
    path.write_text(
        json.dumps([d.model_dump() for d in decisions], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
