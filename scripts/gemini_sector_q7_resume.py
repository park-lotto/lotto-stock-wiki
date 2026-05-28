"""
반도체 Q4~Q7 재실행 스크립트
- Q1~Q3 기존 저장 파일 읽기
- Q4~Q7을 독립 API 호출로 실행 (chat 세션 아님 = 입력 토큰 초과 방지)
- 각 Q마다 이전 답변 요약 500자를 컨텍스트로 첨부
- 429 에러 시 retry_delay 파싱 후 자동 대기 재시도
사용: python scripts/gemini_sector_q7_resume.py
"""
import sys, os, re, time, json
from datetime import date
from pathlib import Path
from google import genai
from google.genai import types
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT   = Path(__file__).parent.parent
ENV    = ROOT / '.env'
TODAY  = date.today().strftime('%Y-%m-%d')
SECTOR = '반도체'

# .env 로드
env = {}
for line in ENV.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

API_KEY = env.get('GEMINI_API_KEY', '')
if not API_KEY:
    print('❌ GEMINI_API_KEY 없음'); sys.exit(1)

client = genai.Client(api_key=API_KEY)

# ─── Q4~Q7 프롬프트 ───────────────────────────────────────────────────────────

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

REMAINING = [
    ("Q4", "미중 패권 전쟁", Q4),
    ("Q5", "소부장 밸류체인", Q5),
    ("Q6", "미래 재료 총정리", Q6),
    ("Q7", "전체 스토리 종합", Q7),
]

# ─── 기존 Q1~Q3 결과 읽기 ───────────────────────────────────────────────────

raw_file = ROOT / 'raw' / 'L5_섹터' / f'{TODAY}_반도체_Q7리서치.md'

existing_summaries = {}
if raw_file.exists():
    raw_text = raw_file.read_text(encoding='utf-8')
    # Q1~Q3 답변 추출 (첫 800자만 요약으로 사용)
    for qn in ['Q1', 'Q2', 'Q3']:
        pattern = rf'## {qn} — .*?\n\n\*\*질문:\*\*.*?\n\*\*답변:\*\*\n(.*?)(?=\n---\n|\Z)'
        m = re.search(pattern, raw_text, re.DOTALL)
        if m:
            answer_text = m.group(1).strip()
            existing_summaries[qn] = answer_text[:800]  # 800자 요약
    print(f"✅ 기존 Q1~Q3 답변 로드 (Q1:{len(existing_summaries.get('Q1',''))}자, Q2:{len(existing_summaries.get('Q2',''))}자, Q3:{len(existing_summaries.get('Q3',''))}자)")
else:
    print(f"⚠️ 기존 파일 없음: {raw_file.name}")
    print("  Q4~Q7을 컨텍스트 없이 독립 실행합니다.")

# ─── 독립 호출 함수 (retry 포함) ─────────────────────────────────────────────

def extract_retry_seconds(error_msg: str) -> float:
    """오류 메시지에서 retryDelay 초 추출"""
    m = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", str(error_msg))
    if m:
        return float(m.group(1)) + 5  # 여유 5초 추가
    return 65.0  # 기본값 65초

def call_gemini_independent(qnum: str, qtitle: str, qtext: str,
                             context_summaries: dict) -> str:
    """독립 API 호출 — 이전 답변 요약 첨부 (chat 세션 아님)"""

    # 컨텍스트 구성: 이전 Q&A 요약 (각 800자 이하)
    context_block = ""
    if context_summaries:
        context_block = f"오늘 날짜는 {TODAY}이야.\n"
        context_block += "너는 한국 주식시장 반도체 섹터 전문 애널리스트야.\n"
        context_block += "이전 질문들에서 아래 내용을 이미 논의했어 (요약):\n\n"
        for qn in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6']:
            if qn in context_summaries:
                context_block += f"[{qn} 요약] {context_summaries[qn][:600]}\n\n"
        context_block += "---\n이걸 배경으로 다음 질문에 답해줘:\n\n"

    full_prompt = context_block + qtext

    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                )
            )
            return response.text

        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'RESOURCE_EXHAUSTED' in err_str:
                wait_secs = extract_retry_seconds(err_str)
                print(f"  ⏳ 429 Rate Limit — {wait_secs:.0f}초 대기 후 재시도 (시도 {attempt+1}/{max_retries})")
                time.sleep(wait_secs)
                continue
            else:
                print(f"  ❌ 오류: {e}")
                return f"[오류: {e}]"

    return "[오류: 최대 재시도 초과]"

