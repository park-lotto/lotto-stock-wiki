# NEXT_SESSION — 여러 병렬 세션(아래 최신순)

## [세션 G, 2026-07-04 밤] YT 레퍼런스 창고 (/yt/refs) — 터진영상 검색·검증·해체·믹스 (로컬완성, 서버미배포)

**브랜치: `feat/briefing-engine`** (공유 워킹트리라 여기 얹힘. 내 YT 커밋은 이 브랜치에 있음. main 정리 후 배포).
**내일 회사PC에서 이어감 → `git pull` 후 이 브랜치 확인.**

### ✅ 로컬 완성 (localhost:8090/yt/refs, 브라우저 실검증 완료)
사용자가 실검색으로 피드백 주며 반복 개선. `dashboard/yt_refs.html` + `scripts/yt_agents/{hot_clips,clip_teardown,gemini_client}.py` + `yt_categories.json` + server.py 엔드포인트 5개.
- **흐름**: 카테고리10종/자유검색/URL → 검색+검증순위 → 🔬해체(Gemini 영상시청, 대본 전체분석) → 멀티선택 믹스 → 대본초안
- **검증지표 ⭐추천 = 3개 교집합**: 배수(구독자대비=소재캐리)+기여도(채널평균대비=제목훅통함)+콘텐츠참여율(썸네일빨아닌 내용빨)
- 컬럼: 추천·판정(금맥/기여/채널빨)·배수·일조회수(velocity)·기여도·댓글·길이·게시·콘텐츠. 제목/채널클릭=유튜브. 다단계정렬 3단계(▼→▲→해제)+초기화.
- 필터: 검증하한 3만뷰(노이즈컷)·쇼츠제외(/shorts 리다이렉트 판별, 3분까지)·뉴스제외(SBS등)·기간(기본 전체). 검색 50×3순서, 배치청킹, 기여도는 필터후 병렬계산(18초).

### 🚨 미결 / 내일 할 것
1. **서버 배포** — 아직 안 함. feat/briefing-engine에 내 YT파일 커밋됨(server.py yt엔드포인트 포함). 브리핑/캘린더 세션과 공유트리라 main 머지·배포는 조율 필요. 로컬만 검증됨.
2. 다음 기능: **썸네일/제목 전용 제작 단계**(해체에서 성공요인=썸네일빨이면 이쪽으로), 창고 **영구저장 DB**, Opus/Sonnet **검수 레이어**(Gemini 대본초안의 논리비약·후킹·CTA빈틈 점검).
3. 속도: 검색 18초(기여도 병렬계산 포함). 필요시 더 최적화 가능.
- 메모리: `project_yt_reference_warehouse.md`. 로컬 백업: scratchpad/yt_backup/.

---

## [세션 F, 2026-07-04] 이벤트·트리거 캘린더 (인사이트 리디자인 + 촉매 시스템) — Phase0·1a·1b1 완료

**브랜치: `feat/briefing-engine`** (세션 E와 공유, 원격 push됨). 커밋 전 `git branch --show-current` 필수.

### 배경 / 목표
"내 종목·섹터에 앞으로 어떤 일정·트리거가 있나"를 누적 원자(atoms)로 차려주는 시스템 + 인사이트 페이지 애플-라이트 리디자인.
- 스펙: `docs/specs/2026-07-04-인사이트-이벤트캘린더-설계.md`
- 계획: `docs/superpowers/plans/2026-07-04-event-calendar-phase0.md`, `...-phase1-api.md`
- 원장: `.superpowers/sdd/progress.md` 맨아래(로컬전용/gitignore — 이 파일이 크로스PC 인수인계 정본)
- 시안(보존): `docs/mockups/insights-apple-light-v5.html`(인사이트 홈, 미빌드), `insights-catalyst-v6.html`(촉매)

### ✅ 완료 (전부 커밋+push)
- **Phase 0** (95626536,52613a43,47cb204d,31749dc3): 이벤트 캘린더 데이터 파이프. `pipeline/atoms/db.py`에 `event_date`컬럼+idx, `calendar_ingest.py`(섹터캘린더JSON→이벤트원자, 확정도/entity_scope/event_form매핑), `calendar_build.py`(select_future_events D-day필터 + build_calendar_board 위키보드). 16 pytest. 임시DB e2e 실증(4건→보드, TSMC foreign감지).
- **Phase 1-a** (d10ee9c6,3253e315): `select_future_events(...,days)` 호라이즌 + `to_api_dict`, **`GET /api/catalysts?mine=&sector=&days=&today=`** (기존 watchlist 재사용). TestClient 3.
- **Phase 1-b-1** (dd75e2dd): **`dashboard/catalysts.html` + `GET /catalysts` 라우트**. 라이트 애플 디자인, 내종목필터·섹터탭·D배지·확정도(●◐○)·해외플래그(🌏). 브라우저 목렌더 실측. watchlist=읽기+필터전용(편집은 시세페이지). 사가=Phase3 placeholder. TestClient 1.

