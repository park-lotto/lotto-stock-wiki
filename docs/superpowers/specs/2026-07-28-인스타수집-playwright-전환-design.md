# 인스타 레퍼런스 수집: Apify → Playwright + 주거용 프록시 전환

작성일: 2026-07-28 · 트랙: AI픽자동적재

## 왜 바꾸나 (실측 근거)

서버 `reference.db.collect_jobs` 실측:

| job | 결과 | 소요 |
|---|---|---|
| `e8c0b0cddece` (07-27) | **running인 채로 50분+**, 사장님이 취소 | — |
| `b02e82a04284` (07-25) | done, 345건 | **28분** |
| `9c2035fe6a05` (07-25) | **error** `403 Forbidden` (Apify 액터 run) | 22분 |
| `b574829c9d77` (07-25) | **error** `403 Forbidden` (Apify 액터 run) | 26분 |

세 가지가 동시에 문제다.

1. **느리다** — 성공해도 28분. 채널 200개를 각각 Apify run 1개로 띄우고 15개씩 병렬로 돈다(`apify_client.py:279-293`).
2. **죽는다** — 20분 넘게 끌다 403으로 통째로 실패한 사례가 이틀 새 2건.
3. **멈췄는지 알 수 없다** — `collect_jobs.updated_at`이 생성 시각에서 한 번도 안 바뀐다. 진행률을 쓰는 코드가 없어 화면은 50분 내내 같은 상태다. 사장님이 취소한 직접 원인.

주거용 프록시(Webshare 계열)는 이미 `REDDIT_PROXY`·`YTDLP_PROXY`로 운영 중이다. 그걸 인스타에도 쓰면 Apify 중개를 걷어낼 수 있다.

## 범위

**인스타 하나만.** 조사 결과 「지금 수집」이 실제로 도는 건 인스타·유튜브·틱톡 셋이고, 그중 Apify에 물린 건 인스타뿐이다.

| 대상 | 현재 | 이번 변경 |
|---|---|---|
| 인스타 랭킹 수집 | Apify `apidojo~instagram-scraper-api` | **Playwright로 교체** |
| 틱톡 계정 시드 | 무료 yt-dlp (`service.py:191`) | 그대로 |
| 틱톡 키워드 검색 | Apify (기본 OFF) | 그대로 |
| 유튜브 | `_collect_youtube` | 그대로 |
| 레퍼런스 랭킹의 샤오홍슈·도우인 탭 | 수집 없음 — 인스·유튜·틱톡 랭킹의 파생 트렌드 뷰(`index.html:464`) | 그대로 |
| 해외HOT 샤오홍슈·도우인 | Apify (별도 기능) | 그대로 |

접근 방식은 **비로그인 + 주거용 프록시**(A안). 부계정 세션(B안)은 **만들지 않는다** — 실제 차단 비율을 재기 전에는 필요한지 알 수 없고, 부계정은 정지 위험과 쿠키 갱신 부담을 새로 만든다. 이번 설계는 그 숫자를 얻는 것까지가 목표다.

## 아키텍처

### 교체 지점은 한 곳

```
service.py:246   reels = fetch_reels(usernames)      ← 이 한 줄만 갈아끼운다
```

새 모듈 `shopping_shorts/instagram_playwright.py`가 `fetch_reels(usernames)`와 **같은 시그니처로 같은 계약**을 돌려준다. 계약은 `_normalize_apidojo_item`(`apify_client.py:255-273`)이 이미 확정해 둔 10개 키다.

```
shortcode, url, timestamp, caption,
commentsCount, likesCount, videoViewCount,
displayUrl, videoUrl, ownerUsername
```

이 10개만 맞추면 `ranking.build_items` → `apply_grades` → `save_last_run` → 화면까지 **전부 무변경**이다. `name/username/inpock/followers`는 엑셀 meta에서 오므로 스크레이퍼가 채울 필요가 없다.

`timestamp`는 필수다 — 없으면 `age_hours` 계산이 안 돼 항목이 통째로 드롭된다(`ranking.py:32-34`).

### 롤백 스위치

```
config.INSTAGRAM_SCRAPER = "playwright" | "apify"   # 기본 apify, 검증 후 전환
```

`service.py`가 이 값으로 분기한다. 라이브 대시보드가 인스타 수집에 묶여 있으므로 **환경변수 하나로 즉시 되돌릴 수 있어야 한다**. Apify 경로 코드는 지우지 않는다.

### DOM이 아니라 JSON을 가로챈다

릴스 화면의 조회수·댓글수는 DOM에 온전히 안 나온다(축약 표기·지연 렌더). Playwright의 `page.on("response")`로 인스타가 스스로 부르는 API 응답을 받아 파싱한다.

- 숫자가 **원본 정수**로 들어온다 — "1.2만" 같은 축약을 역산할 필요가 없다.
- 화면 마크업이 바뀌어도 안 깨진다. DOM 셀렉터는 인스타가 수시로 갈아엎는다.

