# API관측판 — handoff

## 2026-09-01 (회사PC, 새벽) — API 관측판 신설 + 관측 사각 4건 수리

### 사장님 지시 (원문 요지)
"오늘 계속 사고가 발생했어. 제미니 api 때문에. 현재 상황을 물어봐도 잘 모르고 뭘
고쳐야 할지 계속 두더지잡기. 어떤 곳에 어떤 api가 붙어있고 상태·로테이션 약속·
모자라지 않은지, 몇 단계에서 문제나는지 실시간으로, 예방·준비·대응까지 —
최적의 방향으로 페이블이 만들어라."

### 착수 전 실측 (2026-09-01 새벽, 서버 3.35.251.172)
- 08-31 하루 제미니 429: **워커 2,524건 + 웹 24건**, 401 계정사망 호출 9건
- 피크 15시(시간당 390건), 주 타격 gemini-3.1-flash-lite(1,260건)
- 라이브 키풀: SHORTS 제미니 **사장님 1 + 회원 58** / 유튜브 10+37 / vault(.env) 26개
- ★두 env 파일: systemd(/etc/shopping-shorts.env)엔 GEMINI_API_KEY 0개,
  .env(vault가 직접 읽음)에 26개 — 풀마다 사는 파일이 다르다
- 기존 키 현황 API(/api/refs/api_usage)는 08-27 상태포맷 변경(list→dict)을 못 따라가
  **TypeError → exhausted_today 항상 0** ("물어봐도 모르는" 직접 원인)

### 만든 것 (커밋 참조)
1. **`shopping_shorts/api_health.py` (신규)** — 데이터층
   - `api_events` 테이블(reference.db): 외부 API 1콜 1행(성공 포함). 서비스·풀·
     키(끝 6자 마스킹)·기능(op)·outcome(rpm/rpd/auth_dead/silent_fallback/lock/revive…)·
     원문 500자·소요ms·프로세스(web/worker/bulk)
   - `classify()` — 에러 분류 **한 곳**(key_vault 판정 재사용, 0순위-B)
   - `snapshot()` — 두 제미니 풀 + 타 서비스 + 수집 systemd 유닛 상태
   - `aggregates()/verdict()/budget()` — 집계·판정 한 줄·RPD 예산(태평양시 하루 창)
   - `heartbeat()` — 프로세스별 키풀 합류 신고(08-31 "워커가 회원키를 몰랐다" 사고를
     화면에서 즉시 보이게)
   - 가드: 관측 실패 전부 삼킴 / pytest 중 라이브 reference.db 기록 차단 /
     API_HEALTH=0 킬스위치 / auth_dead 발생 즉시 ops_alert(30분 쿨다운)
2. **배선 (한 깔때기 원칙)**
   - `usage_meter.MeteredClient.generate_content` — 성공·실패 모두 api_events로.
     34개 호출부 자동 커버. wrap(pool=, key=)로 키 귀속(생성부 6곳 전달)
   - `comment_gen` 잠금·되살림 이벤트 / `key_vault.mark_exhausted` 잠금 이벤트
   - `tts.py` — ★무음 mp3 폴백을 silent_fallback으로 기록(완전 사각이었음) +
     일레븐랩스·타입캐스트 HTTP 실패 기록
   - `keypool.resync_pools` → heartbeat / `capacity_watch` 크론(5분)에 무인 판정 얹음
3. **수리 4건**
   - /api/refs/api_usage exhausted_today TypeError (dict 포맷 대응, `_live_exhausted()` 사용)
   - `product_facts.py` — 유일하게 usage_meter 미배선이던 생성부: wrap+타임아웃 120초
     (비용·429가 어디에도 안 보이던 경로)
   - serpapi "run out of searches" → rpd 분류
   - usage_meter `_op_from_stack`에 api_health 스킵 + tts→음성합성 op 추가