### 🚨 블로커 / 주의
1. **Gemini 429 쿼터소진** — `fetch_sector_calendar.py`가 오늘 실이벤트 0건. 파이프배선은 정상(빈 파일도 ingest→board 정상). 쿼터리셋/데일리크론 후 실데이터 채워짐. (`fetch_sector_calendar`는 key_vault 안 씀 — 단일키 소진. Phase3에서 볼트연결 검토)
2. **8090 실행서버(PID 8272, 세션E배포)는 구코드** → `/catalysts` 404. 그 서버 재시작/재배포돼야 라이브. 내 코드는 push됨.
3. 공유브랜치: 세션E 시황엔진 커밋(deeb5605)과 내 커밋 교차. 세션E 리스크2가 내 calendar커밋 인지함.

### 다음 할 일
- **Phase 1-b-2**: 인사이트 홈(`dashboard/insights.html`, 154KB 대형 라이브파일)에 촉매 요약섹션+내비링크 그래프트 + 라이트디자인 이식(`docs/mockups/insights-apple-light-v5.html` 참조). 고위험 수술 — 조심.
- **Phase 3**: 진행형 사가 추적(테마이벤트 구조 확장), 예상 트리거 추출(atomizer catalyst→event_date), 락업/옵션/배당락 크롤, event_merge로 확정도 tier2 부스트, 텔레 푸시.
- 실데이터: Gemini쿼터 회복 후 `py fetch_sector_calendar.py` → `py -m pipeline.atoms.calendar_ingest` → `py -m pipeline.atoms.calendar_build`.
- [방식메모] 이 프로젝트 서브에이전트는 python스텁으로 pytest 자체실행 불가 → 컨트롤러 직접구현+`py -m pytest` 실측이 검증된 방식.

---

## [세션 E, 2026-07-04 밤] 장중 시황 브리핑 엔진 설계·구현·서버배포 + KIS장애 대응 — 월요일 실전검증

**브랜치: `feat/briefing-engine`** (원격 push됨). 브리핑 작업은 이 브랜치에서 이어가라.

### ✅ 완성·배포 — 장중 시황 브리핑 엔진 (Phase 0 관측·보정)
"실시간 브리핑" 패널을 **이벤트 감지 기반 + Opus/Sonnet(Max 구독, API 아님) 종합**으로 전면 재설계·구현·서버배포 완료.
- 스펙 `docs/superpowers/specs/2026-07-04-시황-브리핑-엔진-design.md` / 계획 `docs/superpowers/plans/2026-07-04-시황-브리핑-엔진.md`(14 task) / 원장 `.superpowers/sdd/progress.md` 맨아래.
- 신규 dashboard 모듈: `briefing_phase`·`briefing_events`(디텍터6종:수급·프로그램·지수분기점·미선물·디커플링·섹터급등)·`briefing_weather`(claude -p 호출+Gemini폴백)·`briefing_digest`·`briefing_state`. **32 pytest 통과.**
- server.py `_poll_briefing`에 `_weather_tick()` 배선. market.html 패널=판정배지+내러티브+전환점.
- **서버 라이브 E2E 검증**: 이벤트 주입 → 디텍터 5개 감지 → Opus 21초 "🟢 반등, 외인 매수전환+반도체 급등" 판단형 브리핑(아침→지금 흐름·뉴스결합·다음분기점). weather_state·calib log·insight API 정상.

### 월요일(07-06) 장중 할 일
1. **실장중 관측**: 폰 텔레 다이제스트(major즉시/minor15분)로 잡힘·노이즈 확인. `output/weather_calib/*.jsonl` 기록.
2. **브라우저 렌더 확인**: `/market` 새로고침(오늘 browsermcp 미연결로 시각확인만 미완, API·로직은 검증).
3. **임계 튜닝**: 섹터+2%p / 투자자전환300억 / 지수반등·되돌림0.6% / 미선물0.4%p → 관측 보고 조정.
4. **최종 통합리뷰 + main 머지**(아래 브랜치 정리 후).

