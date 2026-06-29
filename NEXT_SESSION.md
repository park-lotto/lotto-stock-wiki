# NEXT SESSION

날짜: 2026-06-29
PC: 회사PC → 재부팅 후 이어서

## 세션 요약
크롤링 인사이트 허브 (/insights) 완성 + 텔레그램 오전/오후 2회 ingest 설계 완료

## 완료 항목
- [x] youtube_ingest.py deeplink 버그 수정 (URL 패턴 매칭 + 채널명 fallback)
- [x] 인사이트 허브 신규 페이지 (dashboard/insights.html) — 유튜브/텔레/리포트 카테고리→채널→문서→상세 드릴다운
- [x] doc_summary.py — AI 요약 생성+캐시 (claude -p subprocess, 6~8항목+highlights)
- [x] server.py — 9개 신규 API 라우트 (/api/insights/*), sys.path 수정, doc_title 추출
- [x] 브라우저 뒤로가기 수정 (History API pushState/popstate)
- [x] 딸깍/섹터맵/인사이트 3페이지 네비게이션 연결
- [x] 타임라인 날짜+시간 명시
- [x] telegram_ingest.py — --force-date 옵션 추가 (오전→오후 2회 재ingest 지원)

## 미완료 / 다음 할 것
- [ ] 텔레그램 오후 재ingest 딸깍 버튼 연결 (server.py에 /api/telegram/reingest 엔드포인트)
- [ ] AI 요약 모델 명시 (doc_summary.py에 --model claude-sonnet-4-6 하드코딩 여부 결정)
- [ ] 기존 캐시된 요약(3줄짜리 구버전) 일괄 재생성 — insights 허브에서 각 문서 [🔄 재생성] 클릭
- [ ] 딸깍 대시보드 장중/마감 버튼 (FastAPI:8090 — 현재 장전만 완성)
- [ ] 섹터 라벨 불일치 문제 (통신=광통신 vs KT 빈집)

## 관련 파일
- dashboard/insights.html — 인사이트 허브 SPA
- dashboard/server.py — FastAPI :8090
- pipeline/atoms/doc_summary.py — AI 요약 생성
- pipeline/atoms/telegram_ingest.py — --force-date 추가됨
- pipeline/atoms/youtube_ingest.py — deeplink 버그 수정됨

## 서버 실행
```
cd "c:\Users\TheRose\Desktop\로또의 주식"
uvicorn dashboard.server:app --port 8090 --reload
```
→ http://localhost:8090/insights
