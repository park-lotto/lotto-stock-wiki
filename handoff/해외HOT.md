# 해외HOT 발굴 — 핸드오프

- 갱신: 2026-07-29 밤 (집→회사 인계) / 트랙: 해외HOT (병합 후 폴더 유지)

## 🏢 다음 세션(회사)이 여기부터 읽으면 됨 — 오늘 배포된 것 4개 + 현재 서버 상태

**오늘 집에서 커밋·배포한 것(시간순, 전부 `.tracks/해외HOT`에서 TDD로 작업 후 `finish`로 main 병합)**:
1. **샤오홍슈 무료 크롤러 Phase 1** — `shopping_shorts/playwright_crawl.py` 신규. 로그인 세션으로
   검색 API 직접 호출, Apify 안 씀.
2. **검색 정렬 최신순 강제** — 기본 인기순(general)이던 걸 요청 body의 `sort`를 `time_descending`으로
   가로채기(route 인터셉트)로 바꿔치기. 서명검증이 이 필드는 안 잠가서 통과됨(실측 확인). "昨天/今天
   HH:MM" 날짜 형식 파싱 추가.
3. **썸네일 자막(텍스트오버레이) 필터** — `video_analysis.text_level_vision`(Gemini 비전, 기존
   비전태그 인프라 재사용) + `overseas_funnel.passes_caption_clutter`. 부수 수정: `fetch_thumb_bytes`가
   인스타 전용 Referer만 있어 샤오홍슈 CDN(xhscdn.com)에서 전부 403 나던 버그도 같이 고침
   (`_referer_for` 도메인별 분기).
4. **틱톡·도우인 켜기/끄기 스위치** — `config.OVERSEAS_TIKTOK_ENABLED`/`OVERSEAS_DOUYIN_ENABLED`
   (기본 true). 틱톡은 캡차로 무료전환 포기 확정, 도우인은 미착수 — 둘 다 재개발 전까지 "지금
   업데이트"가 불필요한 Apify 비용을 안 쓰게 껐다.
5. **탭 전환 시 진행률 표시 이어보이기** — `static/index.html`. 수집 자체는 카테고리 무관 단일
   백그라운드 작업이라 서버는 안 멈추는데, 폴링이 "지금 업데이트" 클릭 시에만 시작돼 탭 갔다오면
   화면엔 표시가 없어 멈춘 것처럼 보이던 문제. `resumeOverseasStatusIfRunning` 추가.

**⚠️ 서버(`/etc/shopping-shorts.env`)에 직접 설정한 값 — git에 없음, 코드 기본값과 다름**:
```
XHS_SCRAPER=playwright          # 기본값 apify인데 서버는 켜둠 — 샤오홍슈 무료크롤 라이브 사용 중
OVERSEAS_TIKTOK_ENABLED=false   # 기본값 true인데 서버는 꺼둠 — 틱톡 발굴 비활성
OVERSEAS_DOUYIN_ENABLED=false   # 기본값 true인데 서버는 꺼둠 — 도우인 발굴 비활성
```
백업 `/etc/shopping-shorts.env.bak-20260729`(오늘 변경 전 상태). 이 세 값을 되돌리려면 저 세 줄을
지우거나 값을 바꾸고 `sudo systemctl restart shopping-shorts`.

**즉 지금 "🌍 해외HOT → 지금 업데이트"를 누르면**: 6카테고리 전부 **샤오홍슈만** 무료로 돌고(최신순
+ 자막적은 것 위주), 틱톡·도우인은 안 돈다. Apify 비용 0.

**⏭ 다음에 할 만한 것**:
- 도우인도 XHS처럼 무료 로그인세션 크롤 시도해볼 수 있는지 조사(미착수, 원래 모바일인증 벽만 확인됨).
- 소스채널 마이닝(②모드, 좋은 계정 등록→매일 직접 크롤) — 설계는 있었지만 구현 안 됨.
- 상시 자동 스케줄(systemd 타이머) — 아직 수동 "지금 업데이트"만 있음.
- 인스타 `/explore/tags/`도 반복요청 소프트블록 관측됨(별도, 손 안 댐).
- `_TEXT_CLUTTER_CAP=15`·`_PER_KEYWORD=40`·정렬강제 방식 전부 실측 하루치라 며칠 더 보고 튜닝 필요.

