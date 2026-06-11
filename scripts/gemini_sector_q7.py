"""
반도체 섹터 Q1~Q7 연속 대화 학습 스크립트
- Gemini Flash에 Q1~Q7을 순서대로 전송 (같은 채팅창 = 컨텍스트 유지)
- 각 Q&A 결과를 누적 저장
- 최종 결과 → wiki/L5_섹터/반도체/sector_반도체.md 업데이트
사용: python scripts/gemini_sector_q7.py
"""
import sys, os, time
from datetime import date
from pathlib import Path
from google import genai
from google.genai import types
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
ENV  = ROOT / '.env'

# .env 로드
env = {}
for line in ENV.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

API_KEY = env.get('GEMINI_API_KEY', '')
if not API_KEY:
    print('❌ GEMINI_API_KEY 없음'); sys.exit(1)

TODAY = date.today().strftime('%Y-%m-%d')
SECTOR = '반도체'

# ─── Q1~Q7 프롬프트 ───────────────────────────────────────────────────────────

OPENING = f"""오늘 날짜는 {TODAY}이야.
너는 한국 주식시장 반도체 섹터 전문 애널리스트야.
앞으로 내가 연속으로 질문할 거야. 모든 답변은:
- 한국 상장사 기준으로
- 구체적인 수치·날짜·종목코드 포함
- 마크다운 테이블 적극 활용
- 모르는 건 모른다고 해줘 (허수 금지)"""

Q1 = """지금 한국 반도체 섹터가 강세인 이유를 전체 그림으로 설명해줘.

단순히 "AI 수요 증가" 같은 얘기 말고,
왜 지금 이 시점에 이렇게 강한지 — 구조적으로 설명해줘.

① 지금 이 강세가 단순 사이클인가, 구조적 변화인가
   그렇게 판단하는 근거 3가지

② 2024~2026 반도체 주가 흐름을 한 줄씩 설명
   | 시기 | 시장 상황 | 주가 방향 | 핵심 이유 |

③ 지금 반도체 섹터를 움직이는 가장 큰 힘 TOP 3
   (수요 측면 / 공급 측면 / 정책·지정학 측면으로)

④ 이 강세가 언제까지 갈 것인가 — 낙관/중립/비관 시나리오"""

Q2 = """방금 말한 내용 중 HBM(고대역폭메모리)이 핵심으로 나왔어.
HBM이 왜 이번 사이클의 핵심인지 더 깊이 파줘.

① HBM이 기존 DRAM과 다른 점 — 구조·단가·마진 비교 테이블
   | 항목 | 일반 DRAM | HBM | 차이 |

② HBM 수요가 폭발한 이유를 엔비디아 GPU 로드맵으로 설명
   Pascal → Volta → Ampere → Hopper → Blackwell → Vera Rubin 흐름에서
   각 세대마다 HBM 탑재량이 어떻게 변했는지 수치로

③ 왜 SK하이닉스가 독점에 가까운 공급자가 됐는가
   삼성전자가 뒤처진 이유는 무엇인가

④ HBM4/HBM4E에서 판도가 바뀔 수 있는가
   삼성전자가 따라잡을 가능성과 조건

⑤ HBM 수혜 밸류체인 — 대장주 → 장비 → 소재 → 부품 순서로
   | 단계 | 종목명 | 코드 | 수혜 이유 |"""

Q3 = """삼성전자(005930) 얘기를 제대로 해줘.
지금 삼성전자 주가가 움직이는 두 가지 엔진 — 메모리와 파운드리.

① 메모리 엔진
   - DRAM/NAND 판가 현재 어느 수준인가 (수치로)
   - HBM에서 SK하이닉스 대비 삼성의 현재 포지션
   - 2026 하반기~2027년 전망

② 파운드리 엔진
   - 삼성 파운드리가 2024~2025년 어려웠던 이유
   - 2026년 회복 신호 — 4nm 가동률, 2nm 수주 현황 수치로
   - 테슬라·애플·퀄컴 수주 현황

③ 두 엔진이 동시에 돌아가면 주가에 어떤 영향인가
   지금 컨센서스 TP 범위와 그 근거

④ 삼성전자를 살 이유 vs 팔 이유 각 3가지씩"""

