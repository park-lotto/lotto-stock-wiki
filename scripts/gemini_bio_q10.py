"""
바이오·제약 섹터 Q1~Q10 리서치
TYPE B 성장형: 임상 결과·FDA 승인·기술이전이 주가 트리거. PER/PBR 무의미.

핵심 논리:
  글로벌 빅파마 파이프라인 부족 → 한국 바이오텍 기술이전 수요 급증
  ADC(항체약물접합체) 슈퍼사이클 → 한국 ADC 원천 기술 보유 기업 주목
  GLP-1(비만약) 시장 폭발 → 원료·CMO·플랫폼 수혜

Q1  섹터 전체 그림 (왜 지금 한국 바이오인가)
Q2  치료 분야별 구조 (ADC·GLP-1·항암·면역·희귀질환·바이오시밀러)
Q3  국내 대장주 스토리 (한미약품·셀트리온·알테오젠·HLB·유한양행·리가켐)
Q4  ADC 심층 — 왜 지금 가장 뜨거운가 (국내 수혜 기업)
Q5  GLP-1 비만약 시장 — 한국 기업 어디가 수혜인가
Q6  기술이전(L/O) 구조 × 임상 이벤트 타임라인 (6~12개월)
Q7  전체 스토리 종합 + 콘텐츠 기회
Q8  뉴스 트리거 × 주가 반응 패턴
Q9  지금 주도 종목 × 왜 강한가
Q10 꼬리에 꼬리 연쇄 구조

사용: python scripts/gemini_bio_q10.py
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
너는 한국 주식시장 바이오·제약 섹터 전문 애널리스트야.

답변 규칙:
- 한국 상장사 기준 (종목명 + 6자리 코드 반드시 포함)
- 구체적 수치·임상 단계·계약금액·날짜 포함. 모르면 "미확인" 명시 (허수 금지)
- 마크다운 테이블 적극 활용
- 핵심만 간결하게 — 테이블 위주
- Google 검색으로 최신 정보 확인"""

Q1 = """지금 한국 바이오·제약 섹터가 주목받는 이유를 전체 그림으로 설명해줘.

① 지금 이 강세가 단순 테마인가, 구조적 변화인가 — 근거 3가지
   - 글로벌 빅파마 파이프라인 고갈 → 한국 기술이전 수요
   - ADC 슈퍼사이클 도래
   - GLP-1 시장 폭발

② 2022~2026 바이오 주가 흐름 한 줄씩
   | 시기 | 시장 상황 | 주가 방향 | 핵심 이유 |

③ 지금 한국 바이오를 움직이는 가장 큰 힘 TOP3

④ 한국 바이오가 글로벌에서 실제로 경쟁력을 가진 영역
   — 항체 기술 / ADC 링커·페이로드 / 바이오시밀러 / CMO 생산 / 플랫폼 기술

⑤ 강세 시나리오 vs 리스크 시나리오
   | 구분 | 핵심 변수 | 주가 영향 |"""

Q2 = """바이오 치료 분야별 시장 구조를 정리해줘.
어디서 진짜 돈이 되고 한국이 강한 곳은 어디인가.

① 분야별 수익성·성장성 비교
   | 분야 | 글로벌 시장 규모 | 성장률 | 한국 경쟁력 | 대표 한국 기업 |
   ADC(항체약물접합체) / GLP-1(비만·당뇨) / 항암(면역항암) / 희귀질환 / 바이오시밀러 / mRNA / 세포·유전자치료

② 바이오시밀러 — 한국이 글로벌 1위인 이유
   - 셀트리온·삼성바이오로직스의 실제 시장 점유율
   - 자가면역·종양 항체 바이오시밀러 수익 구조

③ ADC vs 기존 항암제 — 왜 ADC가 게임체인저인가
   - ADC 구조 (항체 + 링커 + 페이로드)
   - 어느 파트에서 한국 기업이 강점인가

④ GLP-1 — 비만약이 왜 모든 빅파마의 최우선인가
   - 시장 규모 (수치)
   - 한국 기업 중 직접 수혜받는 곳

⑤ 기술이전(License-out) 구조
   - 계약금 구조 (선급금·마일스톤·로열티) 이해
   - 한국이 왜 기술이전을 자주 하는가"""