---

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

---

## ✅ 2026-07-29 (회사) — 자막 없는 썸네일 우선 정렬, 라이브 배포 완료

**한 줄**: 해외HOT 목록에서 썸네일에 자막이 없는 영상이 위로 온다. 사장님 관측("자막 많으면 내용도 지저분")에서 출발.

- 설계: `docs/superpowers/specs/2026-07-29-해외HOT-자막없는썸네일우선-design.md`
- 계획: `docs/superpowers/plans/2026-07-29-해외HOT-자막없는썸네일우선.md` (5태스크 TDD, SDD로 실행)
- 커밋: `a6894cc5e`(캐시테이블) → `279d079d3`(caption_rank) → `3f8233021`(전수판정) → `20452c559`(정렬) → `c5cbffd98`(최종리뷰 수정). finish 게이트 통과 → main 병합.

**바뀐 것**
| | 전 | 후 |
|---|---|---|
| 자막 판정 대상 | 수집순 앞 15개(`_TEXT_CLUTTER_CAP`) | **생존자 전부** + `thumb_text_level` 캐시 |
| 정렬 | `score` 단독 | **`(caption_rank, -score)`** — none→light→(heavy·미판정) |
| `heavy` | 컷 | 컷 유지(변경 없음) |
| 프론트 | — | **미변경**(서버 순서를 그대로 그림) |

**★가장 중요한 교훈 — 테스트 37건이 초록인데 기능은 0% 동작이었다**
개별 태스크 리뷰 4건이 전부 통과한 뒤, **최종 whole-branch 리뷰가 Critical 3건**을 잡았다:
- **C1** `_annotate_text_level`이 `it.get("shortcode")`를 봤는데 **크롤러 raw dict의 키는 `video_id`**다
  (`shortcode`는 나중에 `ranking.build_overseas_items`가 만든다). → 캐시 키가 항상 `None` →
  조회도 저장도 안 됨. 상한을 없앤 상태라 **매 수집마다 전량 재판정**(Gemini 폭증).
- **C2** `build_overseas_items`가 만드는 item dict에 **`text_level` 필드가 없어** 값이 그 자리에서 소실.
  → `caption_rank`가 전부 2 → **정렬 변경이 화면에 아무 영향 없음**.
- **C3** 테스트가 `shortcode`·`text_level`을 **손으로 주입한 dict**를 써서 실제 호출 계약과 달랐다.
  그래서 두 기능이 0% 동작인데 37건 green.

→ 수정 후 **가짜 크롤러 raw(실제 키 `video_id`) → `_run()` → 저장된 피드**를 검증하는 E2E 회귀
테스트를 넣었다(`test_run_e2e_caches_by_video_id_and_sorts_clean_first`). 수정을 하나씩 되돌려
**실제로 실패하는지 확인**했다. 이 테스트가 C1·C2 재발을 막는 유일한 장치다.
**교훈: 픽스처가 주입하는 키를 실제 호출자가 정말 넣는지 grep으로 확인할 것**(memory `feedback_harness_invented_contract`).

**⏭ 다음에 볼 것**
- **첫 수집 실측이 필수다.** 진행표시에 `수집·자막판정 신규N·캐시M`이 뜬다.
  1회차는 신규가 크고 **2회차부터 캐시가 커야 정상**. 안 그러면 캐시가 또 안 먹는 것이다.
- **★미결정(사장님 판단 대기) — 상한 120과 1차 정렬키의 충돌**: `caption_rank`가 1차 키라
  자막 없는 항목이 `_CAP=120`을 넘으면 **자막 있는 항목은 점수와 무관하게 목록에서 사라진다**.
  사장님 선택은 "light는 뒤로 밀기(컷 아님)"였으므로 의도와 어긋날 수 있다. 선택지:
  A. 그대로 / B. 자리 나누기(none 100칸·나머지 20칸, 의도에 가장 가까움) / C. 점수 가산점.
  현재 **A로 배포**됨 — 첫 회차 목록 보고 결정하면 된다.
