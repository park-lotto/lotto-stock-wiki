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

## ⚠️ Phase 0 스파이크 — 결론: 플랫폼별로 다르다 (샤오홍슈 ✅ / TikTok ❌ / 도우인 미착수)
내 크롤이 된 건 **집=주거용 IP**. **서버=AWS 데이터센터 IP**라 막힐 수 있음(Reddit 전례). 그리고 현 Playwright는
대화형 MCP라, 상시엔 **서버에 Playwright+Chromium 설치** 필요.
- [x] 서버에 `pip install playwright && playwright install chromium`(의존성 포함). — 완료(인스타 전환 작업 때 설치됨, 공용).
- [x] **샤오홍슈(rednote) — ✅ Phase 0 완료(2026-07-29). 로그인 세션으로 서버 직결 그대로 뚫림.**
- [x] **TikTok — ❌ 슬라이더 캡차로 막힘(2026-07-29 실측). 별도 세션 인계 대상.**
- [ ] 도우인 — 손 안 댐(원래도 모바일인증 필요, 2026-07-26 기록 그대로).
- [ ] Instagram 서버 실크롤 — 미착수(참고: 인스타 프록시 코드에 버그 있음, 아래 부수발견).

### ✅ 샤오홍슈(rednote) — 최종 결론: 서버 직결 + 로그인 세션이면 끝. 프록시·터널 불필요.

**막힌 원인이 IP가 아니라 로그인이었다.** 처음엔 IP 차단(Reddit 전례)이라 가정하고 프록시·집PC 리버스
SSH 터널까지 팠는데, 전부 헛다리였음 — 아래 순서로 좁혀졌다:

1. `xiaohongshu.com`(중국 본토 도메인)은 어떤 IP로 접속해도(서버 직결·Webshare DE 프록시·**진짜 집IP
   리버스터널까지**) `error_code=300012 "IP存在风险，请切换可靠网络环境后重试"`로 막힘 — 이건 프록시 평판
   문제가 아니라 **비중국 IP 전체를 막는 지역 게이트**로 보임(집IP도 막혔으므로).
2. 반면 **`rednote.com`(해외용 도메인, 처음 성공기록이 쓴 그 도메인)은 IP 차단이 아예 없었다.** 서버
   직결이든 집터널이든 둘 다 `Log in to view search results` 문구만 뜸 — **로그인 여부**가 진짜 벽이었음.
3. Playwright MCP(로컬 브라우저)로 rednote.com 접속 → QR 로그인(실제 계정, 폰 앱 스캔) 완료.
4. `page.context().storageState()`로 쿠키(88개, `web_session`/`csrftoken`/`id_token` 등 인증 토큰 포함)를
   추출 → 서버 `/home/ubuntu/rednote_session.json`(600 권한, git 비추적)에 저장.
5. 서버에서 `browser.new_context(storage_state="/home/ubuntu/rednote_session.json")`로 **헤드리스 +
   데이터센터 IP 직결**로 재접속 → 로그인 상태 유지, 검색결과 카드(제목·작성자·날짜·좋아요) 15개+ 정상 로드.

**재현 코드**:
```python
ctx = browser.new_context(storage_state="/home/ubuntu/rednote_session.json")
page = ctx.new_page()
page.goto("https://www.rednote.com/search_result?keyword=<urlencoded>&type=video")
```

**주의**:
- ⚠️ 노트 링크 패턴이 문서 초안의 `/explore/<id>`에서 **`/search_result/<id>?xsec_token=...`로 바뀜**
  (사이트 개편으로 추정) — Phase 1 크롤러 셀렉터/정규식 이걸로 다시 맞춰야 함.
- ⚠️ 세션 쿠키는 **언젠가 만료됨**(보통 며칠~몇 주). 만료되면 위 3~4번을 반복해 재발급 필요 — 완전
  무인화는 아니고 가끔 수동 재로그인 필요. 자동 갱신은 Phase 1 범위 밖(수동 운영으로 충분).
- ⚠️ 세션 파일 = 로그인 토큰 원본. **절대 git 커밋 금지**, 서버에만 600 권한으로 둘 것.
- 도메인은 반드시 **`rednote.com`**으로 (`xiaohongshu.com` 아님 — 지역 게이트로 100% 막힘).

**즉 XHS는 프록시도 집PC 상시크롤도 필요 없다.** 서버가 이미 상시로 켜져 있으니 로그인 세션 파일 하나만
관리하면 Phase 1(크롤러 코드) 바로 착수 가능.

### ❌ TikTok — 슬라이더 캡차. 다음 세션 인계 대상(별도 조사 필요)

**증상**: `tiktok.com/search/video?q=` 서버 직결 → 매번(2회 재시도 동일) **"Drag the slider to fit the
puzzle"** 캡차 페이지. `captcha`/`verify` 키워드 HTML에 존재. XHS처럼 로그인 세션으로 해결될 성질이
아님(로그인 여부와 무관하게 뜨는 자동화 탐지 챌린지) — 2026-07-26에 "됐다"고 기록된 건 **집 IP + 로컬
Playwright MCP 브라우저**(실제 디스플레이 있는 세션)였고, **헤드리스 + 서버**로는 확인된 적이 없었음(오늘
처음 서버에서 테스트해봄).

