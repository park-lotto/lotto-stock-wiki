"""
전력기기 섹터 Q1~Q10 리서치
TYPE C 하이브리드: 수주잔고(실적형) + 미국 전력인프라 정책(성장형)

핵심 논리:
  AI 데이터센터 폭증 → 전력 수요 급증 → 미국 전력망 노후화 교체
  → 변압기·차단기·GIS 수출 급증 → 국내 전력기기 기업 슈퍼사이클

Q1  섹터 전체 그림 (왜 지금 강한가, 구조적 변화인가)
Q2  핵심 제품 (변압기·차단기·GIS·개폐기) — 어디서 돈이 되는가
Q3  국내 대장주 생태계 (현대일렉트릭·효성중공업·LS일렉트릭·HD현대일렉트릭)
Q4  미국 전력 수요처별 밸류체인 (AI데이터센터·전력망 노후화·신재생)
Q5  수주잔고·납품 현황 — 지금 실제로 돈이 되는 곳
Q6  미국 정책 (IRA·전력인프라법·빅뷰티법) × 이벤트 타임라인
Q7  전체 스토리 종합 + 콘텐츠 기회
Q8  뉴스 트리거 × 주가 반응 패턴
Q9  지금 주도 종목 × 왜 강한가 (수급+펀더멘털+이슈)
Q10 꼬리에 꼬리 연쇄 구조 (미국 발주 → 국내 수주 → 소부장 체인)

사용: python scripts/gemini_power_q10.py
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

BASE_CTX = f"""오늘 날짜는 {TODAY}이야.
너는 한국 주식시장 전력기기 섹터 전문 애널리스트야.

답변 규칙:
- 한국 상장사 기준 (종목명 + 6자리 코드 반드시 포함)
- 구체적 수치·날짜·수주 금액 포함. 모르면 "미확인"이라고 명시 (허수 금지)
- 마크다운 테이블 적극 활용
- 답변은 핵심만 간결하게 — 항목당 3~5줄, 테이블 위주
- Google 검색으로 최신 정보 확인"""

Q1 = """지금 한국 전력기기 섹터가 강세인 이유를 전체 그림으로 설명해줘.

① 지금 이 강세가 단순 사이클인가, 구조적 변화인가 — 근거 3가지

② 2022~2026 전력기기 주가 흐름 한 줄씩
   | 시기 | 시장 상황 | 주가 방향 | 핵심 이유 |

③ 지금 전력기기 섹터를 움직이는 가장 큰 힘 TOP3
   - AI 데이터센터 전력 수요
   - 미국 전력망 노후화 교체 수요
   - 신재생에너지 연계 인프라

④ 이 강세가 언제까지 갈 것인가 — 낙관/중립/비관 시나리오
   각 시나리오별 핵심 변수 1가지씩"""

Q2 = """전력기기 핵심 제품별 시장 구조를 정리해줘.
변압기·차단기·GIS·개폐기·HVDC — 어디서 진짜 돈이 되는가.

① 제품별 수익성·성장성 비교
   | 제품 | 용도 | 단가 | 마진 | 지금 수요 | 한국 경쟁력 |
   변압기 / 차단기 / GIS(가스절연개폐장치) / HVDC / 배전반

② 왜 변압기가 지금 슈퍼사이클인가
   - 공급 부족 구조적 이유 (리드타임 현황)
   - 미국산 변압기 부족 실제 규모 (수치)
   - 한국 기업이 틈새를 가져간 이유

③ HVDC — 왜 다음 성장 동력인가
   - 해상풍력·장거리 송전망 확대 → HVDC 수요
   - 국내 HVDC 역량 보유 기업

④ 제품 포트폴리오별 국내 기업 매핑
   | 제품 | 대표 국내 기업 | 코드 | 글로벌 점유율 |"""

Q3 = """국내 전력기기 대장주 4개사 스토리를 제대로 정리해줘.

① HD현대일렉트릭(267260)
   - 지금 수주잔고 규모 (수치)
   - 미국 매출 비중 및 주요 납품처
   - 현재 컨센서스 TP 범위
   - 살 이유 vs 팔 이유

② 효성중공업(298040)
   - 전력기기 vs 중공업 비중 분리
   - 수주잔고와 납품 일정
   - 컨센서스 TP 범위

