"""
현대차·LG·삼성 — 자율주행 × 로봇 크로스섹터 밸류체인 Q1~Q10 리서치
핵심 논리: 자율주행 AI 기술 = 로봇 AI 기술 (인식·판단·제어 동일 구조)
           → 대기업 그룹의 자율주행 역량이 로봇으로 전이되는 경로 추적

Q1: 자율주행 → 로봇 기술 전이 논리 (왜 같은 기술인가)
Q2: 현대차그룹 전체 그림 (SDV + BD + 레인보우 + RMAC)
Q3: 현대차 계열사 밸류체인 심층 (현대모비스·오토에버·무벡스·위아)
Q4: 현대차 이벤트 타임라인 (6~12개월, 날짜 특정)
Q5: LG그룹 전체 그림 (CLOi + Isaac동맹 + RFM + 피지컬AI)
Q6: LG 계열사 밸류체인 심층 (이노텍·CNS·에너지솔루션·마그나)
Q7: LG 이벤트 타임라인 (6~12개월, 날짜 특정)
Q8: 삼성그룹 로봇 전략 (레인보우 지분 + 전자 + SDI)
Q9: 3개 그룹 비교 × 투자 관점 (어느 계열사가 가장 직접 수혜)
Q10: 꼬리에 꼬리 연쇄 구조 (그룹별 이벤트 → 수혜 체인)

사용: python scripts/gemini_robot_conglomerate_q10.py
"""
import sys, os, re, time
from datetime import date
from pathlib import Path
from google import genai
from google.genai import types
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT  = Path(__file__).parent.parent
ENV   = ROOT / '.env'
TODAY = date.today().strftime('%Y-%m-%d')

env = {}
for line in ENV.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

API_KEY = env.get('GEMINI_API_KEY', '')
if not API_KEY:
    print('❌ GEMINI_API_KEY 없음'); sys.exit(1)

client = genai.Client(api_key=API_KEY)

# ── 공통 컨텍스트 ──────────────────────────────────────────────────────────────
BASE_CTX = f"""오늘 날짜는 {TODAY}이야.
너는 한국 주식시장 전문 애널리스트야. 현대차·LG·삼성 그룹의 자율주행×로봇 크로스섹터 밸류체인을 분석한다.

답변 규칙:
- 한국 상장사 기준 (종목명 + 6자리 코드 반드시 포함)
- 구체적 수치·날짜·계약명 포함. 모르면 "미확인"이라고 명시 (허수 금지)
- 마크다운 테이블 적극 활용
- 답변은 핵심만 간결하게 — 항목당 2~4줄, 테이블 위주
- Google 검색으로 최신 정보 확인"""

# ── Q1~Q10 프롬프트 ───────────────────────────────────────────────────────────

Q1 = """자율주행 기술이 로봇 기술로 전이되는 핵심 논리를 설명해줘.
"자율주행 = 로봇의 두뇌"라는 주장이 왜 성립하는가.

① 자율주행 AI와 로봇 AI의 기술 공통 구조
   인식(Perception) / 판단(Decision) / 제어(Control) — 세 단계가 어떻게 동일한가
   | 기술 요소 | 자율주행 적용 | 로봇 적용 | 공유 가능 여부 |

② 자율주행에서 로봇으로 실제로 전이된 기술 사례
   어떤 회사가 자율주행 기술을 로봇에 먼저 적용했는가 (글로벌 + 국내)

③ 자율주행 역량 보유 기업이 로봇 시장에서 갖는 선행우위
   — 데이터, 센서, AI모델, HW 플랫폼 각각에서 왜 유리한가

④ 반대로 자율주행 없이 로봇만 하는 기업의 한계
   — 순수 로봇 기업이 대기업 대비 뒤처지는 지점"""

Q2 = """현대차그룹의 자율주행 × 로봇 전략 전체 그림을 설명해줘.

① 정의선 회장의 "모빌리티 → 로보틱스" 전략 선언
   — 언제, 어떤 내용, 얼마나 투자하겠다고 했는가 (수치 포함)

② 보스턴다이나믹스 현재 상태
   | 제품 | 주요 고객 | 실제 매출 규모 | 현대차 인수 후 달라진 것 |
   Spot / Atlas / Stretch — 각각 어디에 팔리고 있는가

③ 레인보우로보틱스(277810) × 현대차 관계
   — 지분 구조: 현대차 몇 %, 삼성 몇 %
   — 실제 공동개발 중인 것이 무엇인가 (확인된 내용만)
   — 현대차와 삼성이 동시에 지분 보유 — 이 구조의 의미

④ RMAC(로봇 메타플랜트 응용센터) 미국
   — 위치, 개소 예정 시점, 하는 일이 구체적으로 무엇인가
   — 개소 시 어떤 수주·매출이 가시화되는가"""

