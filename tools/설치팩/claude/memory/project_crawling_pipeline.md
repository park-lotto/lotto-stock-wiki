---
name: project-crawling-pipeline
description: "crawling_bot_data → wiki ingest 파이프라인 설계 현황 (B안 확정, 구현 대기)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 801d2a90-8ff3-44b3-9b67-b11e11f218ff
---

crawling_bot_data 자동 수집 봇 데이터를 wiki에 ingest하는 파이프라인 설계 확정 (2026-06-04).

**소스**: `C:\Users\TheRose\crawling_bot_data\YYYY-MM-DD\` (매일 자동 수집)
**구조**: blog / market / news / reports / telegram / youtube
**reports 특이사항**: .md 파일 안에 PDF 다운로드 링크 포함 — 실제 내용은 PDF에 있음

**Why:** 기존 ingest_excel.py(태린이 엑셀)와 독립 분리. crawling_bot_data는 텍스트(.md) 중심.

**확정 설계 (B안):**
1. `scripts/pdf_summarize.py` — reports/*.md PDF 링크 감지 → Gemini 2.0 Flash 요약 → .md 주입 (선행 처리)
2. `scripts/ingest_crawl.py` — 시간대 필터(--from/--to HHMM) + crawl_ingest_state.json으로 중복 방지 + wiki 라우팅
3. `pipeline/crawl_ingest_state.json` — 처리완료 파일 기록

**라우팅 규칙:**
- reports/ → 증권사명/키워드 → L5_섹터별
- news/ → 종목/섹터 감지 → L5
- telegram/ → 태린이아빠 → L6_수급/전략
- blog/ → 종목명 감지 → L6_종목
- market/ → L3_한국시장
- youtube/ → raw 저장만

**Haiku 서브에이전트**로 ingest 실행 (저비용).

**How to apply:** 다음 세션 시작 시 brainstorming 이어서 → spec 작성 → writing-plans → executing-plans 순으로 진행.