### 🚨 리스크1 — Max 토큰 유지(실발생): 서버 복사 토큰이 로컬 Claude Code 갱신으로 무효화("Not logged in", 20:36만료후 실발생)→재복사 복구. 월요일 calib `models`필드로 Opus유지 vs Gemini폴백 추적. 스테일돼도 Gemini 우아폴백(기능유지). 재복사: 로컬 `~/.claude/.credentials.json`→서버 `/home/ubuntu/.claude/.credentials.json`(chmod600).
### 🚨 리스크2 — 동시세션 섞임(또): `feat/briefing-engine`에 다른PC(park-lotto) calendar/atoms 커밋4개(95626536~31749dc3)+미커밋 server.py·yt_refs.html WIP 얹힘. main 머지 전 분리/포함 결정. 서버 배포 server.py=내 브리핑버전(라이브검증). 커밋전 `git branch --show-current` 필수.

### 별개 마감(main push됨) — KIS 서버장애 대응(commit b41cb803)
서킷브레이커(kis_api)+네이버폴백(naver_api·sector_heatmap·server·market.html·briefing_collect). 2026-07-04 KIS 오픈API 자체장애(금15:47~) 실증대응, 히트맵·ETF·관심종목·차트·탑픽 폴백확보, 서버검증완료. 메모리 `project_kis_outage_2026_07_04`.

---

## [세션 D, 2026-07-04] YT 대시보드 ①기획단계 Task 5 완료 + 실브라우저 버그 2건 발견·수정 — 완료

**주제**: 어제 중단된 YT 대시보드(①기획단계) Task 5 이어가기.

### ✅ 완료 — Task 5 검증 + 실버그 2건 수정
- `dashboard/yt.html`+`GET /yt`는 이미 다른/자동 세션이 커밋해둔 상태(b2f6c702)로 발견 —
  계획서와 코드 대조 확인, 19/19 테스트 통과 확인.
- **verification-grounding-pack 규칙대로 실브라우저+실YouTube API로 검증하다 진짜 버그 2건
  발견·수정(commit 5b8d5744)**:
  1. `hot_clips.search_videos`가 YouTube API 제목의 HTML엔티티(`&#39;` 등)를 방치 →
     "담김" 표시에 엔티티가 그대로 노출되고, 더 심각하게는 이 원문이 Gemini 프롬프트에까지
     그대로 흘러들어가고 있었음. `html.unescape()`로 소스 단일지점 수정.
  2. ①을 고치자 표면화된 2차버그: 디코딩된 실제 apostrophe가 `encodeURIComponent`에서
     이스케이프 안 돼 `onclick='...'` 속성을 깨뜨려 "담기" 클릭이 SyntaxError로 조용히
     죽음(엔티티가 살아있던 이전엔 가려져 있었음). 인덱스기반 조회로 근본수정 +
     `esc()` 헬퍼(다른 대시보드 페이지 기존 관례) 적용.
- 실제 검증: YouTube 검색(반도체 조정 검색 결과 실측)·"담기"(따옴표 포함 제목으로 재현)·
  SSE 기획생성(Gemini 429 quota로 에러경로까지 확인, 에러이벤트 UI 정상 표시) 전부 확인.
- 전체 5개 태스크 완료, main 반영·push 완료(5b8d5744). **Lightsail 서버 배포는 안 함**
  (사용자 확인 후 별도 진행). 상세=`.superpowers/sdd/progress.md`.
- 다음: ②대본③리모션④녹음⑤자막⑥렌더는 다음 사이클(범위 밖).

---

## [세션 C, 2026-07-03] pytest 수집버그 수정 + 브랜드 스타일 인포그래픽 실험 — 완료

**주제**: (1) 일일검증(daily_verify.py) 텔레알림이 fail/ok를 오가던 원인 진단·수정,
(2) 골루프 인포그래픽에 실제 브랜드(클로드/클레이) CI/BI 스타일 입히기 실험.

### ✅ 완료 — pytest 수집 에러 4건
- 원인 3가지: `scripts/_c2_test.py`·`_kis_test.py`(이름만 test패턴, 실제론 수동스크립트)가
  자동수집돼 win32com/KIS_APP_KEY 참조로 항상 에러 / `pandas` 서버venv 미설치 /
  `dashboard.server`를 pytest가 root에서 import할 때 `dashboard/` sys.path 누락.
- 수정: `conftest.py`에 `collect_ignore_glob`+`dashboard/` sys.path 추가, venv에 pandas 설치.
- 결과: 수집에러 0건, "7 failed, 446 passed"로 정상화(남은 7개는 atoms/ingest 파이프라인
  기존 test-source 드리프트, 오늘 작업과 무관 — 미해결로 남김, 사용자가 여기까지만 하기로 함).

