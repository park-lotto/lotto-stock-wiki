"""
조선 섹터 Q1~Q10 리서치
TYPE C 하이브리드: 수주잔고(실적형) + LNG·방산·FLNG(성장형)

핵심 논리:
  LNG선 슈퍼사이클 + 미국 해군 발주 + FLNG 신시장
  → 국내 조선 3사 수주잔고 역대급 → 2027~2030 실적 가시성

Q1  섹터 전체 그림 (왜 지금 강한가, LNG·컨테이너·방산 3각 호황)
Q2  선종별 시장 구조 (LNG·컨테이너·탱커·FLNG·방산 — 어디서 돈이 되는가)
Q3  국내 3사 스토리 (HD한국조선해양·한화오션·삼성중공업)
Q4  LNG 밸류체인 심층 (LNG선 → 보냉재·강재·엔진·소재 체인)
Q5  방산·미해군 수주 체인 (MSRA·MASGA·핵잠수함·무인함 USV)
Q6  지정학·정책 × 이벤트 타임라인 (6~12개월, 날짜 특정)
Q7  전체 스토리 종합 + 콘텐츠 기회
Q8  뉴스 트리거 × 주가 반응 패턴
Q9  지금 주도 종목 × 왜 강한가 (수급+펀더멘털+이슈)
Q10 꼬리에 꼬리 연쇄 구조

사용: python scripts/gemini_shipbuilding_q10.py
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
너는 한국 주식시장 조선 섹터 전문 애널리스트야.

답변 규칙:
- 한국 상장사 기준 (종목명 + 6자리 코드 반드시 포함)
- 구체적 수치·날짜·수주 금액·선박 척수 포함. 모르면 "미확인" 명시 (허수 금지)
- 마크다운 테이블 적극 활용
- 핵심만 간결하게 — 테이블 위주, 과도한 설명 지양
- Google 검색으로 최신 정보 확인"""

Q1 = """지금 한국 조선 섹터가 강세인 이유를 전체 그림으로 설명해줘.

① 지금 이 강세가 단순 사이클인가, 구조적 변화인가 — 근거 3가지
   특히 2016~2020 조선 불황과 지금의 구조적 차이

② 2020~2026 조선 주가 흐름 한 줄씩
   | 시기 | 시장 상황 | 주가 방향 | 핵심 이유 |

③ 지금 조선 섹터를 움직이는 가장 큰 힘 TOP3
   - LNG선 수요 (에너지 전환·미국 LNG 수출)
   - 컨테이너선 교체 사이클
   - 방산·미해군 발주

④ 이 강세가 언제까지 갈 것인가 — 낙관/중립/비관 시나리오
   각 시나리오 핵심 변수 1가지씩

⑤ 한국 조선이 중국 대비 경쟁우위를 유지하는 이유
   LNG선·FLNG·방산에서 기술 격차가 좁혀지고 있는가"""

Q2 = """선종별 시장 구조를 정리해줘. 어디서 진짜 돈이 되는가.

① 선종별 수익성·성장성 비교
   | 선종 | 척당 단가 | 마진 | 지금 수요 | 한국 점유율 | 중국 위협 |
   LNG선 / LNG운반선 / 컨테이너선 / 탱커 / FLNG / 방산함정 / VLCC

② LNG선이 왜 지금 슈퍼사이클인가
   - 미국 LNG 수출 확대 → LNG선 발주 구조적 증가
   - 현재 LNG선 수주잔고 및 신규 발주 수치
   - 리드타임 현황 (계약 후 인도까지)

③ FLNG — 왜 다음 성장 동력인가
   - FLNG 1기 규모와 단가 (LNG선 대비)
   - 삼성중공업이 독점적 위치에 있는 이유
   - 현재 수주 파이프라인

④ 방산함정 — 미국 MRO·신조 발주 현황
   - MSRA(미해군 함정 유지보수) 계약 규모
   - MASGA(미해군 신조) 진행 현황
   - 핵추진잠수함(장보고-N) 개발 일정

⑤ 선종 포트폴리오별 국내 3사 매핑
   | 선종 | HD한국조선해양 | 한화오션 | 삼성중공업 |"""

