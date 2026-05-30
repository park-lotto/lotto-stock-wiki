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

QC_SYSTEM = """유튜브 대본 QC 전문가. 주관 금지. 측정 가능한 기준으로만 채점.

레퍼런스 성공 패턴 (5.4만뷰 영상 기준):
- 첫 문장: "사람들이 [걱정]을 했는데 → 오히려 [반전]"
- 클라이맥스: 개념 전환 1문장 ("이제 X가 아니라 Y입니다")
- 금지어: 첫 문장이 "안녕하세요" / "오늘은" / "이번 시간에" 불가

채점 (각 1점):
1. no_greeting: 첫 문장이 인사말로 시작하지 않는가
2. first_empathy: 첫 15초 안에 공감 유발 문장 있는가
3. first_number: 첫 15초 안에 숫자/수치 등장하는가
4. ref_pattern: 걱정→반전→행동 구조 있는가
5. demo_3screens: 데모 씬에 실제 화면 최소 3개 구체적으로 명시됐는가
6. climax_pivot: 클라이맥스에 개념 전환 문장 1개 있는가
7. duration_ok: 씬별 시간 합산 6~10분 범위인가
8. cta_keyword: "댓글에 [단어] 남겨주세요" 형태가 정확히 있는가
9. visual_concrete: 화면 설명이 Remotion 직원이 바로 만들 수 있는 수준인가
10. series_tease: 마지막 씬에 다음 편 예고가 있는가

반환:
{
  "scores": {"no_greeting":1, "first_empathy":0, ...},
  "total": 8,
  "passed": true,
  "feedback": "실패항목: first_number — 첫 15초에 숫자 없음. 구체적 수치 추가 필요.",
  "weak_scenes": ["씬2: 화면 설명 추상적 — '차트 보여주기' 대신 '삼성전기 수급오실레이터 A등급 화면' 처럼 구체화"]
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
