"""
2차전지 섹터 Q1~Q10 리서치 (전체 — ESS·EV·소재·셀 모두)
TYPE C 하이브리드: 메탈가격·출하량(실적형) + IRA·전기차침투율(성장형)

핵심 논리:
  2023~2024 불황 (전기차 수요 둔화 + 중국 LFP 공세 + 메탈가격 하락)
  → 2025~2026 반등 조건 형성 중
  → IRA 세액공제 유지 여부 + 전기차 재가속 + ESS 폭발 수요

Q1  섹터 전체 그림 (불황 배경 + 지금 반등 논리 + 중국 위협)
Q2  제품 분류별 구조 (셀/양극재/음극재/전해질/분리막/ESS/리사이클)
Q3  국내 셀 3사 스토리 (삼성SDI·LG에너지솔루션·SK온)
Q4  소재 밸류체인 심층 (양극재·음극재·전해질·분리막·동박)
Q5  ESS 전용 시장 (미국 ESS 폭발 수요·LFP vs NCM·수혜 기업)
Q6  IRA·관세·정책 × 이벤트 타임라인 (6~12개월, 날짜 특정)
Q7  전체 스토리 종합 + 콘텐츠 기회
Q8  뉴스 트리거 × 주가 반응 패턴
Q9  지금 주도 종목 × 왜 강한가
Q10 꼬리에 꼬리 연쇄 구조

사용: python scripts/gemini_battery_q10.py
"""
import sys, re, time
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
너는 한국 주식시장 2차전지 섹터 전문 애널리스트야.

답변 규칙:
- 한국 상장사 기준 (종목명 + 6자리 코드 반드시 포함)
- 구체적 수치·날짜·메탈가격·출하량·수주 금액 포함. 모르면 "미확인" 명시
- 마크다운 테이블 적극 활용
- 핵심만 간결하게 — 테이블 위주
- Google 검색으로 최신 정보 확인"""

Q1 = """지금 한국 2차전지 섹터의 전체 그림을 설명해줘.
2023~2024 불황을 먼저 설명하고, 지금 반등 논리가 뭔지 구조적으로.

① 2023~2024 불황의 3가지 원인
   - 전기차 수요 둔화 실제 수치 (글로벌 전기차 판매 YoY)
   - 중국 LFP 배터리 공세 — 어떻게 시장을 잠식했는가
   - 메탈가격(리튬·코발트·니켈) 하락 — 수치와 한국 기업 타격

② 2025~2026 반등 조건 — 지금 뭐가 달라졌는가
   근거 3가지 (수치 포함)

③ 지금 2차전지 섹터를 움직이는 가장 큰 힘 TOP3

④ 강세 시나리오 vs 리스크 시나리오
   | 구분 | 핵심 변수 | 주가 영향 |

⑤ 중국 배터리(CATL·BYD) 위협 — 한국이 살아남는 이유
   기술·가격·공급망 3가지 측면"""

Q2 = """2차전지 제품 분류별 시장 구조를 정리해줘.
셀·소재·ESS·리사이클 — 각각 어디서 돈이 되는가.

① 제품 분류별 수익성·성장성 비교
   | 분류 | 주요 제품 | 마진 | 지금 수요 | 한국 경쟁력 | 중국 위협 |
   배터리셀(EV용) / 배터리셀(ESS용) / 양극재 / 음극재 / 전해질 / 분리막 / 동박 / 리사이클

② 배터리 화학계 — NCM vs LFP vs 전고체
   - NCM: 한국 강점, 왜 프리미엄인가
   - LFP: 중국 독주, 한국이 뛰어드는 이유
   - 전고체: 어디까지 왔는가, 양산 현실적 시점

③ ESS 배터리 — 왜 EV보다 빠르게 성장하는가
   - 미국 ESS 시장 규모와 성장률 (수치)
   - LFP가 ESS에서 NCM을 압도하는 이유
   - 한국 셀 3사의 ESS 포지션

④ 리사이클링 — 언제 매출이 나오는가
   - 배터리 리사이클 수요 시점 (EV 폐차 사이클)
   - 국내 리사이클 수혜 기업"""

Q3 = """국내 배터리 셀 3사 스토리를 제대로 정리해줘.

① LG에너지솔루션(373220)
   - 현재 수주잔고 (수치)
   - 주요 고객사 (테슬라·GM·현대차 비중)
   - 미국 공장 가동률 현황
   - 컨센서스 TP 범위
   - 살 이유 vs 팔 이유

