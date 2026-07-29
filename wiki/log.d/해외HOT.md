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
- 2026-07-29 (집, 밤): 서버에서 XHS_SCRAPER=playwright 라이브 켜고 실사용 중 사장님 피드백 3건 즉시
  반영·배포 — ①검색 기본 인기순이라 몇 달 전 글만 나오는 문제 → **정렬 body를 time_descending으로
  가로채기 강제**(서명검증 안 걸림 확인, 결과가 진짜 어제/오늘 글로 바뀜) ②"자막(텍스트오버레이) 많은
  썸네일 빼줘" → Gemini 비전(`text_level_vision`, 기존 비전태그 인프라 재사용)으로 heavy 컷, 겸사겸사
  샤오홍슈 썸네일이 인스타전용 Referer 때문에 전부 403 나던 버그도 수정 ③"틱톡·도우인은 나중에 다시
  개발할 거니 지금은 빼줘" → `OVERSEAS_TIKTOK_ENABLED`/`OVERSEAS_DOUYIN_ENABLED` 토글 추가, 서버는 둘 다
  false로 설정(샤오홍슈만 운영). 부수: 탭 전환 시 진행률 표시 끊기던 UI버그도 수정. 전부 TDD+실측 검증
  후 `finish`로 main 병합. 회사에서 이어감 — 서버 env 수동설정값은 `handoff/해외HOT.md` 상단 참고.

## 2026-07-29 (회사)
- 해외HOT **자막 없는 썸네일 우선 정렬 라이브**(SDD 5태스크). 판정을 앞 15개→생존자 전부로 넓히고 `thumb_text_level` 캐시로 Gemini 재호출 차단, 정렬을 `(자막등급, -score)`로.
- ★최종 whole-branch 리뷰가 Critical 3건 적발: 캐시 키가 `shortcode`/`video_id` 불일치로 항상 None, `build_overseas_items`가 `text_level`을 안 실어 정렬 무효, 테스트가 손수 주입한 가짜 계약을 검증(37건 초록인데 실동작 0%). 수정 후 E2E 회귀테스트로 못박음.
- 인스타 랭킹의 CN 원본 찾기는 **구글 렌즈로 불가 확정**(실측 5건 → CN 0건). Apify 경로 부활 여부는 사장님 비용 판단.
