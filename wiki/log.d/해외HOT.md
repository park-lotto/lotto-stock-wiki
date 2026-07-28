# 해외HOT 작업 로그

- 2026-07-26 (집PC): 해외HOT 발굴 소스를 **레딧 → 틱톡+CN(샤오·도우) Apify**로 전면 전환·라이브 배포.
  무료 probe로 발굴벽 확인 → Apify 결정. 참여속도 랭킹(build_overseas_items, CN 조회수부재 대응) +
  깔때기(overseas_funnel) + CN search_full 2개 + gap_check 번역 + 카드 UI. 라이브 39건·6카테고리 골고루.
- 2026-07-26 (집PC, 이어서): 튜닝 — 숏폼필터·가전키워드 정밀화·관련성 74%복구(허용어폐기 차단어만)·
  도우인썸네일 프록시허용. **🖐픽업**(무료크롤로 고른 틱톡 URL만 Apify postURLs 픽업) + **🔎같은영상**(렌즈 trace_url) 라이브.
- 2026-07-26 (집→사무실): **무료 Playwright 검색크롤 실측 성공** — 틱톡·인스타(조회수까지!)·샤오홍슈 로그인없이 긁힘,
  도우인만 로그인. PoC(무료크롤36→판단5→Apify픽업5) 성공. **다음: 무료크롤 전환**(2모드=해시태그발굴+소스채널마이닝,
  매일 headless, 토큰0·Apify0). Phase0 서버 데이터센터IP 스파이크부터. 설계 `docs/superpowers/specs/2026-07-26-해외HOT-무료Playwright크롤전환-design.md`.
- 2026-07-29 (사무실, Phase0 서버 스파이크): **샤오홍슈 ✅ 완료** — 막힌 원인이 IP가 아니라 로그인이었음
  (도메인도 rednote.com이어야 함, xiaohongshu.com은 비중국 IP 전체 지역차단이라 집IP도 막힘). QR로그인→
  storage_state 세션 파일(서버 저장)로 헤드리스+데이터센터IP 직결 그대로 뚫림, 프록시·집PC터널 불필요.
  **TikTok ❌ 슬라이더캡차**로 막힘(집터널 태워도 결과 0건) — 별도 세션 인계, 당분간 Apify 유지.
  부수발견: `instagram_playwright.py` 프록시 자격증명 임베드 버그(별도 기록). 상세 `handoff/해외HOT.md`.
- 2026-07-29 (사무실, 이어서): **TikTok 무료발굴 확정 종결(Apify 유지)** — headless=False·집터널·
  navigator.webdriver 은닉 스텔스 3가지 전부 실측 실패(캡차 또는 API 200/본문0 소프트블록). **샤오홍슈
  Phase 1(`playwright_crawl.py`) 구현+TDD 12테스트+`overseas_hot_jobs` XHS_SCRAPER 롤백스위치 배선,
  main 병합·배포 완료**(기본값은 안전하게 apify 유지). 라이브 E2E 첫 재시도 0건 → 다른 세션(레퍼런스랭킹)
  종료 후 재시도하니 15건 정상 수신 — **원인은 세션파일(`rednote_session.json`) 동시사용 경합**으로 확인,
  코드 결함 아님. 인스타 `/explore/tags/`도 반복요청 시 유사 소프트블록 관측(별도 후속).