Q4 = """미국-중국 반도체 패권 경쟁을 한국 투자자 관점에서 설명해줘.
겁먹게 하는 헤드라인 말고, 실제로 한국 기업에 기회인지 위협인지.

① 미국 대중 반도체 수출규제 — 지금까지 뭘 막았고 한국에 어떤 영향인가

② 중국 CXMT의 DRAM 진입
   - 실제 기술 수준은 어느 정도인가 (삼성·SK 대비 몇 세대 뒤인지)
   - 한국 기업에 언제부터 위협이 될 수 있는가
   - 위협이 안 되는 이유도 있다면 함께

③ 미중 경쟁이 한국에 주는 기회
   - 중국 반도체 제재 → 한국으로 수요 이동한 품목
   - AI 인프라 수요에서 한국이 독점적 위치를 가진 이유

④ 향후 6~12개월 미중 반도체 이슈 타임라인
   | 시기 | 예상 이벤트 | 한국 주가 영향 |"""

Q5 = """삼성전자·SK하이닉스 말고,
반도체 소재·부품·장비(소부장) 종목 중 지금 진짜 수혜받고 있는 곳을 정리해줘.

① 지금 한국 반도체 소부장에서 실제로 돈이 되고 있는 분야
   - 수출 데이터로 확인되는 것 (어떤 소재가 판가/물량 급증 중인지)

② 분야별 수혜 종목 테이블
   | 분야 | 종목명 | 코드 | 왜 수혜인가 | 수혜 등급 |
   분야: 식각소재 / 세정소재 / 전공정장비 / 후공정OSAT / 기판소재 / 테스트장비

③ 대형주 대비 소부장의 주가 타이밍
   - 대형주 먼저 가고 소부장이 뒤따르는가
   - 아니면 동시인가 / 소부장이 선행하는 경우는 언제인가

④ 지금 소부장 중 아직 덜 오른 곳 — 투자자가 놓치고 있는 종목 있으면"""

Q6 = """앞으로 6개월~1년 안에 반도체 섹터 주가에 영향을 줄 이벤트·재료를 총정리해줘.
이미 알려진 것 + 아직 잘 모르는 것 모두.

① 확정된 일정 타임라인
   | 날짜 | 이벤트 | 수혜 종목 | 영향 강도 |
   (COMPUTEX, 실적 발표, 정책 발표, 수주 기대 시점 등)

② 아직 불확실하지만 터지면 큰 것들
   - 어떤 조건이 충족될 때 폭발하는가
   - 확인 방법은 무엇인가

③ 시장이 간과하고 있는 미래 재료
   - 헤드라인에 안 나오지만 6개월 후 중요해질 것

④ 반도체 섹터 상승을 막을 수 있는 리스크 타임라인
   | 시기 | 리스크 | 발생 시 영향 |"""

Q7 = """지금까지 얘기한 내용을 하나의 스토리로 종합해줘.
누군가에게 "지금 반도체 섹터 왜 이래?"를 설명할 때 쓸 수 있는 버전으로.

① 반도체 섹터 전체 스토리 — 3단 구조로
   - 배경: 여기까지 어떻게 왔는가 (2~3줄)
   - 현재: 지금 무슨 일이 벌어지고 있는가 (3~4줄)
   - 앞으로: 어디로 가는가 (2~3줄)

② 종목별 포지션 맵
   | 종목명 | 코드 | 지금 상황 | 핵심 재료 | 리스크 |
   (대형주 → 중형주 → 소부장 순서로)

③ 유튜브 영상 주제 — 일반 시청자가 "이거 몰랐는데?" 할 만한 것 5개
   각 주제마다: 제목 후보 + 핵심 메시지 한 줄

④ 마지막으로 — 지금 이 섹터에서 가장 과소평가된 종목/이슈는 무엇인가"""

QUESTIONS = [
    ("Q1", "반도체 섹터 전체 그림", Q1),
    ("Q2", "HBM 게임체인저", Q2),
    ("Q3", "삼성전자 스토리", Q3),
    ("Q4", "미중 패권 전쟁", Q4),
    ("Q5", "소부장 밸류체인", Q5),
    ("Q6", "미래 재료 총정리", Q6),
    ("Q7", "전체 스토리 종합", Q7),
]

# ─── 실행 ──────────────────────────────────────────────────────────────────────

print(f"{'='*60}")
print(f"  반도체 섹터 Q1~Q7 학습 세션 시작")
print(f"  기준일: {TODAY}")
print(f"  모델: gemini-3-flash-preview")
print(f"{'='*60}\n")

client = genai.Client(api_key=API_KEY)

# 채팅 세션 생성 (컨텍스트 유지)
chat = client.chats.create(
    model='gemini-3-flash-preview',
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.3,
    )
)

# 결과 저장 딕셔너리
results = {}

# 오프닝 메시지
print(f"[시스템 셋업] 역할 설정 중...")
opening_resp = chat.send_message(OPENING)
print(f"✅ 시스템 셋업 완료\n")
time.sleep(2)

