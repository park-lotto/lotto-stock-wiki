---
name: project
description: 쇼핑쇼츠 영상제작 자동화 SaaS(tubefactory급) — 기능③ 소스매칭 현황과 아키텍처
metadata: 
  node_type: memory
  type: project
  originSessionId: 2fa09dbe-56ae-4b88-a327-fabde1ac5dcf
---

쇼핑쇼츠는 로또의 주식과 무관한 별개 프로젝트. 코드는 같은 저장소의
`shopping_shorts/` 아래(주식위키와 완전히 독립적인 모듈). 서버 배포는
`https://shoppingshorts.duckdns.org`(nginx→127.0.0.1:8849, systemd
`shopping-shorts`), 자동배포는 주식위키와 같은 패턴(push→서버 크론 pull+재시작).

**기능③ "소스매칭"(제품 찾기, `find.html`)의 진짜 목적**: 레퍼런스 인스타
릴스 하나를 분석해서, **다른 사람이 만든 같거나 비슷한 제품을 다루는 영상**을
여러 플랫폼에서 찾아 짜집기(splicing) 소재로 쓴다. "쇼핑몰에서 이 제품 살
곳 찾기"가 아니다 — 2026-07-10 세션에서 이 오해로 SerpApi Google Lens
"구매처 찾기" 기능을 만들었다가 사용자가 정정, 전체 삭제함
([[feedback_confirm_literal_feature_intent]]).

**아키텍처(2026-07-10 최종 — 링크전용, 임베드 검색 완전 폐지)**:
"실수집"(5언어 전부검색+Gemini채점) → "임베드 미리보기"(채점없이 6개씩) →
**링크전용(최종)** 순서로 하루 만에 세 번 갈아엎었다. 결론: Apify 스크래퍼로
결과를 직접 긁어와 화면에 보여주는 "임베드" 자체가 실측 결과 정확한
키워드로도 관련성 30~50%대(예: "리마커블 2" 검색해도 6개 중 2~3개만 관련)
였고, 스크래퍼가 플랫폼 자체 검색 알고리즘(로그인 개인화 포함)을 복제할 수
없다는 **구조적 한계**로 판단 — 경쟁사(tubefactory.kr)도 결과를 임베드하지
않고 키워드×채널 번역 링크만 만들어 클릭 시 그 플랫폼 자체 검색으로
이동시키는 방식이었고, 이걸 그대로 채택했다. 임베드를 포기하니 액터
품질/관련성 문제 자체가 사라짐(플랫폼 자체 검색이니 100% 정확).

- Gemini(`video_analysis.py`)가 레퍼런스 영상 프레임을 보고 ko/en/zh/ja/ru
  5개 언어로 키워드(언어당 여러 개)+카테고리 추출. **response_schema 강제
  추가(2026-07-10 최종)** — response_mime_type만으론 필드 생략이 허용돼
  zh/ja/ru가 실제 프로덕션에서 빈 배열([])로 나오는 버그가 있었음(중국어
  플랫폼이 영어 문구로 검색되던 원인 중 하나). minItems:1로 스키마 강제.
- **`/api/find/collect`(실수집)·`/api/find/preview`(임베드 미리보기) 둘 다
  완전 삭제됨**. 대신 `search_links.py`(`build_search_links`)가 언어별
  키워드 후보 전부에 대해 `{platform: {lang: [{keyword,url}, ...]}}` 링크를
  생성 — `/api/find/analyze` 응답에 포함. similarity.py의 score_candidate는
  호출부가 없어져 죽은 코드로 남음(파일은 안 지움).
- **find.html 최종 UI**: 왼쪽=원본 레퍼런스 영상 플레이어(다운로드된 mp4를
  `/api/find/frame/{work_id}/{filename}`로 그대로 서빙, 프레임과 같은 경로
  재사용). 오른쪽=채널(행)×키워드(열)×언어(셀 안 2줄, 국기 아이콘)
  링크그리드, 🔗(새탭 이동)/📋(복사) 아이콘 버튼. **플랫폼별 기본 언어를
  콘텐츠 언어에 맞게 지정**(샤오홍슈·도우인=중국어+영어, 나머지=한국어+영어)
  — 이전엔 전부 "한국어" 기본값이라 중국어 플랫폼을 영어 문구로 검색하던
  버그가 이걸로 해결됨. 이전에 있었던 "키워드 여러개 선택(칩 클릭→
  keyword_index)" 기능은 임베드 미리보기와 함께 폐기됨 — 지금은 키워드 칩이
  읽기전용 정보 표시일 뿐, 그리드의 각 열이 이미 키워드 후보별로 나뉘어
  있어 클릭으로 "선택"할 필요 자체가 없어짐.
