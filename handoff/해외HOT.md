# 해외HOT 발굴 — 핸드오프

- 갱신: 2026-07-29 / 트랙: 해외HOT (병합 후 폴더 유지)

## ✅ 샤오홍슈(rednote) — Phase 0 완료, Phase 1(크롤러 코드) 착수 가능
**결론: 프록시도 집PC 상시크롤도 필요 없다. 서버 직결 + 로그인 세션(storage_state)만 있으면 끝.**
막힌 게 IP인 줄 알고 프록시·집PC 리버스터널까지 팠는데 헛다리였고, 진짜 원인은 **로그인 여부**였음
(도메인도 `xiaohongshu.com`이 아니라 `rednote.com`이어야 함 — 본토 도메인은 비중국 IP 자체를 지역차단함,
집IP로 터널 태워도 막히는 걸로 확인). QR로 실제 계정 로그인 → `storageState()` 쿠키 88개를 서버
`/home/ubuntu/rednote_session.json`(600권한, git비추적)에 저장 → 서버 헤드리스가 그 세션으로 재접속하면
데이터센터 IP 그대로 검색결과(제목·작성자·날짜·좋아요) 정상 로드 확인됨(2026-07-29).

- 상세 실측·재현코드·주의사항(세션 만료·노트링크 패턴 변경 등): 설계문서
  `docs/superpowers/specs/2026-07-26-해외HOT-무료Playwright크롤전환-design.md`의 "✅ 샤오홍슈" 절 참고.
- **다음(Phase 1)**: `playwright_crawl.py`에 샤오홍슈 크롤러부터 구현 — 검색 URL → 세션 로드 → 스크롤 →
  `/search_result/<id>?xsec_token=` 패턴 카드 추출 → build_overseas_items 스키마. `overseas_hot_jobs`에서
  샤오홍슈만 Apify 경로 OFF(TikTok/도우인은 유지, 아래 참고).

