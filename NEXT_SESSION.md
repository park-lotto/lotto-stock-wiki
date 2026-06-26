# NEXT_SESSION — 2026-06-26 (회사PC) — 2차 갱신

## 세션 요약
삼프로TV 크롤러(@3protv) 구축 + 마켓 인사이드 영상 리포트 제작

## ✅ 완료
- `scripts/3pro_crawl.py` — 3시간 크롤러 (상태: `pipeline/3pro_state.json`)
- `scripts/3pro_corner_test.py` — 8코너 개별 테스트 스크립트
- `scripts/3pro_storyboard.py` — VTT → 구어체 스토리보드 변환
- Windows Task Scheduler 등록 (`C:\Users\TheRose\AppData\Local\lotto_3pro_crawl.bat`)
- 마켓 인사이드 영상 3종 결과물:
  - `wiki/insights/3pro/SB_마켓인사이드_반도체독주조심.md` — 518블록 구어체 전문
  - `wiki/insights/3pro/SB_요약_마켓인사이드_반도체독주조심.md` — 6씬 요약 마크다운
  - `out/report_마켓인사이드_반도체독주조심.html` — 다크테마 리포트
  - `out/report_마켓인사이드_easy.html` — 라이트 경량 리포트 ✅ 최종 완성 포맷
- 코너별 완료: 아침N투자 ✅ / 클로징벨 ✅ / 마켓 인사이드 ✅

## ❌ 미완료 (집에서 이어서)

### 1. 나머지 5코너 Gemini 분석 미완료
- 여의도 인사이트 / 크립토 PLUS / 뉴스3 / 월가 뉴스레터 / 주린이 구조대
- **원인**: Gemini 무료 티어 20개/일 한도 초과 (KEY_2 소진)
- **해결**: `.env`에 `GEMINI_API_KEY_3=새키값` 추가 후 `python scripts/3pro_corner_test.py` 실행
- 현재 `.env` 상태:
  ```
  GEMINI_API_KEY=... (429 초과)
  GEMINI_API_KEY_2=... (한도 초과)
  GEMINI_API_KEY_3=     ← 여기에 새 키 넣으면 됨
  ```

### 2. 리포트 HTML 포맷 → 다른 코너에도 적용
- `out/report_마켓인사이드_easy.html` 이 완성 포맷 (라이트·경량)
- 다른 코너 분석 완료 후 동일 포맷으로 HTML 리포트 생성 필요

### 3. 딸깍 대시보드 미결 (이전 세션)
- 섹터 라벨 정합성 문제: 통신 A진입했으나 미장·소르티노·빈집 라벨 불일치
- 신호잡 6/22 이후 4일 멈춤 → 수동 복구 필요
- 장중 2단계 (한투 API 연결) 미착수

## 관련 파일
- `scripts/3pro_crawl.py` — 메인 크롤러
- `scripts/3pro_corner_test.py` — 코너 테스트 (GEMINI_API_KEY_3 읽음)
- `pipeline/3pro_state.json` — 처리된 영상 ID 목록
- `.env` — API 키 (KEY_3 추가 필요)
- `out/report_마켓인사이드_easy.html` — 완성 리포트 템플릿
