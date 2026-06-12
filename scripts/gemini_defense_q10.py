"""
방산 섹터 Q1~Q10 리서치
TYPE C 하이브리드: 수출 계약(실적형) + 지정학 성장성(성장형)

핵심 논리:
  우크라이나 전쟁 → 유럽 방산 예산 급증 → K방산 수출 슈퍼사이클
  미국 MSRA·방산 협력 → 글로벌 공급망 편입
  핵잠수함·무인체계 → 국내 방산 고도화

사용: python scripts/gemini_defense_q10.py
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
너는 한국 주식시장 방산 섹터 전문 애널리스트야.

답변 규칙:
- 한국 상장사 기준 (종목명 + 6자리 코드 반드시 포함)
- 구체적 수치·날짜·수주 금액·계약 국가 포함. 모르면 "미확인" 명시 (허수 금지)
- 마크다운 테이블 적극 활용
- 핵심만 간결하게 — 테이블 위주
- Google 검색으로 최신 정보 확인"""

Q1 = """지금 한국 방산 섹터가 강세인 이유를 전체 그림으로 설명해줘.

① 지금 이 강세가 단순 사이클인가, 구조적 변화인가 — 근거 3가지
   특히 과거 방산주 테마와 지금의 구조적 차이

② 2022~2026 방산 주가 흐름 한 줄씩
   | 시기 | 시장 상황 | 주가 방향 | 핵심 이유 |

③ 지금 방산 섹터를 움직이는 가장 큰 힘 TOP3
   - 우크라이나 전쟁 → 유럽 방산 예산 급증
   - K방산 브랜드 (폴란드·루마니아·UAE·호주 등 수출)
   - 미국 방산 협력 (MSRA·신조함·부품 공급)

④ 이 강세가 언제까지 갈 것인가 — 낙관/중립/비관 시나리오

⑤ K방산이 글로벌 경쟁자(미국·유럽·이스라엘) 대비 우위를 가진 이유
   납기·가격·기술 3가지 측면에서"""

Q2 = """방산 품목별 시장 구조를 정리해줘. 어디서 진짜 돈이 되는가.

① 품목별 수익성·성장성 비교
   | 품목 | 단가 | 마진 | 지금 수요 | 한국 경쟁력 | 주요 수출국 |
   K2전차 / K9자주포 / FA-50경공격기 / 천무다연장로켓 / 잠수함 / 함정 / 유도무기(미사일) / 무인체계

② K9 자주포가 왜 K방산의 대표 품목인가
   - 글로벌 시장 점유율 (수치)
   - 수출 국가 현황과 추가 수출 가능 국가
   - 파생 수요 (탄약·정비·업그레이드)

③ 유도무기(미사일·방공) — 왜 다음 성장 동력인가
   - 천궁·현무·해성 등 국내 유도무기 수출 현황
   - 미국·NATO 규격 인증이 수출에 미치는 영향

④ 품목 포트폴리오별 국내 기업 매핑
   | 품목 | 대표 기업 | 코드 | 글로벌 점유율 |"""

Q3 = """국내 방산 주요 기업 스토리를 정리해줘.

① 한화에어로스페이스(012450)
   - 수주잔고 규모와 주요 계약 (수치)
   - K9 자주포·항공엔진·우주 포트폴리오
   - 컨센서스 TP 범위
   - 살 이유 vs 팔 이유

② LIG넥스원(079550)
   - 유도무기·레이더·전자전 포트폴리오
   - 수주잔고와 주요 수출 계약 (수치)
   - 컨센서스 TP 범위

③ 한국항공우주(047810) — KAI
   - FA-50·KF-21·수리온 현황
   - 수출 계약과 수주잔고
   - KF-21 양산 일정과 수출 전망
   - 컨센서스 TP 범위

④ 현대로템(064350)
   - K2전차 수출 현황 (폴란드 등)
   - 방산 vs 레일솔루션 비중
   - 컨센서스 TP 범위

⑤ 한화시스템(272210)
   - 방산전자·우주·UAM 포트폴리오
   - 위성·레이더 수출 현황

⑥ 5개사 비교 테이블
   | 기업 | 코드 | 수주잔고 | 핵심 품목 | TP컨센 | 지금 모멘텀 |"""