- **다음 세션 주의**: 그리드 열(column) 인덱스가 언어별로 리스트 길이가
  다르면 서로 다른 개념을 가리킬 수 있음(product_identify가 ko/en에만
  프리펜드해서 index0만 어긋남) — 실사용 중 "엉뚱한 키워드끼리 짝지어짐"
  불만 나오면 재검토 필요.
- **분석 단계 병렬화(2026-07-11)**: "분석 버튼이 느리다" 피드백 대응 —
  `analyze_video`(Gemini 영상분석)와 `product_identify`의 SerpApi 렌즈검색이
  서로 입력 독립적(렌즈는 프레임 이미지만 필요, category는 프롬프트 힌트일
  뿐)인데 순차 실행돼 시간이 그대로 더해지고 있었음. `product_identify.py`를
  `fetch_lens_lines`/`identify_product_from_lines` 2단계로 분리, `app.py`에서
  `ThreadPoolExecutor`로 `analyze_video`와 병렬 실행(커밋 `9e4c118c`).
- **배포 확인 시 캐시 함정**: 사용자가 "옛날 UI 그대로"라고 제보했을 때
  서버 git log·서비스 재시작 시각을 먼저 확인하니 이미 최신 배포 상태였음
  — 실제 원인은 브라우저 캐시(강력 새로고침으로 해결). "배포했는데 안
  바뀜" 제보는 서버 상태부터 확인하고 캐시를 의심할 것.
- **인스타 검색 액터 전면 교체(2026-07-10)**: 기존
  `apify~instagram-hashtag-scraper`(해시태그 정확일치 전용, 인스타 자체
  검색보다 부정확)를 버리고 `data-slayer~instagram-search-reels`(자유
  텍스트 키워드 검색)로 교체 — 실측 6/6 정확(reMarkable 등). 공식
  `apify~instagram-search-scraper`의 "인기 릴스 검색" 모드는 두 번 다
  "blocked by Instagram"으로 실패해 배제.
- 플랫폼별 실제 수집 액터: youtube=YouTube Data API, tiktok=Apify
  `clockworks~tiktok-scraper`, instagram=Apify `data-slayer~instagram-search-reels`
  (위 참고), xiaohongshu=Apify `zen-studio~rednote-search-scraper`
  (noteType=video 필터), douyin=Apify `zen-studio~douyin-search-scraper`
  (처음 조사한 `natanielsantos~douyin-scraper`는 흔한 키워드도 0건이라
  보류했다가, 같은 개발자 zen-studio의 다른 액터로 재시도해 성공 —
  **액터 신뢰도는 개발자 단위로 어느 정도 이어짐**, 한 액터가 실패해도
  같은 개발자 다른 제품군 액터를 시도해볼 가치 있음)

**영상 콘텐츠 2종 구분(2026-07-10 사용자 설명, 기능 설계 기준)**:
- **타입A(제품 직접홍보형)** — 지금 설계·구현 중인 방향. 화면 속 정확한
  제품(브랜드+모델)을 확인해야 검색 정밀도가 오름. `product_identify.py`
  (2026-07-10 신설): 6개 프레임 전부 SerpApi Google Lens로 역검색 →
  프레임마다 배경소품 오매칭 가능성 있어(실측 확인) 여러 프레임 결과를
  한번에 Gemini에게 보여주고 일관되게 나오는 제품명만 채택 → 5개 언어
  키워드 맨 앞에 추가. 어제 삭제한 "구매처 찾기"와 같은 Lens API 재사용,
  용도만 다름(쇼핑링크 노출 → 내부 키워드 정밀도 개선). **실영상 검증
  완료(2026-07-10, 같은 날 후속)** — "reMarkable Paper Pro" 등 정확히
  뽑힘 확인.