# ─── 실행 ──────────────────────────────────────────────────────────────────────

print(f"{'='*60}")
print(f"  반도체 Q4~Q7 재실행 (독립 호출 방식)")
print(f"  기준일: {TODAY}")
print(f"{'='*60}\n")

new_results = {}
all_summaries = dict(existing_summaries)  # Q1~Q3 요약 포함

for qnum, qtitle, qtext in REMAINING:
    print(f"{'─'*60}")
    print(f"  {qnum} / {qtitle}")
    print(f"{'─'*60}")
    print(f"  컨텍스트: 이전 {len(all_summaries)}개 Q 요약 첨부")
    print(f"  전송 중...")

    answer = call_gemini_independent(qnum, qtitle, qtext, all_summaries)

    if not answer.startswith('[오류'):
        new_results[qnum] = {"title": qtitle, "question": qtext, "answer": answer}
        # 이 Q의 요약도 다음 Q에 사용
        all_summaries[qnum] = answer[:600]
        preview = answer.replace('\n', ' ')[:200]
        print(f"  ✅ 수신 완료 ({len(answer)}자)")
        print(f"  미리보기: {preview}...")
    else:
        new_results[qnum] = {"title": qtitle, "question": qtext, "answer": answer}
        print(f"  ❌ 실패: {answer}")

    print()
    time.sleep(5)  # 요청 간 간격

# ─── 결과 파일 업데이트 ─────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  저장 중...")
print(f"{'='*60}")

# 1. 원본 파일에 Q4~Q7 추가
if raw_file.exists():
    raw_content = raw_file.read_text(encoding='utf-8')
else:
    raw_content = f"# 반도체 섹터 Q1~Q7 리서치 ({TODAY})\n> Gemini Flash 연속 대화 세션\n\n---\n\n"

for qnum, data in new_results.items():
    block = f"""## {qnum} — {data['title']}

**질문:**
{data['question']}

**답변:**
{data['answer']}

---

"""
    if f"## {qnum} —" in raw_content:
        # 기존 섹션 교체
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

# 2. sector_반도체.md 전체 재구성
sector_file = ROOT / 'wiki' / 'L5_섹터' / '반도체' / 'sector_반도체.md'
if sector_file.exists():
    existing_sector = sector_file.read_text(encoding='utf-8')
else:
    existing_sector = f'# 반도체 섹터 — 현재 상태\n\n'

# Q4~Q7 섹션 추가/교체
for qnum, data in new_results.items():
    title_map = {
        'Q4': '미국-중국 패권 전쟁이 한국에 미치는 영향',
        'Q5': '소부장 밸류체인',
        'Q6': '미래 재료 총정리',
        'Q7': '전체 스토리 종합 + 콘텐츠 소재',
    }
    section_title = title_map.get(qnum, data['title'])
    new_section = f"\n### {qnum} — {section_title}\n\n{data['answer']}\n\n---\n"

    if f"### {qnum} —" in existing_sector:
        existing_sector = re.sub(
            rf'### {qnum} —.*?(?=\n### |\Z)',
            new_section.strip() + '\n',
            existing_sector,
            flags=re.DOTALL
        )
    else:
        existing_sector += new_section

sector_file.write_text(existing_sector, encoding='utf-8')
print(f"✅ 위키 업데이트: sector_반도체.md")

# 3. log.md 기록
log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q, d in new_results.items() if not d['answer'].startswith('[오류')]
    failed    = [q for q, d in new_results.items() if d['answer'].startswith('[오류')]
    entry = f"- {TODAY} — 반도체 Q4~Q7 재실행 완료: 성공 {completed} / 실패 {failed}\n"
    log_file.write_text(entry + log, encoding='utf-8')

print(f"✅ log.md 기록 완료")

print(f"\n{'='*60}")
completed_list = [q for q, d in new_results.items() if not d['answer'].startswith('[오류')]
print(f"  완료: {completed_list}")
print(f"  원본: raw/L5_섹터/{TODAY}_반도체_Q7리서치.md")
print(f"  위키: wiki/L5_섹터/반도체/sector_반도체.md")
print(f"{'='*60}")