Q4 = """K방산 수출 국가별 밸류체인을 파줘.
수출 국가마다 수혜 기업이 다르다.

① 폴란드 — K방산 최대 수출처
   - K2전차·K9자주포·FA-50·천무 계약 규모 총합 (수치)
   - 이행 현황 (납품 완료 vs 잔여)
   - 폴란드 현지화 생산 논의 현황
   - 수혜 기업별 납품 품목

② 루마니아·에스토니아·핀란드 등 유럽
   - 계약 현황과 규모
   - K9·K2 추가 수출 가능성

③ UAE·사우디 등 중동
   - 천궁 등 방공 시스템 수출 현황
   - 중동 방산 시장에서 한국의 포지션

④ 호주·필리핀·인도네시아 등 아시아·태평양
   - 계약 현황

⑤ 미국 — MRO + 부품 공급망 편입
   - MSRA 계약 현황 (한화오션·HD현대중공업)
   - 미국산 부품 의존도와 국산화 현황

⑥ 수출 국가 × 수혜 기업 매트릭스
   | 국가 | 품목 | 계약 규모 | 수혜 기업 | 납품 일정 |"""

Q5 = """방산 밸류체인 심층 — 완성품 기업 뒤에 어떤 소부장이 있는가.

① 화약·탄약 체인
   - K9·K2 등 발주 증가 → 탄약 수요 폭증
   - 풍산(103140) — 탄약 독점 포지션
   - 한화(000880) — 화약·탄약 사업부

② 항공 엔진·부품 체인
   - KAI(KF-21·FA-50) → 항공 엔진 공급사
   - 한화에어로스페이스 항공엔진 부문
   - 국내 항공 부품 소부장 현황

③ 전자·레이더·통신 체인
   - 한화시스템·LIG넥스원 → 전자장비 소부장
   - 빅텍·퍼스텍 등 방산 전자 소부장

④ 무인체계(드론·UAV) 체인
   - 전장 드론 수요 급증 → 국내 수혜 기업
   - 한화시스템·LIG넥스원의 드론 포지션
   - 드론 소부장 수혜 기업

⑤ 소부장 전체 요약
   | 체인 | 대표 소부장 기업 | 코드 | 완성품 연결 | 수혜 강도 |"""

Q6 = """지정학·정책 × 향후 6~12개월 방산 이벤트 타임라인.
날짜 특정 가능한 것 위주.

① 핵심 지정학·정책 변수
   - 우크라이나 전쟁 종전 협상 시나리오별 방산 영향
   - NATO 회원국 GDP 2% 이상 방산 예산 의무화
   - 트럼프 행정부 방산 정책 (동맹국 분담·미국산 우선)
   - 국내 방산 수출 금융 지원 정책

② 이벤트 타임라인 (날짜 특정)
   | 날짜 | 이벤트 | 수혜 기업 | 영향 강도 | 근거 |

   아래 항목 커버:
   - 폴란드 추가 계약 발표 예상 시점
   - KF-21 양산 계약 일정
   - 천궁·현무 수출 계약 예상
   - 방산 기업 실적 발표 (2분기·3분기)
   - NATO 정상회의·방산 전시회(DSEI·유로사토리) 일정

③ 리스크 — 상승을 막을 것 TOP3
   | 리스크 | 발생 조건 | 영향 종목 |"""