**운영 중 발견한 인프라 버그 2건(2026-07-10, 같은 세션 후반)**:
- **Gemini 키 로테이션이 계정 비활성화 에러를 못 잡음**: 429 쿼터소진과
  401 UNAUTHENTICATED("바운드 서비스 계정 삭제/비활성화")는 완전히 다른
  에러인데 기존 `is_daily_exhausted_error`/`is_quota_error` 둘 다 후자를
  못 잡아서 새 키를 추가해도 죽은 키만 계속 재시도하는 버그가 있었음.
  `pipeline/atoms/key_vault.py`(공유 모듈)에 `is_account_disabled_error`
  신설, video_analysis·comment_gen·similarity·product_identify 4곳
  전부 적용. **로그가 전혀 안 남아서 진단이 오래 걸림** — video_analysis.py
  의 미분류-오류 조용한 실패 경로에 stderr 로그를 추가하고 나서야 실제
  원인(401)을 찾음. 앞으로 비슷한 "키 추가해도 계속 안 됨" 증상 보이면
  quota가 아니라 계정 자체 문제일 가능성부터 의심할 것.
- **Apify 액터가 예고 없이 입력 스키마를 바꿈**: `apify~instagram-reel-scraper`
  가 당일 새 빌드로 `directUrls` 필드를 완전히 없애고 `username`(유저네임·
  프로필URL·릴스URL 전부 수용) 하나로 통합 — 토큰 개수·URL과 무관하게
  전부 400 "input.username is required"로 실패해서 처음엔 URL이 사진
  게시물인가 의심했지만, 액터 빌드 타임스탬프(`GET
  /v2/acts/{actor}/builds/{buildId}`)를 확인해서 액터 자체 변경임을
  확정. **서드파티 액터는 버전 고정 없이 쓰면 이런 무통보 브레이킹
  체인지에 항상 노출됨** — 이상 증상 나오면 먼저 액터 최신 빌드
  타임스탬프부터 확인할 것.
- **타입B(레시피/생활용품 "비밀 한스푼"형)** — 아직 미설계. 특정 제품 하나가
  아니라 테마/카테고리 기준으로 다양한 영상을 모음(예: 가지볶음→가지요리
  전반, 방충망솔 판매면 방충망청소 영상+솔 들어간 영상 둘 다). 이것도 5개
  언어, 한국어 자막(국내 재편집물) 배제 우선.
- 공통: **국내 재편집물보다 해외 원본이 낫다**는 피드백 → 자동필터 대신
  각 후보 카드에 어떤 언어로 찾았는지 배지(🇰🇷🌐🇨🇳🇯🇵🇷🇺) 표시해 사용자가
  직접 판단(source_candidates.source_lang 컬럼, 2026-07-10).

**운영 리스크**: 하루 테스트를 많이 돌리면 전용 Gemini 키 풀(13개)이 하루
안에 소진될 수 있음(2026-07-10 실측 — 7개+ 소진). video_analysis·
similarity·product_identify가 전부 같은 풀 공유.

경쟁 벤치마크 대상은 tubefactory.kr — 캡션 텍스트만 보는 tubefactory와
달리 우리는 Gemini로 영상 자체를 멀티모달 분석하는 게 차별화 포인트.

