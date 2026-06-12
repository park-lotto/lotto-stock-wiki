"""
반도체 섹터 Q1~Q10 연속 대화 리서치
- Q1~Q7: 기존 섹터 전체 구조 (유지)
- Q8: 뉴스 트리거 × 주가 반응 매핑 (신규)
- Q9: 지금 국내 주도 종목 × 왜 강한가 (신규)
- Q10: 꼬리에 꼬리를 물고 — 연쇄 구조 (신규)
사용: python scripts/gemini_semiconductor_q10.py

## 꼬리에 꼬리 원칙 — 답변이 끝이 아니다
각 Q의 답변에서 새로운 질문이 나온다. 발견된 신규 주제는 다음 실행 시 Q를 추가하거나
별도 스크립트로 분리해 더 깊이 파고든다.

## 발견된 확장 주제 (다음 Q 후보)
Q11 후보: CPU 추론 시대 × 온디바이스 AI 수혜 — 오픈엣지·가온칩스·SOCAMM 체인
Q12 후보: 밸류에이션 갭 플레이 패턴 — 대장주 급등 후 동업종 저PBR 이동 법칙
Q13 후보: 삼성전자 파운드리 2nm 수주 확정 시 연쇄 수혜 체인 심층
Q14 후보: 피지컬 AI × 반도체 교집합 — 오픈엣지 NPU가 로봇에 들어가는 경로
"""
import sys, os, time, re
from datetime import date
from pathlib import Path
from google import genai
from google.genai import types
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
ENV  = ROOT / '.env'

env = {}
for line in ENV.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

API_KEY = env.get('GEMINI_API_KEY', '')
if not API_KEY:
    print('GEMINI_API_KEY 없음'); sys.exit(1)

TODAY = date.today().strftime('%Y-%m-%d')

# ── 시스템 셋업 ─────────────────────────────────────────────────────────────
OPENING = f"""오늘 날짜는 {TODAY}이야.
너는 한국 주식시장 반도체 섹터 전문 애널리스트야.
앞으로 내가 Q1~Q10을 순서대로 질문할 거야. 모든 답변은:
- 한국 상장사 기준으로
- 구체적인 수치·날짜·종목명·종목코드 포함
- 마크다운 테이블 적극 활용
- 모르는 건 모른다고 해줘 (허수 금지)
- Google 검색으로 최신 정보 확인해줘"""

# ── Q1~Q7: 기존 (유지) ──────────────────────────────────────────────────────
Q1 = """지금 한국 반도체 섹터가 강세인 이유를 전체 그림으로 설명해줘.

단순히 "AI 수요 증가" 같은 얘기 말고,
왜 지금 이 시점에 이렇게 강한지 — 구조적으로 설명해줘.

① 지금 이 강세가 단순 사이클인가, 구조적 변화인가
   그렇게 판단하는 근거 3가지

② 2024~2026 반도체 주가 흐름을 한 줄씩
   | 시기 | 시장 상황 | 주가 방향 | 핵심 이유 |

③ 지금 반도체 섹터를 움직이는 가장 큰 힘 TOP 3
   (수요 측면 / 공급 측면 / 정책·지정학 측면)

④ 이 강세가 언제까지 갈 것인가 — 낙관/중립/비관 시나리오"""

Q2 = """HBM이 왜 이번 사이클의 핵심인지 깊이 파줘.

① HBM vs 일반 DRAM — 구조·단가·마진 비교
   | 항목 | 일반 DRAM | HBM | 차이 |

② 엔비디아 GPU 로드맵에서 HBM 탑재량 변화 (세대별 수치)
   Pascal → Hopper → Blackwell → Vera Rubin

③ 왜 SK하이닉스가 독점에 가까운가, 삼성이 뒤처진 이유

④ HBM4/HBM4E에서 판도 변화 가능성

⑤ HBM 수혜 밸류체인
   | 단계 | 종목명 | 코드 | 수혜 이유 |"""

Q3 = """삼성전자(005930) 얘기를 제대로 해줘.
메모리와 파운드리 두 엔진.

① 메모리 엔진
   - DRAM/NAND 판가 현재 수준 (수치)
   - HBM에서 SK하이닉스 대비 포지션
   - 2026 하반기~2027 전망

② 파운드리 엔진
   - 2024~2025년 어려웠던 이유
   - 2026년 회복 신호 — 4nm 가동률, 2nm 수주 현황
   - 테슬라·애플·퀄컴 수주 현황

③ 지금 컨센서스 TP 범위와 근거

④ 삼성전자를 살 이유 vs 팔 이유 각 3가지"""

