> **소유 트랙**: 렌즈CN검색 — 이 파일은 이 트랙 세션만 수정한다. 다른 트랙은 읽기만.
> 트리거: "렌즈CN검색 이어서" / "샤오홍슈 후보검색 이어서"

## 도우인 카드담기 완결 — 2026-07-19 밤 (4플랫폼 전부 라이브)

**샤오홍슈·틱톡·인스타·도우인 카드별 📥담기 전부 작동.** grab_logic.js v-f, origin/main `8618e4710`, 서버 force-pull·재시작 완료.

- **로더 모델(재설치 불필요)**: `grab.user.js`(v2.0.0)는 얇은 로더 — 매 새로고침에 서버 `/grab_logic.js`를
  GM_xmlhttpRequest로 불러 eval. **로직 고쳐도 사용자는 새로고침만.** 60대 재설치 문제 해결.
- **도우인만 특수**: 카드에 `<a href>`·data-id 없음, 영상ID가 React `__reactFiber$` props에만 있음.
  근데 유저스크립트 **sandbox는 페이지 fiber를 못 읽음**(첫 카드만 간헐 성공 = 사장님이 본 "맨앞 하나만").
  → **도우인만 페이지 메인월드에 자립 스크립트 주입**(도우인 CSP 인라인 미차단, 실측). 메인월드는 fiber
  다 보임. 클릭 시 sandbox 안 거치고 `BASE/api/grab` 직접 오픈.
- **두 번째 버그(box)**: 주입 됐는데 box-walk가 `box=img`(150~440px)를 골라 **img(void)에 appendChild →
  안 보임**(19/20 0×0). `img.parentElement`부터 컨테이너 찾게 수정 + `data-aid`로 aweme_id 중복제거.
- **실측(라이브 v-f, 오염 없이)**: 카드 20개=고유ID 20 / 상단 10/10 보이고 클릭가능(elementFromPoint) /
  클릭→`/api/grab`+그 영상ID로 담김·도우인 이동 차단(`didNavigateAway:false`) 확인.
- ⚠️ **교훈**: `buttonsCreated===20`·`distinctBoxes===20`만 보고 "됐다"고 두 번 오판했다. 진짜 검증은
  **elementFromPoint(보이나·클릭 위에 있나)** + 배포 후 **리로드해 실 유저스크립트로** 측정(내 수동 eval은
  메인월드라 sandbox 한계를 못 재현했다). [[project_lens_cn_search]]
- 커밋: `d31ce1885`(메인월드 주입) `657e66e5a`(box 수정). 병합 `905c4261c`·`8618e4710`.

## 렌즈 CN 후보검색 — 60대용 인앱 클릭검색 — 2026-07-19 (SDD 완료·라이브)

**전부 커밋·병합·라이브 배포 완료.** origin/main merge `61a9151d`. 서버 3분 크론이 shopping-shorts 재시작.

### ✅ 완료 (문제 → 처방)
렌즈 "다른 플랫폼 찾아 담기" 샤오홍슈/도우인 링크가 **한국어 검색어**(`st.keyword`)로 외부
중국사이트를 열어 무관결과가 떴다(서버 실측: `풍선감자`=쓰레기, `空气炸锅土豆片`=관련). 처방:
외부링크 대신 **렌즈 모달 안에서 중국어 후보 검색어 큰버튼→그 자리 검색→담기**(외부이동·타이핑 0).

- **Task1** `video_analysis.cn_search_candidates(image,caption)` — 비전이 중국어 후보 3~4개(+한국어 뜻)
- **Task2** `POST /api/lens/cn/keywords` — 프레임→후보(비전만)
- **Task3** `POST /api/lens/cn/search` — 검색어1개→샤오홍슈+도우인 병렬(Apify만)
- **Task4** 프론트(`index.html`): 큰 후보버튼(한국어 큰/중국어 작은)·첫후보 자동검색·클릭 재검색(CN결과만 교체)·클릭 상한6
- SDD 게이트: 신규테스트 25 passed, finish 게이트 통과(신규0/기준선8).

