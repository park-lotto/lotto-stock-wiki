"""
기획 직원 + 기획 검수 직원
스킬: WebSearch → 핫클립 탐색 → 터진 포인트 분석 → 서비스 연결 → 기획서
"""
from pathlib import Path
from . import gemini_client as G

ROOT = Path(__file__).parent.parent.parent

# 서비스 소재 유형 정의
CONTENT_TYPES = """
소재 유형 5가지 (STOCK BRAIN 서비스 시리즈):
1. 뉴스 크롤링 — 실시간 뉴스 키워드 자동 감지 데모
2. 유튜브 요약 — 채널 영상 인사이트 자동 추출 데모
3. 리포트 분석 — 증권사 리포트 자동 정리·TP 신고가 감지 데모
4. 텔레그램 수집 — 100개 채널 자동 모니터링·분류 데모
5. 조합 데모 — 2~4가지 기능 동시 작동·아침 브리핑 1장 데모
"""

SEARCH_SYSTEM = """당신은 유튜브 트렌드 분석 전문가입니다.
주식·경제 채널에서 최근 7일 이내 조회수가 급상승한 영상을 찾아야 합니다.

주어진 검색 결과에서 다음을 추출하세요:
1. 영상 제목
2. 채널명 (추정 가능하면)
3. 왜 이 영상이 터졌는지 — "터진 포인트" (공포/비밀공개/숫자충격/시간압박/공감정확타/시스템공개 중 하나)
4. 제목/썸네일에서 쓰인 공식 (숫자+키워드+프레임)
5. 우리 채널이 배울 점

5개 이상 분석 후 아래 형식으로 출력:
---
## 핫클립 분석 결과

### 영상 1
제목: ...
터진 포인트: ...
공식: ...
배울 점: ...

### 영상 2
...
---
"""

PLAN_SYSTEM = """당신은 주식 유튜브 채널 "로또의 주식인사이트" 영상 기획 전문가입니다.

채널 핵심: 수급빈집추적·대장주 포착·단기 스윙 매매법
서비스: STOCK BRAIN (AI가 뉴스·리포트·텔레그램·유튜브 자동 수집·분석)
슬로건: "300개 정보 중 오늘 써먹을 3가지만"

영상 공식:
- 앞 2/3: 지금 핫한 주식/경제 이슈로 공감·FOMO 유발
- 뒤 1/3: "이게 우리 서비스로 이렇게 해결됩니다" (은근하게)

아래 형식으로 기획서를 작성하세요:

---
# 영상 기획서

## 벤치마킹
- 참고 영상: [가장 터진 영상 1개]
- 터진 포인트: [분석 결과]
- 우리가 쓸 방식: [어떻게 응용할지]

## 소재 유형
[1~5 중 선택 + 이유]

## 제목 후보 (3개)
1. [숫자+충격+시간 조합]
2. ...
3. ...
최종 선택: ...

## 썸네일
- 메인 텍스트:
- 서브 텍스트:
- 포인트:

## 핵심 메시지 (1줄)
[시청자가 보고 나서 기억할 딱 한 줄]

## 훅 문장 (첫 10초)
[첫 문장 — 벤치마킹 방식 그대로 응용]

## 씬 구성
| 씬 | 목적 | 예상시간 | 화면 방향 |
|----|------|---------|---------|
| 1. 훅 | | 20~30초 | |
| 2. 공감 | | 40~50초 | |
| 3. 선언 | | 20~30초 | |
| 4. 데모 | | 3~5분 | [소재 유형 실제 화면] |
| 5. 클라이맥스 | | 40초 | |
| 6. 자각 | | 30초 | |
| 7. 여운 | | 25초 | [다음 편 소재 예고] |
| 8. CTA | | 25초 | [댓글 키워드 + 서비스 대기] |

## 실제 데모 장면 목록
1. [실제 보여줄 화면 1 — 구체적으로]
2. ...
3. ...

## 다음 편 연결
[시리즈 다음 소재 유형 + 예고 방식]
---
"""

QC_SYSTEM = """당신은 유튜브 기획 QC 전문가입니다.
주관적 판단 금지. 아래 측정 가능한 기준으로만 채점하세요.

레퍼런스: 5.4만뷰 영상 공식 = 숫자_충격+시간_압박+행동_촉구+대형종목 (4/6)
성공 훅 패턴: "사람들이 [걱정]을 했는데 → 오히려 [반전] → [행동]하세요"

채점 (각 1점):
1. title_number: 제목에 숫자 포함 (배/만/% 등)
2. title_time: 제목에 시간압박 단어 (6월/다음주/지금/임박)
3. title_action: 제목에 행동촉구 단어 (사세요/모으세요/하세요)
4. title_brand: 제목에 종목명 or 대형 브랜드 포함
5. hook_empathy: 씬1 훅이 "나도 그래" 공감으로 시작하는가
6. demo_concrete: 씬4 데모가 실제 화면 3개 이상 구체적으로 명시됐는가
7. service_back: 서비스 소개가 영상 뒤 1/3에만 등장하는가
8. cta_keyword: CTA에 "댓글에 [키워드]" 형태가 있는가
9. series_hook: 다음 편 예고/궁금증이 있는가
10. benchmark_applied: content_bank 상위 영상 공식을 명시적으로 응용했는가

반환 형식:
{
  "scores": {"title_number":1, "title_time":0, ...},
  "total": 7,
  "passed": false,
  "feedback": "실패항목: title_time — 시간압박 단어 없음. '6월' 또는 '지금' 추가 필요. 레퍼런스: 5.4만뷰 영상 제목 참고",
  "fix_instructions": ["제목에 '6월' 추가", "CTA에 댓글 키워드 추가"]
}
passed = total >= 8
"""