Q3 = """현대차그룹 계열사별 자율주행×로봇 밸류체인을 심층 분석해줘.
각 계열사가 "지금 실제로 무엇을 하고 있는가"에 집중.

① 현대모비스(012330)
   — 자율주행 센서·제어 시스템 중 로봇에 전이 가능한 기술
   — 로봇 관련 매출 현황 or 개발 중인 로봇 부품
   — 투자 관점: 현대차 로봇 사업 확대 시 수혜 강도

② 현대오토에버(467870)
   — 차량 OS(ccOS)에서 로봇 OS/플랫폼으로 확장 현황
   — 현대차그룹 로봇 소프트웨어 허브 역할 근거
   — 실제 로봇 관련 매출 or 수주 있는가

③ 현대무벡스(204490)
   — AGV → AMR 전환 현황 (물류로봇 실제 수주 규모)
   — 쿠팡·이마트 등 국내 물류센터 납품 현황
   — RMAC 개소 시 연동 가능성

④ 현대위아(011210)
   — 기계 부품·CNC에서 로봇 관절·액추에이터로 확장 현황
   — 로봇용 감속기·관절 모듈 개발 여부

⑤ 종합: 위 4개 계열사 중 로봇 사업 매출 가시화가 가장 빠른 순서
   | 계열사 | 코드 | 로봇 매출 가시화 시점 | 수혜 강도 | 현재 밸류 |"""

Q4 = """현대차그룹 자율주행×로봇 관련 향후 6~12개월 이벤트 타임라인.
날짜가 특정된 것만. "하반기 예정" 같은 모호한 표현은 최대한 좁혀줘.

① 확정 or 고확률 이벤트
   | 날짜 | 이벤트 | 관련 계열사 | 주가 영향 | 근거 |

   아래 항목 전부 커버:
   - RMAC 미국 개소 (구체적 월 특정 가능한가)
   - 보스턴다이나믹스 신제품 발표 or 대형 수주
   - 레인보우로보틱스 관련 현대차 추가 액션 (지분 확대 or 공동개발 발표)
   - 현대차 SDV 플랫폼 관련 로봇 연동 발표
   - 현대모비스·오토에버 IR/실적 발표 일정

② 불확실하지만 터지면 강한 것
   — 어떤 조건이 충족될 때 발표되는가

③ 이벤트 발생 시 계열사 반응 순서
   현대차 본사 발표 → 어떤 계열사가 먼저, 어떤 게 나중에 반응하는가"""

Q5 = """LG그룹의 자율주행 × 로봇 × 피지컬AI 전략 전체 그림.

① 구광모 회장 피지컬AI 동맹 — 구체적으로 뭘 하겠다는 건가
   — 젠슨황과의 협력에서 "LG CLOi + 엔비디아 Isaac 결합"이 실제로 무엇을 만드는가
   — LG AI연구원의 로봇 파운데이션 모델(RFM) — 개발 현황, 목표 출시 시점

② LG전자(066570) CLOi 사업 현황
   — 제품 라인업 (서빙·안내·방역·잔디깎이 등) 중 매출 비중 1위
   — 2025~2026 실제 수주 규모 (수치 있으면)
   — 엔비디아 Isaac 결합 후 달라지는 것 — 지금과 어떻게 달라지는가

③ LG의 자율주행 기술 보유 현황
   — LG전자가 자율주행 기술을 갖고 있는가 (ZKW·VS사업부)
   — 이 기술이 로봇에 전이되는 경로

④ LG 로봇 전략이 현대차 대비 다른 점
   — 하드웨어 중심 현대차 vs LG의 차별화 포인트"""

Q6 = """LG그룹 계열사별 로봇 밸류체인 심층 분석.
각 계열사가 지금 실제로 무엇을 하는지 중심으로.

① LG이노텍(011070)
   — 카메라 모듈 기술이 로봇 비전·센서로 전이되는 경로
   — 로봇용 카메라·센서 모듈 현재 개발·납품 현황

② LG CNS(상장 여부 확인)
   — 스마트팩토리 SI → 로봇 시스템통합(SI) 사업 현황
   — 실제 공장 자동화 로봇 도입 수주 규모

③ LG에너지솔루션(373220)
   — 로봇용 배터리 (소형 고밀도) 개발·납품 현황
   — 테슬라 옵티머스 배터리 공급 가능성

④ LG마그나이파워트레인 (비상장)
   — 전기차 모터 기술 → 로봇 서보모터·액추에이터 전이 가능성
   — 상장 계열사 중 이 기술과 연결되는 곳

⑤ 종합: LG 계열사 중 로봇 매출 가시화 가장 빠른 순서
   | 계열사 | 코드 | 로봇 매출 가시화 시점 | 수혜 강도 |"""