4. **화면 `/apiwatch`** (static/apiwatch.html, ops.html 철학 계승)
   - 판정 배너(한 줄+처방) → 카드 → RPD 예산(소진 예상시각·필요 키 수) →
     시간대별 호출·실패 → 서비스별 표 → **단계(op)별 실패 지도** → 실시간 사고
     피드(원문 그대로) → 키 상세(잠금 남은 시간) → 하트비트 → 로테이션 계약
     (POOLED/WIRED/페이서/TTL을 코드에서 실시간으로 뽑음 — 손으로 안 적음) → 읽는 법
   - admin.html 퀵버튼 + ops.html 상호링크. `_require_admin`+`_NOCACHE`
5. **테스트 28건** (`tests/test_api_health.py`) — 분류는 실사고 원문으로, 배선은
   "행이 실제로 박히는지"로, 엔드포인트는 실제 호출 1회(NameError류 차단).
   `test_byok_gemini_wiring` 단일출구 가드에 api_health 관측전용 예외 추가(사유 주석).

### 검증
- pytest test_api_health 28건 + key/vault/meter/tts/byok/charge 부분집합 **718+34 passed**
- 화면: 스텁서버(진짜 api_health 함수+실사고 모양 이벤트)로 실렌더 — 콘솔 오류 0,
  전 패널 렌더 확인(스크린샷 검수), 발견 결함 3건 즉석 수리

### ⏭ 다음 (관측판이 실측을 준 뒤에)
1. **서버 실기 검증**: 배포 후 /apiwatch 열어 실이벤트 유입·판정·예산 확인
2. **429 대기 없는 호출부 통일** — thumb_title·seo_generate(즉시 다음 키),
   ai_categorize·coupang_query·element_stats·structure_analyze·topic_grouper
   (429 구분 없이 포기), script_generate(처리 전무). edit_plan의 RPM 22초 대기
   패턴으로 통일할 후보 — **관측판 실측으로 우선순위 정한 뒤**
3. **뭉갠 문구 잔존**: app.py 12644·12657("키 소진 또는 응답 오류")·2965·3029·3058·2217
   — 이제 api_events에 원문이 남으니 문구를 사유 연동으로 교체 가능
4. **풀 교차 마킹**: edit_plan이 SHORTS 키를 빌려 소진돼도 vault에만 기록 —
   comment_gen 상태파일엔 안 박힘(관측판 키 상세에서 어긋남이 보이면 착수)
5. 죽은 사장님 vault 키 제거(.env) — 관측판 auth_dead 표에서 tail 확인 후
6. Webshare 프록시 잔액: API 토큰이 없어 실패 이벤트로만 감시 중 — 토큰 받으면 잔액 패널

### 함정 (다음 세션 주의)
- api_events는 **성공도 기록**한다(키별 RPD 카운트용) — 볼륨은 gemini_usage와 동급
- 예산 창은 태평양시 자정(서머타임 UTC-7 근사) — KST 오후 4~5시경 리셋
- 관측판이 0건이면 API_HEALTH=0/배선누락부터 의심(화면 읽는 법에도 적어둠)
- vault 잠금은 여전히 TTL 없음(당일 낙인) — 계약 패널에 그 사실을 표시만 해둠

### 2026-09-01 새벽 2차 — 적대 리뷰 라운드 (병합 a37e62cec)
4렌즈(핫패스/SQL/동시성/화면계약)×적대검증 워크플로가 20건 발견 → 18건 확정 → 전부 수리:
- ★예산 used에 lock 이벤트 혼입(429 1건=2행) / ★cap 회원키 이중계산(두 풀 합산) —
  "키가 모자란가"에 과장/낙관 양방향 왜곡이던 2건이 핵심
- purge 하루1회 게이트·pytest 가드 / vault 잠금기록 파일락 밖으로 / 기록 핫패스
  DB 대기 2초 상한 / API_HEALTH=0이면 판정도 쉼 / BYOK 키사망 경보 처방 분기 /
  워커 카드 최근 1시간 창 / heartbeat 7일 보존 / import try 안으로
