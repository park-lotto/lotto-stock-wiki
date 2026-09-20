---
name: project_lens_cn_search
description: 렌즈 유사영상의 샤오홍슈/도우인 자동합류 — Apify 실제 필드명·중국어 번역 필수·썸네일 스프라이트 함정
metadata: 
  node_type: memory
  type: project
  originSessionId: 97dd6282-a16a-4909-b4b2-3cb3502346b5
  modified: 2026-07-19T07:58:12.734Z
---

쇼핑쇼츠 렌즈 유사영상(index.html `lensSearch`)에 샤오홍슈/도우인 자동합류(`/api/lens/cn`) 구현·라이브(2026-07-18). 서버에서 실제 Apify 응답을 3회 probe해 확정한 사실들:

**정확도 장치 2개(제품 특정) — 이게 이 기능의 성패**. `/api/lens/cn`은 프레임(UploadFile)+캡션을 받는다:
- **장치1 비전 추출** `video_analysis.cn_search_keyword_vision(image_bytes, caption)` — 렌즈가 캡처한 프레임(썸네일)을 Gemini 비전(`_MODEL=gemini-3.5-flash`, `types.Part.from_bytes`)이 보고 **화면에 박힌 제품명 글자 + 물건 생김새 + 캡션**을 종합해 제품을 특정하고 중국어 검색어를 만든다. 서버 실썸네일 실측: 리모와 캐리어→`日默瓦`(브랜드 인식), 청소용 퍼미스 스톤→`浮石清洁块`. 프레임 없음/실패 시 `cn_search_keyword`(캡션 소재)→`translate_keyword` 직역 순 폴백.
- **장치2 유사도 판정** `video_analysis.judge_same_product(product, titles)` — 결과 제목들을 추출 제품과 대조해 Gemini가 `same/similar/no`로 판정 → `same`을 위로 정렬, 프론트에 ✅같은제품/⚠️다른주제 배지. 실측: RIMOWA개봉=same·수리/비번변경=similar 정확 구분.
- ★두 함수 모두 `response_schema`로 JSON 강제(안 하면 "Extra data" 파싱 에러 실측). 앞선 접근(앞토큰 직역 / 2그램 관련도 배지)은 오탐 많아 폐기 — 비전+판정이 대체.
- 비용: 검색당 Gemini 비전1 + 판정1 + Apify2. 렌즈 월100회(SerpApi)로 상한.

**Apify 실제 필드명**(추측 금지 — 처음 추정 다 틀려 라이브서 빈칸·격자 사고):
- 샤오홍슈(`zen-studio~rednote-search-scraper`): ★썸네일은 `images[cover_image_index].url` (video.thumbnail은 **스크러빙 스프라이트=격자 몽타주**라 쓰면 안 됨) / 채널=`author.nickname` / 좋아요=`engagement.liked_count`(view_count 필드 없음) / 길이=`video.duration_seconds`(초) / mp4=`video.url_720p`
- 도우인(`zen-studio~douyin-search-scraper`, TikTok clockworks 스키마): 채널=`authorMeta.name`(nickName 없음) / 좋아요=`statistics.diggCount` / 조회수=`statistics.playCount`(**자주 0** → 0이면 좋아요로 표시) / 길이=`videoMeta.duration`(ms) / mp4=`videoMeta.playUrl` / 썸네일=`videoMeta.cover`

**미리보기**: 직접 mp4를 `<video referrerpolicy="no-referrer">`로 재생 시도(썸네일 이미지가 no-referrer로 로드되는 것과 같은 우회). CDN 만료토큰이면 실패 → 원본 링크 폴백. 도우인 영상 CDN 호스트가 `v5-dy-ov-*.zjcdn.com` 등 가변이라 서버 프록시 허용목록은 불안정.

**한계**: 유튜브/틱톡/인스타 결과는 구글렌즈(시각검색)라 응답에 채널·조회수·길이가 원천 없음 → 메타 빈칸·번역 무관.

서버 probe 방법(로컬은 APIFY 토큰 0): `ssh ... "cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && python3 -" < probe.py`. 관련: [[reference_deploy_truth_branch_ssh]] [[reference_gemini_quota_preview_model]]

**2026-07-19 개편 — 60대용 인앱 후보검색(트랙 렌즈CN검색, SDD, 라이브 merge 61a9151d)**: 기존 "찾아 담기" 샤오홍슈/도우인 **외부링크가 한국어 검색어로 열려 무관결과**(서버실측: `풍선감자`=쓰레기 / `空气炸锅土豆片`=관련·고참여, 한국어는 단어 하나면 무관 쓰레기). 처방=외부이동 폐기, **렌즈 모달 안 중국어 후보 큰버튼(한국어라벨)→그 자리 검색→담기**. 신규: `cn_search_candidates`(비전→중국어후보3~4개+ko뜻) / `POST /api/lens/cn/keywords`(비전) / `POST /api/lens/cn/search`(검색어1개→샤오홍슈+도우인, Gemini안씀). 프론트=첫후보 자동검색·클릭 재검색(CN결과만 교체)·클릭상한6. **교훈 3개(리뷰가 잡음)**: ①onclick 큰따옴표 vs `JSON.stringify` 충돌로 버튼 전멸→`zh`를 `&quot;`이스케이프(홑따옴표 shortcode와 섞을 때 필수) ②node-slice pytest 테스트 `WinError6` flaky→`subprocess.run(..., stdin=subprocess.DEVNULL)`로 결정적 해소 ③CN 비동기 재렌더에 형제 `fetchLensYt`의 모달소유자 가드(`root.dataset.sc===shortcode`) 미러 안 하면 카드전환 중 늦은 응답이 현재 모달 덮어씀. **미검증**: 로컬 키0이라 후보생성·검색을 눈으로 못 봄=서버 육안이 진짜 게이트. 후보 엉뚱하면 `_CN_CANDIDATES_PROMPT` 튜닝. 핸드오프 `handoff/렌즈CN검색.md`.

