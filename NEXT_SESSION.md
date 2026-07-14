# NEXT_SESSION — 이어서 할 일 (병행 트랙)

> ⚠️ 여러 작업 트랙이 병행 중. 각자 자기 트랙만 이어서. main 고정, `git add`는 자기 파일만(-A 금지).
> ⚠️ **동시세션 순차커밋 규칙**: 커밋 전 `git status`로 남의 hunk 섞였나 확인 → 내 파일만 stage → 먼저 커밋 중인 세션 있으면 기다렸다 순차. 커밋 후 HEAD에 내 변경 grep 확인(덮임 감지). memory `feedback_동시세션_순차커밋`.

---

## 🎙️ 보이스 프리셋 라이브러리 — ✅ 구현·검증 (2026-07-14 집PC, 커밋 b5463de9~3cd1abfe)

빅채널 나레이션 *느낌*을 페르소나 프리셋(이름+설명+감도값)으로 굳혀 produce 4단계에서 카드로 선택. 하이브리드(MVP=스톡매칭, 클로닝 Phase2).
- 스펙 `docs/superpowers/specs/2026-07-14-보이스-프리셋-라이브러리-design.md` / 계획 `docs/superpowers/plans/2026-07-14-보이스-프리셋-라이브러리.md`
- ElevenLabs 연결완료(키+ToS권한+`.env` load_dotenv, 실음성 E2E). 8태스크 TDD: tts(voice_settings/speed 0.7~1.2 clamp)·audio_post(atempo+silenceremove)·store(voice_presets+voice_json)·voice_presets(seed KR6종)·build_voice_samples·mix_pipeline(resynth_tts_job)·app(프리셋API4종+startup seed)·produce UI(카드·속도·무음·고급접기). 24/25 green, 라이브 API·JS구문 검증.
- ✅ **오늘 완료(2026-07-14 추가)**: 샘플mp3 6종 생성·배포 / 서버 `/etc/shopping-shorts.env`에 ELEVENLABS_API_KEY 추가+실음성검증 / audio_post in-place ffmpeg 버그수정 / **produce 4단계 프리셋 카드를 job 없이도 항상 표시**(커밋 17ca3e8f) — 라이브 서버 반영됨.

- 🔥 **다음 세션 핵심 — v3 감정태그 "인간처럼" 나레이션 (오늘 검증완료, 방향확정)**:
  - **검증됨**: `eleven_v3` 모델 이 키로 접근가능+한국어 지원. 대본에 `[excited]` `[whispers]` `[sighs]` `[laughs]` `[slow]` 인라인 태그 삽입 → 그 뒤 4~5단어에 감정 적용. A/B로 무태그 vs 태그판 확연히 사람같음 확인(사장님 OK).
  - **한국어 여성 성우 후보**(라이브러리): ⭐**Kelee K 서울내레이터**(`5DWGv3VDkihNUcbvaonB`, 사장님 선호) / Jiana(`uD0jH1cfRqteeku18ODi`,크리스프) / Inbeul(`GcdAArSHrZw06Pf1X4Df`) / Yu Haon(`B8rl62CpT9zOQ7RC3Mdl`). 남성: 지훈 onwK4e9ZLuTAKqWW03F9 / 도현 TxGEqnHWrfWFTfGW9XjX.
  - **확정된 설계원칙**:
    1. **역할 3분리**: 성우(voice_id)·감도(voice_settings)는 **프리셋 고정(대본무관)**, **태그만 대본따라(핵심 2~3군데만)**. 감도를 대본마다 바꾸지 않음.
    2. **편차 관리(중요 — 사장님 우려)**: v3+태그는 take편차 큼. "전 문장 태그 도배 금지". 훅·펀치라인만 태그 + **비트별 재생성(re-roll)** + **seed 고정**(문서상 완전보장X but 충분) + N개 베스트픽 + 하이브리드(평상시 v2, 훅만 v3).
    3. **감도 베스트값(v3)**: stability 0.5~0.7(태그가 감정담당→베이스 안정으로 편차↓), style 0~0.3(태그와 겹침방지), similarity 0.75~0.8, **speaker_boost는 v3 비호환**.
    4. **UX**: raw 3슬라이더 노출 X → 프리셋에 감도 박고, 원노브 "차분↔생생"(stability 매핑), 파워유저만 고급.
  - **다음 작업**: 브레인스토밍→설계→구현. 프리셋별 **감정 프로파일**(성우별 어울리는 태그셋) + 제미니 대본생성 시 **감정태그 자동삽입**(핵심만) + **비트별 재생성** + seed. tts.py는 이미 model_id 받게 돼있음.
  - Phase2(더 나중): 앱내 "레퍼런스URL→측정→프리셋 자동생성" 도구 / JP·EN / 보이스 클로닝.
  - 참고: v3 A/B 샘플들 사장님 바탕화면에 있음(v3_쇼츠_*, v3_서울_A/B_*).