# Q1~Q7 순서대로 전송
for qnum, qtitle, qtext in QUESTIONS:
    print(f"{'─'*60}")
    print(f"  {qnum} / {qtitle}")
    print(f"{'─'*60}")
    print(f"  전송 중...")

    try:
        resp = chat.send_message(qtext)
        answer = resp.text
        results[qnum] = {
            "title": qtitle,
            "question": qtext,
            "answer": answer
        }
        # 앞 200자만 미리보기
        preview = answer.replace('\n', ' ')[:200]
        print(f"  ✅ 수신 완료 ({len(answer)}자)")
        print(f"  미리보기: {preview}...")
        print()
        time.sleep(3)  # API 요청 간격

    except Exception as e:
        print(f"  ❌ 오류: {e}")
        results[qnum] = {"title": qtitle, "question": qtext, "answer": f"[오류: {e}]"}
        time.sleep(5)

# ─── 결과 저장 ───────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  Q1~Q7 완료. 결과 파일 저장 중...")
print(f"{'='*60}")

# 1. 원본 Q&A 전체 저장 (raw)
raw_dir = ROOT / 'raw' / 'L5_섹터'
raw_dir.mkdir(parents=True, exist_ok=True)
raw_file = raw_dir / f'{TODAY}_반도체_Q7리서치.md'

raw_content = f"""# 반도체 섹터 Q1~Q7 리서치 ({TODAY})
> Gemini Flash 연속 대화 세션 — 컨텍스트 누적 방식

---

"""
for qnum, data in results.items():
    raw_content += f"""## {qnum} — {data['title']}

**질문:**
{data['question']}

**답변:**
{data['answer']}

---

"""

raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본 저장: {raw_file.name}")

# 2. wiki sector_반도체.md 업데이트
sector_dir  = ROOT / 'wiki' / 'L5_섹터' / '반도체'
sector_file = sector_dir / 'sector_반도체.md'

sector_dir.mkdir(parents=True, exist_ok=True)

# Q7 종합 스토리를 메인 섹션으로, 나머지는 심층 분석 섹션으로
q7_answer  = results.get('Q7', {}).get('answer', '')
q1_answer  = results.get('Q1', {}).get('answer', '')
q2_answer  = results.get('Q2', {}).get('answer', '')
q3_answer  = results.get('Q3', {}).get('answer', '')
q4_answer  = results.get('Q4', {}).get('answer', '')
q5_answer  = results.get('Q5', {}).get('answer', '')
q6_answer  = results.get('Q6', {}).get('answer', '')

sector_content = f"""# 반도체 섹터 — 현재 상태

## 오늘의 한줄 ({TODAY} 업데이트)
> Gemini Q7 리서치 기반 — 전체 스토리 종합에서 추출

---

## 🔬 섹터 딥리서치 Q1~Q7 ({TODAY})
> Gemini Flash 연속 대화 세션 (컨텍스트 누적 방식)
> 원본 전체: `raw/L5_섹터/{TODAY}_반도체_Q7리서치.md`

---

### Q1 — 반도체 섹터 전체 그림

{q1_answer}

---

### Q2 — HBM이 왜 게임체인저인가

{q2_answer}

---

### Q3 — 삼성전자 스토리 (파운드리 + 메모리)

{q3_answer}

---

### Q4 — 미중 패권 전쟁이 한국에 미치는 영향

{q4_answer}

---

### Q5 — 소부장 밸류체인

{q5_answer}

---

### Q6 — 미래 재료 총정리

{q6_answer}

---

### Q7 — 전체 스토리 종합 + 콘텐츠 소재

{q7_answer}

---

## 📰 이벤트 히스토리
- {TODAY}: Q1~Q7 딥리서치 완료 (Gemini Flash 연속 대화)

## 💡 콘텐츠 기회
(Q7 유튜브 주제 참조)

## 관련 파일
- [[스토리보드_반도체]] — 마스터 내러티브
- [[반도체index]] — 일일 업데이트 데이터
"""

sector_file.write_text(sector_content, encoding='utf-8')
print(f"✅ 위키 저장: wiki/L5_섹터/반도체/sector_반도체.md")

# 3. log.md 기록
log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    log_entry = f'- {TODAY} — 반도체 섹터 Q1~Q7 딥리서치 완료 (Gemini Flash 연속 대화, {len(results)}개 질문)\n'
    # 맨 앞에 삽입
    log_file.write_text(log_entry + log, encoding='utf-8')

print(f"✅ log.md 기록 완료")

print(f"\n{'='*60}")
print(f"  🎉 완료!")
print(f"  원본: raw/L5_섹터/{TODAY}_반도체_Q7리서치.md")
print(f"  위키: wiki/L5_섹터/반도체/sector_반도체.md")
print(f"{'='*60}")
