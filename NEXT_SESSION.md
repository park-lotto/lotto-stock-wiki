# NEXT SESSION

날짜: 2026-06-29
PC: 회사PC → Claude Code 재시작 후 이어서

## 세션 요약
NotebookLM MCP 소스 추가 자동화 시도 + 한국어 셀렉터 패치

## 완료 항목
- [x] youtube_ingest.py deeplink 버그 수정 (이전 세션)
- [x] 인사이트 허브 신규 페이지 (이전 세션)
- [x] telegram_ingest.py --force-date 추가 (이전 세션)
- [x] **NotebookLM MCP 한국어 셀렉터 패치** — selectors.js 3곳 수정
  - addButton: "소스 추가" 한국어 추가
  - sourceTypeText: "복사된 텍스트" 한국어 추가
  - insertConfirm: "삽입", "확인" 한국어 추가
  - 패치 파일: `C:\Users\TheRose\AppData\Local\npm-cache\_npx\0d29dd9f4e472da9\node_modules\notebooklm-mcp\dist\notebooklm\selectors.js`
- [x] MCP 재등록 (remove + add)

## 미완료 / 다음 할 것 (우선순위 순)

### 🔴 즉시 (재시작 후 첫 작업)
- [ ] **Claude Code 재시작 필수** → NotebookLM MCP 패치 적용
- [ ] 재시작 후 13개 텔레그램 파일 NotebookLM 소스 추가 (클릭 없이 자동)
  - 노트북: https://notebooklm.google.com/notebook/2630cdd9-812d-4af5-8b94-d8636a3c852c
  - 파일: raw/telegram/2026-06-29_*.md (13개)
  - 순서: add_source(type=text) × 13 → ask_question 교차분석

### 🟡 이어서
- [ ] 텔레그램 오후 재ingest 딸깍 버튼 (server.py /api/telegram/reingest)
- [ ] AI 요약 모델 명시 (doc_summary.py --model claude-sonnet-4-6)
- [ ] 기존 3줄 캐시 요약 일괄 재생성
- [ ] 딸깍 대시보드 장중/마감 버튼
- [ ] 섹터 라벨 불일치 문제 (통신)

## 관련 파일
- `C:\Users\TheRose\AppData\Local\npm-cache\_npx\0d29dd9f4e472da9\node_modules\notebooklm-mcp\dist\notebooklm\selectors.js` — 패치됨
- raw/telegram/2026-06-29_*.md — 13개 텔레파일 (로딩 대기 중)
- dashboard/server.py — FastAPI :8090
- pipeline/atoms/telegram_ingest.py — --force-date 추가됨

## 서버 실행
```
cd "c:\Users\TheRose\Desktop\로또의 주식"
uvicorn dashboard.server:app --port 8090 --reload
```
→ http://localhost:8090/insights

## NotebookLM MCP 문제 배경
- 원인: 한국어 UI에서 버튼 텍스트("소스 추가", "복사된 텍스트")가 MCP 셀렉터 목록 미포함
- MCP 버전: 2.0.0 (최신) — 버전 문제 아님
- 해결: selectors.js 직접 패치 → Claude Code 재시작으로 적용
- 주의: npx 캐시 디렉토리가 변경되면 패치가 초기화될 수 있음
