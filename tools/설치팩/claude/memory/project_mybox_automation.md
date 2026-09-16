---
name: project-mybox-automation
description: 네이버 마이박스 자동 다운로드 + 오실레이터 카드 차트 개발 현황
metadata: 
  node_type: memory
  type: project
  originSessionId: f3032f96-c330-4be3-a5a9-94875f78273b
---

## 완성된 것

### 1. osc_chart2.py — 수급 카드 차트 (완성)
- 프리미엄 금융 카드 스타일, 정사각형 6×6
- 색상: `_BG_NAV="#0A0C1E"`, `_CARD_NAV="#0F1228"` 등 네이비 계열
- INSIGHT_COPY 딕셔너리: 등급×방향 12개 조합 → (헤드라인, 서브타이틀)
- 서브타이틀 색상: BEAR `#FF3030` (빨간색)
- 텔레그램 전송 지원 (`--tg` 플래그)
- 카카오톡 전송: 미완 (토큰 세팅 필요, 이미지 전송 API 추가 필요)

### 2. scripts/download_mybox.mjs — 마이박스 자동 다운로드 (완성)
- puppeteer로 `https://mybox.naver.com/share/list?shareKey=ChSUOIdlgte24uds4mPeCr7bquxYxsdU3c-mlUY1dYsD` 접속
- "공유받은 폴더 전체 내려받기" → 드롭다운 "내려받기" 클릭 → zip 다운로드
- Python으로 zip 압축 해제 → `추정이익 변경(태린이아빠)MMDD.xlsm` 오늘 날짜로 저장
- zip 자동 삭제
- 저장 경로: `raw/매일 엑셀넣을것/`

## 현재 운영 (2026-06-22 갱신)

### scripts/download_daily.py — 3폴더 통합 다운로더 (운영 중, .mjs 대체)
- 3폴더(아메리카노/카페라떼/눈꽃빙수) + 유튜브, playwright 기반, 매일 저녁 자동.
- **URL은 `scripts/mybox_links.json`에 분리** — 키 `ame`/`cafe`/`bingsu`.
- ⚠️ **마이박스 naver.me 주소는 매주 월요일 변경됨.** 월요일마다 사용자가 새 URL 3개 제공 → mybox_links.json의 ame/cafe/bingsu 순서로 교체 + `updated` 날짜 갱신. (ame는 종종 안 바뀜)
- 저장: `raw/매일 엑셀넣을것/{기본명}{MMDD}.{ext}`, 14개 파일.

### 폴더접근 차단 보고 시스템 (2026-06-22 추가)
- `check_access()`: 접속 실패(죽은 링크)·목록 0개(권한 만료)·예외 → `RESULT['blocked']` 기록.
- 다운로드 실패 → `RESULT['failed']`. `_guard()`로 한 폴더 막혀도 나머지 진행.
- `report_problems()`: 문제 있으면 **반드시 텔레그램 보고**("월요일 주소 변경 의심 — 링크 업데이트 필요" 문구), 정상이면 침묵.
- 텔레: `.env`의 BOT_TOKEN/CHAT_ID (stdlib urllib 자체 send_telegram).

**Why:** 주소가 조용히 죽으면 며칠치 데이터 유실 → 즉시 알아채야 함.
**How to apply:** 월요일 URL 교체는 mybox_links.json만 수정. 검증은 `python scripts/download_daily.py` 1회 실행.

관련: [[project_taerini_pipeline]] · 엑셀→신호: ingest_excel.py / build_signal_snapshot.py(계획)