Q3 = """국내 조선 3사 스토리를 제대로 정리해줘.

① HD한국조선해양(009540) / HD현대중공업
   - 수주잔고 규모 (수치)
   - 선종별 포트폴리오 — 어디가 강한가
   - 미국 필리조선소 인수·협력 현황
   - 현재 컨센서스 TP 범위
   - 살 이유 vs 팔 이유

② 한화오션(042660)
   - 수주잔고 규모 (수치)
   - 방산함정·잠수함 포지션 (한화 인수 후 달라진 것)
   - MSRA·미해군 수주 현황
   - 현재 컨센서스 TP 범위
   - 살 이유 vs 팔 이유

③ 삼성중공업(010140)
   - 수주잔고 규모 (수치)
   - FLNG 독점적 포지션 — 왜 삼성만 할 수 있는가
   - 크시리심스·코랄노르트 등 현재 FLNG 파이프라인
   - 현재 컨센서스 TP 범위
   - 살 이유 vs 팔 이유

④ 3사 비교 테이블
   | 기업 | 코드 | 수주잔고 | 핵심 강점 | TP컨센 | 지금 모멘텀 |"""

Q4 = """LNG선 밸류체인을 심층 분석해줘.
LNG선 1척이 수주되면 어떤 소부장·소재 기업이 수혜받는가.

① LNG선 1척 원가 구조
   - 총 단가 (척당 수억달러) 중 주요 비용 항목 비중
   - 국내 조달 vs 수입 비중

② 핵심 소재·부품 체인
   | 부품·소재 | 역할 | 국내 수혜 기업 | 코드 | 수혜 강도 |
   보냉재(LNG화물창) / 강재(후판) / ME-GI엔진 / 열교환기 / 도장·방청 / 전장시스템

③ 보냉재 — 왜 가장 핵심인가
   - GTT 라이선스 구조 (한국 기업의 포지션)
   - 동성화인텍·한국카본 — 실제 공급 현황과 경쟁 구도

④ 후판(강재) — POSCO·현대제철의 수혜
   - LNG선향 후판 단가·물량 현황
   - 조선 호황이 후판 기업에 미치는 실제 영향

⑤ LNG선 체인 전체 요약
   | 단계 | 대표 종목 | 코드 | 수혜 시점 | 수혜 강도 |
   (조선사 수주 → 소재 → 부품 → 인도 순서로)"""

Q5 = """방산·미해군 발주 체인을 정리해줘.
한국 조선이 미국 방산 시장에서 어떤 위치인가.

① MSRA (미해군 함정 유지보수·수리·정비)
   - 계약 규모와 현재 진행 상황 (수치)
   - HD현대중공업·한화오션·삼성중공업 중 누가 수주했는가
   - 실제 매출 인식 시점

② MASGA (미해군 신조함 프로그램)
   - 어떤 함정을 짓는 프로그램인가
   - 한국 조선사 참여 현황
   - 수주 확정 시 매출 규모 예상

③ 핵추진잠수함 (장보고-N 프로그램)
   - 총 사업 규모와 한화오션의 포지션
   - 예상 일정 (설계·착공·진수)
   - 주가에 반영되는 시점은 언제인가

④ 무인함 (USV·UUV)
   - 미해군 무인수상정·수중무인정 발주 현황
   - 국내 조선사의 참여 가능성

⑤ 방산 수주 발생 시 수혜 체인
   조선 3사 → 방산 장비·전장·소재 소부장 → 어떤 종목까지 영향 미치는가"""

Q6 = """지정학·정책 × 향후 6~12개월 이벤트 타임라인.
날짜 특정 가능한 것 위주.

① 핵심 지정학·정책 변수
   - 미국 LNG 수출 확대 정책 (트럼프 행정부)
   - 미국 해운법(Jones Act) 개정 논의
   - 미중 갈등 → 중국 조선 견제 → 한국 반사이익
   - IMO 환경규제 (탄소중립 선박 전환 일정)

② 이벤트 타임라인 (날짜 특정)
   | 날짜 | 이벤트 | 수혜 기업 | 영향 강도 | 근거 |

   아래 항목 커버:
   - 미국 LNG 터미널 신규 FID(최종투자결정) 예상 시점
   - MSRA 추가 발주 일정
   - 삼성중공업 FLNG 수주 발표 예상 시점
   - 조선 3사 실적 발표 일정 (2분기·3분기)
   - IMO 환경규제 주요 시행일

③ 리스크 — 상승을 막을 것 TOP3
   | 리스크 | 발생 조건 | 영향 종목 |"""

