---
name: project-news-matching
description: 대시보드 뉴스 매칭 시스템(섹터/종목 뉴스 자동). 도구·오매칭방지·튜닝법
metadata: 
  node_type: memory
  type: project
  originSessionId: 81939269-3373-415b-b526-da1912c9f8ff
---

# 뉴스 매칭 시스템 (2026-07-01)

**Why:** 유튜브 영상서 보여주고 멤버십 회원이 쓰는 대시보드. "강한섹터 → 빈집종목 → 왜(뉴스)" 스토리.

## 도구 (검증 완료, Playwright 불필요)
- **섹터 뉴스** = 네이버 검색API (`scripts/news_feed.py` `_search`, 키 NAVER_CLIENT_ID/SECRET)
- **종목 뉴스** = 네이버 증권 종목뉴스API `m.stock.naver.com/api/news/stock/{code}` (큐레이션·관련뉴스그룹·**키 불필요**, ETF구성종목과 같은 호스트)
- (미도입) opendart 공시 = 사실 보강

## 오매칭 방지 (핵심 교훈)
호재키워드 개수로만 정렬하면 딴 섹터 기사가 1등 됨(화장품에 반도체 섞임).
→ **must 필수어를 제목에 반드시 포함**해야 통과. `pipeline/sector_news_keywords.json`에 섹터별 `q`(검색어)+`must`(필수어) 정의. 튜닝=이 파일만 수정. + NOISE(정치·날씨) 컷.

## 신선도 개선 (2026-07-02) — 퍼플렉시티 불필요
증상: 자동차 섹터가 어제 뉴스 2개만. 원인=`q`="자동차 관련주" 약한쿼리→Naver가 일반시황만 반환(must필터에 다 걸림). **조치**: `sector_news`가 q 외에 **must[1:]의 구체 종목명 2개로 보조쿼리**("현대차 기아")도 검색·병합→오늘자 섹터기사 확보. top 2→3. 전 섹터 07/02 최신뉴스 확인. 종목뉴스(Naver증권 API)는 원래 매우 신선(분단위)이라 대안으로도 좋음. 뉴스 소스 자체는 멀쩡, 쿼리 문제였음.

## 구조
- 백그라운드 스레드 20분(server.py `_news_loop`) → `_NEWS_FEED` + `pipeline/news_feed.json`(gitignore)
- `/api/news_feed`(탭용), `/api/sector_detail?etf=|codes=`(팝오버용: 섹터뉴스+종목빈집osc+종목뉴스)
- 프론트: 📰뉴스탭(loadNewsTab) + openSectorDetail 팝오버(ETF칩·히트맵타일 공용). 종목뉴스 클릭펼침
- 커스텀 히트맵타일(에너지전선 등)은 ETF매핑 안 돼 섹터뉴스 X, 종목뉴스+빈집만 O

## AI 뉴스 요약 (2026-07-02)
섹터 팝업 상단에 Gemini 요약카드. `/api/sector_summary?etf=|codes=`: 섹터뉴스+상위5종목 종목뉴스 헤드라인(~13건)→`_gemini_text`(gemini-3-flash-preview)로 "🔑한줄+📌핵심이슈2~3+👀관전포인트" 생성(양면론·추천 금지, 팩트만). 15분 캐시. 프론트=팝업에 비동기 로드(뉴스 먼저, 요약 나중), `_mdMini`로 마크다운 렌더, 골드테마 `.ep-summary`. ⚠️서버에 GEMINI_API_KEY·GEMINI_API_KEY_2 추가+`pip install google-genai` 필요(로컬 .env서 복사함). 첫호출 ~24초(gemini-3-flash 느림)나 캐시후 즉시. 개선여지: 상위섹터 백그라운드 프리워밍.

## 관련
[[project_dashboard_deploy]] · 콜아웃(강한섹터×빈집)은 장중기준이라 [[feedback_market_smell]] 취지의 "장전 예측"으로 재설계 필요(기준봉 축적 보류중)
EOF