- `_JOB["phase"]` 카운터는 카테고리별 최신값이지 잡 전체 누적이 아니다(진행표시용으론 충분).
- 2부(인스타 랭킹의 CN 원본 찾기)는 **렌즈로 불가 확정** — 아래 절 참고.

## ❌ 2026-07-29 — 인스타 랭킹의 CN 원본 찾기: 구글 렌즈로는 불가 (실측)
사장님 요구: "인스타 랭킹에 뜬(국내서 이미 터진) 영상의 깨끗한 원본을 찾아달라."
서버에서 제품형 인스타 영상 5건에 렌즈(SerpApi)를 실제로 돌렸다(4건 성공, 1건 이미지 업로드 실패):
- 결과 플랫폼: **유튜브 17 / 인스타 16 / 틱톡 5 — 샤오홍슈·도우인 0건.**
- 구글이 CN 플랫폼을 인덱싱하지 않으므로 렌즈로는 원리상 안 된다.
- **이건 이미 `handoff/렌즈유사영상.md`에 기록돼 있던 사실이다**(렌즈 CN 0건, 샤·도 40개는
  `/api/lens/cn`이 Apify로 긁던 것). 기록을 흘려서 42원을 더 썼다 — **먼저 핸드오프를 검색할 것.**
- 유일한 길은 `/api/lens/cn`(Gemini로 제품명 추출 → Apify 샤오홍슈 키워드 검색) 부활인데,
  **2026-07-19에 사장님이 Apify 과금 때문에 직접 끈 경로**다. 되살릴지는 비용 판단 — 별도 안건.

### ✅ 2026-07-29 오후 — 라이브 실동작 검증 완료 (+ 세션 만료 사고)

**배포 직후 "완료 120건"이 떴지만 실제로는 아무 일도 안 일어났었다.** 원인 추적:
- 피드 갱신시각만 바뀌고 `text_level` 120개 전부 `None`, 캐시 0행.
- 가설을 순서대로 기각 — 썸네일 다운로드 정상(124KB) / Gemini 키 16개·판정 정상(`heavy` 반환) /
  새 코드 배포 확인 / 세션 경합도 아님(크롬 1개인데도 0건).
- **진짜 원인 = 샤오홍슈 로그인 세션 만료.** 크롤이 0건을 받아오니 `_merge_rotate`가 옛 120건을
  그대로 유지 → 판정할 새 항목이 없었다. 서버·로컬 모두 `登录后查看搜索结果`(로그인벽) 확인.

**★세션 재발급 절차(다음에 또 만료되면 이대로)**
1. 로컬 PC에 playwright 필요: `python -m pip install playwright && python -m playwright install chromium`
2. `launch_persistent_context(headless=False)`로 `https://www.rednote.com/explore` 열기 → 폰으로 QR 스캔
3. **로그인 감지 로직을 넣지 마라.** 3초마다 페이지를 다시 여는 폴링을 돌렸더니 QR 인증이
   계속 "실패"로 떨어졌다(실측). 창을 닫으면 저장하는 방식이 안전하다.
4. ⚠️ **`web_session` 쿠키 존재로 로그인 판정하면 안 된다** — 비로그인 상태에도 있어서,
   1차 시도 때 사장님이 스캔하기도 전에 "성공"으로 착각하고 빈 세션을 저장했다.
   **검증은 검색 페이지에 `登录后查看`가 사라졌는지로** 해야 한다.
5. 서버 배치: 기존 파일 백업 → `scp`로 `/home/ubuntu/rednote_session.json` 덮어쓰기 → `chmod 600`
6. 검증: `playwright_crawl.search_full('厨房神器', max_results=5)`가 0건이 아니어야 한다.

**실동작 결과(2026-07-29 14:28 수집)**
```
피드 갱신 14:28 · 항목 120 · 캐시 138행
등급분포: none 27 / light 43 / 미판정 50 / heavy 0(컷)
순서:  1~27 none → 28~70 light → 71~120 미판정
```
상위 12개 전부 `none`이고 제목도 정상 꿀템(`小户型厨房`·`提升幸福感的厨房好物` 등). **설계대로 동작.**