- 검증: api_health 31건 + key/vault/meter/byok 부분집합 619건 green
- 라이브 확인: 웹 01:44 재시작(키풀 제미니 1+64=65 합류 로그), /apiwatch 진입 가능

---

## 2026-09-01 새벽 3차 — VMake·TTS 키 필수 차단 (⚠️커밋만, **미배포**)

### 사장님 지시
- "v메이크랑 tts는 없으면 못하게 막아"
- "그 사람들이 해당 단계에서 실패했을 때 안내문구를 띄우면 된다"
- "포인트제도를 다 없애" (→ 차단이 먼저라 포인트 화면 제거는 후속)
- "박2/관리자/용석/정훈 4명은 제외한다"
- **배포는 오전 9시부터** (지시 시각 새벽 3시)

### 왜 (실측)
회원이 키를 안 내면 **사장님 VMake·일레븐랩스 계정으로 돌면서** 포인트만 깎였다.
회원들은 포인트를 쓰는 줄도 몰랐고(설명받은 적 없음), 잔액이 남은 회원만 조용히
통과해 "어떤 사람은 되고 어떤 사람은 안 되는" 상태가 됐다.
- 최근 30일 제작 46명 중 **16명이 음성 키 없이 86건** 제작
- 잔액 105,530P(이정훈)·98,640P(용석) — 한참 더 태울 상태였다
- 유영창(261): 제미니 5개·SerpAPI 1개는 등록, **VMake·일레븐랩스 0개** → 사장님 키

### 한 것
- `keyroute`: `REQUIRE_OWN_KEY`(vmake·elevenlabs·typecast) + `block_reason`/`tts_block_reason`
  + **`BLOCK_EXEMPT_CIDS = {4,5,9,11,12}`**(현경·용석2계정·이정훈·박2). 판단은 한 곳.
- `app.py`: 진입 게이트 8곳 → 402 `need_own_key` + `settings_url`. `clean_failure_kind`에 사유 추가.
- `mix_pipeline._charge_clean`: 포인트 차감 → **키 없으면 거절**(워커 경로).
- 화면: produce.html 안내·settings.html '내 키 필요' 배지·sidebar.js 모달이
  결제 CTA 대신 **키 등록 버튼**을 띄운다(실렌더로 확인). 죽은 링크 `/keys`→`/settings#keys`.
- 테스트: `test_require_own_key.py` 22건 신설, `test_byok_vmake_charge.py` 재작성. 938건 green.

### ⛔ 배포 전 반드시 고칠 것 — 감사(4렌즈×적대검증)가 확인한 결함
**지금 배포하면 "안내 없이 조용히 실패"가 남는다. 사장님 요구의 정반대다.**

1. **`/api/mix/render`(최종렌더)에 게이트 없음** — 키 없이 렌더가 끝까지 돌아
   **무음 영상**이 나가고 화면은 "✅ 렌더 완료". (app.py:4817)
2. **`/api/produce/mix/preview`·`/api/mix/candidate`·`scene_lab narration`에 게이트 없음**
   — 같은 무음 경로. (app.py:4919·3359·5135)
3. **`resynth_one_beat`·`_conform_beats`에 customer_id 미전달** → 게이트를 통과한
   회원의 재합성이 **사장님 키로 나간다**(막으려던 누수가 이 경로로 잔존).
   (mix_pipeline.py:3039·546)
4. **'전체 음성 생성'이 402를 안 읽고 폴링만** → 2.5초 뒤 **거짓 "✅ 완료"**.
   (produce.html:12842)
5. **게이트가 막으면서 `uncount`·`release_mix_claim`을 안 함** → 체험회원은
   평생 1회가 날아가고 30초간 409. (app.py:3480·14672)