Q7 = """지금까지 얘기한 내용을 하나의 스토리로 종합.

① 조선 섹터 전체 스토리 — 3단 구조
   배경(2016 불황에서 어떻게 여기까지) / 현재(지금 무슨 일) / 앞으로(2027~2030)

② 종목별 포지션 맵
   | 종목명 | 코드 | 지금 상황 | 핵심 재료 | 리스크 |

③ 서브섹터별 온도
   | 서브섹터 | 온도 | 이유 | 대표 종목 |
   LNG선 / FLNG / 컨테이너선 / 탱커 / 방산함정 / 보냉재·소재

④ 유튜브 영상 주제 5개 — "이거 몰랐는데?" 할 만한 것
   각 주제: 제목 후보 + 핵심 메시지 한 줄

⑤ 지금 이 섹터에서 가장 과소평가된 종목·이슈"""

Q8 = """어떤 뉴스가 나오면 어떤 종목이 어떻게 반응했는지.
실제 케이스 기반으로.

① 뉴스 유형별 주가 반응 패턴
   | 뉴스 유형 | 1차 반응 종목 | 2차 반응 종목 | 강도 | 시차 | 실제 사례 |

   아래 유형 전부 커버:
   - 미국 LNG 터미널 FID(최종투자결정) 발표
   - 대형 LNG선 수주 공시 (10척+ 규모)
   - 삼성중공업 FLNG 수주 공시
   - MSRA·미해군 방산 계약 공시
   - 클락슨 선가 지수 신고가 경신
   - 선박 발주 취소·인도 지연 뉴스
   - 중국 조선 저가 수주 공세 보도
   - IMO 환경규제 강화 발표
   - 원달러 환율 급등 (수출주 수혜)

② 무반응 케이스 — "조선 뉴스니까 다 오르겠지" 착각
   | 뉴스 | 왜 안 움직였나 |

③ 지금 당장 나오면 섹터 전체 폭발할 뉴스 TOP3"""

Q9 = """지금 이 시점 조선 섹터에서 가장 강한 종목들.
수급 + 펀더멘털 + 이슈 삼중으로.

① 현재 주도주 TOP5
   | 종목 | 코드 | 왜 지금 주도주인가 | 핵심 근거 | 언제까지 | 확인 지표 |

② HD한국조선해양 vs 한화오션 vs 삼성중공업
   - 지금 이 세 종목 중 모멘텀 가장 강한 곳은
   - 밸류에이션 비교 — PBR·PSR 기준 어디가 싼가
   - 수주잔고 대비 시총 비율 비교

③ 소부장 중 지금 가장 강한 모멘텀 종목
   - 동성화인텍·한국카본·HJ중공업·수산인더스트리 중 어디인가
   - 왜 지금 이 종목인가

④ 외국인·기관이 지금 가장 많이 담는 조선주 TOP3
   vs 아직 안 담은 것 중 논리 있는 종목

⑤ 대형 조선사 대비 소부장에서 알파를 찾을 수 있는가
   지금 어느 구간인가"""