③ LS일렉트릭(010120)
   - 전력기기 + 자동화 + EV인프라 포트폴리오
   - 전력기기 비중과 미국 수출 현황
   - 컨센서스 TP 범위

④ 현대일렉트릭(267260) 외 중소형 플레이어
   - 제룡전기·일진전기·서전기전 등
   - 각각 어느 세부 제품에서 강점인가

⑤ 4개사 비교 테이블
   | 기업 | 코드 | 수주잔고 | 미국 비중 | TP컨센 | 지금 가장 매력적인 이유 |"""

Q4 = """미국 전력 수요처별 밸류체인을 파줘.
수요처가 어디냐에 따라 수혜 기업이 다르다.

① AI 데이터센터 전력 수요
   - 빅테크(MS·구글·아마존·Meta)의 데이터센터 전력 용량 계획 (수치)
   - 데이터센터 1개 짓는 데 변압기 몇 대 필요한가
   - 국내 전력기기 기업 중 데이터센터 납품 실적 있는 곳

② 미국 전력망 노후화 교체
   - 미국 변압기 평균 수명 vs 현재 노후화 규모 (수치)
   - IRA·인프라법 전력망 투자 규모와 집행 현황
   - 한국 기업에 실제로 넘어온 수주 규모

③ 신재생에너지 연계 인프라
   - 해상풍력·태양광 연결 → 어떤 전력기기 필요한가
   - HVDC·ESS 연계 수요
   - 국내 수혜 기업

④ 수요처별 국내 수혜 기업 매핑
   | 수요처 | 핵심 제품 | 국내 수혜 기업 | 수혜 강도 |"""

Q5 = """지금 전력기기 기업들의 실제 수주잔고·납품 현황.
"기대"가 아니라 "확정된 것"만.

① 국내 주요 기업 수주잔고 현황 (2026년 1분기 기준)
   | 기업 | 코드 | 수주잔고 | YoY증감 | 납품 예정 시점 | 리드타임 |

② 미국향 수출 실제 수치
   - 산업통상자원부 수출 데이터 기준 전력기기 수출 YoY
   - 변압기 수출 단가 변화 추이

③ 수주잔고 → 매출 전환 시차
   - 계약 후 실제 납품까지 몇 개월인가 (제품별)
   - 2026년 하반기~2027년 인식될 수주 규모

④ 지금 수주잔고 기준 가장 유리한 기업 TOP3
   이유와 함께"""

Q6 = """미국 전력 관련 정책과 향후 6~12개월 이벤트 타임라인.
날짜 특정 가능한 것 위주.

① 핵심 정책 현황
   - IRA(인플레이션 감축법) 전력기기 관련 조항
   - 인프라투자법 전력망 투자 집행 현황
   - 트럼프 행정부의 에너지 정책 — 전력기기에 우호적인가 중립인가
   - '빅뷰티법(Big Beautiful Bill)' 전력인프라 관련 조항

② 이벤트 타임라인 (날짜 특정)
   | 날짜 | 이벤트 | 수혜 기업 | 영향 강도 | 근거 |

   아래 항목 커버:
   - 미국 연방에너지규제위원회(FERC) 주요 결정 일정
   - 빅테크 데이터센터 착공·가동 발표 예정
   - 국내 주요 기업 수주 발표 가능 시점
   - 실적 발표 일정 (2분기·3분기)

③ 리스크 — 상승을 막을 것 TOP3
   | 리스크 | 발생 조건 | 영향 |"""

Q7 = """지금까지 얘기한 내용을 하나의 스토리로 종합.

① 전력기기 섹터 전체 스토리 — 3단 구조
   배경(어떻게 여기까지 왔나) / 현재(지금 무슨 일) / 앞으로(어디로 가나)

② 종목별 포지션 맵
   | 종목명 | 코드 | 지금 상황 | 핵심 재료 | 리스크 |

③ 서브섹터별 온도
   | 서브섹터 | 온도 | 이유 | 대표 종목 |
   초고압변압기 / 차단기·GIS / HVDC / 배전반·중저압 / 스마트그리드

④ 유튜브 영상 주제 5개 — "이거 몰랐는데?" 할 만한 것
   각 주제: 제목 후보 + 핵심 메시지 한 줄

