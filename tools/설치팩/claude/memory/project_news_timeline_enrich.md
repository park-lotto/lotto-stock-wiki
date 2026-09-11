---
name: project_news_timeline_enrich
description: 뉴스이슈/시장상황 타임라인 대개편(2026-07-06). 강한 텔레원문 직접노출+관심종목매칭+중요도=상승기여도. 다음=순환매감지기·공시형 enrich(DART)
metadata: 
  node_type: memory
  type: project
  originSessionId: c68e1198-2af7-44fa-875d-a5d4962ee779
---

대시보드 뉴스 타임라인 개편 (2026-07-06 배포완료, dashboard/market.html·server.py·briefing_collect.py).

**구조**: 타임라인 2개 분리 — 🕐시장상황(turning_points 이벤트) / 📰뉴스이슈(뉴스). 카드 8-up 동일크기, 각자 접기/펼치기.

**뉴스 소스 2겹**:
- `ai_brief` = Gemini가 헤드라인 요약(출처X) → **타임라인선 제외**(신뢰X). "실시간 브리핑" 패널엔 남음.
- `raw_news` = `_surface_strong_news`(server.py)가 뉴스피드에서 **강한 원문 직접노출**: 속보·특징주·확정·수주·계약 키워드 + **관심종목(stock_sector_map) 매칭된 것만** + 거버넌스·인사 제외. 원문+출처뱃지+섹터+종목뱃지.

**핵심 함수/규칙**:
- `_match_stock`: 한글경계+최장매칭(이닉스⊂하이닉스, AI/SK 2자영문 오탐 제거)
- 중복제거: 같은종목=한클러스터(서버) + 클라 종목별 최신1개+"+N더". ai_brief는 최근6개 대비 0.35↑유사시 생성스킵
- **중요도 = 오늘 상승기여도(pct)** — 종목 등락률 점수반영 → 크게오른 종목뉴스 맨앞 🔥중요 고정. (pct는 뉴스피드 섹터상위종목만 있어 대표주 위주)
- date필터: /api/market_briefing이 오늘 date만 반환(어제것 시간만맞아 뜨던 문제 차단)

**다음 세션(설계완료·구현대기)**:
1. **순환매 감지기** ← 사용자 관심. 결론: 화살표맵 불필요. **섹터맵(버킷)+Claude지식+"트리거뉴스+실제급등 둘다" 게이트**. 트리거뉴스↔타섹터급등 매칭+근거서술 (반도체클러스터확정→시멘트 성신양회+16%→"건자재 2차수혜"). [[project_naver_board_sentiment]] cause_hunt(다른세션 미귀속강세)와 상보적.
2. **P1 공시형 enrich**: DART로 `계약금액÷연매출=호재강도` 자동. 기가비스 실데이터 실현확인(opendart MCP: 연매출524억 조회성공, 계약금액은 공시본문 rcept API 1콜 더). 목업 artifact 있음.
3. P2 이벤트형(이벤트캘린더 D-day·시나리오) / P3 여론형(ai_brief 출처링크).

관련: [[reference_deploy_truth_branch_ssh]] [[project_briefing_weather_engine]] [[feedback_briefing_source_citation]]