## ⏭ TikTok — 다음 세션에서 이어갈 것 (별도 조사 필요, 샤오홍슈와 묶지 말 것)
**증상: 서버 헤드리스 직결 시 매번 슬라이더 캡차("Drag the slider to fit the puzzle")로 막힘.** 로그인
문제가 아니라 자동화 탐지라 샤오홍슈처럼 세션 파일로 해결되는 성질이 아님. 2026-07-26에 "TikTok 됐다"고
기록한 건 **로컬 GUI 브라우저(집IP)** 기준이고, **서버·헤드리스로는 이번이 처음 테스트**했음 — 안 됐음.
집PC 리버스 SSH 터널(`ssh -R 1080` → 서버가 socks5://localhost:1080 경유) 태우면 캡차는 안 뜨는데
대신 **검색결과가 0건**(원인 미확인 — 스크롤 트리거 필요/API 별도 차단 등 가설만 있고 미검증).

**다음 세션 시도 순서** (설계문서 "❌ TikTok" 절에 상세):
1. `headless=False` 또는 가상디스플레이로 캡차 여부 재확인(headless 플래그 자체가 탐지 트리거일 수 있음)
2. 캡차 사람이 한 번 수동으로 풀고 그 세션(storage_state) 재사용 시도 — 단 TikTok은 세션 단위가 아니라
   매 요청 재검증할 수도 있어 통할지 미지수
3. 집터널 "0건" 원인 파기 — `browser_network_requests`로 실제 검색 API 호출·응답코드 확인, 스크롤 트리거
4. 그래도 안 되면 **TikTok은 Apify(`tiktok_search.py`) 유지** — 샤오홍슈만 무료크롤 전환하는 하이브리드로 확정

## 도우인 — 미착수
2026-07-26 그대로: 로그인 벽(QR/휴대폰 인증) 확인만 되고 미시도. 계속 Apify(`douyin_search.py`) 사용.

## ⚠️ 부수 발견 — 인스타 프록시 코드 버그(범위 밖, 기록만)
`instagram_playwright.py:41`이 프록시 자격증명을 `server` URL에 임베드하는데 Playwright가 이 형식을
못 읽음(`username`/`password` 분리 필요, 공식 스펙). 2026-07-28 인스타 프록시 "타임아웃" 결론이 이 버그
때문일 가능성 있음 — 인스타 프록시 재시도할 때 이것부터 고치고 검증할 것.

## (구) 사무실서 이어서 — 무료 Playwright 크롤 전환 — 위 섹션들로 대체됨
- **크롤 2모드**: ①해시태그/검색어 발굴(넓게) ②소스채널 마이닝(발굴서 나온 좋은 계정 등록→매일 그 채널 직접 크롤=선점 최상).
- **정리**: 현 픽업 5개(Apify분) 삭제 OK(픽업 기능=수동URL+렌즈는 유지).

---

## 현재 상태 — Apify 발굴전환 라이브 완결 ✅
레딧 발굴을 **틱톡 + CN(샤오홍슈·도우인) Apify 발굴**로 전면 전환. main 병합·서버 배포 완료.

- **왜 전환**: 레딧 틈새 서브의 hot은 "틱톡 바이럴 원본/선점"과 불일치 → 잡탕(80건 중 76건 일반바이럴,
  꿀템 카테고리 0). 무료 발굴경로(틱톡 tiktok:tag broken·Creative Center gated·CN 검색추출기 없음)는
  전부 벽 확인 → Apify 유료로 결정(사장님 승인).
- **재활용**: `apify_client`(토큰17개 `/etc/shopping-shorts.env`) · `tiktok_search.search_full` ·
  `gap_check` · store/job/폴링/🌍탭. 신규: CN `search_full`2개 · `build_overseas_items`(참여속도 랭킹) ·
  `overseas_funnel`(형식·관련성·안터진상한) · job 재작성 · 카드 UI.
- **랭킹 = 참여속도**: CN은 조회수를 안 줌(실측: 도우인 playCount=0, 샤오홍슈 view필드 없음) →
  랭킹 기준을 **(좋아요+댓글+수집+공유)/경과h** 로 통일(세 플랫폼 좋아요 자릿수 유사). 조회수는 표시용.
- **깔때기**: STAGE0 쿼리(유료 40/카테고리/플랫폼) → 형식·관련성·안터진상한(무료) → 참여속도 랭킹 →
  dedup → 생존자만 gap_check(쿼터보호). 폐기 카테고리(옛 레딧) 자동퇴출 가드 있음(셀프힐링).
- **실측 라이브(2026-07-26)**: 39건, 6카테고리 골고루(가전14·인테리어6·뷰티6·정리5·주방4·살림4),
  전부 tiktok/douyin/xiaohongshu. 옛 레딧 잡탕 퇴출 완료.

## 검증 상태
- 신규 유닛테스트 전부 통과(seeds3·build_overseas3·douyin2·xhs2·funnel4·gap2·job4). 전체게이트 통과(기준선 11건 무관).
- 라이브 실수집 1회 성공(949초/39건). **주의**: `/api/*`·`/`는 로그인 게이트라 익명 curl은 401/랜딩(정상).
- 서버 Apify 토큰 17개 `/etc/shopping-shorts.env`(systemd EnvironmentFile). 앱 config는 여기서 env 로드.

## ⏭ 다음 (Phase 2 — 남은 것)
1. **CN 선점뱃지 = 현재 "미확인"** — `gap_check` 번역이 CN 중국어제목→한국어가 안 돼(translate_keyword
   방향이 KO→ZH로 추정) 안전하게 미확인 처리 중. ZH→KO 번역경로 붙이면 CN도 🔥선점 판정 가능.
   (거짓 선점 방지 위해 번역결과에 한글 없으면 미확인 반환하도록 구현돼 있음 — Task7)
2. **관련성/생존율 튜닝** — 시드 키워드(overseas_seeds.json)·차단어(overseas_funnel.BLOCK_WORDS)·
   조회수상한(DEFAULT_VIEW_CEILING=300만) 라이브 며칠 보고 조정.
3. **가속(accel) 정착** — 참여 Δ의 Δ는 2회+ 스냅샷부터 성립. 매일 수집 누적되면 급상승 신호 강화.
4. **Phase 3** — 생존자 yt-dlp 다운로드 → [재편집] → mix 파이프라인 연결.

## 파일
설계 `docs/superpowers/specs/2026-07-26-해외HOT-Apify발굴전환-design.md`
계획 `docs/superpowers/plans/2026-07-26-해외HOT-Apify발굴전환.md`
핵심코드 `overseas_hot_jobs.py`·`overseas_funnel.py`·`ranking.build_overseas_items`·
`douyin_search.search_full`·`xiaohongshu_search.search_full`·`gap_check.gap_badge(translate=)`·
`static/index.html`(renderOverseas 카드)·`overseas_seeds.json`