Q10 = """조선 섹터 꼬리에 꼬리를 무는 연쇄 구조.

① LNG 터미널 FID 체인
   미국 LNG 터미널 최종투자결정(FID) 발표
     → HD한국조선해양 (LNG선 수주 기대) — 왜? 시차?
         → 삼성중공업 (LNG선·FLNG 동시) — 왜? 시차?
         → 한국카본·동성화인텍 (보냉재) — 왜? 시차?
         → POSCO홀딩스 (후판 단가 상승) — 왜? 시차?
         → 수산인더스트리·HJ중공업 (기자재) — 왜? 시차?

② FLNG 수주 체인
   삼성중공업 FLNG 수주 공시
     → 삼성중공업 (1차 직접) — 즉각
         → 보냉재 업체 (동성화인텍·한국카본) — 왜? 시차?
         → 해양플랜트 기자재 업체 — 왜? 시차?
         → FLNG 뉴스 → LNG선 발주 기대 → HD한국조선해양 동반 상승 — 왜?

③ 미해군 방산 수주 체인
   MSRA 추가 발주 공시
     → 한화오션 (방산 대장) — 즉각
         → HD현대중공업 (공동 수주 가능) — 왜?
         → 방산 전장·기자재 업체 — 왜? 시차?
         → 장보고-N 핵잠수함 → 한화오션 장기 모멘텀 재부각 — 왜?

④ 선가 상승 체인
   클락슨 선가지수 신고가 경신
     → 조선 3사 전체 (마진 개선 기대) — 즉각
         → 수주잔고 단가 재산정 기대 — 왜?
         → 소부장으로 자금 이동 — 시차?

⑤ 연결이 끊기는 지점 — 오해 케이스
   "조선 수주니까 소부장 다 올라" 가 틀린 이유
   어떤 소부장이 실제로 연결되고 어떤 게 연결 안 되는가

⑥ 지금 어느 체인이 가장 활성화돼 있는가
   다음 체인은 무엇이 될 것인가"""

QUESTIONS = [
    ("Q1",  "섹터 전체 그림",                           Q1),
    ("Q2",  "선종별 구조 (LNG·FLNG·방산)",               Q2),
    ("Q3",  "국내 3사 스토리",                           Q3),
    ("Q4",  "LNG 밸류체인 심층 (보냉재·강재·엔진)",       Q4),
    ("Q5",  "방산·미해군 수주 체인 (MSRA·MASGA·핵잠)",   Q5),
    ("Q6",  "지정학·정책 × 이벤트 타임라인",              Q6),
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
print(f"  조선 섹터 Q1~Q10 리서치")
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
raw_file = raw_dir / f'{TODAY}_조선_Q10리서치.md'
raw_content = f"# 조선 섹터 Q1~Q10 리서치 ({TODAY})\n> Gemini Flash + Google Search | TYPE C 하이브리드\n\n---\n\n"
for qnum, data in results.items():
    raw_content += f"## {qnum} — {data['title']}\n\n**질문:**\n{data['question']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본: {raw_file.name}")

sector_dir  = ROOT / 'wiki' / 'L5_섹터' / '조선'
sector_dir.mkdir(parents=True, exist_ok=True)
sector_file = sector_dir / 'sector_조선_Q10.md'

sector_content = f"""# 조선 섹터 — 현재 상태 [TYPE C 하이브리드]

> 수주잔고(실적형) + LNG·FLNG·방산(성장형) 동시 적용
> Gemini Q1~Q10 리서치: {TODAY}
> 원본: `raw/L5_섹터/{TODAY}_조선_Q10리서치.md`

---

### Q1 — 섹터 전체 그림

{get('Q1')}

---

### Q2 — 선종별 구조 (LNG·FLNG·컨테이너·방산)

{get('Q2')}

---

### Q3 — 국내 3사 스토리

{get('Q3')}

---

### Q4 — LNG 밸류체인 심층 (보냉재·강재·엔진)

{get('Q4')}

---

### Q5 — 방산·미해군 수주 체인 (MSRA·MASGA·핵잠)

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

## 관련 파일
- [[L6_수급/export_monitor]] — 수출 데이터
"""
sector_file.write_text(sector_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/조선/sector_조선_Q10.md")

log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q,d in results.items() if not d['answer'].startswith('[오류')]
    entry = f"- {TODAY} — 조선 Q1~Q10 딥리서치: 성공 {completed} / 실패 {failed}\n"
    log_file.write_text(entry + log, encoding='utf-8')
print(f"✅ log.md 기록")

print(f"\n{'='*60}")
print(f"  완료: {[q for q,d in results.items() if not d['answer'].startswith('[오류')]}")
if failed: print(f"  실패: {failed}")
print(f"\n  원본: raw/L5_섹터/{TODAY}_조선_Q10리서치.md")
print(f"  위키: wiki/L5_섹터/조선/sector_조선_Q10.md")
print(f"{'='*60}")
