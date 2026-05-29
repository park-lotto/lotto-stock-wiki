"""
로봇·피지컬AI 섹터 Q5~Q10 재실행 스크립트
- Q1~Q4 기존 저장 파일 읽기
- Q5~Q10을 독립 API 호출로 실행 (chat 세션 아님 = 입력 토큰 초과 방지)
- 각 Q마다 이전 답변 요약 600자를 컨텍스트로 첨부
- 429 에러 시 retry_delay 파싱 후 자동 대기 재시도
사용: python scripts/gemini_robot_q5to10_resume.py
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

# ── Q5~Q10 프롬프트 ──────────────────────────────────────────────────────────

Q5 = """협동로봇·물류로봇·의료로봇 — 응용 분야별 실제 수요.

① 협동로봇(코봇) 시장
   - 글로벌 코봇 시장 성장률 (수치)
   - 두산로보틱스·레인보우 vs 유니버설로봇·FANUC
   - 한국 내 실제 코봇 수요처 TOP3 산업
   - 지금 코봇에서 진짜 돈 버는 회사가 국내에 있는가

② 물류로봇·AMR 시장
   - 현대무벡스(204490) — AGV에서 AMR로 전환 현황
   - 이커머스 물류센터 자동화 실제 수주 규모
   - 국내 AMR에서 경쟁력 있는 기업 (씨메스·유진로봇 포함)
   - 쿠팡·SSG·마켓컬리 물류센터 자동화 — 어느 로봇 기업이 수혜인가

③ 의료·재활로봇
   - 큐렉소(060280) — 수술로봇 실제 매출 현황과 성장 가능성
   - 엔젤로보틱스(476080) — 재활로봇 수가 인정 현황
   - 고영(098460) — 수술로봇 시장에서의 포지션
   - 의료로봇이 일반 산업로봇보다 마진이 높은 이유

④ 응용 분야별 수혜 강도 테이블
   | 분야 | 대표 종목 | 코드 | 2026년 기준 시장 규모 | 성장률 | 수혜 강도 |"""

Q6 = """미중 로봇 패권 경쟁 — 한국 투자자 관점으로.

① 중국 로봇 기업의 실제 수준
   - 유비테크(UBTECH)·Unitree·화웨이 로봇 — 기술 수준 현재 어디인가
   - 중국 휴머노이드 로봇 — 한국·일본 대비 몇 년 뒤 or 어디가 앞서는가
   - 감속기·액추에이터에서 중국의 자체 개발 현황

② 중국이 한국에 위협인가, 기회인가
   - 한국 기업이 중국에 팔 수 있는가 vs 중국이 한국 시장을 잠식하는가
   - 일본 감속기(나부테스코) 대체가 한국 기회인가, 중국 기회인가

③ 미국 정책 — 로봇 섹터에서의 미중 분리
   - AI 규제·수출통제가 로봇 AI에도 적용되는가
   - 미국 제조업 리쇼어링과 로봇 수요 — 한국 수혜 가능성

④ 앞으로 6~12개월 로봇 섹터 이벤트 타임라인
   | 날짜 | 이벤트 | 수혜 종목 | 영향 강도 |
   (테슬라 이벤트 / 엔비디아 이벤트 / 현대차 발표 / 중국 이벤트 포함)

⑤ 상승을 막을 리스크 TOP3
   | 리스크 | 발생 조건 | 발생 시 영향 종목 |"""

Q7 = """지금까지 얘기한 내용을 하나의 스토리로 종합.

① 로봇·피지컬AI 섹터 전체 스토리 — 3단 구조
   배경 / 현재 / 앞으로

② 종목별 포지션 맵
   | 종목명 | 코드 | 지금 상황 | 핵심 재료 | 리스크 |
   (완성로봇 대형주 → 부품 중형주 → 응용 분야별)

