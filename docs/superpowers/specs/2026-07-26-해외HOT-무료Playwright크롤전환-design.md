# 해외HOT 무료 Playwright 크롤 전환 — 설계 (2026-07-26, 사무실서 이어감)

> 선행: `2026-07-26-해외HOT-Apify발굴전환-design.md`(Apify 발굴, 라이브). 이 문서는 그 **발굴 소스를
> 무료 Playwright 크롤로 교체**하는 다음 단계. Apify는 발굴에서 빼고 픽업·렌즈 전용으로만 남긴다.

## 배경 / 결정
- Apify 검색은 1,440건 긁어 39건 남김(~$2.4/배치, 74% 낭비). 사장님 지시: **무료로 채우자, 많이 모을수록 좋다.**
- **실측(2026-07-26, 브라우저)**: 로그인·봇차단 없이 검색크롤 됨 —
  - **TikTok** `/search/video?q=키워드` ✅ (좋아요·제목·작성자·날짜·URL·썸네일)
  - **Instagram** `/explore/tags/태그/`(→/popular/) ✅ **조회수(▷)까지** + 좋아요·제목·작성자
  - **샤오홍슈** `rednote.com/search_result?keyword=&type=video` ✅ (좋아요·제목·작성자·날짜)
  - **도우인** ❌ 로그인 벽(QR/휴대폰) → 사장님 모바일 인증 쿠키 확보 후.
- **비용: Claude 토큰 0 · Apify 0.** 서버 headless Playwright 독립 스크립트라 대화와 무관. 판단도 코드 규칙이라 0.
- PoC 성공: 무료크롤 36건 → 내가 판단 5개 → Apify postURLs로 그 5개만 픽업(=현 픽업 기능). 무료크롤이 픽업/발굴을 대체.

## 목표
**매일 headless 무료 크롤로 6카테고리를 대량 상시 수집.** 신선한(막 올라온=조회수 낮은) 꿀템을 선점.

## 크롤 2모드 (핵심)
1. **해시태그/검색어 발굴 (넓게)** — 카테고리 키워드로 새 영상·새 크리에이터 훑기.
2. **소스채널 마이닝 (깊게)** — 발굴에서 나온 좋은 계정을 **소스채널로 등록** → 그 채널 릴스/영상을 매일 직접 크롤.
   막 올라온 새 영상을 조회수 낮을 때 잡음 = 최상의 선점. (계정 리스트는 JSON, 원클릭/자동 추가)

## 데이터/랭킹
- 크롤 산출 스키마 = build_overseas_items 입력({video_id,url,title,likes,views(있으면),published_at,thumbnail,channel_title,media_platform,duration}).
- 랭킹 = 기존 **참여속도**((좋아요+댓글+수집+공유 또는 조회수)/경과h). 인스타는 조회수 있음, 틱톡/샤오는 좋아요 기반. 재방문 Δ=가속(무료로 확보).
- 깔때기 = 기존 overseas_funnel(숏폼·차단어·안터진상한) + dedup. 전부 코드=토큰0.

## ⚠️ Phase 0 스파이크 (사무실서 제일 먼저 — 전체가 여기 달림)
내 크롤이 된 건 **집=주거용 IP**. **서버=AWS 데이터센터 IP**라 막힐 수 있음(Reddit 전례). 그리고 현 Playwright는
대화형 MCP라, 상시엔 **서버에 Playwright+Chromium 설치** 필요.
- [ ] 서버에 `pip install playwright && playwright install chromium`(의존성 포함).
- [ ] 서버 headless로 TikTok/Instagram/XHS 검색 1건씩 실크롤 → 카드 추출되나 확인.
- [ ] 막히면 **Webshare 프록시(REDDIT_PROXY 재활용)** 경유로 재시도. (Playwright launch(proxy=...))
- [ ] 인스타 **채널 릴스 페이지**(/{user}/reels/)가 로그인 없이 긁히는지도 확인(소스채널 모드용).
- 결과로 "서버 무료크롤 가능/프록시필요/로컬대안" 확정 → 나머지 Phase 진행.

## Phase 1~4
1. **크롤러 모듈** `playwright_crawl.py`: 플랫폼별 검색/채널 URL → 스크롤 → 카드 추출(아래 참고 셀렉터) → 스키마. headless.
2. **파이프라인**: 크롤 → overseas_funnel → build_overseas_items → store. **overseas_hot_jobs의 Apify 수집 경로 OFF**(코드는 남기고 크롤로 교체).
3. **상시 스케줄**: systemd 타이머 **매일**(원하면 6~12h). 누적+가속. 키워드·스크롤깊이 공격적으로.
4. **소스채널**: `overseas_seeds.json`에 seed_accounts(플랫폼별 계정) → 채널 마이닝. 발굴서 좋은 계정 승격 UI.
5. **도우인**: 모바일 인증 쿠키 저장 → 크롤 추가.

## 참고 — 검증된 추출 로직(TikTok, 이미 성공)
`a[href*="/video/"]` 순회 → `@author/video/id` 파싱 → 카드 컨테이너 innerText에서 좋아요/제목.
(인스타는 `/reel/` 링크 + ▷조회수, 샤오는 note 카드. 각 셀렉터는 Phase 1서 확정.)

## 정리 작업
- **현 픽업 5개(Apify분) 삭제 OK**(사장님) → 픽업 카테고리 클리어(픽업 기능=수동 URL+렌즈는 유지).

## 이미 라이브(이번 세션 완료분, 유지)
Apify 발굴전환 · 참여속도 랭킹 · 숏폼/키워드/관련성/도우인썸네일 튜닝 · 🖐픽업(수동URL) · 🔎같은영상(렌즈 trace_url).