6. 안내 헬퍼를 6개 호출부 중 2곳만 씀(복제·재생성·미리듣기가 '❌ 실패'로 뭉갬).
7. `/settings#keys`가 `initTab`에서 처리 안 됨 → 안내를 눌러도 키 탭이 안 열릴 수 있음.
8. `_USER_ERROR_RULES`가 차단 문구를 "잠시 후 다시 시도"로 뭉갬(app.py:3918).
9. 관리자(`customers.admin=1`)는 면제 안 됨 — cid 0만 통과(현경은 명단에 넣어 해결).
10. `tts.py` 무음 폴백이 회원(cid≠0)에겐 **예외를 던져야** 워커가 실패로 떨어지고
    안내가 화면에 닿는다 — 근본 수정 위치.

### ⏭ 다음 세션 (9시 이후)
1. 위 10건 수정 → 테스트 → **그 다음에 `finish`**(지금 배포 금지)
2. 포인트 화면 제거(settings 💎탭·admin UI·sidebar 문구) — 차단이 걸려 급하진 않음
3. 배포 후 /apiwatch에서 `need_own_key` 이벤트로 실제 차단 관측

### 막히는 회원 16명(면제 4명 제외 시 12명)
김데릭(241)·박준영(260)·김승식(79)·최일환(291)·유영창(261)·문혜린(232)·
김미화(222,344)·임상현(247)·백지훈(235)·홍영현(231)·박루아(223)·(14)

---

## 2026-09-01 04:11 — 죽은 키 진짜 제거 (앞선 조치는 오진이었다)

### 경위 — 내가 두 번 틀렸다
1. 관측판 피드에 `auth_dead` 12건이 떠서 사장님이 "이렇게 많이 죽은 게 맞냐"고 물으셨다.
   → 실제로는 **죽은 키 1개(`…VRgKpw`)를 34분간 12번 때린 것**이었다(피드가 12줄로
   펼쳐져 무더기 사망처럼 보였다). 피드를 묶어 보이게 고쳤다.
2. 범인을 **크롤봇(`crawling_bot/main.py`)**으로 지목하고 재시작했다 → **틀렸다.**
   재시작 후에도 30건이 더 났다. 크롤봇 env엔 그 키가 아예 없었다(실측 0건).

### 진짜 범인 (실측으로 확정)
**`/etc/stockbrain.env`의 `GEMINI_BRIEFING_KEY`** — `stockbrain.service`
(`dashboard/server.py`)가 이 값을 들고 12분마다 3모델을 헛호출했다.
- 확정 방법: `/proc/<pid>/environ`을 뒤져 **어느 프로세스 env에 그 키가 있는지** 직접 확인
  (dashboard 1건 / 크롤봇 0건) → `systemctl status <pid>`로 유닛 역추적
- 그 키 실호출 → **HTTP 401** 확인 후 제거

### 조치
- 백업: `/etc/stockbrain.env.bak.0901_0410`
- `sed -i '/^GEMINI_BRIEFING_KEY=/d'` → `systemctl restart stockbrain`
- 새 PID env에 죽은 키 **0건** 확인
- briefing 그룹은 이제 키 0개지만 `get_live_keys_cascade`가 다른 그룹으로 폴백한다
  (key_vault.py `_cascade_groups`) — 브리핑 기능은 계속 돈다

### ★교훈 (다음에 같은 걸 만나면)
```
□ 파일(.env·systemd env)에 없다고 "없다"고 결론내지 마라 —
  **프로세스 메모리**에 남아 있고, env 파일이 여러 개다
  (/etc/shopping-shorts.env · /etc/stockbrain.env · 프로젝트 .env — 셋 다 봐야 한다)
□ 범인은 /proc/<pid>/environ 으로 **직접** 찾아라. 시각·주기로 추론하면 틀린다
  (나는 12분 주기만 보고 크롤봇으로 오진했다)
□ "재시작했으니 됐다"고 하지 말고 **다음 주기까지 지켜봐라** — 30건이 더 났다
```