Q3 = """국내 바이오 주요 기업 스토리를 정리해줘.

① 한미약품(128940)
   - 핵심 파이프라인 (TP-0184·에피노페그듀타이드·롤론티스 등)
   - GLP-1 계열 파이프라인 — 글로벌 경쟁력 실제 어떤가
   - 최근 기술이전 계약 현황
   - 컨센서스 TP 범위

② 셀트리온(068270)
   - 바이오시밀러 현재 매출 구조
   - 짐펜트라(피하주사 인플릭시맙) — 미국 시장 침투 현황
   - 신약 파이프라인 (CT-P59 등)
   - 컨센서스 TP 범위

③ 알테오젠(196170)
   - ALT-B4(히알루로니다제) 기술이전 — 왜 이게 핵심인가
   - SC(피하주사) 전환 플랫폼의 가치
   - 계약 현황과 로열티 구조
   - 컨센서스 TP 범위

④ 리가켐바이오(141080)
   - ADC 링커·페이로드 플랫폼 — 글로벌 위치
   - 기술이전 계약 현황 (아스트라제네카 등)
   - 컨센서스 TP 범위

⑤ HLB(028300)
   - 리보세라닙 (카보메탁스) 현황
   - FDA 승인 경과·현재 상황
   - 컨센서스 TP 범위

⑥ 유한양행(000100)
   - 레이저티닙(렉라자) 글로벌 현황
   - J&J 공동개발 진행 상황
   - 컨센서스 TP 범위

⑦ 비교 테이블
   | 기업 | 코드 | 핵심 파이프라인 | 임상 단계 | TP컨센 | 지금 모멘텀 |"""

Q4 = """ADC(항체약물접합체) 심층 분석.
왜 지금 가장 뜨겁고, 한국 어떤 기업이 실제 수혜인가.

① ADC가 왜 항암 치료의 게임체인저인가
   - 기존 항암제 대비 ADC의 기전적 우위
   - 글로벌 ADC 시장 규모와 성장률 (수치)
   - 빅파마들이 ADC에 천문학적 금액을 투자하는 이유

② ADC 3대 구성 요소별 한국 기업 포지션
   | 구성 | 역할 | 국내 핵심 기업 | 코드 | 글로벌 경쟁력 |
   항체(Antibody) / 링커(Linker) / 페이로드(Payload)

③ 리가켐바이오(141080) — ADC 링커·페이로드 플랫폼
   - 구체적으로 어떤 기술인가
   - 기술이전 계약 건수와 계약금 (수치)
   - 왜 글로벌 빅파마들이 선택하는가

④ ADC 관련 국내 기업 전체 매핑
   | 기업 | 코드 | ADC 내 역할 | 현재 계약 | 수혜 강도 |

⑤ ADC에서 가장 빠르게 매출 나올 한국 기업과 시점"""

Q5 = """GLP-1 비만·당뇨약 시장 — 한국 수혜 기업 분석.

① GLP-1 시장이 왜 이렇게 커졌는가
   - 오젬픽·위고비·마운자로 — 시장 규모 수치
   - 비만약이 단순 비만 치료를 넘어선 이유 (심혈관·신장·알츠하이머)
   - 2030년까지 시장 전망

② 빅파마 GLP-1 경쟁 구도 → 한국 기회
   - 노보노디스크·일라이릴리 독주 → 2위권 진입 경쟁
   - 후발 주자들이 필요한 것: 기술·원료·CMO

③ 한미약품 GLP-1 파이프라인
   - 에피노페그듀타이드 (GLP-1/GCG) — 현재 임상 단계
   - 차별화 포인트가 실제로 있는가
   - 글로벌 경쟁 약물 대비 위치

④ GLP-1 원료·CMO 수혜 기업
   - 삼성바이오로직스(207940) — GLP-1 CMO 현황
   - GLP-1 원료 공급 국내 기업 있는가

⑤ GLP-1에서 가장 직접 수혜받는 한국 기업 TOP3
   이유와 매출 인식 시점"""