---

## 🔍 렌즈 유사영상 발굴 — ✅ 구현·배포·라이브 (2026-07-14 집PC, 커밋 9ca8a6d9)

멈춘 장면 구글렌즈 역검색 → 5플랫폼(유튜브·틱톡·인스타·샤오홍슈·도우인) 유사 동영상 발굴. 6태스크 TDD 완료·서버배포·라우트라이브.
- 스펙 `docs/superpowers/specs/2026-07-14-쇼핑쇼츠-렌즈유사영상발굴-design.md` / 계획 `docs/superpowers/plans/2026-07-14-렌즈유사영상발굴.md`
- lens_discover(google_lens 5플랫폼 도메인필터)/store 월카운트/api_lens_search+api_media/유튜브·틱톡 mp4재생통일(embed폴백)/렌즈탭UI. python-multipart 서버설치 완료.
- **2026-07-14 디버깅·개선 대량(라이브 검증완료, 커밋 ~94cd17cc)**:
  - 🐛 **핵심버그 3연쇄 해결**: ① `type=visual_matches` 파라미터가 오히려 "no results" 유발 → 제거하고 all모드+`hl=ko&country=kr` 로케일. ② **진짜 원인=Google 인덱싱 지연**: 갓 호스팅한 우리서버 이미지를 렌즈가 못 읽어 0개(30분 후엔 됨) → **캡처를 imgur 익명업로드 후 그 URL로 검색**(imgur는 Google 상시크롤링, 즉시 매칭). 실증: 실패프레임 0→imgur→10~59개.
  - ✨ **UX 개선**: 결과를 **팝업 모달(wide 1040px)**로(인라인이 UI 밀던 것). 썸네일 gstatic 직접로드. **큰 세로썸네일(9:16 260px)+클릭시 그자리 embed 재생**+원본링크. 재생안한 **썸네일상태에서도 카드img 캡처**해 검색. 틱톡 **discover/검색페이지 제외**(개별영상만).
  - 💰 **비용**: SerpApi 월250회 무료→이후 $50/5000=~14원/회. imgur 무료. → 향후 포인트=현금 차감 반영.
  - imgur Client-ID는 공개테스트ID 폴백중 — **전용 발급해 `IMGUR_CLIENT_ID` env 넣는 게 안정적**(선택).
- ⏭ **남은 것(다음 세션)**: **API 결제부터**(사용자 명시) — SerpApi 유료전환(월 무료소진 대비) + imgur 전용 Client-ID. / 매칭정확도는 렌즈 특성상 유사장르 섞임(제목키워드 후처리 필터 얹으면 개선 가능, 미착수).

---

## 🅔 쇼핑쇼츠 레퍼런스랭킹 — 비용전환+같은주제그룹핑+멀티테넌시 — 2026-07-13 (다른 PC 세션)

**전부 완료·배포·라이브 검증까지 끝남.** 커밋: `2b859d1d`(apidojo전환) `01839b92`(200캡) `b76be003`(같은주제그룹핑) `e8d0d50b`~`f2d123ac`(멀티테넌시) `278c099a`(그룹핑버그수정+썸네일).