### ✅ 완료 — 브랜드 스타일 인포그래픽 (`scripts/nlm_bridge.py`)
- `create_infographic()`에 `brand=` 파라미터 추가 — 기존엔 커스텀 focus를 줘도 항상
  `_BRAND_DESIGN`(라임그린 HUD)이 같이 붙어 스타일이 섞이는 버그였음(예: 클로드 실험 시
  크림+라임그린 혼합) → `BRAND_STYLE_PRESETS` dict로 완전 대체 가능하게 고침.
- 등록된 프리셋 3종(전부 텔레그램 전송·사용자 확인 완료): `claude`(크림+코랄 에디토리얼),
  `claude_terminal`(다크+픽셀아웃라인폰트+터미널창, 이미지소스 없이도 재현됨), `clay`
  (3D클레이메이션+채도색카드순환, clay.com 실이미지 3장을 노트북소스로 추가해서 성공).
- 부수 발견: `studio status` 폴링이 `arts[-1]`(최고참)을 봐서 예전 완료본을 오판하던 버그 수정
  (`arts[0]`으로, API가 최신순 응답). `nlm download infographic` CLI가 `--profile` 옵션
  자체를 미지원(create/status는 지원) — 다른 계정 다운로드 시 `nlm login switch`로 임시전환 후
  즉시 원복하는 우회 필요. 계정 2개(default=parklotto12, secondary=parklotto20) 운용 중,
  하나가 rate limit 걸리면 다른 계정으로 전환.
- 참고: `scripts/goal_loop/design_refs/{claude,clay}_design.md`, `clay_images/`(원본 3장).
  메모리: `project_brand_style_infographics.md`, `feedback_brand_style_workflow.md`.
- **다음**: 애플/구글 등 추가 스타일 원하면 질문지 먼저 드리고 컨펌 후 진행(사용자 요청 절차).

### ✅ 완료 — wiki 건강검진 후속조치 3건(별개 작업, 같은 세션)
BRAIN_INDEX.md 6개 레이어 링크 전부 깨져있던 것 수정 / `raw/캡처본`(오타폴더) 정리 /
`wiki/stock_현대백화점_20260507.md`(루트 고아파일) → `L5_섹터/소비내수/stock/`로 정식 이전.

---

## [세션 B] 텔레그램 뉴스릴레이 파이프라인 + 일일검증 에이전트 (완료)

**날짜**: 2026-07-03 · **PC**: DESKTOP-T8CB1GG

## 이번 세션(텔레그램+검증에이전트+대시보드UI) 요약 — 전부 완료·배포됨

### ✅ 텔레그램 뉴스릴레이 → 히트맵 파이프라인 실전검증·버그수정
- 4개 채널(주식픽/실시간속보단독뉴스/실시간주식뉴스/그로쓰리서치특징주) 실채널 데이터로
  검증 → 진짜 버그 3개 발견·수정: 중복재게시 필터, 언론 관용약칭(삼전/하닉) 매칭,
  `stock_sector_map.json` 자기참조 항목(시장/자동차 등 18개) 종목 오탐
  (`scripts/telegram_news_filter.py`, `tests/test_telegram_news_filter.py`)
- 크롤 주기 하루5번→**15분마다(7~23시)**로 상향, "주식픽" 타임아웃 40s→90s,
  텔레그램 전용 경량 동기화 스크립트 신설(`scripts/sync_telegram_only.py`, 크론 15분)
- 섹터 키워드 오탐 2건 실사례 발견·수정: "증권"(→증권주 등 구체화), "엔씨"(→엔씨소프트,
  "지엔씨에너지" 종목명 부분매칭 오탐 원인) — `pipeline/sector_news_keywords.json`
- **[마지막 발견·수정]** 텔레그램 뉴스아이템에 `date` 필드가 없어서(ts만 있음) AI 섹터요약의
  "오늘자만" 필터(`_is_today`)에서 텔레그램발 뉴스가 통째로 제외되던 버그. 히트맵엔 텔레그램
  뉴스가 잔뜩 보이는데 AI요약 배지엔 "N건 종합"이 소수만 나오는 걸로 발견됨. `group_by_
  sector_and_stock(matched, date_str)`에 필수 파라미터 추가해 `news_feed._fmt_rss`와 같은
  "MM/DD HH:MM" 포맷으로 date 채움. 배포·테스트(17개) 통과 완료.

