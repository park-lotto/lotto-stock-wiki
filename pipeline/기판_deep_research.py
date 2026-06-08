"""
기판 섹터 딥리서치 — Gemini 2.5 Pro + Google Search Grounding
FC-BGA / MLCC / 유리기판 / CCL / ABF 전체
"""

import os, sys
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
        "id": "기판_01_FCBGA_시장전체",
        "query": """
반도체 기판 섹터 딥리서치: FC-BGA(플립칩 볼그리드 어레이) 시장 전체 분석 (2026년 최신)

다음 항목을 수치와 출처 포함해 상세히 조사하라:
1. 글로벌 FC-BGA 시장 규모 — 2026년 현재 및 2030년 전망, CAGR
2. 공급-수요 갭 현황 — 수요 초과 비율, 공급 부족 지속 예상 기간
3. 주요 플레이어 경쟁 구도 — 이비덴(일본 1위) vs 삼성전기 vs 大덕전자 vs LG이노텍 시장점유율
4. 삼성전기 FC-BGA 실적 — 2025/2026년 매출, 영업이익률, 증설 계획
5. AI서버용 FC-BGA 특성 — 일반 PC 기판 대비 크기·층수·단가 차이
6. 에이전틱 AI로 인한 CPU FC-BGA 수요 폭발 현황 (CPU:GPU 비율 변화)
7. 2026-2027년 주요 트리거 이벤트 목록

출처(매체명, 날짜) 명시 필수.
"""
    },
    {
        "id": "기판_02_MLCC_AI서버",
        "query": """
반도체 부품 딥리서치: MLCC(적층세라믹콘덴서) AI서버 수요 급증 분석 (2026년 최신)

다음 항목을 수치와 출처 포함해 상세히 조사하라:
1. AI서버 1대당 MLCC 탑재량 — NVIDIA GB300/B300 기준 개수, 스마트폰 대비
2. AI서버 MLCC 수요 성장 전망 — 2025→2030년 배수 (무라타·골드만삭스 등 기관 전망)
3. AI서버용 고급 MLCC ASP — 일반 MLCC 대비 가격 프리미엄
4. 무라타 vs 삼성전기 경쟁 — 시장점유율, 가격 인상 현황 (2026년)
5. Si-Cap(실리콘 커패시터) 현황 — AI서버 적용 범위, 삼성전기 ASP·매출 전망
6. MLCC 공급부족 해소 타임라인 및 리스크 요인
7. 국내 수혜 종목별 영향 (삼성전기 중심)

출처(매체명, 날짜) 명시 필수.
"""
    },
    {
        "id": "기판_03_유리기판_타임라인",
        "query": """
반도체 차세대 기판 딥리서치: 유리기판(Glass Substrate) 상용화 타임라인 전체 분석 (2026년 최신)

다음 항목을 수치와 출처 포함해 상세히 조사하라:
1. 유리기판 기술 이점 — 플라스틱 대비 열관리·신호속도·전력효율 수치
2. SKC(앱솔릭스) 현황 — 미국 조지아 공장 완공·양산 일정, 기술 난제
3. 삼성전기 현황 — 수직계열화 전략, JV 파트너, 2027년 양산 계획
4. 빅테크 채택 로드맵 — 인텔·엔비디아·구글 공식 일정, 첫 탑재 제품
5. 시장 규모 전망 — 유리기판 TAM 2025→2030년
6. 경쟁사 현황 — 이비덴·쇼와덴코 등 일본 업체 준비 현황
7. 유리기판 상용화 시 기존 FC-BGA 시장에 미치는 영향

출처(매체명, 날짜) 명시 필수.
"""
    },
    {
        "id": "기판_04_CCL_ABF_소재",
        "query": """
반도체 기판 소재 딥리서치: CCL(동박적층판)·ABF(아지노모토 빌드업 필름) 공급망 분석 (2026년 최신)

다음 항목을 수치와 출처 포함해 상세히 조사하라:
1. ABF 필름 공급 현황 — 아지노모토 독점 구조, AI서버향 수요 급증, 공급부족 상황
2. CCL 시장 — AI서버용 고성능 CCL 수요, 주요 공급사, 국내 업체 포지션
3. 이수페타시스 — FC-BGA·MLB 사업 현황, AI서버향 매출 비중, 2026년 실적 전망
4. 심텍(SEMCO) — 기판 사업 현황, AI서버 수혜 정도
5. AI서버 PCB 공급망 전체 — 소재→기판→패키징 밸류체인 수혜 구조
6. 국내 소재·기판 업체 경쟁력 — 일본·대만 대비 차별화 포인트
7. 2026-2027년 주요 트리거

출처(매체명, 날짜) 명시 필수.
"""
    },
]


def research_topic(topic: dict) -> str:
    print(f"\n{'='*55}")
    print(f"[{topic['id']}] 리서치 중...")
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
        print(f"  완료 ({len(result):,} chars)")
        return result
    except Exception as e:
        print(f"  오류: {e}")
        return f"## 오류\n{e}"


if __name__ == "__main__":
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    print(f"기판 딥리서치 시작 — {len(TOPICS)}개 토픽")
    print(f"저장: {OUT_DIR}\n")

    for topic in TOPICS:
        result = research_topic(topic)
        header = f"# {topic['id'].replace('_', ' ')}\n\n*Gemini 2.5 Pro + Google Search Grounding · {today}*\n\n---\n\n"
        path = OUT_DIR / f"{topic['id']}.md"
        path.write_text(header + result, encoding="utf-8")
        print(f"  저장: {path.name}")

    print(f"\n✅ 완료 — {OUT_DIR}")