def _load_skills_guide() -> str:
    p = ROOT / 'channel' / 'strategy' / 'agent_skills_기획직원.md'
    return p.read_text(encoding='utf-8')[:3000] if p.exists() else ''

def _load_channel_strategy() -> str:
    p = ROOT / 'channel' / 'yt' / 'yt_전략_채널방향.md'
    return p.read_text(encoding='utf-8')[:2000] if p.exists() else ''

def _load_content_bank() -> str:
    """소재 탐색 직원이 수집한 실제 핫클립 데이터"""
    p = ROOT / 'channel' / 'yt' / 'content_bank.md'
    return p.read_text(encoding='utf-8') if p.exists() else ''

def _load_top_transcripts(n: int = 3) -> str:
    """공식수 높은 영상의 자막 첫 90초 가져오기"""
    ref_dir = ROOT / 'wiki' / '외부인사이트' / '주식_레퍼런스'
    if not ref_dir.exists():
        return ''
    import re
    files = sorted(ref_dir.glob('stock_*.md'))
    results = []
    for f in files[:n]:
        txt = f.read_text(encoding='utf-8')
        # 공식수 추출
        m = re.search(r'\((\d)/6\)', txt)
        score = int(m.group(1)) if m else 0
        # 첫 90초 훅만
        hook_m = re.search(r'## 첫 90초 훅\n\n(.+?)\n\n##', txt, re.DOTALL)
        hook = hook_m.group(1)[:500] if hook_m else ''
        # 제목
        title_m = re.search(r'# (.+)\n', txt)
        title = title_m.group(1)[:60] if title_m else f.name
        results.append(f"[공식 {score}/6] {title}\n훅: {hook}")
    return '\n\n---\n\n'.join(results)

def search_hot_clips(idea: str) -> str:
    """Google Search grounding으로 실시간 핫클립 탐색"""
    queries = [
        f"주식 유튜브 핫클립 조회수 급상승 최신 {idea} site:youtube.com OR 유튜브",
        "주식 경제 재테크 유튜브 최근 7일 조회수 많은 영상 2026",
        f"주식 유튜브 바이럴 인기 영상 {idea} 최신",
    ]
    results = []
    for q in queries:
        try:
            raw = G.search(q)  # 실제 Google Search grounding
            # 분석 프롬프트로 가공
            analyzed = G.call(
                prompt=f"검색 결과:\n{raw}\n\n위 결과에서 주식·경제 관련 유튜브 영상들을 찾아 분석하세요. 왜 조회수가 높은지 '터진 포인트'를 추출하세요.",
                system=SEARCH_SYSTEM,
                temperature=0.3,
            )
            results.append(analyzed)
        except Exception as e:
            results.append(f"검색 실패: {e}")
    return '\n\n'.join(results)

def run(idea: str, feedback: str = '') -> str:
    """기획서 생성 — content_bank 실제 데이터 우선 사용"""
    skills   = _load_skills_guide()
    strategy = _load_channel_strategy()
    bank     = _load_content_bank()
    transcripts = _load_top_transcripts(n=3)

    fb_note = f"\n\n이전 검수 피드백 (반드시 반영):\n{feedback}" if feedback else ''

    prompt = f"""=== 스킬 가이드 ===
{skills}

=== 채널 전략 ===
{strategy}

=== 서비스 소재 유형 ===
{CONTENT_TYPES}

=== 실제 수집된 핫클립 소재 풀 (content_bank) ===
{bank}

=== 상위 영상 실제 훅 대본 (공식수 높은 순) ===
{transcripts}

=== 우리 영상 아이디어 ===
{idea}
{fb_note}

위 실제 핫클립 데이터를 바탕으로:
1. 가장 터진 영상의 공식(제목/훅/구조)을 벤치마킹하고
2. STOCK BRAIN 서비스와 연결해서
3. 영상 기획서를 작성하세요."""

    return G.call(prompt, PLAN_SYSTEM, temperature=0.7)

def qc(plan_text: str) -> dict:
    """기획서 검수"""
    prompt = f"아래 기획서를 채점하세요:\n\n{plan_text}"
    return G.call_json(prompt, QC_SYSTEM)
