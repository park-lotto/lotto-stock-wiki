"""
기획 직원 + 기획 검수 직원
"""
from pathlib import Path
from . import gemini_client as G

ROOT = Path(__file__).parent.parent.parent

def _load_context():
    """채널방향 + 레퍼런스 로드"""
    refs = []
    for p in [
        ROOT / 'channel' / 'yt' / 'yt_전략_채널방향.md',
        ROOT / 'channel' / 'strategy' / 'strategy_remotion_가이드.md',
    ]:
        if p.exists():
            refs.append(f"=== {p.name} ===\n{p.read_text(encoding='utf-8')[:2000]}")
    return '\n\n'.join(refs)

PLAN_SYSTEM = """당신은 주식 유튜브 채널 "로또의 주식인사이트" 전속 영상 기획 전문가입니다.
핵심 방향: 수급빈집추적·대장주 포착·단기 스윙 매매법
타겟: 주식 중수~전업 트레이더
스타일: 실제 데이터·실전 중심·"오늘 바로 쓸 수 있는 것"

아래 형식으로 기획서를 작성하세요 (반드시 모든 항목 포함):

# 영상 기획서

## 제목 후보 (3개)
1. [숫자+충격조건+시간 조합]
2. ...
3. ...

## 최종 제목
[선택한 제목]

## 썸네일
- 메인 텍스트:
- 서브 텍스트:
- 배경/이미지:

## 핵심 메시지 (1줄)
[시청자가 영상 보고 나서 기억할 딱 한 줄]

## 타겟 시청자
[구체적으로]

## 훅 문장 (첫 10초)
[시청자가 멈추게 하는 첫 문장 — 숫자/충격/질문 포함]

## 씬 구성
| 씬 | 목적 | 예상시간 | 화면 방향 |
|----|------|---------|---------|
| 1. 훅 | | 20~30초 | |
| 2. 공감 | | 40~50초 | |
| 3. 선언 | | 20~30초 | |
| 4. 데모 | | 3~5분 | |
| 5. 클라이맥스 | | 40~60초 | |
| 6. 자각 | | 30~40초 | |
| 7. 여운 | | 20~30초 | |
| 8. CTA | | 20~30초 | |

## 다음 편 연결고리
[시리즈 2편의 궁금증]

## CTA 방식
[댓글 키워드 / 서비스 티저]
"""

QC_SYSTEM = """당신은 유튜브 영상 기획서를 독립적으로 검토하는 QC 전문가입니다.
아래 9가지 기준으로 각 1점씩 채점하고 JSON으로 반환하세요.

채점 기준:
1. title_hook: 제목에 숫자+충격조건이 있는가
2. first_hook: 첫 10초 훅이 "나도 그래"를 유발하는가
3. scene_flow: 씬 흐름이 공감→문제→해결→증명→CTA 순서인가
4. message_clear: 핵심 메시지가 1줄로 압축되는가
5. channel_fit: 채널 방향(수급빈집/대장주/스윙)과 일치하는가
6. duration_ok: 총 영상 길이가 7~10분 범위인가
7. cta_clear: CTA가 구체적이고 행동 유도가 명확한가
8. series_hook: 다음 편 궁금증이 심어지는가
9. differentiation: 일반 주식 채널 대비 차별점이 있는가

반환 형식:
{
  "scores": {
    "title_hook": 1,
    "first_hook": 0,
    ...
  },
  "total": 7,
  "passed": true,
  "feedback": "실패한 항목과 구체적 개선 방법",
  "critical_issues": ["가장 중요한 문제 1", "문제 2"]
}
passed = total >= 7
"""

def run(idea: str, feedback: str = '') -> str:
    """기획서 생성"""
    ctx = _load_context()
    fb_note = f"\n\n이전 검수 피드백 (반드시 반영):\n{feedback}" if feedback else ''
    prompt = f"""채널 맥락:\n{ctx}\n\n영상 아이디어: {idea}{fb_note}

위 아이디어로 영상 기획서를 작성하세요."""
    return G.call(prompt, PLAN_SYSTEM, temperature=0.7)

def qc(plan_text: str) -> dict:
    """기획서 검수 → {total, passed, feedback, ...}"""
    prompt = f"아래 기획서를 채점하세요:\n\n{plan_text}"
    result = G.call_json(prompt, QC_SYSTEM)
    return result
