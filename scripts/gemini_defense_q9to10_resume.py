"""방산 Q9~Q10 재실행"""
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
client  = genai.Client(api_key=API_KEY)

BASE_CTX = f"""오늘 날짜는 {TODAY}이야.
너는 한국 주식시장 방산 섹터 전문 애널리스트야.
답변 규칙: 한국 상장사 기준 / 종목코드 포함 / 수치·날짜 포함 / 모르면 미확인 / 테이블 위주 / 간결하게
Google 검색으로 최신 정보 확인."""

Q9 = """지금 이 시점 방산 섹터에서 가장 강한 종목들.
수급 + 펀더멘털 + 이슈 삼중으로.

① 현재 주도주 TOP5
   | 종목 | 코드 | 왜 지금 주도주인가 | 핵심 근거 | 언제까지 | 확인 지표 |

② 한화에어로스페이스 vs LIG넥스원 vs KAI
   - 지금 이 세 종목 중 모멘텀 가장 강한 곳
   - 밸류에이션 비교 (PBR·PSR 기준)

③ 현대로템이 방산주로 재평가받는 이유
   - 철도 비중 vs 방산 비중 현재 구도
   - 수주잔고 대비 주가 평가

④ 소부장 중 지금 가장 강한 종목
   - 풍산·한화·빅텍·퍼스텍 중 어디인가

⑤ 외국인·기관이 지금 가장 많이 담는 방산주 TOP3
   vs 아직 안 담은 것 중 논리 있는 종목"""

Q10 = """방산 섹터 꼬리에 꼬리를 무는 연쇄 구조.

① 폴란드 추가 수주 체인
   폴란드 추가 계약 공시
     → 현대로템 (K2전차) — 즉각
         → 한화에어로스페이스 (K9·항공엔진) — 왜? 시차?
         → 한국항공우주 (FA-50) — 왜? 시차?
         → 풍산 (탄약 파생수요) — 왜? 시차?
         → 한화시스템 (전자장비) — 왜? 시차?

② KF-21 수출 계약 체인
   KF-21 첫 해외 수출 계약
     → 한국항공우주 (직접) — 즉각
         → 한화에어로스페이스 (엔진) / LIG넥스원 (레이더) — 왜?

③ 유도무기 수출 체인
   천궁·현무 대형 수출 계약
     → LIG넥스원 → 한화시스템 → 소부장 — 시차?

④ 우크라이나 종전 체인 (리스크)
   휴전 협상 타결 시
     → 방산주 하락 압력
         → 낙폭 가장 큰 종목 vs 방어되는 종목
         → 우크라이나 재건 수혜 전환 종목

⑤ 연결 끊기는 지점 — 오해 케이스

⑥ 지금 가장 활성화된 체인 + 다음 체인"""

REMAINING = [("Q9", "지금 주도 종목", Q9), ("Q10", "꼬리에 꼬리 연쇄", Q10)]

# 기존 Q1~Q8 요약 읽기
raw_file = ROOT / 'raw' / 'L5_섹터' / f'{TODAY}_방산_Q10리서치.md'
summaries = {}
if raw_file.exists():
    raw_text = raw_file.read_text(encoding='utf-8')
    for qn in ['Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8']:
        m = re.search(rf'## {qn} — .*?\n\n\*\*질문:\*\*.*?\n\*\*답변:\*\*\n(.*?)(?=\n---\n|\Z)', raw_text, re.DOTALL)
        if m:
            summaries[qn] = m.group(1).strip()[:600]
    print(f"✅ Q1~Q8 요약 로드: {list(summaries.keys())}")

def extract_retry_seconds(err: str) -> float:
    m = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", err)
    return float(m.group(1)) + 8 if m else 70.0

def call_gemini(qtext: str, context: dict) -> str:
    ctx = BASE_CTX + "\n\n이전 Q 요약:\n"
    for qn in ['Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8']:
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
                return f"[오류: {e}]"
    return "[오류: 최대 재시도 초과]"

print(f"{'='*60}\n  방산 Q9~Q10 재실행\n{'='*60}\n")

new_results = {}
for qnum, qtitle, qtext in REMAINING:
    print(f"{'─'*60}\n  {qnum} / {qtitle}\n{'─'*60}")
    answer = call_gemini(qtext, summaries)
    new_results[qnum] = {"title": qtitle, "answer": answer}
    if not answer.startswith('[오류'):
        summaries[qnum] = answer[:600]
        print(f"  ✅ 완료 ({len(answer)}자)")
        print(f"  미리보기: {answer.replace(chr(10),' ')[:200]}...\n")
    else:
        print(f"  ❌ 실패: {answer}\n")
    time.sleep(5)

# 원본 파일 업데이트
if raw_file.exists():
    raw_content = raw_file.read_text(encoding='utf-8')
else:
    raw_content = f"# 방산 섹터 Q1~Q10 리서치 ({TODAY})\n\n---\n\n"

for qnum, data in new_results.items():
    block = f"## {qnum} — {data['title']}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
    if f"## {qnum} —" in raw_content:
        raw_content = re.sub(rf'## {qnum} —.*?(?=\n## |\Z)', block, raw_content, flags=re.DOTALL)
    else:
        raw_content += block
raw_file.write_text(raw_content, encoding='utf-8')
print(f"✅ 원본 업데이트")

# sector_방산.md Q9~Q10 추가
sector_file = ROOT / 'wiki' / 'L5_섹터' / '방산' / 'sector_방산.md'
if sector_file.exists():
    sector = sector_file.read_text(encoding='utf-8')
    for qnum, data in new_results.items():
        titles = {'Q9': '지금 주도 종목 × 왜 강한가', 'Q10': '꼬리에 꼬리 연쇄 구조'}
        new_sec = f"\n### {qnum} — {titles[qnum]}\n\n{data['answer']}\n\n---\n"
        if f"### {qnum} —" in sector:
            sector = re.sub(rf'### {qnum} —.*?(?=\n### |\Z)', new_sec.strip()+'\n', sector, flags=re.DOTALL)
        else:
            sector += new_sec
    sector_file.write_text(sector, encoding='utf-8')
    print(f"✅ 위키 업데이트")

log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    completed = [q for q,d in new_results.items() if not d['answer'].startswith('[오류')]
    log_file.write_text(f"- {TODAY} — 방산 Q9~Q10 재실행: 성공 {completed}\n" + log, encoding='utf-8')
print(f"✅ log.md 기록\n완료: {list(new_results.keys())}")