② 삼성SDI(006400)
   - 전고체 배터리 개발 현황 — 어디까지 왔나
   - ESS 사업 비중과 성장률
   - PRiMX(프리미엄 EV 배터리) 전략
   - 컨센서스 TP 범위
   - 살 이유 vs 팔 이유

③ SK온 (SK이노베이션 011790 산하, 비상장)
   - IPO 일정 현황 — 아직 추진 중인가
   - 수익성 전환 시점 (흑자 전환 달성했는가)
   - 포드·현대차 JV(블루오벌SK·얼티엄셀즈) 현황

④ 3사 비교 테이블
   | 기업 | 코드 | 수주잔고 | 주력 화학계 | 미국 공장 | TP컨센 | 지금 모멘텀 |"""

Q4 = """소재 밸류체인 심층 분석 — 셀 뒤에 어떤 소재 기업이 있는가.

① 양극재 — 배터리 원가의 40%
   - 양극재 종류 (NCM·LFP·NCMA) × 한국 기업 매핑
   - 에코프로비엠(247540) — 현재 상황·수주잔고·TP
   - 엘앤에프(066970) — 현재 상황·수주잔고·TP
   - 포스코퓨처엠(003670) — 현재 상황
   - 중국 양극재와 가격 격차 — 언제까지 버틸 수 있나

② 음극재 — 흑연 vs 실리콘
   - 포스코퓨처엠 천연흑연 포지션
   - 실리콘 음극재 — 국내 선두 기업과 기술 현황
   - 중국 흑연 수출규제가 미치는 영향

③ 전해질·전해액
   - 동화기업(025900)·솔브레인(357780) — 전해질 국내 포지션
   - 전고체 전환 시 전해질 시장 변화

④ 분리막
   - 더블유씨피(073490)·SKC(011790) 산하 SKIET(361220) — 포지션

⑤ 동박 (음극 집전체)
   - 일진머티리얼즈(020150)·솔루스첨단소재(336370)
   - 동박 공급 과잉 현황과 회복 시점

⑥ 소재 체인 전체 요약
   | 소재 | 대표 기업 | 코드 | 지금 수혜 강도 | 매출 인식 시점 |"""

Q5 = """ESS(에너지저장시스템) 전용 시장 분석.
EV 둔화 속에서도 ESS가 왜 폭발적으로 성장하는가.

① 미국 ESS 시장 폭발 이유
   - AI 데이터센터 전력 수요 → ESS 필요성
   - 재생에너지 확대 → 저장장치 필수
   - 미국 ESS 시장 규모와 성장률 (수치)

② LFP vs NCM — ESS에서는 왜 LFP가 압도적인가
   - 가격·안전성·수명 비교
   - 한국 셀 3사의 LFP 개발 현황
   - 중국 CATL에 밀리는 부분과 한국이 가진 강점

③ 국내 ESS 수혜 기업 정리
   | 기업 | 코드 | ESS 내 역할 | 미국 납품처 | 수혜 강도 |
   셀 / 양극재 / BMS·PCS / 시스템통합

④ 미국 IRA ESS 세액공제
   - 배터리 셀·모듈·팩 각각 세액공제 요건
   - 빅뷰티법(OBBBA) 이후 ESS 세액공제 변화 여부

⑤ ESS에서 가장 빠르게 매출 나오는 한국 기업 TOP3
   이유와 함께"""

Q6 = """IRA·관세·정책 × 향후 6~12개월 이벤트 타임라인.

① IRA 핵심 조항 현황
   - AMPC(첨단제조생산세액공제) — 셀·모듈별 단가, 지금 기업별 수령액
   - 외국우려기업(FEOC) 규정 — 2026년 이후 중국산 배터리 제한
   - 빅뷰티법(OBBBA)에서 EV·배터리 세액공제 변화

② 트럼프 관세 영향
   - 중국산 배터리·소재 관세 현황
   - 한국 배터리 기업에 기회인가 위협인가

③ 이벤트 타임라인 (날짜 특정)
   | 날짜 | 이벤트 | 수혜 기업 | 영향 강도 | 근거 |

   아래 항목 커버:
   - FEOC 규정 시행 강화 일정
   - 주요 셀 3사 실적 발표 (2분기·3분기)
   - 전고체 배터리 양산 관련 발표 (삼성SDI 등)
   - 글로벌 완성차 신규 EV 모델 출시 일정 (배터리 수요 촉매)
   - 리튬·니켈·코발트 가격 전망

④ 리스크 TOP3
   | 리스크 | 발생 조건 | 수혜/피해 기업 |"""

Q7 = """지금까지 얘기한 내용을 하나의 스토리로 종합.