**집IP 리버스 SSH 터널 경유**: 캡차는 안 떴지만(IP 평판 문제는 아닌 듯) **검색결과 자체가 0건** —
HTML은 75KB 정도 로드되는데 실제 비디오 카드가 안 실림. 원인 미확인(스크롤 트리거 필요/API 별도 차단/
세션·쿠키 필요 등 여러 가설 미검증 상태).

**다음 세션에서 시도해볼 것(우선순위)**:
1. **headless=False**(진짜 GUI 브라우저)로 서버에서 캡차가 그래도 뜨는지 확인 — headless 플래그 자체가
   TikTok 탐지 트리거일 가능성 있음(XVFB 등 가상디스플레이로 headless지만 GUI인 척 하는 방법도 있음).
2. 사람이 **캡차를 한 번 수동으로 풀고** 그 브라우저 컨텍스트(storage_state)를 재사용하는 방식 —
   XHS와 같은 패턴. 캡차 통과 후 세션이 재사용 가능한지가 관건(TikTok은 세션 단위가 아니라 매 요청마다
   재검증할 수도 있음 — 미검증).
3. 집터널 경유 시 "결과 0건"의 원인 파고들기 — `page.mouse.wheel`로 스크롤 트리거, 네트워크 탭
   (`browser_network_requests`)으로 실제 검색 API 호출이 나가는지·응답 코드 확인.
4. 그래도 안 되면 **TikTok은 계속 Apify(`tiktok_search.py`, `clockworks~tiktok-scraper`)로 유지** —
   XHS만 무료 크롤로 바꾸고 TikTok/도우인은 유료로 남기는 하이브리드가 현실적 대안.

### 도우인 — 미착수
2026-07-26 기록 그대로: 로그인 벽(QR/휴대폰 인증) 확인만 되고 아무 시도 안 함. 계속 Apify(`douyin_search.py`) 사용.

### ⚠️ 부수 발견(인스타, 이번 조사 중 우연히 잡음)
`instagram_playwright.py:41`의 `ctx_kw["proxy"] = {"server": config.INSTAGRAM_PROXY}`가 자격증명을
`server` URL에 임베드하는 형태인데, **Playwright는 이 방식을 못 읽는다**(`username`/`password`를 별도
필드로 줘야 함 — 공식 스펙, XHS 프록시 테스트 중 실증). 2026-07-28 인스타 프록시 실측의 "20초·60초
타임아웃" 결론이 이 버그 때문일 가능성 있음 — 코드 안 고치고 발견만 기록해둠(범위 밖). 인스타 프록시
전환을 다시 시도할 때 `docs/superpowers/plans/2026-07-28-인스타-playwright-10채널-실측.md`와 같이
참고해서 `username`/`password` 분리부터 재검증할 것.

## Phase 1~4 (하이브리드로 조정 — XHS만 무료크롤, TikTok/도우인은 Apify 유지)
1. **크롤러 모듈** `playwright_crawl.py`: 우선 **샤오홍슈만** 구현(검색 URL → `storage_state` 세션 로드 →
   스크롤 → `/search_result/<id>?xsec_token=` 패턴 카드 추출 → 스키마). TikTok/도우인은 캡차·로그인벽
   해결 전까지 Apify 그대로 둔다(코드 안 건드림).
2. **파이프라인**: XHS 크롤 → overseas_funnel → build_overseas_items → store. `overseas_hot_jobs`에서
   **샤오홍슈만** Apify 경로 OFF, TikTok/도우인은 그대로 유지(플랫폼별 분기 필요).
3. **상시 스케줄**: systemd 타이머 매일(6~12h). 세션 만료 시 실패 알림(텔레그램 등) — 조용히 0건 나는 것 방지.
4. **소스채널**: `overseas_seeds.json`에 seed_accounts → 채널 마이닝(XHS 우선 적용).
5. **TikTok/도우인**: 위 "다음 세션에서 시도해볼 것" 참고해 별도 세션에서 이어감.

## 참고 — 검증된 추출 로직(TikTok, 이미 성공)
`a[href*="/video/"]` 순회 → `@author/video/id` 파싱 → 카드 컨테이너 innerText에서 좋아요/제목.
(인스타는 `/reel/` 링크 + ▷조회수, 샤오는 note 카드. 각 셀렉터는 Phase 1서 확정.)

## 정리 작업
- **현 픽업 5개(Apify분) 삭제 OK**(사장님) → 픽업 카테고리 클리어(픽업 기능=수동 URL+렌즈는 유지).

## 이미 라이브(이번 세션 완료분, 유지)
Apify 발굴전환 · 참여속도 랭킹 · 숏폼/키워드/관련성/도우인썸네일 튜닝 · 🖐픽업(수동URL) · 🔎같은영상(렌즈 trace_url).
