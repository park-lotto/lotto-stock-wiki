# 해외HOT 원본영상 조기발굴 — 설계

- 날짜: 2026-07-24
- 트랙(구현 시): 해외HOT (아직 생성 전 — writing-plans 후 executing-plans에서 트랙 생성)
- 상태: 설계 승인됨(사장님 "무료로 해봐") → 스펙 작성 → 사장님 검수 대기 → writing-plans

## 1. 목표

해외에서 **터지는 중인 원본영상**을 국내 재편집본보다 **먼저** 발굴해, 숏템박스
**레퍼런스랭킹 하위 "🌍 해외HOT" 탭**에 카테고리별 큐로 쌓는다. 각 항목에서 재편집
파이프라인(mix)으로 바로 넘긴다. 용도 두 가지를 한 엔진으로 처리:

1. 리액션·재편집 쇼츠 소재 (해외 웃긴·놀라운·감동 클립)
2. 커머스 쇼츠 소재 (해외에서 터진 제품영상 — `#tiktokmademebuyit` 계열)
3. (부산물) 매일 "해외에서 뭐가 뜨는지" 트렌드 인텔리전스 = 위 큐 자체가 리포트

## 2. 핵심 개념 — "발굴" ≠ "등록채널 랭킹"

병행 중인 `2026-07-24-레퍼런스랭킹-5플랫폼확장-design.md`는 **내가 등록한 채널**을
여러 플랫폼에서 랭킹한다. 본 설계는 **내가 아직 모르는** 신규 바이럴을 **발굴**한다.
둘은 같은 화면(레퍼런스랭킹) 아래 공존하는 별개 모드다.

**"먼저 찾기"의 정의**: 이미 뜬 영상이 아니라 **속도(velocity)가 붙는 중인 영상**을 잡는다.
- 속도 = 반응수 ÷ 경과시간
- 가속 = 이번 스냅샷 Δ − 직전 스냅샷 Δ (매일 스냅샷 2회분부터 성립)
- **선점 갭** = 국내 재편집본이 아직 없음 (참고 뱃지, 필터 아님)

## 3. 비용 — 100% 무료 (v1에서 Apify 미사용)

사장님 확정: **v1은 완전 무료.** clockworks/tiktok-scraper($1.70/1,000 results)는 v1에서
쓰지 않는다. 무료 조달 경로:

| 소스 | 조달 | 비용 |
|---|---|---|
| Reddit rising/top-day | 공개 `.json` 엔드포인트 | 무료 |
| Reddit이 링크한 원본 TikTok/YouTube URL | yt-dlp 메타·다운로드 | 무료 |
| 해외 시드계정(TikTok) 최근영상 | yt-dlp `tiktok:user` (5플랫폼확장이 구축) | 무료 |
| 선점뱃지 국내검색 | YouTube Data API 무료쿼터 | 무료 |

**TikTok 해시태그 "검색"은 무료로 불가** → 그 공백은 Reddit 정찰이 메꾼다(아래 4절).
Apify 해시태그 검색·자동 시드수확은 **v2 선택 토글**(6절 범위밖).

## 4. 아키텍처 — Reddit 정찰 → yt-dlp 정밀타격

```
매일 배치(overseas_hot):
  for 카테고리 in 시드팩:
    ── 정찰(무료) ──────────────────────────────
    reddit = 각 서브레딧 /rising.json + /top.json?t=day     # upvote속도로 급상승 감지
    for 포스트 in reddit:
        원본URL = extract_media_url(포스트)                  # v.redd.it / youtube / tiktok / streamable
        if 원본URL 이 tiktok·youtube:
            메타 = yt-dlp 로 조회수·좋아요·게시시각 보강(무료)
    ── 시드계정(무료) ──────────────────────────
    for 계정 in 카테고리.시드계정:
        영상 = yt-dlp tiktok:user 최근목록(무료)             # TikTok-네이티브 트렌드 일부 커버
    ── 랭킹·뱃지·저장 ─────────────────────────
    items = build_reddit_items(reddit) + build_tiktok_items(시드계정)
    apply_grades(items)                                      # ranking.py 재사용
    for top N in items: gap_check(item)                      # 선점뱃지, 무료쿼터 캡
    카테고리 태그 부여 → overseas_hot 피드에 누적 저장(로테이션)
```