Q4 = """미중 반도체 패권 경쟁 — 한국 투자자 관점으로.

① 미국 대중 규제가 지금까지 한국에 어떤 영향을 미쳤나

② 중국 CXMT DRAM 진입 실제 기술 수준
   삼성·SK 대비 몇 세대 뒤, 언제부터 위협인가

③ 미중 경쟁이 한국에 주는 기회
   AI 인프라에서 한국이 독점적 위치를 가진 이유

④ 향후 6~12개월 미중 이슈 타임라인
   | 시기 | 예상 이벤트 | 한국 주가 영향 |"""

Q5 = """삼성·SK하이닉스 말고 소부장 수혜 종목 정리.

① 지금 실제로 돈이 되고 있는 분야
   수출 데이터로 확인되는 것

② 분야별 수혜 종목 테이블
   | 분야 | 종목명 | 코드 | 왜 수혜 | 수혜 등급 |
   식각소재 / 세정소재 / 전공정장비 / 후공정OSAT / 기판소재 / 테스트장비 / MLCC·FC-BGA

③ 대형주 대비 소부장 주가 타이밍
   대형주 먼저인가, 동시인가, 소부장이 선행하는 케이스는 언제인가

④ 지금 아직 덜 오른 곳 — 투자자가 놓치고 있는 종목"""

Q6 = """앞으로 6개월~1년 안에 주가에 영향을 줄 이벤트 총정리.

① 확정된 일정 타임라인
   | 날짜 | 이벤트 | 수혜 종목 | 영향 강도 |

② 아직 불확실하지만 터지면 큰 것들
   어떤 조건이 충족될 때 폭발하는가

③ 시장이 간과하고 있는 미래 재료

④ 상승을 막을 리스크 타임라인
   | 시기 | 리스크 | 발생 시 영향 |"""

Q7 = """지금까지 얘기한 내용을 하나의 스토리로 종합.

① 반도체 섹터 전체 스토리 — 3단 구조
   배경 / 현재 / 앞으로

② 종목별 포지션 맵
   | 종목명 | 코드 | 지금 상황 | 핵심 재료 | 리스크 |
   (대형주 → 중형주 → 소부장)

③ 유튜브 영상 주제 — "이거 몰랐는데?" 할 만한 것 5개
   각 주제: 제목 후보 + 핵심 메시지 한 줄

④ 지금 이 섹터에서 가장 과소평가된 종목/이슈"""

# ── Q8~Q10: 신규 추가 ──────────────────────────────────────────────────────
Q8 = """이번에는 "어떤 뉴스가 나오면 어떤 종목이 어떻게 반응했는지"를 정리해줘.
과거 6개월 실제 케이스 기반으로.

① 뉴스 유형별 주가 반응 패턴 테이블
   | 뉴스 유형 | 1차 반응 종목 | 2차 반응 종목 | 반응 강도 | 시차 | 실제 사례 날짜 |

   아래 유형 전부 커버해줘:
   - NVDA 어닝 서프라이즈 / 가이던스 상향
   - NVDA 신규 GPU 아키텍처 발표 (Vera Rubin 등)
   - 삼성전자 HBM 수율 개선 뉴스
   - 삼성전자 파운드리 수주 확정 뉴스
   - SK하이닉스 HBM 독점 공급 재확인
   - DRAM/NAND ASP 상향 보고서
   - 미중 반도체 규제 강화 발표
   - COMPUTEX·GTC 젠슨황 발표
   - 한국 반도체 수출 서프라이즈
   - 삼성전기 MLCC 판가 전환 신호
   - FC-BGA 쇼티지 뉴스
   - 소부장 증권사 TP 일괄 상향

② 뉴스가 나왔는데 무반응이었던 케이스
   "같은 반도체니까 오르겠지" 착각 — 실제로 안 움직인 것들
   | 뉴스 | 왜 안 움직였나 |

③ 지금 당장 나오면 섹터 전체가 폭발할 뉴스 유형 TOP 3
   각각 어떤 종목부터 어떤 순서로 뜨는가"""

