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