Q6 = """기술이전(License-out) 구조와 향후 6~12개월 임상·이벤트 타임라인.

① 기술이전 계약 구조 이해
   - 선급금(Upfront) / 마일스톤 / 로열티 각각의 의미
   - 계약금 1조가 진짜 1조인가 — 실제 인식 방식
   - 임상 실패 시 반환 조건 (반환의무·옵션반환)

② 한국 바이오 주요 기술이전 현황 (확정된 것)
   | 기업 | 기술 | 상대방 | 계약 규모 | 현재 단계 | 주가 반영 여부 |

③ 이벤트 타임라인 (날짜 특정 가능한 것만)
   | 날짜 | 이벤트 | 기업 | 주가 영향 | 근거 |

   아래 항목 커버:
   - FDA 허가 심사 일정 (PDUFA 날짜)
   - 주요 임상 3상 결과 발표 예정
   - 글로벌 학술대회 (ASCO·ESMO·ASH) 발표 일정
   - 기술이전 계약 마일스톤 수령 예상 시점
   - 국내 기업 실적 발표 (2분기·3분기)

④ 리스크 TOP3
   | 리스크 | 발생 조건 | 영향 종목 |"""

Q7 = """지금까지 얘기한 내용을 하나의 스토리로 종합.

① 한국 바이오 섹터 전체 스토리 — 3단 구조
   배경(왜 한국 바이오인가) / 현재(ADC·GLP-1 슈퍼사이클) / 앞으로(2027~2030)

② 서브섹터별 온도
   | 서브섹터 | 온도 | 이유 | 대표 종목 |
   ADC / GLP-1 / 바이오시밀러 / 면역항암 / 희귀질환 / mRNA / CMO

③ 종목별 포지션 맵
   | 종목 | 코드 | 지금 상황 | 핵심 재료 | 리스크 |

④ 유튜브 영상 주제 5개 — "이거 몰랐는데?" 할 만한 것

⑤ 지금 이 섹터에서 가장 과소평가된 종목·이슈"""

Q8 = """어떤 뉴스가 나오면 어떤 종목이 어떻게 반응했는지. 실제 케이스.

① 뉴스 유형별 주가 반응 패턴
   | 뉴스 유형 | 1차 반응 | 2차 반응 | 강도 | 시차 | 실제 사례 |

   아래 유형 전부:
   - FDA 허가 승인 공시
   - FDA 허가 거절 (CRL) 공시
   - 임상 3상 성공 발표
   - 임상 실패 (중단·데이터 미충족)
   - 글로벌 빅파마 기술이전 계약 공시
   - ASCO·ESMO 핵심 발표
   - 마일스톤 수령 공시
   - 반환의무 발동 (계약 해지)
   - 삼성바이오로직스 대형 CMO 계약
   - 미국 바이오 섹터 전반 상승 (KBIO·XBI ETF)

② 무반응 케이스 — "바이오 뉴스니까 다 오르겠지" 착각

③ 지금 당장 나오면 섹터 전체 폭발할 뉴스 TOP3"""

Q9 = """지금 이 시점 바이오 섹터에서 가장 강한 종목들.

① 현재 주도주 TOP5
   | 종목 | 코드 | 왜 지금 주도주인가 | 핵심 근거 | 언제까지 | 확인 지표 |

② 알테오젠 vs 리가켐바이오
   - 지금 이 두 종목 중 모멘텀 더 강한 곳
   - 밸류에이션 비교 (시총 대비 계약 규모)

③ 임상 결과 임박 종목
   - 6개월 내 결과 나오는 것 중 기대치 가장 높은 곳

④ 외국인·기관이 지금 가장 많이 담는 바이오주 TOP3
   vs 아직 안 담은 것 중 논리 있는 종목

⑤ 대형주 대비 중소형 바이오에서 알파를 찾을 수 있는가"""

Q10 = """바이오 섹터 꼬리에 꼬리를 무는 연쇄 구조.

① 기술이전 대형 계약 체인
   한국 바이오텍 빅파마 기술이전 공시 (1조+ 규모)
     → 해당 기업 상한가급 — 즉각
         → 동일 플랫폼 보유 기업 동반 상승 — 왜? 시차?
         → ADC·GLP-1 관련 기업 전반 — 왜?
         → CMO 기업 (삼성바이오·에스티팜) — 시차?

② FDA 승인 체인
   국내 기업 FDA 허가 최초 취득
     → 해당 기업 — 즉각
         → 동일 적응증 임상 중인 기업 — 왜?
         → CMO·원료 기업 — 시차?

③ 임상 실패 충격 체인
   주요 임상 3상 실패 공시
     → 해당 기업 -50%~-70% — 즉각
         → 동일 플랫폼 기업 동반 하락 — 왜?
         → 섹터 전반 투심 위축 — 시차?

④ ADC 빅딜 체인
   알테오젠·리가켐 ADC 플랫폼 추가 계약
     → 해당 기업 — 즉각
         → 국내 ADC 관련 기업 전반 — 시차?
         → 항체·페이로드 소부장 — 왜?

⑤ 연결이 끊기는 지점 — 오해 케이스
   "바이오 뉴스 = 다 같이 올라" 가 틀린 이유

⑥ 지금 어느 체인이 가장 활성화돼 있는가"""

