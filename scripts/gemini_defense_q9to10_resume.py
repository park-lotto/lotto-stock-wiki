"""방산 Q9~Q10 재실행"""
import sys, re, time
from datetime import date
from pathlib import Path
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT  = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gemini_q10_lib as lib

TODAY = date.today().strftime('%Y-%m-%d')
env = lib.load_env(ROOT)
client = lib.get_client(env)

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

PRIOR_Q = ['Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8']

# 기존 Q1~Q8 요약 읽기
raw_file = ROOT / 'raw' / 'L5_섹터' / f'{TODAY}_방산_Q10리서치.md'
summaries = lib.load_prior_summaries(raw_file, PRIOR_Q)
if summaries:
    print(f"✅ Q1~Q8 요약 로드: {list(summaries.keys())}")

def call_gemini(qtext: str, context: dict) -> str:
    ctx = lib.build_context(BASE_CTX, context, PRIOR_Q)
    return lib.call_gemini(client, ctx + qtext, retry_wait_margin=8)

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

# 원본 파일 업데이트 (질문 텍스트는 이미 REMAINING에 있으니 채워서 넘김)
for qnum, qtitle, qtext in REMAINING:
    if qnum in new_results:
        new_results[qnum]["question"] = qtext
lib.update_raw_file(raw_file, new_results, f"# 방산 섹터 Q1~Q10 리서치 ({TODAY})\n\n---\n\n")
print(f"✅ 원본 업데이트")

# sector_방산.md Q9~Q10 추가
sector_file = ROOT / 'wiki' / 'L5_섹터' / '방산' / 'sector_방산.md'
if sector_file.exists():
    titles = {'Q9': '지금 주도 종목 × 왜 강한가', 'Q10': '꼬리에 꼬리 연쇄 구조'}
    lib.update_sector_wiki(sector_file, new_results, titles, f"# 방산 섹터 — 현재 상태\n\n")
    print(f"✅ 위키 업데이트")

completed = [q for q, d in new_results.items() if not d['answer'].startswith('[오류')]
lib.log_completion(ROOT / 'wiki' / 'log.md', f"- {TODAY} — 방산 Q9~Q10 재실행: 성공 {completed}\n")
print(f"✅ log.md 기록\n완료: {list(new_results.keys())}")