Q7 = """LG그룹 자율주행×로봇 관련 향후 6~12개월 이벤트 타임라인.
날짜 특정 가능한 것 위주.

① 확정 or 고확률 이벤트
   | 날짜 | 이벤트 | 관련 계열사 | 주가 영향 | 근거 |

   아래 항목 전부 커버:
   - 젠슨황 방한(6/5) 이후 LG-엔비디아 구체적 협력 발표 예상 시점
   - CLOi 신제품 or 대형 수주 발표
   - LG AI연구원 RFM 공개 or 시연 일정
   - LG이노텍·LG CNS 로봇 관련 수주 공시 예상
   - LG전자 실적 발표 일정 (로봇 매출 별도 공시 여부)

② 불확실하지만 터지면 강한 것

③ LG 이벤트 발생 시 계열사 반응 순서"""

Q8 = """삼성그룹 로봇 전략 전체 그림 + 현대·LG와 비교.

① 삼성전자(005930)의 레인보우로보틱스(277810) 지분 취득
   — 현재 지분율, 취득 경위, 추가 지분 확대 계획 (공식 발표된 것만)
   — 삼성이 레인보우에 투자한 실제 이유 — 어떤 기술·시장을 노리는가

② 삼성전자 로봇 사업부 현황
   — 어떤 로봇 제품 개발 중인가 (확인된 것만)
   — 자율주행 관련 기술 보유 현황 (SDC·자율주행 칩 등)

③ 삼성SDI(006400)
   — 로봇용 배터리 (원통형·파우치) 공급 현황
   — 테슬라 옵티머스 배터리 공급 논의 있는가

④ 삼성 vs 현대 vs LG — 로봇 전략 핵심 차이
   | 그룹 | 핵심 전략 | 강점 | 약점 | 매출 가시화 시점 |

⑤ 삼성 관련 로봇 이벤트 타임라인 (6~12개월)"""

Q9 = """3개 그룹(현대·LG·삼성) 통합 비교 — 투자 관점.

① 지금 이 시점 투자 관점에서 가장 직접적인 로봇 수혜 계열사 TOP10
   | 순위 | 계열사 | 코드 | 그룹 | 수혜 이유 | 매출 가시화 시점 | 리스크 |

② 지금 가장 저평가된 곳은 어디인가
   — 로봇 스토리가 주가에 덜 반영된 계열사
   — 왜 시장이 아직 모르는가

③ 각 그룹에서 "이 계열사 하나만 골라야 한다면"
   현대차그룹: ?  /  LG그룹: ?  /  삼성그룹: ?
   — 선택 이유를 수치 기반으로

④ 3개 그룹 동시에 뜨는 공통 촉매
   — 어떤 이벤트가 현대·LG·삼성 전부에 동시 수혜인가"""

Q10 = """3개 그룹 자율주행×로봇 — 꼬리에 꼬리를 무는 연쇄 구조.

① 현대차 RMAC 미국 개소 체인
   RMAC 개소 공식 발표
     → 현대차 본주 (모빌리티 비전 재평가)
         → 현대오토에버 (로봇 OS 플랫폼 수주) — 왜? 시차?
         → 현대무벡스 (물류로봇 RMAC 납품) — 왜? 시차?
         → 현대모비스 (자율주행 모듈 로봇 전이) — 왜? 시차?
         → 레인보우로보틱스 (현대차 공동개발 가시화) — 왜? 시차?
         → 에스비비테크·에스피지 (부품 공급) — 왜? 시차?

② LG-엔비디아 협력 구체화 체인
   구광모-젠슨황 협력 세부 발표
     → LG전자 (CLOi+Isaac 결합 신제품) — 즉각
         → LG이노텍 (로봇 비전 센서 수주) — 왜? 시차?
         → LG CNS (스마트팩토리 SI 수주) — 왜? 시차?
         → LG에너지솔루션 (로봇 배터리 수요) — 왜? 시차?

③ 삼성 레인보우 추가 지분 취득 체인
   삼성전자 레인보우 추가 지분 공시
     → 레인보우로보틱스 (상한가급) — 즉각
         → 두산로보틱스 (로봇 섹터 전반 재평가) — 왜?
         → 에스비비테크 (공급망 기대) — 왜?

④ 3개 그룹 이벤트가 겹치는 최강 시나리오
   — 현대 RMAC + LG-NVDA 구체화 + 삼성 레인보우 추가 지분 동시에 나오면
   — 섹터 전체가 어떻게 움직이는가, 이 시나리오 확률은

⑤ 연결이 끊기는 지점 — 오해 케이스
   — "현대차 로봇 뉴스 = 현대모비스·오토에버 다 오른다" 가 왜 항상 맞지 않는가"""

