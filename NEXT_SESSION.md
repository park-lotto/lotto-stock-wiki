# NEXT SESSION
> 2026-06-06 | 집PC → 회사PC 이어서

## 세션 요약
장전 브리핑 자동화 시스템 전체 구축 완료.  
Task Scheduler 전체 7개 평일(월~금)만 실행으로 변경.  
다음 실행: 6월 8일(월) 07:40~

---

## 완료

- `scripts/briefing/collect.py` — wiki L5_섹터 → Gemini 이슈 3~5개 추출
- `scripts/briefing/bot.py` — 텔레그램 양방향 브리핑 봇 (자유 텍스트 판단, 08:00 타임아웃)
- `scripts/briefing/card_gen.py` — 운영자 판단 담긴 HTML 카드 생성 (FREE/A/B/AUTO 배지)
- `scripts/briefing/publish.py` — Playwright PNG 캡처 → 채널(@stockbrain_lotto) 전송
- `scripts/briefing/run_briefing.bat` — collect→bot→publish 순서 자동 실행
- `pipeline/briefing_state.json` — stage 기반 상태 관리
- `scripts/briefing/assistant_bot.py` — Gemini 어시스턴트 봇 (/s /ask /brief /enhance /wiki)
- Task Scheduler 7개 전부 평일(월~금) 07:40~ 실행으로 변경

---

## 미완료 → 회사PC에서 이어서

### 🔴 assistant_bot.py 상시 실행 Task Scheduler 등록 (최우선)
현재 수동 실행만 됨. 로그인 시 자동 시작되게 등록 필요.
```
태스크명: StockBrain_AssistantBot
실행: C:\Users\CH\Desktop\로또의 주식\scripts\briefing\run_assistant_bot.bat (새로 만들어야 함)
트리거: 로그온 시 / 또는 평일 06:00
```

### 🟡 6월 8일(월) 첫 브리핑 풀플로우 검증
- 07:40 Task Scheduler 자동 실행 확인
- 텔레그램에서 이슈 수신 → 답변 → 카드 생성 → 채널 전송 전 과정 확인

### 🟡 publish.py Playwright chromium 설치 확인
```
.venv\Scripts\playwright.exe install chromium
```

---

## 명령어 정리 (assistant_bot.py)

| 명령어 | 기능 |
|--------|------|
| `/s [검색어]` | Gemini 웹서치 |
| `/ask [질문]` | Gemini 분석 |
| `/brief` | 브리핑 카드 재생성 + 채널 전송 |
| `/enhance [내용]` | 서치 후 브리핑 보강 재생성 |
| `/wiki [검색어]` | 로컬 wiki 검색 |
| 자유 텍스트 | Gemini 자동 답변 |

---

## Task Scheduler 현황 (전체 7개, 평일만)

| 태스크명 | 실행시간 |
|----------|---------|
| StockBrainBriefing | 07:40 |
| LottoStock_Download_0700 | 07:00 |
| LottoStock_Wisereport_0705 | 07:05 |
| LottoStock_Ingest_0730 | 07:30 |
| LottoStock_Download_0900 | 09:00 |
| LottoStock_Wisereport_0905 | 09:05 |
| LottoStock_Ingest_0930 | 09:30 |

---

## 관련 파일

- `scripts/briefing/` — 전체 브리핑 파이프라인
- `pipeline/briefing_state.json` — 상태 파일
- `docs/superpowers/specs/2026-06-06-morning-briefing-design.md` — 설계 스펙
