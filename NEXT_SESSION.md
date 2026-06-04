# NEXT SESSION

날짜: 2026-06-04 | PC: 사무실PC

## 세션 요약
투경 관리 시스템 완성 + 스케줄 버그 수정 + yt-content-research + crawling_bot_data ingest 파이프라인 설계 착수

---

## ✅ 완료

- pipeline/투경_관리.json 생성 (12종목)
- wiki/rules/투경_관리규칙.md 작성
- scripts/crawl_kind.py 완전 재작성 (관리종목만 표시 + 오늘신규 질문)
- scripts/ingest_excel.py KeyError 2건 수정 (op_2026, op_chg1m)
- scripts/download_daily.py 서브폴더 try/except 추가
- Task Scheduler 5개 python 전체경로로 수정
- yt-content-research STEP 0~6 완료
  - 최종 주제: "반도체만 올랐다, 이제 이 업종이 달린다 — 6월 순환매 핵심"

---

## ⏳ 미완료 — 다음 세션 최우선

### 크롤링봇 ingest 파이프라인 (brainstorming 진행 중, B안 확정)

**소스**: `C:\Users\TheRose\crawling_bot_data\YYYY-MM-DD\`
**구조**: blog / market / news / reports / telegram / youtube

**구현할 컴포넌트 (설계 확정):**

1. `scripts/pdf_summarize.py`
   - reports/*.md 안의 PDF 다운로드 링크 감지
   - PDF 다운로드 → Gemini 2.0 Flash API 요약 → .md에 주입
   - 처리완료 상태 저장 (선행 처리 필수)

2. `scripts/ingest_crawl.py`
   - 파일명 HHMM 기준 시간대 필터 (`--from 07:00 --to 10:00`)
   - `pipeline/crawl_ingest_state.json`으로 중복 방지 (안된것만 ingest)
   - 라우팅: reports→L5섹터별 / news→L5 / telegram→L6수급 / blog→L6종목 / market→L3
   - Haiku 서브에이전트로 저비용 운영

3. `pipeline/crawl_ingest_state.json` — 처리완료 파일 기록

**사용법:**
```bash
python scripts/ingest_crawl.py --from 07:00 --to 10:00
python scripts/ingest_crawl.py --today
python scripts/ingest_crawl.py --date 2026-06-04
```

**다음 세션 순서:**
1. `superpowers:brainstorming` 이어서 → spec 문서 작성 → writing-plans → executing-plans

---

## yt-gemini-pipeline 대기

주제: **"반도체만 올랐다, 이제 이 업종이 달린다 — 6월 순환매 핵심 3종목"**
Gemini 브리프 완성. 다음: yt-gemini-pipeline 스킬 실행