**★상한 120 충돌(설계 §8 미결정)은 실측상 문제 없음** — 자막 없는 항목이 27개라 상한에 한참
못 미친다. 자막 있는 항목이 밀려 사라지는 일이 없으므로 **A(현재 설계) 유지**. 향후 none이
120에 근접하면 그때 B(자리 나누기)를 검토하면 된다.

**미판정 50건**은 이전 수집분(판정 전 시대 항목)이라 자연히 밀려 있다. 로테이션으로 교체된다.

---

## 2026-07-29 (회사) — 독립워커 작업큐 배포 완료

### 무엇을 왜
긴 작업(믹스 렌더·프리뷰·해외HOT 수집)이 FastAPI `BackgroundTasks`로 **서버 프로세스 안에서**
돌아서, 3분 크론 배포가 `systemctl restart shopping-shorts`를 하는 순간 **조용히 죽었다**
(2026-07-29 하루 3건 실사고). 옛 가드는 mix_jobs의 `rendering` 상태만 봐서 해외HOT 수집과
믹스 매칭 단계는 그물에 안 걸렸다.

### 무엇을 했나
`job_queue` 테이블 + **별도 systemd 서비스 `shopping-shorts-worker`**로 실행을 분리했다.
서버는 이제 큐에 넣기만 한다 → **서버는 언제 재시작해도 안전**, 워커만 진행 중이면 재시작 연기.

- `store.py`: `job_queue` 테이블 + `enqueue/claim_next/heartbeat/finish/reap_stale/queue_status`
  (원자적 claim은 SQLite `UPDATE ... RETURNING`, 서버 3.45.1 확인)
- `worker.py`(신규): 6개 태스크(render·preview·overseas 등) 디스패치, 30초 heartbeat 스레드,
  모든 예외를 삼켜 워커 자체는 안 죽는다
- `deploy/shopping-shorts-worker.service`: `Restart=always`, `TimeoutStopSec=1800`
- `deploy/auto_deploy.sh`: 가드를 `job_queue` 기준으로 교체. **배포를 통째로 미루지 않고**
  (`exit 0` → `WORKER_BUSY=1`) 서버는 재시작하고 워커 재시작만 연기.
  ★좀비 가드: heartbeat 2분 미갱신이면 죽은 워커로 보고 안 미룬다(죽은 job이 배포를 영영
  막는 게 이 repo 최악 사고).

### ★리뷰가 잡은 Critical 1건
`start()`가 **서버 프로세스의** `_JOB`을 running으로 세팅했는데 `_run()`은 **워커 프로세스**에서
돈다 → 서버 쪽 상태가 영원히 running에 고착, `app.py:672/708/754` 가드가 **샤오홍슈 발굴을
서버 재시작 전까지 통째로 막을** 뻔했다. `status()`가 `job_queue`를 읽도록 고쳐 해소.
**프로세스가 갈리면 모듈 전역변수는 공유되지 않는다** — 이 전환에서 가장 밟기 쉬운 함정.

### 실측 검증 (라이브 서버)
```
워커 설치 후 enqueue('overseas') → qid=1 state=running, Gemini 판정 실제 진행
★sudo systemctl restart shopping-shorts  → 워커 PID 3863930 그대로, state 여전히 running,
  heartbeat 09:27:36 → 09:28:36 갱신됨   = 서버 재시작이 작업을 못 죽인다(이 작업의 목적 달성)
배포 가드 라이브 실행 → busy_count 1, exit 0 = 워커 재시작 연기 정상 판정
```

### 남은 것 / 주의
- 아직 큐로 안 옮긴 짧은 백그라운드 작업들이 있다(설계 §범위: 긴 것 둘만 먼저). 필요해지면
  같은 패턴으로 `TASKS`에 추가하면 된다.
- **모션레벨훅 트랙도 같은 A안을 시작하려 했다** — 워커는 해외HOT 트랙이 이미 만들어 라이브에
  올렸으니 중복 구현하지 말 것.