### ✅ 완료
1. **벤치마킹 채널 정리**: 443개 → 팔로워 낮은거·죽은채널(API로 생존확인) 제거 → 151개. `MAX_CHANNELS=200` 자동캡도 추가(엑셀+발굴채널 union 양쪽 다 적용).
2. **수집 액터 전환**: `apify~instagram-reel-scraper`(비쌈) → `apidojo~instagram-scraper-api`(run당 $0.005 고정, 151채널/회 실측 $0.755). `apify_client.py` fetch_reels() 재작성, 필드 정규화, until날짜필터, 15동시병렬.
3. **"같은 주제 모아보기"**: `topic_grouper.py`(신규) — 수집 배치 안에서 Gemini가 캡션 의미로 그룹핑. `topic_groups` 테이블(platform 컬럼 포함 — 유튜브·틱톡 나중에 붙어도 그대로 편입). 카드에 🔗버튼+모달.
   - **버그수정(278c099a)**: 청크(batch_size=25)로 나눠 처리하는데 배치 인덱스 없이 날짜만 접두어로 써서 서로 다른 배치의 "그룹1"들이 충돌 — 배치 시작 인덱스 포함해 수정. 모달에 썸네일도 추가.
   - ⚠️ **미완**: 도서관(위키)/우리믹스 쪽 대본선택 리스트에도 썸네일 추가 요청받았으나 **착수 전 중단**(store.py `script_wiki`에 thumbnail 컬럼 자체가 없음 — 추가 필요). `save_to_wiki()`가 item에서 thumbnail 안 받아서 저장 안 됨.
4. **멀티테넌시(100명 고객 대비)**: `customers` 테이블(pbkdf2 해시), `/signup` 회원가입, saved/mix_basket/commented/script_wiki 4개 테이블 (customer_id,shortcode) 복합키로 격리. 기존 admin 계정은 LEGACY_CUSTOMER_ID(0) 하위호환. 별도 워크트리(`feat/multi-tenancy`)에서 작업 후 무충돌 병합, 라이브 서버 실검증(회원가입→로그인→저장 4단계) 완료.

### ⏭ 다음
1. **위키/우리믹스 썸네일 추가**(중단된 것 이어서): `store.py` script_wiki 테이블에 `thumbnail` 컬럼 마이그레이션 추가 + `save_to_wiki()`가 `item.get("thumbnail")` 저장하도록 + `_WIKI_COLS`/`_wiki_row`에 포함 + `produce.html`의 `loadWikiForMix()` 렌더링에 좌측 썸네일(64x64) 추가.
2. 사용자가 "지금 수집" 재실행 후 같은주제 그룹핑 정확도 육안 확인 필요(버그수정 이후 아직 실데이터 미검증 — 서버 topic_groups 0행 상태로 세션 종료됨).
3. 서버 앞단이 **Apache 리버스프록시**(443/80→내부 8849)임을 확인 — 재배포 타이밍과 겹치면 502 HTML을 프론트가 JSON파싱 실패하는 걸로 착각할 수 있음(정상, 일시적).

---

## 🅓 대본위키 학습소재 선택기 + 디벨롭 루프 — 2026-07-13 (사무실) → 집에서 이어서

**주제**: 대본 위키(`library.html`) 생성 모달의 "유지할 요소" 6개(주변인물/발상전환/전개방식/훅/어필포인트/말투)를, 위키에 쌓인 대본들을 통계낸 **카테고리 중 선택**하거나 **랜덤**할 수 있게 확장(4단 모드: 원본유지/카테고리지정/카테고리중랜덤/AI자유즉흥) + 생성된 초안을 **개별 편집·프롬프트로 재생성·버전 이력**까지 되는 "디벨롭 루프" 추가.

**진행 상태**: ✅ **전 12태스크(A1~A7 + B1~B5) 구현·리뷰·커밋 완료 (2026-07-14 집PC, 서브에이전트 기반 SDD).** origin push까지 완료 → 서버 자동배포.

- 스펙: `docs/superpowers/specs/2026-07-13-쇼핑쇼츠-대본위키-학습소재선택기-design.md`
- 계획: `docs/superpowers/plans/2026-07-13-쇼핑쇼츠-대본위키-학습소재선택기.md` (A 7태스크 + B 5태스크, TDD 스텝별 완전한 코드 포함)