Q7 = """지금까지 얘기한 내용을 하나의 스토리로 종합.

① 방산 섹터 전체 스토리 — 3단 구조
   배경 / 현재 / 앞으로 (2027~2030)

② 종목별 포지션 맵
   | 종목명 | 코드 | 지금 상황 | 핵심 재료 | 리스크 |

③ 서브섹터별 온도
   | 서브섹터 | 온도 | 이유 | 대표 종목 |
   지상무기 / 항공 / 함정·잠수함 / 유도무기 / 방산전자 / 무인체계 / 탄약

④ 유튜브 영상 주제 5개 — "이거 몰랐는데?" 할 만한 것

⑤ 지금 이 섹터에서 가장 과소평가된 종목·이슈"""

Q8 = """어떤 뉴스가 나오면 어떤 종목이 어떻게 반응했는지.
실제 케이스 기반.

① 뉴스 유형별 주가 반응 패턴
   | 뉴스 유형 | 1차 반응 종목 | 2차 반응 종목 | 강도 | 시차 | 실제 사례 |

   아래 유형 전부 커버:
   - 폴란드·유럽 추가 수주 공시
   - KF-21 수출 계약 발표
   - 우크라이나 전쟁 확전/종전 뉴스
   - NATO 방산 예산 확대 발표
   - 트럼프 동맹국 방위비 분담 압박
   - 미국 MSRA 추가 계약 공시
   - 천궁·현무 수출 계약
   - 국내 방산 예산 증액 뉴스
   - 경쟁국(유럽·이스라엘) 수주 뉴스

② 무반응 케이스 — "방산 뉴스니까 다 오르겠지" 착각

③ 지금 당장 나오면 섹터 전체 폭발할 뉴스 TOP3"""

Q9 = """지금 이 시점 방산 섹터에서 가장 강한 종목들.
수급 + 펀더멘털 + 이슈 삼중으로.

① 현재 주도주 TOP5
   | 종목 | 코드 | 왜 지금 주도주인가 | 핵심 근거 | 언제까지 | 확인 지표 |

② 한화에어로스페이스 vs LIG넥스원 vs KAI
   - 지금 이 세 종목 중 모멘텀 가장 강한 곳
   - 밸류에이션 비교

③ 현대로템이 방산주로 재평가받는 이유
   - 철도 비중 vs 방산 비중 현재 구도
   - 수주잔고 대비 주가 평가

④ 소부장 중 지금 가장 강한 종목
   - 풍산·한화·빅텍·퍼스텍 중 어디인가

⑤ 외국인·기관이 지금 가장 많이 담는 방산주 TOP3
   vs 아직 안 담은 것 중 논리 있는 종목"""

Q10 = """방산 섹터 꼬리에 꼬리를 무는 연쇄 구조.

① 폴란드 추가 수주 체인
   폴란드 K2전차·K9·FA-50 추가 계약 공시
     → 현대로템 (K2전차) — 즉각
         → 한화에어로스페이스 (K9자주포·항공엔진) — 왜? 시차?
         → 한국항공우주 (FA-50) — 왜? 시차?
         → 풍산 (탄약 파생수요) — 왜? 시차?
         → 한화시스템 (전자장비) — 왜? 시차?

② KF-21 수출 계약 체인
   KF-21 첫 해외 수출 계약 공시
     → 한국항공우주 (직접) — 즉각
         → 한화에어로스페이스 (엔진) — 왜?
         → LIG넥스원 (레이더·항전) — 왜?
         → 항공 소부장 전반 — 시차?

③ 유도무기 수출 체인
   천궁·현무 대형 수출 계약
     → LIG넥스원 (직접) — 즉각
         → 한화시스템 (전자전·레이더) — 왜?
         → 국내 탄두·추진 소부장 — 시차?

④ 우크라이나 종전 체인 (리스크 시나리오)
   우크라이나 휴전 협상 타결 시
     → 방산주 전반 하락 압력
         → 어떤 종목이 낙폭 가장 크고 어떤 게 방어되는가
         → 우크라이나 재건 수혜로 전환되는 종목은

⑤ 연결이 끊기는 지점 — 오해 케이스
   "방산 수주 = 소부장 다 올라" 가 틀린 이유

⑥ 지금 어느 체인이 가장 활성화돼 있는가"""