③ 서브섹터별 현재 온도
   | 서브섹터 | 현재 온도 | 이유 | 대표 종목 |
   (완성로봇 / 감속기 / 액추에이터 / 협동로봇 / 물류로봇 / 의료로봇 / AI두뇌)

④ 유튜브 영상 주제 — "이거 몰랐는데?" 할 만한 것 5개
   각 주제: 제목 후보 + 핵심 메시지 한 줄

⑤ 지금 이 섹터에서 가장 과소평가된 종목/이슈"""

Q8 = """어떤 뉴스가 나오면 어떤 종목이 어떻게 반응했는지 정리해줘.
과거 6개월 실제 케이스 기반으로.

① 뉴스 유형별 주가 반응 패턴 테이블
   | 뉴스 유형 | 1차 반응 종목 | 2차 반응 종목 | 반응 강도 | 시차 | 실제 사례 날짜 |

   아래 유형 전부 커버:
   - 테슬라 옵티머스 양산 목표 공식 발표
   - 테슬라 AI Day / 로봇 데모 영상 공개
   - 현대차 보스턴다이나믹스 대규모 수주 뉴스
   - 현대차 레인보우로보틱스 추가 지분 취득
   - 엔비디아 GR00T/Isaac 신규 파트너 발표
   - 두산로보틱스 해외 대형 수주 공시
   - 에스비비테크 감속기 납품처 확정 공시
   - ABB·FANUC 로봇 수요 가이던스 상향
   - 정부 스마트팩토리·로봇 보급 정책 발표
   - 중국 로봇 기업 한국 시장 진출 뉴스

② 뉴스가 나왔는데 무반응이었던 케이스
   "로봇 섹터니까 다 오르겠지" 착각 — 실제로 안 움직인 것들
   | 뉴스 | 왜 안 움직였나 |

③ 지금 당장 나오면 섹터 전체가 폭발할 뉴스 유형 TOP3
   각각 어떤 종목부터 어떤 순서로 뜨는가"""

Q9 = """지금 이 시점 한국 로봇 섹터에서 가장 강한 종목들.
단순히 "많이 올랐다"가 아니라 왜 이 종목이 지금 주도주인가 — 수급+펀더멘털+이슈 삼중으로.

① 현재 주도주 TOP5
   | 종목 | 코드 | 왜 지금 주도주인가 | 핵심 근거 | 언제까지 | 이걸 확인할 지표 |

② 에스비비테크(389500) 지금 상황
   - 감속기 국산화 어디까지 왔나, 실제 납품처
   - 지금 TP 컨센서스와 증권사 의견

③ 레인보우로보틱스(277810) vs 두산로보틱스(454910)
   - 어느 쪽이 더 강한 모멘텀인가, 왜
   - 밸류에이션 비교 — 어느 쪽이 더 싼가

④ 대형주 대비 부품주에서 알파를 찾아야 하는 이유
   지금 어디서 수익을 낼 수 있는가

⑤ 외국인·기관이 지금 가장 많이 담고 있는 로봇주 TOP3
   vs 아직 안 담은 것 중 논리 있는 종목"""

Q10 = """마지막 — 로봇 섹터 내 꼬리에 꼬리를 물고 연쇄 흐름 구조.
A가 뜨면 왜 B가 뜨고, B가 뜨면 왜 C가 뜨는지. 각 연결마다 이유와 시차.

① 테슬라 옵티머스 체인
   테슬라 옵티머스 양산 공식 발표
     → 레인보우로보틱스 — 왜? 시차?
         → 에스비비테크 (감속기) — 왜? 시차?
         → 에스피지 (액추에이터) — 왜? 시차?
         → 뷰웍스 (로봇 비전) — 왜? 시차?
         → 라온피플 (AI 두뇌) — 왜? 시차?
   각 단계 시차 실제 사례로 검증

