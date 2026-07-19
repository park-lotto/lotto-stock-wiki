> **소유 트랙**: 렌즈CN검색 — 이 파일은 이 트랙 세션만 수정한다. 다른 트랙은 읽기만.
> 트리거: "렌즈CN검색 이어서" / "샤오홍슈 후보검색 이어서"

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

### ⏭ 다음 (서버 실측 = 진짜 게이트)
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