QUESTIONS = [
    ("Q1",  "섹터 전체 그림",                       Q1),
    ("Q2",  "품목별 구조 (K9·KF-21·유도무기)",       Q2),
    ("Q3",  "국내 5대 기업 스토리",                  Q3),
    ("Q4",  "수출 국가별 밸류체인",                  Q4),
    ("Q5",  "소부장 체인 (탄약·항공·전자·드론)",      Q5),
    ("Q6",  "지정학·정책 × 이벤트 타임라인",          Q6),
    ("Q7",  "전체 스토리 종합 + 콘텐츠",              Q7),
    ("Q8",  "뉴스 트리거 × 주가 반응",                Q8),
    ("Q9",  "지금 주도 종목 × 왜 강한가",             Q9),
    ("Q10", "꼬리에 꼬리 연쇄 구조",                  Q10),
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
            text = resp.text
            if text is None:
                text = "[오류: 응답 없음 (None)]"
            return text
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
print(f"  방산 섹터 Q1~Q10 리서치")
print(f"  기준일: {TODAY} | TYPE C 하이브리드")
print(f"  gemini-3-flash-preview + Google Search | 독립 호출")
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

raw_dir  = ROOT / 'raw' / 'L5_섹터'
raw_dir.mkdir(parents=True, exist_ok=True)
raw_file = raw_dir / f'{TODAY}_방산_Q10리서치.md'
raw_content = f"# 방산 섹터 Q1~Q10 리서치 ({TODAY})\n> Gemini Flash + Google Search | TYPE C 하이브리드\n\n---\n\n"
for qnum, data in results.items():
    raw_content += f"## {qnum} — {data['title']}\n\n**질문:**\n{data['question']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본: {raw_file.name}")

sector_dir  = ROOT / 'wiki' / 'L5_섹터' / '방산'
sector_dir.mkdir(parents=True, exist_ok=True)
sector_file = sector_dir / 'sector_방산.md'

sector_content = f"""# 방산 섹터 — 현재 상태 [TYPE C 하이브리드]

> 수출 계약(실적형) + 지정학 성장성(성장형) 동시 적용
> Gemini Q1~Q10 리서치: {TODAY}
> 원본: `raw/L5_섹터/{TODAY}_방산_Q10리서치.md`

---

### Q1 — 섹터 전체 그림

{get('Q1')}

---

### Q2 — 품목별 구조 (K9·KF-21·유도무기·무인체계)

{get('Q2')}

---

### Q3 — 국내 5대 기업 스토리

{get('Q3')}

---

### Q4 — 수출 국가별 밸류체인 (폴란드·유럽·중동·미국)

{get('Q4')}

---

### Q5 — 소부장 체인 (탄약·항공·전자·드론)

{get('Q5')}

---

### Q6 — 지정학·정책 × 이벤트 타임라인

{get('Q6')}

---

### Q7 — 전체 스토리 종합 + 콘텐츠

{get('Q7')}

---

### Q8 — 뉴스 트리거 × 주가 반응

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
"""
sector_file.write_text(sector_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/방산/sector_방산.md")

log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q,d in results.items() if not d['answer'].startswith('[오류')]
    entry = f"- {TODAY} — 방산 Q1~Q10 딥리서치: 성공 {completed} / 실패 {failed}\n"
    log_file.write_text(entry + log, encoding='utf-8')
print(f"✅ log.md 기록")

print(f"\n{'='*60}")
print(f"  완료: {[q for q,d in results.items() if not d['answer'].startswith('[오류')]}")
if failed: print(f"  실패: {failed}")
print(f"\n  원본: raw/L5_섹터/{TODAY}_방산_Q10리서치.md")
print(f"  위키: wiki/L5_섹터/방산/sector_방산.md")
print(f"{'='*60}")