② 현대차 로보틱스 체인
   현대차 로봇 사업 대규모 투자 발표
     → 현대로보틱스·현대오토에버 (직계)
         → 현대무벡스 (물류로봇 수주) — 왜?
         → 레인보우로보틱스 (공동개발) — 왜?
         → 에스비비테크·세진티에스 (부품 공급) — 왜?

③ 협동로봇 수출 체인
   두산로보틱스 해외 대형 수주 확정
     → 두산로보틱스 (1차)
         → 로보스타·클로봇 (SI 연동) — 왜?
         → 에스피지 (모터 공급) — 왜?

④ 의료로봇 수가 인정 체인
   엔젤로보틱스 재활로봇 건보 급여화 확정
     → 엔젤로보틱스 → 큐렉소 → 고영 — 각각 왜?

⑤ 연결이 안 되는 오해 케이스
   "로봇 섹터니까 다 같이 올라" 가 틀린 이유
   각 체인에서 연결이 끊기는 지점

⑥ 지금 어느 체인이 가장 활성화돼 있는가
   다음 체인은 무엇이 될 것인가"""

REMAINING = [
    ("Q5",  "협동로봇·물류·의료 응용분야",  Q5),
    ("Q6",  "미중 패권 × 이벤트 타임라인",  Q6),
    ("Q7",  "전체 스토리 종합",             Q7),
    ("Q8",  "뉴스 트리거 × 주가 반응",      Q8),
    ("Q9",  "국내 주도 종목 × 왜 강한가",   Q9),
    ("Q10", "꼬리에 꼬리 연쇄 구조",        Q10),
]

# ── 기존 Q1~Q4 결과 읽기 ─────────────────────────────────────────────────────

raw_file = ROOT / 'raw' / 'L5_섹터' / f'{TODAY}_로봇_Q10리서치.md'

existing_summaries = {}
if raw_file.exists():
    raw_text = raw_file.read_text(encoding='utf-8')
    for qn in ['Q1', 'Q2', 'Q3', 'Q4']:
        pattern = rf'## {qn} — .*?\n\n\*\*질문:\*\*.*?\n\*\*답변:\*\*\n(.*?)(?=\n---\n|\Z)'
        m = re.search(pattern, raw_text, re.DOTALL)
        if m:
            existing_summaries[qn] = m.group(1).strip()[:600]
    print(f"✅ 기존 Q1~Q4 로드: {list(existing_summaries.keys())}")
else:
    print(f"⚠️ 기존 파일 없음 — 컨텍스트 없이 독립 실행")

# ── 독립 호출 함수 (429 자동 대기) ──────────────────────────────────────────

def extract_retry_seconds(error_msg: str) -> float:
    m = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", str(error_msg))
    if m:
        return float(m.group(1)) + 8
    return 70.0

def call_gemini(qnum: str, qtext: str, context: dict) -> str:
    context_block = (
        f"오늘 날짜는 {TODAY}이야.\n"
        "너는 한국 주식시장 로봇·피지컬AI 섹터 전문 애널리스트야.\n"
        "이전 질문들에서 아래 내용을 논의했어 (요약):\n\n"
    )
    for qn in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8', 'Q9']:
        if qn in context:
            context_block += f"[{qn} 요약] {context[qn]}\n\n"
    context_block += "---\n이걸 배경으로 다음 질문에 답해줘:\n\n"

    full_prompt = context_block + qtext

    for attempt in range(5):
        try:
            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
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

# ── 실행 ─────────────────────────────────────────────────────────────────────

print(f"{'='*60}")
print(f"  로봇 Q5~Q10 재실행 (독립 호출 방식)")
print(f"  기준일: {TODAY}")
print(f"{'='*60}\n")

new_results = {}
all_summaries = dict(existing_summaries)

for qnum, qtitle, qtext in REMAINING:
    print(f"{'─'*60}")
    print(f"  {qnum} / {qtitle}")
    print(f"{'─'*60}")
    print(f"  컨텍스트: {list(all_summaries.keys())} 요약 첨부")

    answer = call_gemini(qnum, qtext, all_summaries)

    if not answer.startswith('[오류'):
        new_results[qnum] = {"title": qtitle, "question": qtext, "answer": answer}
        all_summaries[qnum] = answer[:600]
        print(f"  ✅ 완료 ({len(answer)}자)")
        print(f"  미리보기: {answer.replace(chr(10), ' ')[:200]}...")
    else:
        new_results[qnum] = {"title": qtitle, "question": qtext, "answer": answer}
        print(f"  ❌ 실패: {answer}")

    print()
    time.sleep(5)

# ── 저장 ─────────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  저장 중...")
print(f"{'='*60}")

# 1. 원본 파일 업데이트
if raw_file.exists():
    raw_content = raw_file.read_text(encoding='utf-8')
else:
    raw_content = f"# 로봇·피지컬AI 섹터 Q1~Q10 리서치 ({TODAY})\n> Gemini Flash + Google Search\n\n---\n\n"

for qnum, data in new_results.items():
    block = f"## {qnum} — {data['title']}\n\n**질문:**\n{data['question']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
    if f"## {qnum} —" in raw_content:
        raw_content = re.sub(
            rf'## {qnum} —.*?(?=\n## |\Z)',
            block,
            raw_content,
            flags=re.DOTALL
        )
    else:
        raw_content += block

raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본 업데이트: {raw_file.name}")

# 2. sector_로봇.md 업데이트
sector_file = ROOT / 'wiki' / 'L5_섹터' / '로봇' / 'sector_로봇.md'

def get(q):
    return new_results.get(q, {}).get('answer', '[미완료]')

if sector_file.exists():
    sector_content = sector_file.read_text(encoding='utf-8')
else:
    sector_content = f"# 로봇·피지컬AI 섹터 — 현재 상태\n\n"

section_map = {
    'Q5':  ('협동로봇·물류로봇·의료로봇 응용 분야', get('Q5')),
    'Q6':  ('미중 패권 경쟁 × 이벤트 타임라인',    get('Q6')),
    'Q7':  ('전체 스토리 종합 + 콘텐츠 기회',       get('Q7')),
    'Q8':  ('뉴스 트리거 × 주가 반응 패턴',         get('Q8')),
    'Q9':  ('지금 국내 주도 종목 × 왜 강한가',      get('Q9')),
    'Q10': ('꼬리에 꼬리를 물고 (연쇄 구조)',        get('Q10')),
}

for qnum, (title, content) in section_map.items():
    new_section = f"\n### {qnum} — {title}\n\n{content}\n\n---\n"
    if f"### {qnum} —" in sector_content:
        sector_content = re.sub(
            rf'### {qnum} —.*?(?=\n### |\Z)',
            new_section.strip() + '\n',
            sector_content,
            flags=re.DOTALL
        )
    else:
        sector_content += new_section

sector_file.write_text(sector_content, encoding='utf-8')
print(f"✅ 위키: wiki/L5_섹터/로봇/sector_로봇.md")

# 3. log.md
log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q, d in new_results.items() if not d['answer'].startswith('[오류')]
    failed    = [q for q, d in new_results.items() if d['answer'].startswith('[오류')]
    entry = f"- {TODAY} — 로봇 Q5~Q10 재실행: 성공 {completed} / 실패 {failed}\n"
    log_file.write_text(entry + log, encoding='utf-8')
print(f"✅ log.md 기록")

completed_list = [q for q, d in new_results.items() if not d['answer'].startswith('[오류')]
failed_list    = [q for q, d in new_results.items() if d['answer'].startswith('[오류')]

print(f"\n{'='*60}")
print(f"  완료: {completed_list}")
if failed_list:
    print(f"  실패: {failed_list}")
print(f"  원본: raw/L5_섹터/{TODAY}_로봇_Q10리서치.md")
print(f"  위키: wiki/L5_섹터/로봇/sector_로봇.md")
print(f"{'='*60}")