### ✅ 일일 검증 에이전트 신설·배포 (사용자 요청: 매일 자동 오류검사+보고 시스템)
- 스펙: `docs/superpowers/specs/2026-07-03-daily-verify-agent-design.md`
- 계획: `docs/superpowers/plans/2026-07-03-daily-verify-agent.md`
- 구현: `scripts/daily_verify.py` + `tests/test_daily_verify.py`(20 테스트) — 크롤신선도(요일별
  4주평균)+pytest회귀+stockbrain서비스상태(재시작1회시도) → 텔레그램 통합보고
- 원격서버 크론 등록: `45 21 * * *`(마지막 인제스트 21:35 이후로 — 최초 21:30 오타 수정함)
- **실행검증 중 실버그 2개 추가 발견·수정**: (1) cp949 콘솔 print 크래시, (2) 원격서버엔
  `python` 명령어가 없는데(`python3`만 존재) 하드코딩 호출→FileNotFoundError가 "측정
  실패=경보아님"으로 조용히 삼켜져 체커가 매일 "정상"으로 오보고할 뻔함 → `sys.executable`
  사용으로 수정. **교훈: 이런 유형의 "체커 자체가 무력화되는 버그"가 제일 위험 — 로컬
  개발환경과 배포환경 차이를 항상 실배포 후 재검증할 것.**
- 외부 도달성(서버 자체 네트워크 장애) 체크는 명시적으로 범위 밖 — 같은 날 실제로 서버가
  2번 다운됐는데(AWS 네트워크단 장애, 원인불명) 온서버 체커로는 원리적으로 감지 불가함이
  실증됨. 필요시 UptimeRobot 등 외부서비스 가입 권장(안내만 함, 계정 필요해 대신 못 함).

### ✅ 대시보드 UI 개선 3건
- 섹터상세 팝오버: 종목 등락률(`kis_api.get_price`) 추가 + 폭 300→420px 확장.
  KIS API 500 일시장애 대응 1회 재시도 추가(5분 캐시라 실패시 오래 굳는 문제 발견·수정)
- AI 요약 출처 표기 "Gemini"→"STOCK BRAIN" (2곳)
- AI 요약 프롬프트에서 "유튜브 채널 애널리스트/시청자" 프레이밍 제거 → 대시보드에
  "안녕하세요 시청자 여러분" 같은 영상 인트로가 섞여 나오던 문제 수정(섹터+종목 요약 2곳)

### 배포 상태
전부 `git push` + 원격서버(stockbrain1.duckdns.org) pull+재시작 완료, 브라우저로 실제
렌더링 확인 완료. 남은 작업 없음.

### 🚨 동시세션 충돌 패턴 (이번 세션에도 반복 발생 — 계속 주의)
원격서버 배포 시 `git pull`이 여러 번 다른 세션의 커밋(YT 대시보드/클레이 프리셋/기타)과
충돌 — 매번 `git stash push -u` → pull → `stash pop` → (충돌시 `atoms.db`/캐시성 JSON 등
데이터파일은 `--ours` 유지, 코드파일은 없었음) 패턴으로 안전 처리함. **다음 세션도 배포 전
항상 이 패턴 사용.**

---

## [다른 세션 기록, 미완료] YT 대시보드 ①기획단계 — Task 5 남음

**주제**: 유튜브 영상제작(기획→대본→리모션→녹음→자막→렌더) 통합 대시보드 첫 단계.
Task 1-4 완료(hot_clips.py, /yt/hot_clips, plan_stage.py, /yt/generate_plan SSE),
**Task 5**(`dashboard/yt.html` + `GET /yt` 라우트)만 미시작 — HTML/CSS/JS는 계획서에
이미 작성돼 있어 transcription+테스트만 하면 됨. **render 산출물이라 실제 브라우저
구동 확인 필수(자동테스트만으로 완료 처리 금지).**

- 스펙: `docs/superpowers/specs/2026-07-03-yt-기획단계-대시보드-design.md`
- 계획: `docs/superpowers/plans/2026-07-03-yt-기획단계-대시보드.md`
- 원장: `.superpowers/sdd/progress.md`
- Task 5 리뷰 → 전체 브랜치 최종 리뷰 → `superpowers:finishing-a-development-branch`
- 배포: git push만 완료, Lightsail 서버 배포는 Task5 완성 후 별도 진행
- ②대본 ③리모션 ④녹음 ⑤자막 ⑥렌더는 범위 밖(①기획 확인 후 별도 사이클)