**기능④ "영상 믹싱"(짜집기, 2026-07-12 구현·배포 완료)**: 동일 주제 레퍼런스
영상 2~5개 + 목표 길이 → 새 쇼핑 숏폼 mp4 자동 생성. `mix.html`(사이드바 "🎬
영상 믹싱"). 핵심 설계 결정: 대본 합성과 장면 매칭을 **순차로 하면 안 되고
한 번에**(footage-first — 대본 먼저 확정하면 장면을 억지로 끼워맞추게 됨, 사용자
지적). 그래서 `edit_plan.py`가 소스 세그먼트 인벤토리를 Gemini에 주고 비트마다
{나레이션+지목 seg_id+길이+효과}를 동시 생성. **환각 방지**: 모델은 seg_id로만
지목, 코드가 실제 타임코드 되붙임(`_ground_ref`). **표절가드** n-gram(브리프의
합본방식은 짧은표절 희석버그라 소스별-max로 수정). 구조모드 템플릿(훅→페인→
반전→실용→CTA)/자유 둘 다. TTS=ElevenLabs(키없으면 실무음 mock으로 E2E 관통).
렌더=ffmpeg(setpts로 소스구간을 TTS길이에 맞춤+배속보정 초과시 차순위 후보 대체).
파이프라인: `script_extract`→`edit_plan`→`tts`→`video_assemble`를 `mix_pipeline`이
백그라운드 job으로 오케스트레이션, `/api/mix/*` 7엔드포인트+폴링 UI. 스펙
`docs/superpowers/specs/2026-07-12-쇼핑쇼츠-영상믹싱-design.md`, 계획 `docs/.../plans/
2026-07-12-쇼핑쇼츠-영상믹싱.md`. 서브에이전트 방식 10태스크(개별리뷰+수정 5건+
최종 Opus 전체리뷰) 전부 통과, 유닛 180 passed, 렌더 grounding 실측 2회 성공, 배포완료.
**남은 사람-관찰 E2E**: 실제 릴스로 믹스해 EDL 매칭품질(나레이션↔장면) 눈으로 판정 /
실제 음성 원하면 서버 `/etc/shopping-shorts.env`에 ELEVENLABS_API_KEY 추가.
교훈: 순차 파이프라인의 "억지 끼워맞춤"을 통합 단계로 푸는 게 핵심, 단일 거대 LLM콜은
seg_id 지목+코드 그라운딩으로 환각 방어. [[feedback_confirm_literal_feature_intent]]

**믹스 렌더 재작업(2026-07-12, `video_assemble.py` 4연속 실렌더 피드백 수정)**:
초기 setpts 배속보정 방식은 실제로 돌려보니 문제 다발 → 방식 전환. ①**페이싱**
(45da313e): 배속압축(최대1.2x)이 12초 나레이션을 2초 구간에 욱여넣어 자막이
16.4자/초로 3배속화 → 배속압축 폐지, 소스를 나레이션(TTS) 길이만큼 1배속 재생.
②**새 대본 자막이 화면에 아예 안 나오던 근본문제**(02fd75c1): 렌더러가 오디오만
TTS로 교체하고 drawtext 자막 굽기 단계가 없었음 → 하단 불투명 바 위에 자막 굽기.
③**한글 폰트**(2d908760): 서버(우분투)에 폰트 없으면 자막 생략됨 → NanumGothic을
repo에 번들(`shopping_shorts/assets/`), 필터그래프 콜론 이스케이프 불가 문제는
폰트/텍스트를 work로 복사 후 cwd=work에서 파일명만 참조로 회피. ④**장면 반복+자막
끊김**(5eaaaa9a): 짧은 구간을 -stream_loop로 되풀이하던 걸 연속재생으로(원본이
나레이션보다 짧을 때만 루프), 자막 균등분할을 문장경계 분할로. **다음(집 이어작업)**:
자막을 어절단위 짧은 구절로 분할(사용자 요청 "오이 사자마자/냉장고에/넣으셨나요?"
식, 너무 규칙적이면 이상 — 어절 greedy target 7자 알고리즘 검증완료, NEXT_SESSION.md).
서버는 아직 무음(ElevenLabs 키 없음)→Gemini TTS 검토. 교훈: 렌더 산출물은 실제로
돌려 프레임을 눈으로 봐야 함 — "열기만 하고 확인 안 함"으로 컬러바 더미·자막 잘림·
장면반복을 사용자가 먼저 잡아낸 사례.

**인스타 수집 비용 전환+같은주제그룹핑+멀티테넌시(2026-07-13, 다른PC 세션)**:
- **Apify 무료계정 전멸**: 17개 무료토큰 전부 월 $5 한도 소진(403)이 "지금
  수집" 에러의 진짜 원인 — 코드버그 아니었음. 신규 무료계정도 발급 직후엔
  되다가 몇 분 안에 401로 죽음(Apify의 신규계정 어뷰징 탐지로 추정) — 유료
  Starter 전환이 유일한 해법.
- **액터 교체**: `apify~instagram-reel-scraper`(비쌈) → `apidojo~instagram-scraper-api`.
  실측 비용은 아이템수 무관 **flat $0.005/run**(Apify 빌링 API `usageTotalUsd`로
  직접 검증, 처음엔 잘못 추정해 $27→$66로 두 번 헛짚었다가 실측으로 확정).
  151채널×매일 수집 = 월 **$22.65**.
  `apify_client.py`의 `fetch_reels()`가 채널별 병렬(`ThreadPoolExecutor`,15)
  런으로 재작성됨, 필드 매핑은 `_normalize_apidojo_item`.
- **벤치마킹 엑셀 정리**: 443→151행(팔로워 1만 미만 제외+생존여부 실API
  전수조사, 원본은 `벤치마킹시트.backup_20260713.xlsx`로 백업).
- **200채널 자동캡**: `config.MAX_CHANNELS=200`, `channels.cap_channels()`가
  팔로워순 정렬 후 자르지만, 채널발굴(discovery)로 유입되는 채널은 이 경로를
  안 거쳐 캡을 우회할 수 있었음 → `service.py`의 `collect()`에 이중가드 추가
  (엑셀+발굴 합산 후 다시 자름). discover_jobs의 `merge_feeds`도 `cap` 파라미터
  받아 팔로워 기준 회전(새 채널 유입 시 저성과 채널 자연 탈락).
- **"같은 주제" AI그룹핑 버그(실사용자 리포트로 발견)**: 신규 `topic_grouper.py`
  (Gemini 배치, ≤25개씩)가 감자레시피+아이스박스+피아노처럼 전혀 무관한
  영상을 한 그룹으로 묶는 버그 발생. 근본원인은 `mapping[sc] = f"{run_tag}_{gid}"`
  로 **배치 시작 인덱스(`start`)를 안 넣어서** 서로 다른 배치가 각자 독립적으로
  매긴 "그룹1"끼리 전역 group_id가 충돌한 것 — `f"{run_tag}_{start}_{gid}"`로
  수정. **교훈: 배치 단위로 병렬/분할 처리해 만든 로컬 ID를 전역 키로 쓸 때는
  반드시 배치 식별자를 키에 포함시켜야 함**, 안 그러면 각 배치의 "1번"들이
  전부 같은 걸로 오인됨 — 유닛테스트만으론 안 잡히고 실제 데이터로만 드러남.
  관련영상 모달(`showRelated()`)에 64×64 썸네일 추가해 그룹 정확도를 눈으로
  바로 검증 가능하게 함.
- **멀티테넌시(고객 100명 판매 대비, 워크트리로 병행구현)**: 공유 수집
  파이프라인은 그대로 두고(고객별로 Apify 비용 안 늘리려고) `customers`
  테이블+pbkdf2_hmac(26만회)+자체서명 세션쿠키(`{customer_id}:{expiry}:{hmac}`,
  서버측 세션스토어 없음)로 로그인/회원가입 추가. 개인 데이터 테이블
  (commented/saved/mix_basket/script_wiki)을 `(customer_id, shortcode)` 복합PK로
  마이그레이션(`_migrate_personal_tables`, rename-recreate-copy-drop, 컬럼정의는
  `PRAGMA table_info`로 동적 보존 — 하드코딩 안 함). 기존 단일사용자 데이터는
  `LEGACY_CUSTOMER_ID=0`으로 보존.
- **동시세션 안전 병행 패턴**: 다른 세션이 `app.py`/`store.py`를 uncommitted로
  편집 중인 상태에서 `git worktree add -b feat/multi-tenancy`로 격리 개발 →
  머지 직전 `git stash push -u -- <그 파일들>`로 남의 미커밋 작업 보존 →
  `git merge --ff-only` → `git stash pop`으로 복원, 두 번 다 충돌 없이 성공.
  [[feedback_shared_worktree_branch_check]] 패턴의 연장.
- **미결(다음 세션)**: `script_wiki` 테이블에 `thumbnail` 컬럼이 없어서
  `produce.html`의 대본 선택 체크리스트에 썸네일을 못 붙임(`save_to_wiki()`가
  `item.get("thumbnail")`을 애초에 안 받음) — 사용자가 명시 요청("왼쪽에 썸네일
  작게 오른쪽에 대본전체")했지만 착수 전 다른 버그 리포트로 중단. index.html의
  `showRelated()` 썸네일 패턴 그대로 재사용하면 됨. 상세 핸드오프 NEXT_SESSION.md 🅔.