Q9 = """지금 이 시점 한국 반도체 섹터에서 가장 강한 종목들.
단순히 "많이 올랐다"가 아니라 왜 이 종목이 지금 주도주인가 — 수급+펀더멘털+이슈 삼중으로.

① 현재 주도주 TOP5
   | 종목 | 코드 | 왜 지금 주도주인가 | 핵심 근거 | 언제까지 | 이걸 확인할 지표 |

② 삼성전기가 이번 주 7개 증권사 동시 TP 상향, LG이노텍 6개 증권사 동시 상향.
   MLCC·FC-BGA·기판 섹터가 왜 지금 주도주가 됐는가
   - 대형주(SK하이닉스·삼성전자)에서 부품주로 자금이 넘어오는 신호인가
   - 아니면 독립적인 모멘텀인가
   - MLCC 판가 YoY가 음수→양수 전환한 것이 얼마나 큰 신호인가

③ SK하이닉스 TP 컨센 310만, 삼성전자 TP 컨센 39~55만.
   대형주가 선반영이 많이 됐다면 지금 어디서 알파를 찾아야 하는가

④ 외국인·기관이 지금 가장 많이 담고 있는 반도체주 TOP5
   vs 아직 안 담은 것 중 논리가 있는 종목"""

Q10 = """마지막으로 — 반도체 섹터 내 "꼬리에 꼬리를 물고" 연쇄 흐름 구조.
A가 뜨면 왜 B가 뜨고, B가 뜨면 왜 C가 뜨는지. 각 연결마다 이유와 시차까지.

① HBM 체인
   엔비디아 HBM 수요 확정
     → SK하이닉스 (HBM 독점 공급) — 당일
         → 한미반도체 (TC본더 독점) — 왜? 시차?
         → HPSP (고압수소어닐링) — 왜? 시차?
         → 심텍 (HBM용 MR-MUF 기판) — 왜? 시차?
         → 피에스케이홀딩스 (PR Strip) — 왜? 시차?
         → 코미코 (부품 세정, 교체주기 단축) — 왜? 시차?
   각 단계마다 시차가 얼마나 있는가 — 실제 사례로 검증해줘

② MLCC·기판 체인
   삼성전기 MLCC 판가 양전환 신호
     → 삼성전기 뜸
         → 심텍 (서버용 고층기판) — 왜?
         → 대덕전자 (FC-BGA) — 왜?
         → 이수페타시스 (AI 서버 고다층 PCB) — 왜?
         → 코리아써키트 — 왜?

③ 파운드리 체인
   삼성전자 파운드리 2nm 수주 확정 뉴스
     → 삼성전자 파운드리 리레이팅
         → 솔브레인 (식각액 ASP 연동) — 왜?
         → 코미코 (부품 세정) — 왜?
         → 피에스케이 (PR Strip 신규 공정) — 왜?

④ 소부장 리레이팅 체인
   대형주 TP 상향 → 소부장으로 자금 이동할 때
   어떤 순서로 어떤 종목이 움직이는가
   실제로 이 패턴이 확인된 사례가 있는가

⑤ 실제로 연결이 안 되는 것 — 오해 케이스
   "반도체 섹터니까 다 같이 올라" 가 틀린 이유
   각 체인에서 연결이 끊기는 지점이 어디인가

⑥ 지금 이 시점 어느 체인이 가장 활성화돼 있는가
   그리고 다음 체인은 무엇이 될 것인가"""

# ── 실행 ────────────────────────────────────────────────────────────────────
QUESTIONS = [
    ("Q1",  "섹터 전체 그림",           Q1),
    ("Q2",  "HBM 게임체인저",           Q2),
    ("Q3",  "삼성전자 스토리",           Q3),
    ("Q4",  "미중 패권 전쟁",           Q4),
    ("Q5",  "소부장 밸류체인",           Q5),
    ("Q6",  "미래 재료 총정리",          Q6),
    ("Q7",  "전체 스토리 종합",          Q7),
    ("Q8",  "뉴스 트리거 × 주가 반응",   Q8),
    ("Q9",  "국내 주도 종목 × 왜 강한가", Q9),
    ("Q10", "꼬리에 꼬리 연쇄 구조",     Q10),
]

print(f"{'='*60}")
print(f"  반도체 섹터 Q1~Q10 리서치 시작")
print(f"  기준일: {TODAY}")
print(f"  모델: gemini-3-flash-preview + Google Search")
print(f"  총 {len(QUESTIONS)}개 질문")
print(f"{'='*60}\n")

client = genai.Client(api_key=API_KEY)

chat = client.chats.create(
    model='gemini-3-flash-preview',
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.3,
    )
)

results = {}

print("[시스템 셋업] 역할 설정 중...")
chat.send_message(OPENING)
print("✅ 셋업 완료\n")
time.sleep(2)