⑤ 지금 이 섹터에서 가장 과소평가된 종목·이슈"""

Q8 = """어떤 뉴스가 나오면 어떤 종목이 어떻게 반응했는지 정리해줘.
실제 케이스 기반으로.

① 뉴스 유형별 주가 반응 패턴
   | 뉴스 유형 | 1차 반응 종목 | 2차 반응 종목 | 강도 | 시차 | 실제 사례 |

   아래 유형 전부 커버:
   - 미국 빅테크 데이터센터 대규모 전력 계약 발표
   - 미국 주요 전력사(PG&E·Dominion 등) 변압기 발주 공시
   - 국내 기업 미국향 대형 수주 공시
   - FERC 전력망 투자 승인
   - 변압기 리드타임 추가 연장 보도
   - 미국 에너지부(DOE) 보조금 지원 발표
   - 경쟁사(ABB·지멘스·에너지이노베이션) 수주 뉴스
   - 원자재(규소강판) 가격 급등락

② 무반응이었던 케이스 — "전력기기니까 다 오르겠지" 착각
   | 뉴스 | 왜 안 움직였나 |

③ 지금 당장 나오면 섹터 전체가 폭발할 뉴스 TOP3"""

Q9 = """지금 이 시점 전력기기 섹터에서 가장 강한 종목들.
수급 + 펀더멘털 + 이슈 삼중으로.

① 현재 주도주 TOP5
   | 종목 | 코드 | 왜 지금 주도주인가 | 핵심 근거 | 언제까지 | 확인 지표 |

② HD현대일렉트릭이 대장주인 이유
   - 수주잔고 vs 경쟁사 비교
   - 미국 고압변압기 시장에서의 포지션

③ 중소형 중 지금 가장 강한 모멘텀 종목
   - 제룡전기·일진전기·서전기전 중 지금 어디인가
   - 왜 시장이 이 종목을 주목하는가

④ 외국인·기관이 지금 가장 많이 담고 있는 전력기기주 TOP3
   vs 아직 안 담은 것 중 논리 있는 종목

⑤ 대형주 대비 중소형에서 알파를 찾을 수 있는가
   지금 어느 구간인가"""

Q10 = """전력기기 섹터 꼬리에 꼬리를 무는 연쇄 구조.

① 미국 빅테크 데이터센터 대형 발주 체인
   MS·구글·아마존 데이터센터 전력 계약 발표
     → HD현대일렉트릭 (초고압변압기 1차) — 왜? 시차?
         → 효성중공업 (GIS·차단기) — 왜? 시차?
         → LS일렉트릭 (배전반·자동화) — 왜? 시차?
         → 제룡전기·일진전기 (중소형 변압기) — 왜? 시차?
         → 규소강판 (포스코 등 원자재) — 왜? 시차?

② 미국 전력망 노후화 교체 발주 체인
   FERC·DOE 전력망 투자 승인
     → HD현대일렉트릭 → 효성중공업 (순서와 이유)
         → 스마트그리드·배전 자동화 — 왜?

③ HVDC 신규 발주 체인
   해상풍력 대형 프로젝트 HVDC 발주
     → 어느 기업이 1차 수혜인가
         → 2차 수혜 소부장 체인

④ 국내 전력 정책 체인
   국내 RE100·전력시장 개편 발표
     → 국내 전력기기 수요 → 어느 기업 수혜

⑤ 연결이 끊기는 지점 — 오해 케이스
   "미국 전력기기 뉴스 = 전부 올라" 가 틀린 이유
   제품별·고객사별로 연결이 끊기는 지점