### 🔧 리뷰서 잡은 것(다 수정됨)
1. **Task4 Critical**: onclick 큰따옴표 vs `JSON.stringify` 충돌로 버튼클릭 전부 죽음 → `zh`를 `&quot;`
   이스케이프(`61f30c55`). node 실렌더로 확증.
2. **테스트 flaky**: node-slice 테스트가 `WinError6`로 간헐실패(5중3) → `stdin=DEVNULL`로 해소(`b8d5fd76`, 8/8).
3. **whole-branch Important**: CN 비동기 함수가 `renderLens`를 무조건 호출 → 카드 전환 중 늦은 응답이
   현재 모달 덮어씀. 형제 `fetchLensYt`의 `root.dataset.sc===shortcode` 가드 미러(`ee16f727`).

### 🔄 무료화 전환 (2026-07-19 오후, 사장님 "에피파이 안쓰고 무료로")
Apify 인앱 자동검색(샤오홍슈/도우인 그리드)은 **유료**라 폐기. 대신:
- **후보 버튼 = 사이트 링크**: 비전이 중국어 후보(무료 Gemini) 생성 → 각 후보에 `📕 샤오홍슈`/`🎬 도우인`
  링크(그 중국어로 사이트 검색 오픈) → 고객이 사이트서 유저스크립트 `📥 담기`(무료). **Apify 비용 0.**
- 제거: `doLensCnSearch`·`_lensCnCapReached`·클릭상한·CN 인앱 그리드/재생 미리보기·cnActive/cnClicks/cnLoading.
- 유지: `/api/lens/cn/keywords`(비전 후보). `/api/lens/cn/search`(Apify) 엔드포인트는 **죽은 코드로 남김**(프론트 호출 0, 후속 정리 가능).
- 무료 담기 유저스크립트 `grab.user.js` v1.1.0: `@match`에 rednote·`*.xiaohongshu`·`*.douyin` 추가(라이브).
- 커밋: `f27bd678`(무료화) `85583caf`(grab @match). 라이브 merge `f8d9aeff`.
- 트레이드오프: 인앱 재생 미리보기 상실(사이트서 봄) = 공짜의 대가. 도우인 인앱 미리보기는 어차피 CDN 핫링크차단으로 안 됐음.

### ⏭ 다음 (서버 실측 = 진짜 게이트)
- 사장님 Tampermonkey에서 `grab.user.js` **업데이트** → 샤오홍슈(rednote)·도우인 사이트에서 📥담기 버튼 뜨나 확인.
- 렌즈에서 후보 링크 눌러 그 중국어로 사이트 열리나 → 담기 되나.
- (구버전 실측 메모, 무료화 이전):
로컬은 APIFY·SHORTS_GEMINI 키 0이라 **후보생성·검색을 눈으로 못 봤다**(배선·로직만 검증). 서버엔 키 있음.
→ shoppingshorts.duckdns.org 렌즈: 감자칩류 영상 → 🔍 렌즈 유사영상 → "📕🎬 중국 앱에서 찾기"
  후보 버튼 뜨나 → 첫 후보 자동으로 샤오홍슈/도우인 결과 채워지나 → 다른 버튼 눌러 재검색되나 → 담기 되나.
  후보가 엉뚱하면 `_CN_CANDIDATES_PROMPT` 튜닝(후속).

### 파일
- `shopping_shorts/video_analysis.py` (cn_search_candidates / _CN_CANDIDATES_PROMPT·SCHEMA)
- `shopping_shorts/app.py` (/api/lens/cn/keywords · /api/lens/cn/search)
- `shopping_shorts/static/index.html` (fetchLensCnKeywords·doLensCnSearch·_lensCnCapReached·후보버튼줄·가드3)
- 테스트: tests/test_cn_candidates.py · test_app_lens.py(추가) · test_lens_cn_js.py
- 설계: docs/superpowers/specs/2026-07-19-렌즈CN후보검색-design.md / plans/2026-07-19-렌즈CN후보검색.md