# ── 실행 설정 ────────────────────────────────────────────────────────────────
QUESTIONS = [
    ("Q1",  "자율주행→로봇 기술 전이 논리",          Q1),
    ("Q2",  "현대차그룹 전체 그림 (SDV+BD+레인보우)", Q2),
    ("Q3",  "현대차 계열사 밸류체인 심층",            Q3),
    ("Q4",  "현대차 이벤트 타임라인",                 Q4),
    ("Q5",  "LG그룹 전체 그림 (CLOi+Isaac+RFM)",      Q5),
    ("Q6",  "LG 계열사 밸류체인 심층",                Q6),
    ("Q7",  "LG 이벤트 타임라인",                     Q7),
    ("Q8",  "삼성그룹 로봇 전략 + 3그룹 비교",        Q8),
    ("Q9",  "3그룹 통합 투자 관점",                   Q9),
    ("Q10", "꼬리에 꼬리 연쇄 구조",                  Q10),
]

def extract_retry_seconds(error_msg: str) -> float:
    m = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", str(error_msg))
    return float(m.group(1)) + 8 if m else 70.0

def call_gemini(qnum: str, qtext: str, context: dict) -> str:
    ctx = BASE_CTX + "\n\n이전 Q 요약:\n"
    for qn in ['Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8','Q9']:
        if qn in context:
            ctx += f"[{qn}] {context[qn]}\n\n"
    ctx += "---\n다음 질문에 답해줘:\n\n"

    for attempt in range(5):
        try:
            resp = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=ctx + qtext,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                )
            )
            return resp.text
        except Exception as e:
            err = str(e)
            if '429' in err or 'RESOURCE_EXHAUSTED' in err:
                wait = extract_retry_seconds(err)
                print(f"  ⏳ 429 — {wait:.0f}초 대기 (시도 {attempt+1}/5)")
                time.sleep(wait)
            else:
                print(f"  ❌ 오류: {e}")
                return f"[오류: {e}]"
    return "[오류: 최대 재시도 초과]"

# ── 메인 실행 ─────────────────────────────────────────────────────────────────
print(f"{'='*60}")
print(f"  현대차·LG·삼성 자율주행×로봇 크로스섹터 리서치")
print(f"  기준일: {TODAY} | gemini-3-flash-preview + Google Search")
print(f"  총 {len(QUESTIONS)}개 질문 | 독립 호출 방식")
print(f"{'='*60}\n")

results    = {}
summaries  = {}
failed     = []

for qnum, qtitle, qtext in QUESTIONS:
    print(f"{'─'*60}")
    print(f"  {qnum} / {qtitle}")
    print(f"{'─'*60}")

    answer = call_gemini(qnum, qtext, summaries)

    if not answer.startswith('[오류'):
        results[qnum]   = {"title": qtitle, "question": qtext, "answer": answer}
        summaries[qnum] = answer[:600]
        print(f"  ✅ 완료 ({len(answer)}자)")
        print(f"  미리보기: {answer.replace(chr(10),' ')[:200]}...\n")
    else:
        results[qnum] = {"title": qtitle, "question": qtext, "answer": answer}
        failed.append(qnum)
        print(f"  ❌ 실패: {answer}\n")

    time.sleep(5)

# ── 저장 ─────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}\n  저장 중...\n{'='*60}")

def get(q): return results.get(q, {}).get('answer', '[미완료]')

# 1. 원본 저장
raw_dir  = ROOT / 'raw' / 'L5_섹터'
raw_dir.mkdir(parents=True, exist_ok=True)
raw_file = raw_dir / f'{TODAY}_대기업로봇_Q10리서치.md'

raw_content = f"# 현대차·LG·삼성 자율주행×로봇 크로스섹터 리서치 ({TODAY})\n> Gemini Flash + Google Search | 독립 호출 방식\n\n---\n\n"
for qnum, data in results.items():
    raw_content += f"## {qnum} — {data['title']}\n\n**질문:**\n{data['question']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본: {raw_file.name}")