# 실패한 Q 재시도용 저장
failed = []

for qnum, qtitle, qtext in QUESTIONS:
    print(f"{'─'*60}")
    print(f"  {qnum} / {qtitle}")
    print(f"{'─'*60}")

    for attempt in range(3):
        try:
            resp = chat.send_message(qtext)
            answer = resp.text
            results[qnum] = {"title": qtitle, "question": qtext, "answer": answer}
            preview = answer.replace('\n', ' ')[:200]
            print(f"  ✅ 완료 ({len(answer)}자)")
            print(f"  미리보기: {preview}...\n")
            time.sleep(3)
            break
        except Exception as e:
            print(f"  ❌ 오류 (시도 {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(10)
            else:
                results[qnum] = {"title": qtitle, "question": qtext, "answer": f"[오류: {e}]"}
                failed.append(qnum)

# ── 저장 ────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  저장 중...")
print(f"{'='*60}")

# 1. 원본 Q&A 저장
raw_dir = ROOT / 'raw' / 'L5_섹터'
raw_dir.mkdir(parents=True, exist_ok=True)
raw_file = raw_dir / f'{TODAY}_반도체_Q10리서치.md'

raw_content = f"# 반도체 섹터 Q1~Q10 리서치 ({TODAY})\n> Gemini Flash + Google Search 연속 대화\n\n---\n\n"
for qnum, data in results.items():
    raw_content += f"## {qnum} — {data['title']}\n\n**질문:**\n{data['question']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"

raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본: {raw_file.name}")

# 2. sector_반도체.md 업데이트
sector_dir  = ROOT / 'wiki' / 'L5_섹터' / '반도체'
sector_file = sector_dir / 'sector_반도체.md'
sector_dir.mkdir(parents=True, exist_ok=True)

def get(q):
    return results.get(q, {}).get('answer', '')

sector_content = f"""# 반도체 섹터 — 현재 상태

---

## 🔬 섹터 딥리서치 ({TODAY})
> Gemini 2.5 Flash + Google Search | Q1~Q10 연속 대화
> 원본: `raw/L5_섹터/{TODAY}_반도체_Q10리서치.md`

---

### 오늘의 한줄 ({TODAY} 업데이트)
> Q7 종합 스토리 기반 — 전체 흐름 요약

---

### Q1 — 섹터 전체 그림 (왜 지금 강한가)

{get('Q1')}

---

### Q2 — HBM이 왜 게임체인저인가

{get('Q2')}

---

### Q3 — 삼성전자 스토리 (메모리 + 파운드리)

{get('Q3')}

---

### Q4 — 미중 패권 전쟁 × 한국 기회·위협

{get('Q4')}

---

### Q5 — 소부장 밸류체인 (MLCC·기판·소재·장비)

{get('Q5')}

---

### Q6 — 미래 재료 총정리 (D-Day 달력)

{get('Q6')}

---

### Q7 — 전체 스토리 종합 + 콘텐츠

{get('Q7')}

---

### Q8 — 뉴스 트리거 × 주가 반응 패턴

{get('Q8')}

---

### Q9 — 지금 국내 주도 종목 × 왜 강한가

{get('Q9')}

---

### Q10 — 꼬리에 꼬리를 물고 (연쇄 구조)

{get('Q10')}

---

## 📰 이벤트 히스토리
- {TODAY}: Q1~Q10 딥리서치 완료 (Gemini Flash + Google Search)

## 💡 콘텐츠 기회
(Q7 유튜브 주제 참조)

## 관련 파일
- [[스토리보드_반도체]] — 마스터 내러티브
- [[반도체index]] — 일일 업데이트 데이터
"""

sector_file.write_text(sector_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/반도체/sector_반도체.md")

# 3. log.md
log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    entry = f'- {TODAY} — 반도체 Q1~Q10 딥리서치 완료 (Q8 뉴스트리거·Q9 주도종목·Q10 연쇄구조 신규 추가)\n'
    log_file.write_text(entry + log, encoding='utf-8')
print(f"✅ log.md 기록")

if failed:
    print(f"\n⚠️  실패한 Q: {failed} — gemini_sector_q7_resume.py로 재시도 필요")

print(f"\n{'='*60}")
print(f"  완료!")
print(f"  원본: raw/L5_섹터/{TODAY}_반도체_Q10리서치.md")
print(f"  위키: wiki/L5_섹터/반도체/sector_반도체.md")
print(f"{'='*60}")