QUESTIONS = [
    ("Q1",  "섹터 전체 그림 (왜 지금 한국 바이오)",         Q1),
    ("Q2",  "치료 분야별 구조 (ADC·GLP-1·바이오시밀러)",    Q2),
    ("Q3",  "국내 대장주 6사 스토리",                       Q3),
    ("Q4",  "ADC 심층 (링커·페이로드·국내 수혜)",            Q4),
    ("Q5",  "GLP-1 비만약 시장 한국 수혜",                  Q5),
    ("Q6",  "기술이전 구조 × 임상 이벤트 타임라인",          Q6),
    ("Q7",  "전체 스토리 종합 + 콘텐츠",                    Q7),
    ("Q8",  "뉴스 트리거 × 주가 반응",                      Q8),
    ("Q9",  "지금 주도 종목 × 왜 강한가",                   Q9),
    ("Q10", "꼬리에 꼬리 연쇄 구조",                        Q10),
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
print(f"  바이오·제약 섹터 Q1~Q10 리서치")
print(f"  기준일: {TODAY} | TYPE B 성장형")
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

raw_dir  = ROOT / 'raw' / 'L5_섹터'
raw_dir.mkdir(parents=True, exist_ok=True)
raw_file = raw_dir / f'{TODAY}_바이오_Q10리서치.md'
raw_content = f"# 바이오·제약 섹터 Q1~Q10 리서치 ({TODAY})\n> Gemini Flash + Google Search | TYPE B 성장형\n\n---\n\n"
for qnum, data in results.items():
    raw_content += f"## {qnum} — {data['title']}\n\n**질문:**\n{data['question']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본: {raw_file.name}")

sector_dir  = ROOT / 'wiki' / 'L5_섹터' / '바이오'
sector_dir.mkdir(parents=True, exist_ok=True)
sector_file = sector_dir / 'sector_바이오.md'

sector_content = f"""# 바이오·제약 섹터 — 현재 상태 [TYPE B 성장형]

> 임상 결과·FDA 승인·기술이전이 주가 트리거. PER/PBR 무의미.
> Gemini Q1~Q10 리서치: {TODAY}
> 원본: `raw/L5_섹터/{TODAY}_바이오_Q10리서치.md`

---

## Q1 — 섹터 전체 그림 (왜 지금 한국 바이오인가)

{get('Q1')}

---

## Q2 — 치료 분야별 구조 (ADC·GLP-1·바이오시밀러)

{get('Q2')}

---

## Q3 — 국내 대장주 6사 스토리

{get('Q3')}

---

## Q4 — ADC 심층 (링커·페이로드·국내 수혜 기업)

{get('Q4')}

---

## Q5 — GLP-1 비만약 시장 한국 수혜

{get('Q5')}

---

## Q6 — 기술이전 구조 × 임상 이벤트 타임라인

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
"""
sector_file.write_text(sector_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/바이오/sector_바이오.md")

log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q,d in results.items() if not d['answer'].startswith('[오류')]
    entry = f"- {TODAY} — 바이오 Q1~Q10 딥리서치: 성공 {completed} / 실패 {failed}\n"
    log_file.write_text(entry + log, encoding='utf-8')
print(f"✅ log.md 기록")

print(f"\n{'='*60}")
print(f"  완료: {[q for q,d in results.items() if not d['answer'].startswith('[오류')]}")
if failed: print(f"  실패: {failed}")
print(f"\n  원본: raw/L5_섹터/{TODAY}_바이오_Q10리서치.md")
print(f"  위키: wiki/L5_섹터/바이오/sector_바이오.md")
print(f"{'='*60}")
