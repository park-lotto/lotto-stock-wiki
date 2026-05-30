"""
대본 직원 + 대본 검수 직원
"""
from pathlib import Path
from . import gemini_client as G

ROOT = Path(__file__).parent.parent.parent

SCRIPT_SYSTEM = """당신은 주식 유튜브 전문 대본 작가입니다.
채널: 로또의 주식인사이트 / 스타일: 구어체·실전·실데이터

기획서의 씬 구성대로 대본을 작성하세요.

각 씬 형식:
---
## 씬 {번호} — {씬명} ({예상시간})

**대사:**
(구어체로 — 실제 말하듯. 한 문장 = 한 아이디어. 반말 금지. 존댓말 O)

**화면 설명 (Remotion 직원용):**
(Phase별로 구체적: 어떤 이모지/텍스트/차트/UI가 언제 등장하는지)

**강조 키워드:** [민트색 강조할 단어들]
**예상 녹음 시간:** XX초
---

작성 원칙:
- 첫 문장: 숫자 or 충격 or 질문으로 시작 (절대 "안녕하세요" 금지)
- 전문용어 쓰면 바로 다음 문장에 쉬운 설명
- 호흡 포인트: [2초 쉬기] 표시
- 총 시간이 기획서 목표와 맞아야 함
"""

QC_SYSTEM = """유튜브 대본 QC 전문가. 10개 기준으로 채점 후 JSON 반환.

채점:
1. opening: 첫 문장이 기획서 훅과 일치하며 강렬한가
2. colloquial: 구어체로 자연스럽게 읽히는가
3. scene_match: 각 씬 대사가 씬 목적을 달성하는가
4. logic_flow: 씬 간 연결이 자연스러운가
5. jargon_explained: 전문용어 사용 시 바로 설명이 붙는가
6. duration_match: 총 시간이 목표(7~10분)와 ±30초 이내인가
7. no_repetition: 반복 단어/표현 3회 이상 없는가
8. visual_specific: 화면 설명이 Remotion 제작 가능한 수준으로 구체적인가
9. cta_clear: CTA가 "댓글에 X 남겨주세요" 형태로 명확한가
10. series_end: 마지막 씬이 다음 편 궁금증으로 끝나는가

반환:
{
  "scores": {"opening": 1, "colloquial": 1, ...},
  "total": 9,
  "passed": true,
  "feedback": "실패 항목 + 구체적 개선 방법",
  "weak_scenes": ["씬 번호 + 문제점"]
}
passed = total >= 8
"""

def run(plan_text: str, feedback: str = '') -> str:
    fb_note = f"\n\n이전 검수 피드백 (반드시 반영):\n{feedback}" if feedback else ''
    prompt = f"""아래 기획서를 바탕으로 완성된 대본을 작성하세요.

=== 기획서 ===
{plan_text}
{fb_note}"""
    return G.call(prompt, SCRIPT_SYSTEM, temperature=0.6)

def qc(script_text: str, plan_text: str) -> dict:
    prompt = f"""기획서:
{plan_text[:500]}

대본:
{script_text}

위 대본을 채점하세요."""
    return G.call_json(prompt, QC_SYSTEM)