① 2차전지 섹터 전체 스토리 — 3단 구조
   배경(불황) / 현재(반등 초입인가) / 앞으로(2027~2030 EV 재가속)

② 서브섹터별 온도
   | 서브섹터 | 온도 | 이유 | 대표 종목 |
   대형 셀 / 양극재 / 음극재 / 분리막 / 동박 / ESS 전용 / 전고체 / 리사이클

③ 종목별 포지션 맵
   | 종목 | 코드 | 지금 상황 | 핵심 재료 | 리스크 |

④ 유튜브 영상 주제 5개 — "이거 몰랐는데?" 할 만한 것

⑤ 지금 이 섹터에서 가장 과소평가된 종목·이슈"""

Q8 = """어떤 뉴스가 나오면 어떤 종목이 어떻게 반응했는지. 실제 케이스 기반.

① 뉴스 유형별 주가 반응 패턴
   | 뉴스 유형 | 1차 반응 | 2차 반응 | 강도 | 시차 | 실제 사례 |

   아래 유형 전부:
   - 테슬라 배터리 대규모 발주 공시
   - 리튬 가격 급등 / 급락
   - 중국 CATL 신기술 발표 (LFP 신형·나트륨 배터리)
   - IRA AMPC 금액 확대/축소 발표
   - FEOC 규제 강화 발표
   - 완성차 EV 판매 부진 발표
   - 삼성SDI 전고체 양산 일정 발표
   - 국내 셀 3사 대형 수주 공시
   - ESS 미국 대형 계약 공시
   - 니켈·코발트 가격 반등

② 무반응 케이스 — "2차전지니까 다 오르겠지" 착각

③ 지금 당장 나오면 섹터 전체 폭발할 뉴스 TOP3"""

Q9 = """지금 이 시점 2차전지 섹터에서 가장 강한 종목들.
수급 + 펀더멘털 + 이슈 삼중으로.

① 현재 주도주 TOP5
   | 종목 | 코드 | 왜 지금 주도주인가 | 핵심 근거 | 언제까지 | 확인 지표 |

② 대형 셀 3사 중 지금 가장 강한 모멘텀 — 이유와 함께
   LG에너지솔루션 vs 삼성SDI 비교

③ 양극재 — 에코프로비엠 vs 엘앤에프 지금 어느 쪽인가
   밸류에이션·수주잔고·모멘텀 비교

④ ESS 폭발 수요에서 가장 직접 수혜받는 종목
   셀·소재·시스템 각각에서 1개씩

⑤ 외국인·기관이 지금 가장 많이 담는 2차전지주 TOP3
   vs 아직 안 담은 것 중 논리 있는 종목"""

Q10 = """2차전지 섹터 꼬리에 꼬리를 무는 연쇄 구조.

① 리튬 가격 반등 체인
   리튬 가격 반등 확인
     → 양극재 (에코프로비엠·엘앤에프·포스코퓨처엠) — 왜? 시차?
         → 셀 3사 (LG에너지솔루션·삼성SDI) — 왜? 시차?
         → 동박·분리막 소재 — 왜? 시차?
         → 리사이클링 기업 — 왜?

② 미국 ESS 대형 수주 체인
   미국 ESS 프로젝트 수주 공시
     → LG에너지솔루션·삼성SDI (셀 공급) — 즉각
         → 에코프로비엠·포스코퓨처엠 (양극재 연동) — 시차?
         → BMS·PCS 기업 — 왜?

③ 전고체 배터리 양산 발표 체인
   삼성SDI 전고체 양산 일정 확정 발표
     → 삼성SDI — 즉각
         → 전고체 소재 기업 (전해질·양극재 특수형) — 왜?
         → 기존 NCM 소재 기업 — 역풍 or 중립?

④ FEOC 규제 강화 체인
   중국산 배터리 FEOC 적용 강화
     → 한국 셀 3사 (반사이익) — 즉각
         → 국내 양극재 (수요 증가) — 시차?
         → 중국 흑연 의존 음극재 기업 — 리스크

⑤ 연결이 끊기는 지점 — 오해 케이스
   "배터리 뉴스 = 소재 다 올라" 가 틀린 이유