# 2. 현대차 계열사 파일 업데이트
hyundai_dir  = ROOT / 'wiki' / 'L5_섹터' / '자동차'
hyundai_dir.mkdir(parents=True, exist_ok=True)
hyundai_file = hyundai_dir / 'sector_자율주행로봇_현대차.md'

hyundai_content = f"""# 현대차그룹 — 자율주행 × 로봇 밸류체인 ({TODAY})
> 원본: `raw/L5_섹터/{TODAY}_대기업로봇_Q10리서치.md`

---

## 기술 전이 논리 (Q1)

{get('Q1')}

---

## 그룹 전체 그림 — SDV + BD + 레인보우 + RMAC (Q2)

{get('Q2')}

---

## 계열사 밸류체인 — 현대모비스·오토에버·무벡스·위아 (Q3)

{get('Q3')}

---

## 이벤트 타임라인 6~12개월 (Q4)

{get('Q4')}

---

## 관련 파일
- [[로봇index]] — 로봇 섹터 전체
- [[sector_로봇]] — Q1~Q10 로봇 리서치
"""
hyundai_file.write_text(hyundai_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/자동차/sector_자율주행로봇_현대차.md")

# 3. LG 계열사 파일 업데이트
lg_dir  = ROOT / 'wiki' / 'L5_섹터' / '전자전기'
lg_dir.mkdir(parents=True, exist_ok=True)
lg_file = lg_dir / 'sector_자율주행로봇_LG.md'

lg_content = f"""# LG그룹 — 자율주행 × 로봇 × 피지컬AI 밸류체인 ({TODAY})
> 원본: `raw/L5_섹터/{TODAY}_대기업로봇_Q10리서치.md`

---

## 그룹 전체 그림 — CLOi + Isaac + RFM (Q5)

{get('Q5')}

---

## 계열사 밸류체인 — 이노텍·CNS·에너지솔루션 (Q6)

{get('Q6')}

---

## 이벤트 타임라인 6~12개월 (Q7)

{get('Q7')}

---

## 관련 파일
- [[로봇index]] — 로봇 섹터 전체
- [[sector_로봇]] — Q1~Q10 로봇 리서치
"""
lg_file.write_text(lg_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/전자전기/sector_자율주행로봇_LG.md")

# 4. 통합 비교 파일
compare_dir  = ROOT / 'wiki' / 'L5_섹터' / '로봇'
compare_file = compare_dir / 'robot_대기업비교.md'

compare_content = f"""# 현대차·LG·삼성 로봇 전략 통합 비교 ({TODAY})
> 원본: `raw/L5_섹터/{TODAY}_대기업로봇_Q10리서치.md`

---

## 삼성그룹 로봇 전략 (Q8)

{get('Q8')}

---

## 3그룹 통합 투자 관점 (Q9)

{get('Q9')}

---

## 꼬리에 꼬리 연쇄 구조 (Q10)

{get('Q10')}

---

## 관련 파일
- [[sector_자율주행로봇_현대차]] — 현대차 밸류체인
- [[sector_자율주행로봇_LG]] — LG 밸류체인
- [[sector_로봇]] — 로봇 섹터 전체 리서치
"""
compare_file.write_text(compare_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/로봇/robot_대기업비교.md")

# 5. log.md
log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q,d in results.items() if not d['answer'].startswith('[오류')]
    entry = f"- {TODAY} — 대기업 자율주행×로봇 크로스섹터 Q10 리서치 완료: {completed}\n  [현대차] SDV+BD+RMAC 밸류체인 / [LG] CLOi+Isaac+RFM / [삼성] 레인보우 지분전략 / 3그룹 비교·연쇄구조\n"
    log_file.write_text(entry + log, encoding='utf-8')
print(f"✅ log.md 기록")

print(f"\n{'='*60}")
print(f"  완료: {[q for q,d in results.items() if not d['answer'].startswith('[오류')]}")
if failed: print(f"  실패: {failed}")
print(f"\n  원본: raw/L5_섹터/{TODAY}_대기업로봇_Q10리서치.md")
print(f"  현대: wiki/L5_섹터/자동차/sector_자율주행로봇_현대차.md")
print(f"  LG:   wiki/L5_섹터/전자전기/sector_자율주행로봇_LG.md")
print(f"  비교: wiki/L5_섹터/로봇/robot_대기업비교.md")
print(f"{'='*60}")