### 확정된 설계 결정 (스펙에 상세)
1. 통계 표본 = 위키 저장분만이 아니라 **대본추출된 전체**(`script_extracts`)
2. 카테고리(레시피/뷰티/생활용품 등)**별로 따로** 통계·옵션 생성
3. 모드 4가지 전부 유지(원본유지/카테고리지정/랜덤/AI자유즉흥)
4. 통계는 **자동으로 매일 새벽** 재계산(수동버튼 없음)
5. 재생성은 **전체재작성 + 부분선택수정 둘 다** 구현
6. 버전 **이력 저장**(되돌리기 가능, 덮어쓰기 아님)

### ✅ 완료 (2026-07-14)
- A1 script_extracts category+구조백필 / A2 element_stats 클러스터링 / A3 element_category_stats 테이블 / A4 daily_batch(예외격리 포함) / A5 element_options API / A6 script_generate 4단모드 / A7 생성모달 드롭다운UI+JSON body
- B1 script_drafts 테이블 / B2 초안저장+draft_id / B3 재생성(전체·부분) / B4 draft refine·edit·history API / B5 편집텍스트박스+지시문재생성+버전이력UI
- 검증: 태스크별 유닛테스트 통과 + 앱부팅·라우트등록 + **실DB E2E 스모크 통과**(버전 2→3단 체이닝·refine 가드·edit). 신규 실패 0.
- ⚠️ 작업 중 **다른 세션이 같은 워킹트리에서 틱톡·꾸미기·lens 동시 커밋** → 각 커밋은 foreign hunk를 인덱스에서 격리(`git apply --cached -R`)해 오염 없이 분리함. (A1 커밋만 초반에 틱톡 hunk 섞임 — 사용자 승인하에 유지.)

### ✅ 배포 후속 3건 전부 완료 (2026-07-14 집PC, 이어서 세션)
1. **A4 원격 크론 등록** — 이미 등록돼있었음(`0 4 * * *`, `/tmp/shopping_shorts_daily_batch.log`). 로그 확인: 매일 정상 자동실행 중.
2. **UI 실브라우저 검증** — 라이브에서 전체 플로우 실클릭 검증 완료: 생성모달 열기 → 요소별 랜덤/카테고리 드롭다운(레시피·생활용품 각각 다른 라벨 정상 조회) → 초안 3개 생성 → 지시문 입력 후 **전체 재작성**(톤 변경 확인) → **버전 이력**(v1/v2)에서 **v1 되돌리기** → **선택 부분만 수정**(더블클릭 선택한 단어만 교체, 나머지 원문 유지) 전부 정상 동작.
3. **A7 마이너 하드닝** — 재확인 결과 `n=int()` 파싱(app.py:630)과 `elem_modes` non-dict 가드(app.py:634-636)는 **이미 코드에 있었음**(과거 세션이 반영, 목록만 안 지워짐). `option value` 라벨은 `textContent`로 세팅해 애초에 XSS 안전. **카테고리 DOM추출**만 실제 취약(`.meta`가 카드당 2개 있어 첫 매치·`split('·')` 문자열파싱에 의존 — 마크업 순서 바뀌면 조용히 깨짐) → `card`에 `data-category` 속성 부여로 교체·커밋(`b7538392`)·서버반영·라이브 재검증 완료.

