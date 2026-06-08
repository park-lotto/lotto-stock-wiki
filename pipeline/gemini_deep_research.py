"""
조선 섹터 딥리서치 — Gemini API + Google Search Grounding
8개 토픽 순차 실행 후 out/딥리서치/ 에 MD 저장
"""

import os, re, textwrap, sys
from pathlib import Path
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
from google import genai
from google.genai import types

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ["GEMINI_API_KEY"]
OUT_DIR = Path(__file__).parent.parent / "out" / "딥리서치"
OUT_DIR.mkdir(parents=True, exist_ok=True)

client = genai.Client(api_key=API_KEY)

TOPICS = [
    {
        "id": "01_FLNG_시장전체",
        "query": """
조선 섹터 딥리서치: FLNG(부유식 LNG 생산설비) 시장 전체 분석

다음 항목을 상세히 조사하라:
1. 전 세계 FLNG 시장 규모 (현재 및 향후 전망)
2. 삼성중공업 FLNG 독점 근거 — 수주 현황, 기술 우위, 경쟁사 대비 점유율
3. 모잠비크 코랄 노르트(Coral Norte) FLNG 입찰 현황 — 발주사 에니(ENI), 입찰 경쟁사, 예상 타임라인
4. 2026년 FLNG 수주 파이프라인 전체 (델핀 1·2호기, 캐나다 크시리심스 등)
5. FLNG 건조 단가, 수익성, 백로그 현황

출처와 날짜를 명시하라.
"""
    },
    {
        "id": "02_캐나다_잠수함_함대",
        "query": """
조선 섹터 딥리서치: 캐나다 잠수함 사업(CPSP) + 함대 현대화 전체

다음 항목을 상세히 조사하라:
1. 캐나다 순찰잠수함 프로젝트(CPSP) 전체 규모 — 척수, 사업비, 타임라인
2. 최종 후보 비교: 한화오션(KSS-III 배치-II) vs 독일 TKMS(212CD형) — 기술·비용·정치 변수
3. 2026년 6월 말 우협 발표 가능성 — 카니 총리 발언, 최신 진행 상황
4. 한화오션-어빙조선(Irving Shipbuilding) 협력 내용 — 온타리오 훈련함, 고용 효과
5. 한국 수주 시 수혜 종목별 영향 (한화오션, 한화에어로스페이스 등)

출처와 날짜를 명시하라.
"""
    },
    {
        "id": "03_AUKUS_핵잠수함",
        "query": """
조선 섹터 딥리서치: AUKUS 핵잠수함 협약과 한국 방산 조선 연계 기회

다음 항목을 상세히 조사하라:
1. AUKUS 핵잠수함 협약 현황 — 버지니아급 공급 계획, 호주 핵잠 일정
2. 한국 조선소(HD현대, 한화오션)의 AUKUS 연계 가능성 — 부품 공급, MRO, 기술 협력
3. 미국의 한국 조선소 활용 논의 현황 — 미해군 MRO, 동맹 조선 협력
4. 핵잠수함 관련 방산 부품 수혜 종목 (LIG넥스원, 한화에어로스페이스 등)
5. 실현 타임라인 및 리스크 요인

출처와 날짜를 명시하라.
"""
    },
    {
        "id": "04_FLNG_MRO",
        "query": """
조선 섹터 딥리서치: FLNG MRO(유지보수·정비) 시장

다음 항목을 상세히 조사하라:
1. FLNG MRO 시장 규모 및 계약 구조 — 글로벌 현황
2. 삼성중공업의 FLNG MRO 수주 가능성 — 건조사 독점 근거, 실제 계약 사례
3. FLNG MRO 수익성 — 건조 대비 마진 비교, 계약 기간(10~20년)
4. HD현대마린솔루션의 선박 MRO 사업 현황 — 매출, 성장률, 주요 고객
5. 해양플랜트 MRO 시장 전체 규모 및 성장 전망

출처와 날짜를 명시하라.
"""
    },
    {
        "id": "05_부유식_데이터센터",
        "query": """
조선 섹터 딥리서치: 부유식 해상 데이터센터(Floating Data Center)

다음 항목을 상세히 조사하라:
1. 부유식 데이터센터 시장 현황 — 실제 발주·프로젝트 사례, 기업별 투자 현황
2. 글로벌 시장 규모 및 성장 전망 (2024~2034)
3. Microsoft, Meta, Google 등 빅테크의 해상 데이터센터 계획
4. 한국 조선소(삼성중공업, HD현대) 경쟁력 — FLNG·FPSO 기술 전용 가능성
5. 실제 상업화까지 예상 타임라인 및 주요 기술·규제 장벽

출처와 날짜를 명시하라.
"""
    },
    {
        "id": "06_조선엔진_AI",
        "query": """
조선 섹터 딥리서치: HD현대 조선 AI·자율운항 기술

다음 항목을 상세히 조사하라:
1. HD현대아비커스 하이나스(HiNAS) 기술 현황 — 상용화 단계, 적용 선박 수
2. HD현대마린솔루션 오션와이즈 항로 최적화 — 연료 절감 실증 수치, 계약 현황
3. 세계 최초 LNG선 완전 자율 태평양 항해 — 상세 내용, 의미
4. 경쟁사(삼성중공업, 한화오션, 일본·중국 조선소) AI 기술 비교
5. AI 기술이 신규 수주에 미치는 실제 영향 — 프리미엄 마진, 발주사 선호도 변화

출처와 날짜를 명시하라.
"""
    },
    {
        "id": "07_Section301_리스크_시나리오",
        "query": """
조선 섹터 딥리서치: Section 301 유예 연장 리스크 시나리오

다음 항목을 상세히 조사하라:
1. 미중 무역 협상 현황 (2026년 6월 기준) — 최신 협상 상황, 합의 가능성
2. Section 301 유예 만료(2026-11-09) 연장 시나리오 — 연장 가능성, 조건
3. 유예 연장 시 조선주 주가 영향 — 과거 유사 사례, 예상 낙폭
4. SHIPS Act(S.1541) 진행 상황 — 상원 계류 현황, 통과 가능성
5. 미중 협상 모니터링 핵심 지표 — 어떤 뉴스가 나오면 리스크인가

출처와 날짜를 명시하라.
"""
    },
    {
        "id": "08_미해군_MRO",
        "query": """
조선 섹터 딥리서치: 미해군 함정 MRO와 한국 조선소

다음 항목을 상세히 조사하라:
1. 미해군 함정 MRO 현황 — 미국 내 조선 능력 부족 실태, 외국 조선소 활용 필요성
2. 한국 조선소 미해군 MRO 수주 현황 및 논의 — 한화오션 필라델피아 조선소, HD현대
3. 미국 Shipbuilding for America 정책 — 동맹국 조선소 활용 방안
4. 실제 수주 가능성과 규모 — 타임라인, 계약 구조
5. 수혜 종목 및 리스크 요인

출처와 날짜를 명시하라.
"""
    },
]

def research_topic(topic: dict) -> str:
    print(f"\n{'='*60}")
    print(f"[{topic['id']}] 리서치 시작...")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=topic["query"],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
            ),
        )
        result = response.text
        print(f"  완료 ({len(result)} chars)")
        return result
    except Exception as e:
        print(f"  오류: {e}")
        return f"## 오류\n{e}"


def save_md(topic_id: str, content: str):
    path = OUT_DIR / f"{topic_id}.md"
    path.write_text(content, encoding="utf-8")
    print(f"  저장: {path}")


if __name__ == "__main__":
    print(f"딥리서치 시작 — {len(TOPICS)}개 토픽")
    print(f"저장 위치: {OUT_DIR}")

    for topic in TOPICS:
        result = research_topic(topic)
        md_content = f"# {topic['id'].replace('_', ' ')}\n\n*Gemini 2.5 Pro + Google Search Grounding · 2026-06-08*\n\n---\n\n{result}"
        save_md(topic["id"], md_content)

    print(f"\n\n✅ 완료 — {OUT_DIR} 에 {len(TOPICS)}개 파일 저장")