⑥ 지금 어느 체인이 가장 활성화돼 있는가
   다음 활성화될 체인은 무엇인가"""

QUESTIONS = [
    ("Q1",  "섹터 전체 그림",                      Q1),
    ("Q2",  "핵심 제품 (변압기·GIS·HVDC)",          Q2),
    ("Q3",  "국내 대장주 4개사 스토리",              Q3),
    ("Q4",  "미국 수요처별 밸류체인",                Q4),
    ("Q5",  "수주잔고·납품 현황 (확정된 것만)",       Q5),
    ("Q6",  "미국 정책 × 이벤트 타임라인",           Q6),
    ("Q7",  "전체 스토리 종합 + 콘텐츠",             Q7),
    ("Q8",  "뉴스 트리거 × 주가 반응 패턴",          Q8),
    ("Q9",  "지금 주도 종목 × 왜 강한가",            Q9),
    ("Q10", "꼬리에 꼬리 연쇄 구조",                 Q10),
]

def extract_retry_seconds(err: str) -> float:
    m = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", err)
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

print(f"{'='*60}")
print(f"  전력기기 섹터 Q1~Q10 리서치")
print(f"  기준일: {TODAY} | TYPE C 하이브리드 (실적형+성장형)")
print(f"  gemini-3-flash-preview + Google Search | 독립 호출 방식")
print(f"{'='*60}\n")

results   = {}
summaries = {}
failed    = []

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
        print(f"  ❌ 실패\n")

    time.sleep(5)

# ── 저장 ─────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}\n  저장 중...\n{'='*60}")

def get(q): return results.get(q, {}).get('answer', '[미완료]')

# 1. 원본
raw_dir  = ROOT / 'raw' / 'L5_섹터'
raw_dir.mkdir(parents=True, exist_ok=True)
raw_file = raw_dir / f'{TODAY}_전력기기_Q10리서치.md'
raw_content = f"# 전력기기 섹터 Q1~Q10 리서치 ({TODAY})\n> Gemini Flash + Google Search | TYPE C 하이브리드\n\n---\n\n"
for qnum, data in results.items():
    raw_content += f"## {qnum} — {data['title']}\n\n**질문:**\n{data['question']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본: {raw_file.name}")

# 2. sector_전력기기.md
sector_dir  = ROOT / 'wiki' / 'L5_섹터' / '전력기기'
sector_dir.mkdir(parents=True, exist_ok=True)
sector_file = sector_dir / 'sector_전력기기.md'

sector_content = f"""# 전력기기 섹터 — 현재 상태 [TYPE C 하이브리드]

> 수주잔고(실적형) + 미국 전력인프라 정책(성장형) 동시 적용
> Gemini Q1~Q10 리서치: {TODAY}
> 원본: `raw/L5_섹터/{TODAY}_전력기기_Q10리서치.md`

---

### Q1 — 섹터 전체 그림 (왜 지금 강한가)

{get('Q1')}

---

### Q2 — 핵심 제품 (변압기·차단기·GIS·HVDC)

{get('Q2')}

---

### Q3 — 국내 대장주 4개사 스토리

{get('Q3')}

---

### Q4 — 미국 수요처별 밸류체인 (AI데이터센터·전력망·신재생)

{get('Q4')}

---

### Q5 — 수주잔고·납품 현황 (확정된 것만)

{get('Q5')}

---

### Q6 — 미국 정책 × 이벤트 타임라인

{get('Q6')}

---

### Q7 — 전체 스토리 종합 + 콘텐츠 기회

{get('Q7')}

---

### Q8 — 뉴스 트리거 × 주가 반응 패턴

{get('Q8')}

---

### Q9 — 지금 주도 종목 × 왜 강한가

{get('Q9')}

---

### Q10 — 꼬리에 꼬리 연쇄 구조

{get('Q10')}

---

## 📰 이벤트 히스토리
- {TODAY}: Q1~Q10 딥리서치 완료

## 💡 콘텐츠 기회
(Q7 유튜브 주제 참조)

## 관련 파일
- [[전력기기index]] — 일일 업데이트
- [[L6_수급/export_monitor]] — 변압기 수출 시트#30·#31
"""
sector_file.write_text(sector_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/전력기기/sector_전력기기.md")

# 3. log.md
log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q,d in results.items() if not d['answer'].startswith('[오류')]
    entry = f"- {TODAY} — 전력기기 Q1~Q10 딥리서치: 성공 {completed} / 실패 {failed}\n"
    log_file.write_text(entry + log, encoding='utf-8')
print(f"✅ log.md 기록")

print(f"\n{'='*60}")
print(f"  완료: {[q for q,d in results.items() if not d['answer'].startswith('[오류')]}")
if failed: print(f"  실패: {failed}")
print(f"\n  원본: raw/L5_섹터/{TODAY}_전력기기_Q10리서치.md")
print(f"  위키: wiki/L5_섹터/전력기기/sector_전력기기.md")
print(f"{'='*60}")
