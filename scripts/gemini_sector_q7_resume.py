"""
반도체 Q4~Q7 재실행 스크립트
- Q1~Q3 기존 저장 파일 읽기
- Q4~Q7을 독립 API 호출로 실행 (chat 세션 아님 = 입력 토큰 초과 방지)
- 각 Q마다 이전 답변 요약 500자를 컨텍스트로 첨부
- 429 에러 시 retry_delay 파싱 후 자동 대기 재시도
사용: python scripts/gemini_sector_q7_resume.py
"""
import sys, re, time
from datetime import date
from pathlib import Path
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT   = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gemini_q10_lib as lib

TODAY  = date.today().strftime('%Y-%m-%d')
SECTOR = '반도체'
env = lib.load_env(ROOT)
client = lib.get_client(env)

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
PRIOR_Q = ['Q1', 'Q2', 'Q3']

existing_summaries = lib.load_prior_summaries(raw_file, PRIOR_Q, char_limit=800)
if existing_summaries:
    print(f"✅ 기존 Q1~Q3 답변 로드 (Q1:{len(existing_summaries.get('Q1',''))}자, Q2:{len(existing_summaries.get('Q2',''))}자, Q3:{len(existing_summaries.get('Q3',''))}자)")
else:
    print(f"⚠️ 기존 파일 없음: {raw_file.name}")
    print("  Q4~Q7을 컨텍스트 없이 독립 실행합니다.")

_BASE_CTX = (f"오늘 날짜는 {TODAY}이야.\n너는 한국 주식시장 반도체 섹터 전문 애널리스트야.\n"
             "이전 질문들에서 아래 내용을 이미 논의했어 (요약):")

def call_gemini_independent(qnum: str, qtitle: str, qtext: str,
                             context_summaries: dict) -> str:
    """독립 API 호출 — 이전 답변 요약 첨부 (chat 세션 아님)"""
    if not context_summaries:
        return lib.call_gemini(client, qtext)
    ctx = lib.build_context(_BASE_CTX, context_summaries, ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6'])
    return lib.call_gemini(client, ctx + qtext)

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
lib.update_raw_file(raw_file, new_results,
                     f"# 반도체 섹터 Q1~Q7 리서치 ({TODAY})\n> Gemini Flash 연속 대화 세션\n\n---\n\n")
print(f"✅ 원본 업데이트: {raw_file.name}")

# 2. sector_반도체.md 전체 재구성
sector_file = ROOT / 'wiki' / 'L5_섹터' / '반도체' / 'sector_반도체.md'
title_map = {
    'Q4': '미국-중국 패권 전쟁이 한국에 미치는 영향',
    'Q5': '소부장 밸류체인',
    'Q6': '미래 재료 총정리',
    'Q7': '전체 스토리 종합 + 콘텐츠 소재',
}
lib.update_sector_wiki(sector_file, new_results, title_map, f'# 반도체 섹터 — 현재 상태\n\n')
print(f"✅ 위키 업데이트: sector_반도체.md")

# 3. log.md 기록
completed = [q for q, d in new_results.items() if not d['answer'].startswith('[오류')]
failed    = [q for q, d in new_results.items() if d['answer'].startswith('[오류')]
lib.log_completion(ROOT / 'wiki' / 'log.md',
                    f"- {TODAY} — 반도체 Q4~Q7 재실행 완료: 성공 {completed} / 실패 {failed}\n")
print(f"✅ log.md 기록 완료")

print(f"\n{'='*60}")
completed_list = [q for q, d in new_results.items() if not d['answer'].startswith('[오류')]
print(f"  완료: {completed_list}")
print(f"  원본: raw/L5_섹터/{TODAY}_반도체_Q7리서치.md")
print(f"  위키: wiki/L5_섹터/반도체/sector_반도체.md")
print(f"{'='*60}")