### 남은 Minor(최종리뷰 defer — 급하지 않음)
- 첫 자동검색이 클릭6중 1소비(설계 의도) / cap도달시 cnActive 미갱신(cosmetic) / 후보 텍스트 innerHTML 미이스케이프(Gemini 소스·저위험)

### 🆕 CN 카드별 담기 (2026-07-19 오후, grab.user.js v1.2.0)
"영상마다 담기가 있어야지" → 검색 그리드 카드마다 📥 버튼. **rednote.com 로그인상태 브라우저 실측으로 셀렉터 확정**(추측금지): 카드=`section.note-item`, 커버=`a.cover[href]`(→`/search_result/{id}`·`/explore/{id}`). 클릭시점에 URL·썸네일·제목 추출(SPA 노드재사용 안전). 그리드선 플로팅 숨김(단일영상 페이지에만 플로팅). **라이브 페이지 주입테스트로 16버튼·grab페이로드 실증**. 커밋 9aae60ed. ⚠️xiaohongshu.com은 게스트 로그인벽('登录后查看')이라 rednote.com에서만 카드 뜸(둘 다 같은 클래스). 도우인 카드별은 미착수(구조 다름, 별도 그라운딩 필요)—도우인은 플로팅 폴백.

### 🆕 4플랫폼 바로가기 + 인스타 담기 + 도우인 결론 (2026-07-19 오후 2차)
- **rednote 담기 거부 버그**: 서버 `_GRAB_DOMAINS` xiaohongshu 튜플에 `rednote.com` 추가(app.py:2546)=카드별 담기가 보내는 rednote/search_result URL 담김. 회귀테스트+main 병합.
- **후보 바로가기 4플랫폼화**: 후보 행에 🎵틱톡·📷인스타 추가. 샤오홍슈/도우인=중국어(c.zh), 틱톡/인스타=한국어(c.ko). node로 4URL·언어 실측검증.
- **인스타 담기**: grab.user.js @match에 instagram 추가(v1.3.0)=인스타 영상페이지서 플로팅 담기. (인스타 전용 스크립트 insta_fill_comment.user.js는 댓글용, 별개)
- **도우인 카드별 = 불가 확정**: 브라우저 실측—도우인 검색카드는 href·data-id 없는 div+JS, React fiber props까지 뒤져도 aweme_id 없음(URL이 클릭해야 생성). 추측코드 안 짬. **도우인 최선=영상 클릭후 플로팅 담기**.
- 커밋: 184b54ab(rednote) 13fff95b(틱톡·인스타·grab v1.3.0).

### 🆕 틱톡·인스타 카드별 담기 + 로더 방식 (2026-07-19 저녁)
- **로더 방식 v2.0.0**: grab.user.js를 얇은 로더로 전환(GM_xmlhttpRequest로 /grab_logic.js 받아 eval). 로직은 서버파일만 고치면 자동반영=재설치 불필요. 사장님은 이번 1회만 v2.0.0 설치(GM 권한 허용).
- **틱톡·인스타 카드별**: grab_logic.js에 addAnchorCardBtns 추가. 틱톡=`a[href*=/video/]`, 인스타=`a[href*=/p/,/reel/]`. 앵커 안 버튼+preventDefault/stopImmediate로 이동차단. isGridPage 가드로 그리드에서만(단일영상 플로팅 안 가림). **라이브 실측: 틱톡 12·인스타 3 버튼, navigated:false, URL·썸네일 정상.**
- **도우인**: div+JS라 URL이 DOM에 없음(React까지 확인)=카드별 영영 불가. 플로팅만.
- 셀렉터 실측: 틱톡 div[data-e2e=search_top-item]>a, 인스타 a[href*=/p/](320²), rednote section.note-item>a.cover.
- 커밋: 로더 379d4cd7 이전 + 틱톡인스타 379d4cd7.