응답 스키마가 바뀔 위험은 남는다. 그래서 **파싱 실패를 채널 단위로 격리**하고(아래), 떠 둔 응답 샘플로 회귀 테스트를 고정한다.

### 동시성과 프록시

```
브라우저 1개
 └ 컨텍스트 5개 (재사용, 각각 프록시 물림)
     └ 채널당 페이지 1회 방문 → 응답 가로채기 → 컨텍스트 반납
```

채널마다 브라우저를 새로 띄우면 느리고 메모리를 먹는다. 컨텍스트를 돌려쓴다.

- 프록시: `config.INSTAGRAM_PROXY` 신규(형식은 기존 `REDDIT_PROXY`와 동일 `http://user:pass@host:port`). 미설정이면 직결로 동작한다(로컬 개발용).
- 동시 개수는 상수로 두고 조정 가능하게 한다(초기 5).
- 채널당 릴스 개수·기간은 기존 값을 그대로 쓴다(`RESULTS_PER_CHANNEL=3`, 2일 이내 — `config.py:126-127`).

**목표: 200채널 10분 내.** 현재 28~50분 대비 개선이 목표이며, 실측으로 확인한다.

### 실패 격리와 분류

채널 하나가 실패해도 전체가 죽으면 안 된다(지금 403이 그렇다). 채널별로 결과를 분류한다.

| 분류 | 판정 |
|---|---|
| `ok` | 릴스 1건 이상 파싱 성공 |
| `login_wall` | 로그인 요구 화면/응답 |
| `not_found` | 계정 없음·비공개 |
| `error` | 타임아웃·파싱 실패 등 |

집계를 job 결과에 함께 담는다. **이 숫자가 B안(부계정) 도입 여부의 판단 근거다** — `login_wall`이 몇 %인지 한 번 돌리면 나온다.

### 진행률 노출

`collect_jobs`에 progress 컬럼이 없다(`job_id, status, result_json, error, created_at, updated_at`). 스키마를 바꾸지 않고, 채널을 처리할 때마다 `result_json`에 부분 payload를 쓴다.

```json
{"phase": "collecting", "done": 37, "total": 200, "items_so_far": 112,
 "ok": 34, "login_wall": 2, "error": 1}
```

프론트는 이미 `/api/collect/status/{job_id}`를 폴링하고 있으므로(`app.py:216-222`) 표시만 붙이면 된다. 화면에 **"37/200 채널 · 112건"**이 뜨면 "멈춘 건가?"가 사라진다.

`_COLLECT_STALE_MIN = 60`(`app.py:259`)은 새 소요시간에 맞춰 낮춘다. 진행률이 갱신되는 동안은 stale로 보지 않도록 `updated_at` 기준으로 판정한다.

## 검증 전략

**1단계 — 파서 단위테스트 (네트워크 없음)**
가로챈 실제 응답을 fixture 파일로 떠서 `_parse_*` 함수를 검증한다. 10개 키가 모두 채워지는지, `timestamp`가 있는지, 숫자가 정수인지. 인스타 응답 스키마가 바뀌면 이 테스트가 먼저 깨진다.

**2단계 — 10채널 실측 게이트 (서버)**
`limit_channels=10`으로 서버에서 돌려 다음을 잰다.

- 성공률(`ok` 비율)
- 채널당 평균 소요
- `login_wall` 비율

**성공률이 낮으면 200채널로 열지 않는다.** 숫자를 먼저 보고하고 B안 도입 여부를 사장님이 정한다. 이 게이트를 건너뛰고 전면 전환하지 않는다.

**3단계 — 전환**
게이트를 통과하면 `INSTAGRAM_SCRAPER=playwright`로 전환하고, 첫 전체 수집의 소요·건수를 Apify 시절(28분/345건)과 대조한다.

## 선행 작업 (리스크)

- **Playwright가 서버에 없다.** 코드에 사용처 0건, `requirements.txt`에도 없다. `pip install playwright` + `playwright install chromium` + 우분투 시스템 라이브러리 설치가 필요하다. 서버 디스크·메모리 여유를 먼저 확인한다.
- **크로미움은 메모리를 먹는다.** 컨텍스트 5개 동시가 서버에서 감당되는지 10채널 게이트에서 함께 관측한다. 안 되면 동시 개수를 줄인다.
- **비로그인 성공률은 해보기 전엔 모른다.** 그래서 2단계 게이트가 설계의 일부다. 낙관도 비관도 하지 않고 숫자로 결정한다.

## 하지 않는 것 (YAGNI)

- 부계정 세션 로그인 — 차단 비율을 재기 전엔 만들지 않는다
- 다른 플랫폼 전환 — 인스타가 자리잡은 뒤에 판단
- Apify 코드 삭제 — 롤백 경로로 남긴다
- 재시도 큐·분산 워커 — 200채널 규모에 과설계