**Reddit이 "무료 정찰병"인 이유**: `/rising`은 플랫폼이 직접 계산한 "지금 표가 빠르게
붙는 중" 피드다. 우리가 추측하지 않는다. 포스트가 원본 TikTok/YouTube를 링크하면
그 URL을 yt-dlp로 무료 수집 → 탐색을 Reddit이 공짜로 대신한다.

## 5. 컴포넌트 명세

### 5.1 `reddit_source.py` (신규)
- **입력**: 서브레딧명 리스트, 정렬(rising|top), window_hours
- **동작**: `https://www.reddit.com/r/{sub}/{sort}.json?limit=50&t=day` GET
  (top은 `t=day`). 적절한 User-Agent 필수(없으면 429).
- **원본 URL 추출** `extract_media_url(post)`:
  - `post.is_video` → `media.reddit_video.fallback_url` (v.redd.it, yt-dlp 다운로드 가능)
  - 아니면 `post.url` (외부: youtube.com/youtu.be, tiktok.com, streamable, redgifs, imgur)
  - 텍스트/이미지 전용 포스트는 제외(영상 없음)
- **정규화 출력 dict** (build_reddit_items가 소비):
  ```
  {source:"reddit", post_id, subreddit, title, permalink,
   media_url(원본영상), media_platform("tiktok"|"youtube"|"reddit"|"other"),
   thumbnail, ups(upvote), num_comments, created_utc → published_at(ISO)}
  ```
- **안정성**: 서브레딧당 재시도 2회 + 호출 간 간격(1s), 부분실패 허용(한 서브레딧
  죽어도 나머지로 진행), 429 시 backoff.

### 5.2 yt-dlp 메타 보강 (기존 자산 재사용)
- 시드계정: `tiktok_client.fetch_account_videos`(이미 존재, 무료, 재시도 내장).
- Reddit이 링크한 개별 URL: yt-dlp `-J`로 단건 메타(조회수·좋아요·게시시각).
  `media_download.py`/`tiktok_client._fetch_once` 패턴 재사용해 단건 어댑터 하나 추가.
- 실패(비공개·삭제·지역차단)는 빈 결과로 건너뛴다 — Reddit 지표(upvote)만으로도 랭킹 가능.

### 5.3 시드팩 (카테고리 → 소스 매핑) — `overseas_seeds.json` (신규 데이터)
레퍼런스 카테고리를 그대로 사용. 각 카테고리에 서브레딧 묶음 + 해외 시드계정 묶음.
**초안값**(사장님 승인 후 확장):

| 카테고리 | Reddit 서브레딧 | TikTok 해외 시드계정(예시, 추후 채움) |
|---|---|---|
| 주방/레시피 | GifRecipes, foodhacks, cooking | (채움) |
| 살림/생활꿀템 | lifehacks, CleaningTips, BuyItForLife | (채움) |
| 인테리어 | InteriorDesign, CozyPlaces | (채움) |
| 자취템 | organization, simpleliving | (채움) |
| 가전템 | gadgets, BuyItForLife, tiktokmademebuyit(서브레딧) | (채움) |
| 뷰티 | SkincareAddiction, MakeupAddiction, beauty | (채움) |

- 서브레딧·시드계정은 JSON에서 관리 → 코드 수정 없이 사장님이 추가/삭제.
- 시드계정은 v1 초기엔 비어도 됨(Reddit만으로 가동). 운영하며 "잘 터지는 계정" 발견 시 등록.

### 5.4 랭킹 어댑터 `build_reddit_items` (ranking.py에 추가)
- 기존 `build_tiktok_items`/`build_youtube_items`와 동일 구조.
- **주신호 = upvote** (조회수 대신): `base_count=ups`, `speed=ups/age`,
  `density=num_comments/ups`(반응밀도), `accel=Δ−직전Δ`.
- `apply_grades`는 그대로 재사용(정규화 후 균등 종합). **소스가 섞여도**(reddit upvote vs
  tiktok 조회수) 각자 정규화되므로 카테고리 내 상대순위로 비교 가능.
- 5플랫폼확장의 지표 표(속도=반응/경과, 밀도=반응율)와 정합 유지.

### 5.5 선점체크 `gap_check.py` (신규)
- **입력**: item(title). **동작**: `youtube_search`(기존)로 title 핵심구절을 한국어 검색.
- **판정**: 최근(예: 30일) 한국어 제목 결과가 임계 이상 → `이미유입`,
  없으면 `🔥선점가능`, 검색실패 → `미확인`.