⑥ 지금 어느 체인이 가장 활성화돼 있는가"""

QUESTIONS = [
    ("Q1",  "섹터 전체 그림 (불황→반등 논리)",           Q1),
    ("Q2",  "제품 분류별 구조 (셀/소재/ESS/리사이클)",    Q2),
    ("Q3",  "국내 셀 3사 스토리",                        Q3),
    ("Q4",  "소재 밸류체인 심층 (양극재·음극재·동박)",    Q4),
    ("Q5",  "ESS 전용 시장 (LFP·미국·수혜기업)",          Q5),
    ("Q6",  "IRA·관세·FEOC × 이벤트 타임라인",           Q6),
    ("Q7",  "전체 스토리 종합 + 콘텐츠",                  Q7),
    ("Q8",  "뉴스 트리거 × 주가 반응",                    Q8),
    ("Q9",  "지금 주도 종목 × 왜 강한가",                 Q9),
    ("Q10", "꼬리에 꼬리 연쇄 구조",                      Q10),
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
                model='gemini-2.5-flash',
                contents=ctx + qtext,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                )
            )
            text = resp.text
            return text if text is not None else "[오류: 응답 없음]"
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
print(f"  2차전지 섹터 Q1~Q10 리서치 (전체)")
print(f"  기준일: {TODAY} | TYPE C 하이브리드")
print(f"  gemini-2.5-flash + Google Search | 독립 호출")
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

print(f"\n{'='*60}\n  저장 중...\n{'='*60}")

def get(q): return results.get(q, {}).get('answer', '[미완료]')

# 원본 저장
raw_dir  = ROOT / 'raw' / 'L5_섹터'
raw_dir.mkdir(parents=True, exist_ok=True)
raw_file = raw_dir / f'{TODAY}_2차전지_Q10리서치.md'
raw_content = f"# 2차전지 섹터 Q1~Q10 리서치 ({TODAY})\n> Gemini Flash + Google Search | TYPE C 하이브리드\n\n---\n\n"
for qnum, data in results.items():
    raw_content += f"## {qnum} — {data['title']}\n\n**질문:**\n{data['question']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본: {raw_file.name}")

# sector_2차전지.md 저장
sector_dir  = ROOT / 'wiki' / 'L5_섹터' / '2차전지ESS'
sector_dir.mkdir(parents=True, exist_ok=True)
sector_file = sector_dir / 'sector_2차전지.md'

sector_content = f"""# 2차전지 섹터 — 현재 상태 [TYPE C 하이브리드]

> 메탈가격·출하량(실적형) + IRA·전기차침투율(성장형)
> Gemini Q1~Q10 리서치: {TODAY}
> 원본: `raw/L5_섹터/{TODAY}_2차전지_Q10리서치.md`

---

## Q1 — 섹터 전체 그림 (불황 배경 + 반등 논리)

{get('Q1')}

---

## Q2 — 제품 분류별 구조 (셀/소재/ESS/리사이클)

{get('Q2')}

---

## Q3 — 국내 셀 3사 스토리

{get('Q3')}

---

## Q4 — 소재 밸류체인 심층 (양극재·음극재·동박·분리막)

{get('Q4')}

---

## Q5 — ESS 전용 시장 (미국·LFP·수혜기업)

{get('Q5')}

---

## Q6 — IRA·관세·FEOC × 이벤트 타임라인

{get('Q6')}

---

## Q7 — 전체 스토리 종합 + 콘텐츠

{get('Q7')}

---

## Q8 — 뉴스 트리거 × 주가 반응

{get('Q8')}

---

## Q9 — 지금 주도 종목 × 왜 강한가

{get('Q9')}

---

## Q10 — 꼬리에 꼬리 연쇄 구조

{get('Q10')}

---

## 📰 이벤트 히스토리
- {TODAY}: Q1~Q10 딥리서치 완료

## 관련 파일
- `raw/L5_섹터/{TODAY}_2차전지_Q10리서치.md` — Gemini 원본
"""
sector_file.write_text(sector_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/2차전지ESS/sector_2차전지.md")

# log.md
log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q,d in results.items() if not d['answer'].startswith('[오류')]
    entry = f"- {TODAY} — 2차전지 Q1~Q10 딥리서치: 성공 {completed} / 실패 {failed}\n"
    log_file.write_text(entry + log, encoding='utf-8')
print(f"✅ log.md 기록")

print(f"\n{'='*60}")
print(f"  완료: {[q for q,d in results.items() if not d['answer'].startswith('[오류')]}")
if failed: print(f"  실패: {failed}")
print(f"\n  원본: raw/L5_섹터/{TODAY}_2차전지_Q10리서치.md")
print(f"  위키: wiki/L5_섹터/2차전지ESS/sector_2차전지.md")
print(f"{'='*60}")