**2026-07-19 밤 유저스크립트 카드담기 완결 — 4플랫폼(grab_logic.js v-f, merge 8618e4710)**: `📥담기`를 페이지 전체(플로팅) 말고 **검색 그리드 카드마다** 붙임. 로더로 재설치 문제 해결 + 도우인 특수.
- **로더 모델(★60대 재설치 불필요)**: `grab.user.js`(v2.0.0)는 얇은 로더 — 매 새로고침에 서버 `/grab_logic.js`를 `GM_xmlhttpRequest`로 불러 `eval`. 로직 고쳐도 사용자는 **새로고침만**(Tampermonkey 재설치 X). app.py에 `/grab_logic.js` 라우트(Cache-Control:max-age=60)+공개경로 허용.
- **플랫폼별 카드 셀렉터**: 샤오홍슈=`section.note-item`+`a.cover`(rednote 도메인) / 틱톡=`a[href*="/video/"]`·인스타=`a[href*="/p/","/reel/"]`(앵커 '안'에 버튼 넣고 capture+stopImmediatePropagation로 이동차단) / 도우인=아래 특수.
- **★도우인 = sandbox가 fiber를 못 읽는다**: 도우인 카드엔 `<a href>`·data-id 없음, 영상ID가 React `__reactFiber$` props에만 있음. 유저스크립트 **sandbox(격리세계)에선 페이지가 DOM노드에 박은 fiber가 안 보임** → 첫 카드만 간헐 성공(사장님이 본 "맨앞 하나만"). unsafeWindow로도 불안정. **해법=도우인만 페이지 '메인월드'에 자립 `<script>` 주입**(`fn.toString()` 삽입, 도우인 CSP는 인라인 미차단·실측). 메인월드는 fiber 다 보임. 클릭 시 sandbox 안 거치고 `BASE/api/grab` 직접 오픈. 주입 1회+자체 setInterval 유지.
- **★두 번째 버그—void img에 appendChild**: 주입 성공해도 box-walk가 `box=img`(150~440px 매치)를 골라 **img(void요소)에 버튼 append→렌더 안 됨(0×0), 19/20 실종**. `img.parentElement`부터 컨테이너 찾게 수정 + `data-aid=aweme_id`로 숨은 단열 레이아웃 중복제거.
- **★검증 교훈(두 번 오판함)**: `buttonsCreated===20`·`distinctBoxes===20`만 보고 "됐다" 했다가 화면엔 1개뿐. 진짜 검증=**`elementFromPoint`(정말 보이나·클릭 위에 있나)** + **배포 후 리로드해 실 유저스크립트(sandbox)로** 측정. 내 `javascript_tool` 수동 eval은 **메인월드**라 sandbox 한계를 원천적으로 못 재현 → 이게 "뚫었다" 헛보고의 근원. [[feedback_verify_with_real_data]] [[feedback_harness_invented_contract]]
- 실측(라이브): 카드20=고유ID20 / 상단 10/10 보임·클릭가능 / 클릭→`/api/grab`+그 영상ID로 담김·도우인 이동 차단.

**2026-07-19 오후 무료화 전환(사장님 "에피파이 안쓰고 무료로", merge f8d9aeff)**: 인앱 Apify 검색은 유료라 폐기. **핵심 사실=샤오홍슈/도우인은 로그인·봇차단이라 자동 인앱검색을 무료로는 원리적으로 못 함(Apify 전용). 무료 유일경로=사용자가 사이트 직접 둘러보며 유저스크립트 담기.** 그래서: 후보 버튼을 Apify검색→**중국어로 샤오홍슈/도우인 사이트 검색을 여는 링크**(`_lensSearchUrl`)로 바꿈. 비전 후보(무료 Gemini)만 유지, `doLensCnSearch`·클릭상한·인앱그리드·재생미리보기 전부 제거(재생 미리보기 상실=공짜 대가, 도우인은 어차피 CDN 핫링크차단으로 인앱재생 불가였음). `/api/lens/cn/search`(Apify) 엔드포인트는 죽은코드로 남음. 무료 담기 유저스크립트 `grab.user.js`(og:image/title 읽어 `/api/grab`으로 저장, Apify 무관) v1.1.0으로 `@match`에 rednote·`*.xiaohongshu`·`*.douyin` 추가(샤오홍슈 로그인도메인이 rednote라 www.xiaohongshu만 매치하면 버튼 안 떴음). 교훈: **"무료로 자동 CN 검색"은 불가능—로그인/봇차단이 근본 이유. 무료는 곧 수동(사이트 둘러보기)**.
