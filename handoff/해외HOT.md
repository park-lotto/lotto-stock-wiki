# 해외HOT 발굴 — 핸드오프

- 갱신: 2026-07-29 (이어받은 세션) / 트랙: 해외HOT (병합 후 폴더 유지)

## ✅ 샤오홍슈(rednote) 발굴 — Phase 0·Phase 1 코드 완료, 라이브 E2E 재확인만 남음
**Phase 0 결론(이전 세션)**: 프록시도 집PC 상시크롤도 필요 없다. 서버 직결 + 로그인 세션(storage_state)만
있으면 끝(도메인은 `rednote.com`, `xiaohongshu.com`은 지역차단). 세션 `/home/ubuntu/rednote_session.json`
(600권한, git비추적) — **레퍼런스 랭킹(계정등록) 쪽 `xiaohongshu_playwright.py` 작업과 세션을 공유**하니
만료 시 양쪽 다 영향받는다는 점 계속 유효.

**Phase 1(이번 세션, 2026-07-29) — 완료**: `shopping_shorts/playwright_crawl.py` 신규.
- 검색 API `webapi.rednote.com/api/sns/web/v1/search/notes` 응답 JSON을 가로채는 방식(DOM 파싱 안 함,
  인스타 크롤과 동일 원칙). 실측 스키마: `note_card.type`(video/normal 필터) · `display_title`(title 없는
  경우 있음) · `interact_info.{liked,comment,collected,shared}_count`(문자열 숫자) · `user.nickname` ·
  `cover.url_default` · `corner_tag_info[type=publish_time].text`(날짜, 3형식 혼재: "X小时前"/"MM-DD"/
  "YYYY-MM-DD") · `xsec_token`. **duration·정확한 타임스탬프는 리스트 응답에 없음** — duration=None 고정
  (`overseas_funnel.passes_shortform`이 길이불명 통과시켜 문제 없음), 날짜는 파싱해 근사(MM-DD류는 정오
  UTC로 근사 — 14일 신선도 창이 오래된 오차를 어차피 걸러냄).
- 광고 슬롯(`model_type != "note"`, id가 `uuid#타임스탬프` 형식)·이미지 노트(`type=normal`)는 제외.
- `overseas_hot_jobs.py`에 `config.XHS_SCRAPER` 분기 배선(`"playwright"`면 새 모듈, 기본 `"apify"`는
  기존 경로 그대로 — 롤백 스위치, 인스타 전환 때 쓴 패턴 재사용).
- 단위테스트 12+2개 전부 통과(`test_playwright_crawl.py`, `test_overseas_hot_jobs.py`의 분기 테스트 2개).
  전체 스위트 회귀 없음(13 fail은 기존 베이스라인, 내 변경 파일과 무관 확인).

**✅ 라이브 E2E 재확인 완료(2026-07-29, 다른 세션들 종료 후) — 원인은 세션 경합이 맞았다.**
옆세션(레퍼런스랭킹)이 켜져 있는 동안엔 `search_full("厨房神器")`가 0건을 반복했는데, 그 세션이
멈춘 뒤 같은 호출을 재시도하니 **첫 시도부터 실 데이터 15건 정상 수신**(제목·좋아요·채널명·날짜
전부 정상, "6a5d8eea..." 항목은 발행시각까지 `2026-07-26T17:29:19Z`로 정확히 파싱돼 상대시간
파싱 경로도 검증됨). `/home/ubuntu/rednote_session.json`을 **레퍼런스랭킹 세션과 발굴 세션이
동시에 쓰면 서로 방해**한다는 뜻 — 크롤러 로직 결함이 아니었다.
- **운영 시 주의**: 두 기능(해외HOT 발굴 / 레퍼런스랭킹 계정수집)이 같은 세션 파일을 쓰는 한,
  **동시 실행을 피해야 한다**(스케줄 시간을 겹치지 않게 하거나, 장기적으로는 세션 파일을 용도별로
  분리하는 것 고려). 상시 스케줄(systemd 타이머) 설계 시 이 제약을 반영할 것.
- **다음**: `XHS_SCRAPER=playwright`로 서버 env 플립은 여러 카테고리·여러 키워드로 한 번 더 돌려보고
  안정성 확인한 뒤 사장님 승인받고 진행. 코드·파서는 이제 신뢰 가능한 상태.

- 상세 실측·재현코드·주의사항: 설계문서
  `docs/superpowers/specs/2026-07-26-해외HOT-무료Playwright크롤전환-design.md`의 "✅ 샤오홍슈" 절 참고.

## ❌ TikTok 발굴(키워드/해시태그) — 3가지 방법 전부 막힘, Apify 유지로 결론
**주의: 이건 "레퍼런스랭킹의 틱톡 계정수집"(`tiktok_client.fetch_account_videos`, yt-dlp, 무료·이미 라이브)과
완전히 다른 기능이다.** 계정 하나 넣고 그 영상 목록 긁는 건 이미 무료로 잘 된다 — 캡차 문제는 **키워드/
해시태그로 아직 모르는 새 영상을 찾는(발굴) 검색 경로만** 해당.

2026-07-29에 서버에서 3가지를 실측했고 전부 진짜 데이터를 못 받았다:
1. **서버 직결 + `headless=False`(Xvfb 가상디스플레이)**: 캡차 여전(`headless` 플래그가 원인이 아님을 반증).
2. **집IP 리버스 SSH 터널**(`socks5://127.0.0.1:1080`, IP는 `1.234.137.87`로 확인): 페이지엔 캡차가 뜨는데
   검색 API(`/api/search/item/full/`)는 **status 200·본문 길이 0**(조용한 소프트블록 — IP를 바꿔도 안 뚫림).
3. **위 터널 + 스텔스 패치**(`navigator.webdriver` 은닉, `--disable-blink-features=AutomationControlled`):
   동일하게 캡차 + 빈 응답.

**결론: IP 평판만의 문제가 아니라 서명된 요청 파라미터(msToken/X-Bogus류)나 더 정교한 디바이스
핑거프린트로 막는 것으로 보임 — Playwright 설정 몇 개로 뚫을 수준이 아니다.** 사람이 캡차를 수동으로
풀고 세션 재사용하는 방법은 시도 안 함(TikTok은 세션 단위가 아니라 매 요청 재검증할 수 있다는 사전
경고가 있었고, 위 3가지 실패로 볼 때 성공 가능성이 낮다고 판단). **TikTok 발굴은 Apify(`tiktok_search.py`)
유지로 확정** — 무료 전환은 샤오홍슈만.

## 🔍 인스타 `/explore/tags/` 발굴 — 첫 요청은 성공, 반복하면 조용히 막힘(2026-07-29 관측)
설계문서 Phase 0(2026-07-26)에서 로컬 GUI로 성공했다던 것과 별개로, **서버 데이터센터 IP + headless**로
첫 요청은 완전히 성공했다: 로그인벽 없음, `graphql` 응답에 실제 영상 노드(캡션·커버 URL 등)가 정상 포함.
그런데 곧이어 같은/다른 해시태그로 재요청하니 **로그인벽도 없고 HTML도 똑같이 로드되는데 media-info
쿼리 자체가 응답에서 빠짐**(조용한 소프트블록, TikTok의 명시적 캡차와는 다른 패턴). 요청 간격을 넉넉히
띄우면 되는지는 미확인 — 다음에 이어볼 때 딜레이를 두고 재확인할 것. 아직 크롤러 코드는 없음(탐색만).

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