- **캡**: 매 배치 상위 N개(예: 카테고리당 15개)만 체크 → YouTube 무료쿼터(≈100검색/일) 보호.
- **필터 아님**: 뱃지만 부여, 랭킹에서 거르지 않는다(사장님 확정 — 최종판단은 사람).

### 5.6 배치잡 `overseas_hot_jobs.py` (discover_jobs 패턴 재사용)
- `discover_jobs.py`의 백그라운드 스레드 + 폴링 구조를 그대로 복제.
- **트리거**: (a) 탭의 `지금 업데이트` 버튼 (b) 매일 밤 자동 1회(기존 daily_batch/스케줄러 연계).
- **저장**: Store에 `overseas_feed`(레퍼런스 discovery_feed와 분리) — 카테고리 태그 포함.
  스냅샷 이력(prev_base/prev_delta)은 기존 Store 이력 메커니즘 재사용(가속계산).
- **로테이션**: `merge_feeds(cap)` 재사용 — 신규 우선 배치 후 상위 cap개만 유지(성과 낮은 것 자연 탈락).

### 5.7 UI — 레퍼런스랭킹 하위 "🌍 해외HOT" (refs/index 탭)
- 5플랫폼확장이 되살리는 `#platformTabs` 구조에 **발굴 탭 하나** 추가(플랫폼 토글과 별개 레인).
- **카테고리 필터**: 레퍼런스와 동일 카테고리 칩(주방/살림/인테리어/자취/가전/뷰티) — 사장님이
  "가전템 해외HOT"만 눌러 봄.
- **행 구성**: 썸네일 · 속도등급 · **선점뱃지(🔥/이미유입)** · 소스(레딧/틱톡) · 원본링크 · [재편집] 버튼.
- 저장/상태 패널은 기존 플랫폼별 구조·시스템상태 패널 재사용.

## 6. 단계 (한 번에 다 하지 않는다)

- **Phase 1 — Reddit 발굴 + 랭킹 + 탭(무료)**: reddit_source + build_reddit_items +
  overseas_hot_jobs + 탭 UI + 카테고리 필터. 이것만으로 "해외 급상승이 매일 큐에 쌓인다"가 실물로 섬.
- **Phase 2 — 선점뱃지 + yt-dlp 메타보강**: gap_check + Reddit URL/시드계정 yt-dlp 보강.
- **Phase 3 — 재편집 연결**: [재편집] → mix 파이프라인 인계(원본 다운로드 → produce).

Phase 1만으로도 최소가치(매일 무료 해외 발굴 큐)가 선다.

## 7. 데이터 스키마 요약

- **overseas_seeds.json**: `{카테고리: {subreddits:[...], seed_accounts:[{platform,handle}...]}}`
- **overseas_feed item**: 정규화 dict(5.1) + `category`, `grade`, `score`, `speed`, `accel`,
  `density`, `gap_badge`("🔥선점가능"|"이미유입"|"미확인"), `snapshot_ts`.
- **Store**: `save_overseas_feed`/`load_overseas_feed`(discovery_feed와 분리), 이력은 공용 재사용.

## 8. 테스트 전략

- `reddit_source`: 고정 JSON 픽스처 → extract_media_url 분기(video/외부/텍스트) 단위테스트.
- `build_reddit_items`: upvote 기반 지표·48h 필터·is_new/accel 계산(기존 랭킹 테스트 패턴 준용).
- `gap_check`: youtube_search를 목(mock)해 판정 3분기 테스트.
- `overseas_hot_jobs`: 수집 fn 목으로 병합·로테이션·부분실패 허용 검증.
- 네트워크 실호출 테스트는 별도 마킹(기본 CI 제외) — 기존 관행 준수.

## 9. 범위 밖 (YAGNI — v2 이후)

- **Apify TikTok 해시태그 검색** 토글(유료). 무료 커버리지가 아쉬울 때만.
- **Reddit 키워드 → TikTok 해시태그 자동수확**(Apify 유료 검색과 세트라 v2).
- **성과 기반 시드 자동 로테이션**(승격/탈락) — 수동 관리로 시작, 데이터 쌓이면 자동화.
- 샤오홍슈·도우인 등 CN 소스(5플랫폼확장 Phase 3와 중복 — 그쪽에 위임).
- 플랫폼/소스 통합 단일순위(지금은 카테고리 큐 안에서 정규화 비교).