### ⚠️ 검증 중 새로 발견한 이슈
1. ~~`script_extracts.category`가 항상 NULL~~ → **사용자 결정: 옛 데이터 역매핑 안 함, 대신 상위랭킹 신선데이터로 기본값 시드** (2026-07-14). 레퍼런스 랭킹(`last_run`, score 내림차순) 상위 30개는 이미 category가 붙어있는 신선한 데이터이므로, 그걸 추출+구조분석해 `element_category_stats` 초기 표본을 까는 `shopping_shorts/seed_baseline.py` 작성·커밋(`c6857caf`)·서버 실행. 위키 저장 없이 `script_extracts`만 채움(설계결정#1과 부합: 표본=위키뿐 아니라 대본추출 전체). 진행상황은 이 세션 로그/log.md 참조.
2. ~~"AI 자유즉흥" 모드가 UI에 노출 안 됨~~ → **사용자 확인: 불필요, 조치 안 함** (2026-07-14). 백엔드 `free` 모드는 옵션 없을 때 자동 폴백 용도로만 유지, UI에 명시적 선택지 추가 안 함.

### 참고 — 이번 세션에 별도로 완료·배포된 것들(이 트랙과 무관, 조치 불필요)
- `/find` 페이지: 사용자 직접 키워드입력+5개국어 번역(`translate_keyword`), 레시피영상이 조리도구로 오분석되던 문제 수정, Lens 추천프레임 — 전부 커밋·배포 완료.
- 소통큐(`/outreach`) 댓글 자동채우기 Tampermonkey 유저스크립트 — 사무실 PC 설치까지 완료·실사용 검증됨.
- 홈 PC의 유튜브 레퍼런스 랭킹 Phase1 작업물은 이 PC에도 pull 받아 확인함.

---

## 🅒 틱톡 키워드검색 발굴(Apify B2) — ✅ 완료 (2026-07-14 집PC, 커밋 919058e8, push됨)

**전부 구현·테스트·UI·라이브푸시 완료.** TDD 37개 테스트 신규. 로컬서버로 UI·가드 429(예산/하루) 육안검증.
- tiktok_search.search_full()(풀 raw 스키마) / store 하루카운트·월예산 헬퍼 / service.collect(tiktok) 키워드분기(5개국어 번역→Apify) / app 가드+/api/tiktok/settings / index.html 틱톡탭 모드토글+노브패널+비용·남은횟수 표시.
- 요율 clockworks/tiktok-scraper $1.70/1,000건. 기본값 검색60·하루10회·월$5.
- **2026-07-14 방향전환**(커밋 6d3c9736, 서버 수동배포 완료): 5개국어 자동 폐기 → **사용자 언어지정+국가확장** 방식. 키워드 시드 kind=언어코드(ko/en/ja/zh/ru), 켠 언어만 각각 검색. 언어당 기본 50개(60→50). 중단조건 없음(비용은 나중에 **포인트=현금 차감** 모델로 갈 예정이라 괜찮음). UI 언어선택기+언어당개수+언어수기반 비용표시. 브라우저 육안검증 완료(ko/en 공존, $0.170=2언어×50).
- ⏭ **남은 것(다음 세션)**: 실제 Apify 토큰으로 라이브 1회 수집(요금 발생) 육안검증 — 서버 배포·env토큰 준비완료, 대시보드 틱톡탭 키워드모드에서 언어 골라 "지금 수집"만 하면 됨. 테스트는 개수 낮춰서(예: 15개, ~$0.04). / 향후: 검색기반 포인트=현금 차감 과금.

### (원본 설계 메모 — 아카이브)
**주제**: 쇼핑쇼츠 레퍼런스 랭킹에 틱톡 키워드검색 발굴 추가. 설계 확정·실증 완료.

### 확정 방향 (이번 세션 전부 실증)
- **틱톡 무료 발굴 불가**(실증): yt-dlp `/search`=Unsupported, `/tag`=차단. 계정방식·개별영상 yt-dlp만 됨.
- **B1(무료 브라우저) 폐기**: 로그인 크롬 검색 24개 수확은 실증했으나 Playwright설치+로그인+봇취약+**운영자전용(고객불가)**. 5센트 아끼려는 취약도구라 폐기.
- **B2(Apify) 채택**: 서버·고객 공용·안정. 인스타 `apify_client.py`·JWT 재사용.

### Apify 요율 (조사확정)
- 액터 **`clockworks/tiktok-scraper`**, `searchQueries` 키워드검색 지원.
- **$1.70/1,000건**(1건 $0.0017): 30개=~5센트, 60개=~10센트, 100개=~17센트. **월 $5 무료=~2,900건/월.**

### 구현할 것 — 관리자 노브 3개 + Apify 연동 (한 세트, 기본값은 나중에 조정)
1. **검색당 개수**(설정값, 기본 60) — 하드코딩 금지. 60 fetch→우리필터(댓글/속도/가속) top30 추림.
2. **사용자별 하루 수집 횟수**(기본 10/일) — 남용방지. UI에 "오늘 남은 N회".
3. **월 예산 상한 킬스위치**(기본 $5) — 넘으면 자동중단. 비용폭주 차단.
- 번역기능(있음, translate_keyword)과 결합 → 5개국어. 다국어는 개수×언어수 곱 과금(설명필요).

### 파이프 (3조각 다 실증)
`번역(있음) → Apify tiktok searchQueries(신규) → build_tiktok_items(있음) → apply_grades(있음) → 랭킹저장(있음)`

### 구현 위치
- `apify_client.py`: 인스타 패턴 참고, actor=clockworks/tiktok-scraper 호출. **input 스키마는 액터페이지 보며 배선.**
- `service.py` `_collect_tiktok()`: 키워드검색(Apify) 분기 추가(현재 계정시드 yt-dlp만).
- `ranking.py` `build_tiktok_items`: 있음, Apify 결과 필드 매핑만.
- `store.py`: 설정테이블+하루카운트+월예산누적.
- `app.py`: 수집 엔드포인트에 하루횟수·월예산 가드 + 설정 GET/POST.

### 참고
- 이미 배포됨: 틱톡 Phase2(**계정시드** 방식) 커밋 `c43c0042`, 서버 active. 인스타/유튜브/틱톡(계정) 3분할 탭 라이브. 이번 건 그 위에 **키워드검색** 얹는 것.
- APIFY 토큰 = 서버 env 인스타용 그대로 사용.
- **별개(무료·언제든)**: 유튜브 발굴루프(뜬 영상 채널을 창고 자동축적) 미구현.

---

## 🅐 쇼핑쇼츠 "대본 위키(도서관)" — 2026-07-13 (집 PC) 대량 진척

라이브: **https://shoppingshorts.duckdns.org** (서버 `ubuntu@3.39.179.148`, systemd `shopping-shorts`)
전부 커밋·푸시·배포 완료. 최신 **HEAD 4fc04971** (서버 동일). 로컬 SSH키: `C:\Users\CH\Desktop\LightsailDefaultKey-ap-northeast-2.pem`

### ✅ 오늘 완료
1. **레퍼런스 랭킹 개선** — 카드 채널명 옆 🔗 링크복사 / 썸네일 클릭 인라인 재생(`/api/video` 프록시, 인스타 핫링크 우회).
2. **카테고리 2단 구조**(유형=비법형/제품형/혼합형 → 세부주제) + **AI 캡션 분류**
   - `categorize.py`: 캡션 우선 점수제(채널명 태그도배 오분류 해결) + 채널명은 강한 장르어만.
   - `ai_categorize.py`: 수집 시 Gemini가 캡션 의미로 재분류(주), 키워드는 폴백. `service.collect`에 통합.
3. **대본추출** — 카드 📝 → download_video + `script_extract`(Gemini) → 세그먼트+전체대본 모달. 캐시 `script_extracts`. 0초 훅 누락 프롬프트로 해결. 모달은 이동식(드래그)·논블로킹.
4. **대본 위키(도서관)** — 핵심 신규:
   - store: `script_wiki` 테이블. app: `/api/wiki/save·list·remove·video·generate`.
   - `structure_analyze.py`: 대본→구조(훅유형·hook_line·**화자**·**주변인물**·스토리라인·**전개방식**·**발상전환**·**어필포인트**·**tone(말투·어미)**·비트·설득장치·왜).
   - `library.html`: 원본영상 **인라인 재생**(영구보관 `data/wiki_media`, `/api/wiki/video` Range지원) + 강화 구조분석 나란히.
   - **생성(적용) Phase A** — `script_generate.py`: 요소별 **유지/변형 토글** + 모드 **A(같은주제 변주)/B(내주제 이식)** → 20초 초안 N개. 도서관 카드 🎬 "이 구조로 생성" 모달.
   - 스모크 검증: "주변인물만 변형" → **농원 언니 / 김밥집 이모님** 등 자연스러운 초안 생성 확인. (사용자 핵심 요구 = 주변인물 자연스러운 스토리텔링 재현 OK)

### ⏭ 내일 이어서 (우선순위)
1. **모드 B(내 제품 이식) 실사용 테스트** — 제품 하나 넣어 품질 확인, 생성 프롬프트 튜닝.
2. **믹스(Feature B)** — 도서관 카드 체크박스 → 2~3개 S급 선택 → 강점 조합(훅=A·전개=B·주변인물=C) → 생성. (`/api/wiki/mix` + `script_generate.generate_mix`)
3. **스타일 라이브러리** — 뽑아둔 `tone`(말투·어미)들을 모아 조합(사용자 요청 "스타일 규정을 만들어놓고 샘플 조합").
4. S급 더 담아 구조분석·생성 품질 점검(현재 위키 3개).

### 파일 지도
`shopping_shorts/`: categorize.py, ai_categorize.py, script_extract.py, structure_analyze.py, script_generate.py, store.py, app.py / `static/`: index.html(랭킹), library.html(도서관)

### ⚠️ 배포 주의 (오늘 실제로 겪음)
서버 자동배포(3분 크론)가 **텔레그램 크롤봇의 `raw/telegram` 실시간 쓰기 + `pipeline/atoms/autopilot_state.json` dirty**로 `git pull --ff-only`이 계속 막혀 서버가 옛 커밋에 정체됐음.
→ 수동배포는 **`git fetch && git reset --hard origin/main && sudo systemctl restart shopping-shorts`** 로 강제정렬(raw는 봇이 재생성하니 손실 무해). 근본해결은 `deploy/auto_deploy.sh`를 reset 방식/skip-worktree로 손봐야 함.
관련 메모리: [[project_쇼핑쇼츠_자동화]] / [[reference_deploy_truth_branch_ssh]]

---

## 🅑 VMake 자막제거 실스펙 채우기 (다른 트랙 — 내일 회사서)

**날짜**: 2026-07-13 (집 PC) → 내일 회사서 VMake API 키/문서 확보 후 이어서

### ✅ 완료 — VMake 자막제거 연동 뼈대 (전부 커밋됨)
믹스된 최종 영상의 원본 하드섭을 VMake API로 제거하고 우리 자막을 굽는 기능.
흐름: **믹스(자막X) → VMake제거 → 우리자막**. 옵션 토글, 개인키 대시보드 저장.
설계: `docs/superpowers/specs/2026-07-13-쇼핑쇼츠-VMake자막제거-design.md` / 계획: `docs/superpowers/plans/2026-07-13-VMake자막제거.md`

### ⚡ 내일 바로: VMake 실제 API 스펙 채우기
`shopping_shorts/vmake_client.py`가 **모든 불확실 스펙을 격리**. 지금은 추정값+mock. open.vmake.ai(로그인) 문서 보고 교체:
1. `_API_BASE`(추정 `https://open.vmake.ai/api/v1`) 2. `_sign()` 서명 알고리즘 3. `_auth_headers()` 헤더명 4. `_submit()` 엔드포인트·업로드 필드 5. `_poll()` job 조회·상태·결과URL 필드 6. 키 형식(`app_key:secret` 가정, `_split_key`).
교체 후: mock 테스트 유지 + **실제 키 등록 → 진짜 소스 1회 렌더** → 자막제거+우리자막 프레임 눈검증(로컬 ffmpeg) → 서버 라이브 1건.

### ⚠️ 최종 코드리뷰가 짚은 "옵션 ON 첫 실전 필수 확인 2가지"
VMake 반환 영상에서 반드시 확인, 미보존이면 `_burn_captions`(video_assemble.py) 보강:
1. **오디오 보존?** — 지금 `-c:a copy`로 VMake출력 오디오 복사. VMake가 오디오 빼거나 재인코딩하면 **TTS 나레이션 무음**. 미보존이면 원본 TTS 트랙 재매핑.
2. **길이·fps 보존?** — 자막 타이밍(t0)은 TTS 길이 누적 기준. VMake가 길이/fps 바꾸면 자막 밀림.
(사소: `_download`를 requests로 통일하면 결과 URL 인증/에러본문도 잡힘.)

**사용자가 줄 것**: VMake 결제 후 API 키 + 개발자 문서(엔드포인트/서명 스펙).
