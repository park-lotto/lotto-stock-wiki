# NEXT_SESSION — 이어서 할 일 (병행 트랙)

> ⚠️ 여러 작업 트랙이 병행 중. 각자 자기 트랙만 이어서. main 고정, `git add`는 자기 파일만(-A 금지).
> ⚠️ **동시세션 순차커밋 규칙**: 커밋 전 `git status`로 남의 hunk 섞였나 확인 → 내 파일만 stage → 먼저 커밋 중인 세션 있으면 기다렸다 순차. 커밋 후 HEAD에 내 변경 grep 확인(덮임 감지). memory `feedback_동시세션_순차커밋`.

---

## 🎞️ 영상제작소 모션효과 — Phase1 뼈대 ✅완료·푸시됨 / Phase2(팩) 미착수 (2026-07-15 사무실 → 회사에서 이어서)

**트리거**: "모션효과 Phase2 이어서" → 이 섹션 + memory `project_영상제작소_모션효과` + `reference_ffmpeg_alpha_overlay` 읽기.

**한 줄**: 딸깍 넘는 최상 효과 = Remotion으로 **모션 자산 프리렌더**(전환·스티커) → ffmpeg `overlay`로 합성(전체 Remotion 렌더는 자동화 죽여서 폐기=오바). 전환도 xfade 아닌 **타임드 투명 레이어 오버레이**로 처리(concat `-c copy` 유지=서버 다운 회피).

- 스펙 `docs/superpowers/specs/2026-07-15-영상제작소-모션효과-뼈대-design.md`
- 계획 `docs/superpowers/plans/2026-07-15-영상제작소-모션효과-뼈대.md` (8태스크 TDD, SDD)

**✅ Phase1 뼈대 완료·origin/main 푸시됨 (SDD 서브에이전트, 각 spec+quality 리뷰 통과, 12 유닛테스트 green + e2e 육안검증):**
- `motion_assets.py`: 매니페스트 로드 + 레이어(asset_id) 해석(default병합·`_abspath`·미존재 skip).
- `video_assemble.py`: `_motion_layer_filters`(타임드 투명레이어 filter_complex 빌더) + `_burn_captions`에 모션 레이어 N개 합성 + `color_filter`(eq/curves) 통합. **concat 무변경.**
- `mix_pipeline.run_render`: `deco.motion.layers` asset_id→실경로 해석(`MOTION_ASSETS_DIR`).
- `motion_text.py`: 텍스트종속 렌더 인터페이스 **스텁**(`TextRenderUnavailable`) — Phase2 연결점.
- `shopping_shorts/motion/`: **Remotion 프로젝트**(`npm run render:library`) — SwipeLeft·Sparkle 컴포지션 → **ProRes4444→qtrle .mov(argb)** 자산 생성. `assets/motion/`에 `swipe_left.mov`·`sparkle.mov`·`ph_*`(플레이스홀더)·`manifest.json`.
- **육안검증**: 파란 베이스에 스와이프 바 + ✨스파클이 enable 타이밍대로 투명 합성 + 색감필터 확인.

**⚠️ 하드-원 교훈(반드시 숙지, memory `reference_ffmpeg_alpha_overlay`)**:
1. ffmpeg `drawbox`는 rgba **알파채널을 안 박음** → 투명자산은 **불투명도형을 투명캔버스에 `overlay=format=auto`로 합성**해야 함(자산 생성 시).
2. **VP9 알파 webm 금지** — ffmpeg 기본 vp9 디코더가 알파 무시(불투명 박스로 합성됨). `libvpx-vp9` 강제해야 알파 나옴. 제품 빌더는 디코더 플래그 없으므로 **qtrle .mov(argb) 사용**(실측 정상).
3. 제품 빌더(default overlay)는 알파를 **정상 존중** — 자산에 진짜 알파만 있으면 됨.
4. `_burn_captions`는 폰트 미해결 시 조기 복사 return → 모션도 스킵(프로덕션엔 폰트 22종 있어 정상).

**⏭ 회사에서 이어서 — Phase2(프리셋 팩):**
- 빅채널 레퍼런스 뜯어 **팩 3~4개 정의**(예: 다이나믹팝/미니멀시크) = {전환 + 키네틱타이포 + 콜아웃 + 색감} 세트. 딸깍 완성스타일의 모션 버전.
- **per-video 텍스트 렌더 실구현**: `motion_text.render_text_overlay` 스텁을 Remotion `render:overlay`(투명 오버레이) subprocess 호출로 채움. **선행: 서버(Lightsail)에 Node/헤드리스크롬 있는지 확인**(없으면 텍스트팩은 로컬/위저드 렌더만).
- **위저드 UI**: produce 꾸미기 단계에 팩 선택(딸깍 통합). `deco.motion={pack_id,layers[],color_filter}` 저장은 기존 `/api/produce/mix/settings`(deco) 재사용 — 신규 엔드포인트 불필요.
- 색감 필터 프리셋 세부값 튜닝.

---

## 🎬 장면 라이브러리(재사용 짤 뱅크) — 설계 완료, 구현 0 (2026-07-15 사무실 → 집에서 이어서)

**트리거**: "장면 라이브러리 이어서" / "짤뱅크 이어서"

**한 줄**: 믹스 첫단계에서 자주 쓰는 후킹 장면(놀라는짤·효과음·비법 한스푼 등)을 모아두고, 믹스할 때 AI가 대본 비트에 맞는 걸 자동배치. = "AI 큐레이션 재사용 짤 뱅크".

**✅ 완료**: 브레인스토밍(시각 companion)→설계→spec 커밋. 스펙 `docs/superpowers/specs/2026-07-15-쇼핑쇼츠-장면라이브러리-재사용짤뱅크-design.md`.

**확정된 설계결정(스펙에 상세)**:
1. 3타입 = 화면짤(clip)/효과음(sfx)/오버레이(overlay). 화면짤은 **replace(화면교체)/cutaway(삽입) 하이브리드**(자산마다 지정).
2. "한스푼" 애매함(가루↔액체↔세제) = **한단어 라벨 금지, 다축 구조태그**(scene_desc·role·category·subject·tone·keywords). 저장 순간 Gemini 자동초안 → 사람 확인·수정(딸깍저장).
3. 출처 = 우리 작업영상(produce) + 레퍼런스랭킹(reference) + 업로드. 구간컷으로 자산화. `scene_assets` 테이블(멀티테넌시 격리).
4. 매칭 = `detect_subject`(있음)+카테고리 1차 DB필터(subject 불일치=여기서 탈락) → Gemini 판정(그라운딩: asset_id·beat_idx만 지목) → score≥0.7 자동배치, 미만은 제안만.
5. 렌더 = video_assemble 4처리(replace/cutaway/sfx/overlay). **cutaway 자막 t0 싱크가 최대 리스크**(삽입이 타임라인 밀림 → TDD로 못박기).
6. 접근1(자산=확장 화면인벤토리) **2페이즈**: 페이즈1(뱅크: 테이블+저장/자동태깅+관리UI scene_library.html+저장다리) → 페이즈2(매칭 match_scene_assets+렌더확장+믹스검수 배치패널).

**⏭ 집에서 재개**:
- **사용자 spec 검토 대기** — 파일 열어 확인, 고칠 것 있으면 반영 후 → `superpowers:writing-plans`로 페이즈1 계획서부터.
- 관련파일 사전확인: `edit_plan.py`(detect_subject·_vault_call·_ground_ref 패턴 재사용), `video_assemble.py`(_render_mix·_burn_captions의 overlay/BGM amix 배선 확장), `mix_pipeline._plan_and_tts`(EDL직후 asset_match 스텝), `store.py`(멀티테넌시 패턴), `static/scene_library.html`(신규)·`sidebar.js`(항목추가).
- 공유워킹트리 위생: `git add`는 내 파일만(-A 금지). 이번 세션도 동시세션 커밋들 사이로 spec커밋 dangling 겪음 — 커밋 전 `git status`·커밋 후 HEAD grep 확인.

---

## 🎬 영상제작소 대본·영상믹스 단계 통합 — SDD Task1~2完·Task3 백엔드完·프론트 未 (2026-07-15 집PC → 집에서 이어서)

**트리거**: "영상제작소 대본믹스 통합 이어서" → 이 섹션 + memory `project_영상제작소_대본믹스통합` 읽기.

**목표**: 영상제작소(`produce.html`)의 분리된 "1·대본"+"2·영상"을 하나의 "제작소"(좌=영상풀·우=결과) 2단으로 통합. 넘어온 영상=재료풀, 각 영상에 📝뽑기(대본)·🎬담기(화면) 겸용. 대본 뽑기는 **도서관 생성모달 재사용**(2경로 1엔진: 레퍼런스→도서관=학습축적 / 레퍼런스→제작소직행=바로제작). ⭐위키저장 다리로 제작소서도 학습 반영.

- 스펙 `docs/superpowers/specs/2026-07-15-쇼핑쇼츠-영상제작소-대본믹스-통합-design.md`
- 계획 `docs/superpowers/plans/2026-07-15-쇼핑쇼츠-영상제작소-대본믹스-통합.md` (5태스크 TDD, SDD 서브에이전트 방식)

**✅ 완료·배포됨**:
- **Task1** (커밋 9e74e892+b0128340): 백엔드 `/api/produce/save_to_wiki` — URL기반 위키저장(load_last_run 비의존), category `.strip() or None` 정규화(학습 NULL누수 방지). spec·품질 리뷰 통과.
- **Task2** (커밋 2e121144에 흡수, 코드 온전): produce.html 단계병합 골격 — STEPS 8→7, data-step 2~7→1~6, 좌우2단, `renderPool`/`toggleFootage`/`syncFootageToMixUrls`/`refreshFinalPeek`, `openScriptModal(i)`는 **임시 스텁**(alert). 역할배정 UI 폐기. spec·품질 리뷰 통과.
- **Task3 백엔드** (커밋 bcd32029): `/api/wiki/generate`에 **위키미저장 폴백** — body에 `structure`/`base_script`/`category` 실어오면 위키 없어도 생성(제작소 직행 대본생성 지원). 테스트 3 green. 기존 위키경로 하위호환 유지.

**⏭ 집에서 이어서 — Task3 프론트(도서관 모달 이식)부터**:
- **produce.html에 pm 네임스페이스 모달 이식 미완**(pmModal/pmRunGen/pmUseDraft 0 — 세션한도로 중단). 계획서 Task3 Step1~5 코드 참고. `openScriptModal(i)` 스텁을 교체: 📝뽑기→`/api/produce/extract_from_url`(url·shortcode·category)로 추출→도서관식 생성모달(구조/요소토글/초안/편집·재생성·버전이력/**확정버튼**). generate 호출 시 body에 structure/base_script/category 실어보냄(백엔드 폴백과 짝). 확정=`STATE.script=…;setScriptMode('manual');refreshFinalPeek();saveWork()`.
- ⚠️ **`extract_from_url`에 category 전달 보완**(계획§6.2): 지금 `save_script(code,result)`가 category 안 넘김 → `category=body.get("category")` 추가 필요(app.py:518~). Task3 안에서 같이.
- **Task4**: 오른쪽 `#saveWikiBtn`(현재 display:none, onclick=saveScriptToWiki 미정의)에 `saveScriptToWiki()` 배선 → Task1 라우트 호출. 확정대본+category로 위키저장.
- **Task5**: whole-file seam검사(중복id/미정의핸들러/data-step) + 실렌더 통합 grounding(즐겨찾기 영상 2개→📝뽑기 실추출·생성·확정→🎬담기→MIX매칭→⭐위키저장→element_stats 증가 확인) + 라이브 배포검증.

**⚠️⚠️ 이 워킹트리 동시편집 지옥**: 다른 세션/PC가 초단위로 같은 produce.html·motion·tts·app.py 커밋 중. Task2때 내 커밋이 남의 커밋에 흡수됨(코드유실0). **집에서는 그 세션 꺼져있길 기대** — 안 그러면 격리커밋+autostash rebase 반복 필요. 구현자에게 "변경즉시 자기파일만 격리커밋+push, 보류창0" 지시할 것. `git add -A` 절대금지. produce.html에 `DEFAULT_APPLIED`(남의것) 섞이면 staged 제외.
- 학습배치 정상 확인(2026-07-15): 서버크론 0 4 * * *, element_category_stats 81행 실축적.

---

## ✅ 대본생성 소재고정 리메이크 — 구현·검증 완료 (2026-07-15 집PC, 커밋 15bbfe99~49f7d023)

애매하던 대본생성 모드 A/B를 **remake(원본 소재 고정·표현만 새로=중복회피) / transplant(내 제품 이식)**로 재편. 리메이크는 원본 대본에서 소재 자동감지(수정가능) → 프롬프트에 소재 잠금. SDD 5태스크, 각 spec+quality(opus) 리뷰·최종 전체리뷰 통과, 65 테스트 green.
- 스펙 `docs/superpowers/specs/2026-07-15-대본생성-소재고정-리메이크-design.md` / 계획 `docs/superpowers/plans/2026-07-15-대본생성-소재고정-리메이크.md`
- ⏭ **남은것(다음 세션)**: 라이브 배포 후 실 S급 항목으로 **브라우저 육안 검증**(이번엔 브라우저 MCP를 동시세션이 점유해 이월) — 리메이크 생성 결과가 원본 소재 유지+표현만 다른지, 소재칸 자동프리필 뜨는지 눈으로 확인.

---

## ✅ 꾸미기(5단계) "피팅룸" UX 재설계 — 구현·검증·배포 완료 (2026-07-15 집PC, origin/main)

**배경**: 꾸미기 페이지 "버튼 벽" 불만 → "직접 옷 피팅해보듯" 실장면 위 완성본 카드로 고르기 + 최적샘플 기본 + 세부는 고급 접기.

**✅ 완료**: SDD 3태스크(+통합 grounding) 전부 구현·리뷰·배포. 각 태스크 spec+quality(opus) 리뷰 통과 → 통합 grounding 4/4 통과(JS에러0) → 전체브랜치 리뷰 Ready.
- Task1 좌측 큰 미러(380px)+완성스타일 카드+강조단어 노출 / 세부(폰트·자막·워터마크·내프리셋) `details#advDetails` 접기
- Task2 `renderStyleCards` — 실장면 poster 위 스타일텍스트 미니 9:16 카드(대표5+더보기18)
- Task3 `applyDefaultStyleOnEntry`(기본=임팩트옐로+실장면배경 자동ON) `initHeadcopy`에 배선
- 리뷰가 잡은 버그 5건 수정: ①poster캐시 매칭전 빈값영구고정 ②선택카드 하이라이트 오탐(PICKED_STYLE_IDX) ③색상 대소문자매칭 ④alert가드 setTimeout경합(→silent 파라미터 클로저) ⑤**재진입 시 수동조정 날아가는 회귀(DEFAULT_APPLIED 최초1회 가드)** — 시그니처 경로라 유보안하고 수정
- 커밋 3ba5671b·a5610c0d·4f29c742·22466b17·320c9dba, 회귀수정은 동시세션 커밋 0f2c2791에 실려 반영(파일 온전 확인). 순수 produce.html이라 서버무변경, 자동배포 반영.
- ⚠️ 동시세션 `git add -A`가 내 변경을 자기 커밋에 쓸어담음(무손실) — 공유워킹트리 -A 위험 재확인
- ⏭ **남은것(defer, cosmetic)**: poster캐시 재매칭 시 카드썸네일 stale(미러는 live·cache-buster). 필요 시 MIX_JOB 재할당 지점에서 `POSTER_URL_CACHE=null` 무효화. 계획서 Task4 stale 참고.

---

## 🎙️ 보이스 프리셋 라이브러리 — ✅ 구현·검증 (2026-07-14 집PC, 커밋 b5463de9~3cd1abfe)

### 🔥 2026-07-15 (사무실) 보이스 "자연화 엔진(AI티 제거)" — 구현 거의 완료, 집에서 마감
**방향 대전환(사장님 확정)**: 감정태그 몇 개 뿌리기 ❌ → **규칙기반으로 텍스트를 다듬어 서울 20대 여성 톤·AI티 제거**. 기준 = "1%라도 AI로 판단되면 실패". 브레인스토밍→스펙→계획→SDD 구현까지 진행.
- 스펙: `docs/superpowers/specs/2026-07-15-쇼핑쇼츠-보이스-자연화엔진-AI티제거-design.md` (커밋 826a7451)
- 계획 2부: `docs/superpowers/plans/2026-07-15-보이스-자연화엔진-1-엔진과통합.md` / `-2-작업대와ASR.md` (커밋 4f53a9e1)
- **핵심 통찰**: AI티 병목은 감정부족이 아니라 ①문어체 종결(낭독체) ②비트마다 리셋되는 콜드스타트 억양 ③v3 take 편차. → 8스테이지 순수엔진 + 튜닝작업대 + N-best/연속성/seed.
- **✅ 구현·테스트·커밋 완료 (SDD, 서브에이전트 기반, 구현=sonnet·리뷰=opus)**:
  - **엔진** `narration_naturalize.py`: 8스테이지(정규화·구어체·연음·끊어읽기·끝음·추임새·감정곡선·억양) 순수함수, 결정적, 하드캡(태그≤3·비트당≤1·추임새상한). 28테스트. opus리뷰로 실버그3개(phrasing "고"오탐·whitespace훼손·emotion_arc IndexError)+죽은코드 수정. 커밋 ea6087ee~a04b1029.
  - **tts.py**: seed·previous_text/next_text(연속성)·**v3 speaker_boost 자동drop**·N-best래퍼(`synthesize_best`). 하위호환 유지. 11테스트. 커밋 6eaf2b86·b6d4b2e0.
  - **mix_pipeline.py**: TTS루프를 `_synthesize_beats` 헬퍼로 추출, naturalize+연속성(raw나레이션)+N-best 통합. `_plan_and_tts`·`resynth_tts_job` 둘 다. 커밋 2e121144.
  - **asr_check.py**: Whisper(GROQ) 재전사→diff 오독자동경보 + mismatch_score(N-best ranker). config에 `GROQ_API_KEY`. 커밋 928539ba.
  - **store.py+voice_presets.json**: 프리셋에 `naturalize_profile` 저장(컬럼마이그레이션) + **speaker_boost 42개 전부 정리**. 커밋 65ab3488.
  - **app.py**: 튜닝전용 API 4개(`/api/voice-tune/corpus·preview·synth·profile`)+auth allow. 코퍼스 10줄. 커밋 6cb4cbbb·b41af1a0.
  - **작업대** `static/voice_tune.html`: 좌 코퍼스카드(원문→변환텍스트→▶합성/재롤→ASR diff) 우 8스테이지 토글+강도슬라이더+seed+N-best+💾동결. 서빙200·corpus·preview(좋습니다→좋아요/50%→오십 퍼센트) 백엔드 검증완료. 커밋 3546cd3f.
- ⏭ **집에서 마감(다음 세션 즉시)**:
  1. **whole-branch 최종리뷰**(SDD 필수단계, 아직 안 함) — cross-unit seam 확인. memory `feedback_whole_branch_review_catches_seams`.
  2. **작업대 실 grounding**: ELEVENLABS 키로 코퍼스 전체 합성→**사장님 귀 튜닝**(각 성우 프로파일 강도·구어체맵·발음사전 다듬어 동결). 이게 "진짜 게이트"(자동테스트 대체불가). freeze버튼·스크린샷 grounding도 미완(세션한도로 서브에이전트 중단).
  3. **규칙 정교화**: 구어체맵·연결어미·감정곡선 태그·추임새뱅크는 **시작점**임. 사장님 귀로 값 조정이 본론. (엔진은 이미 값을 데이터로 받게 돼있음 — 코드수정 최소)
  4. **서버 배포**: `/etc/shopping-shorts.env`에 `GROQ_API_KEY` 추가(ASR용). push하면 3분 자동배포.
  5. (선택) **연속성 v3 실지원 확인**: previous_text/next_text가 eleven_v3에서 실제 먹는지 실키로 1회 검증(미지원이면 payload무시라 안전).
- ⚠️ 이 세션 내내 **동시세션 3~4개가 같은 워킹트리 편집**(produce.html·motion·대본생성). 공유인덱스 레이스로 produce.html이 내 커밋 2e121144에 한번 섞임(무손실, 0f2c2791이 위에 재작업). 이후 전부 **`git commit -- <경로>` pathspec 커밋**으로 격리 성공.


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

> **2026-07-14 추가 완료(이 세션, 집에서 이어서)**: ① 배포후속 3건(A4크론 이미가동확인·UI실브라우저 전체플로우검증·A7 카테고리DOM추출 하드닝 `data-category`) 완료. ② **학습 기본값 시드**: `shopping_shorts/seed_baseline.py` 신규 — 레퍼런스랭킹 상위30 분석해 `element_category_stats` 2카테고리30행→4카테고리(레시피·생활용품·인테리어·가전)70행 확장(서버 실행완료). ③ **`library.html` 카드 레이아웃 대량 반복수정 후 확정**: 영상 | 본문(폭제한, 발상전환 아래 하단에 액션버튼3개 `margin-top:auto`로 채움) | 사이드(비트구조·전체대본보기·설득장치·학습현황) 3열. 전부 커밋·푸시·서버배포·라이브검증 완료. ⚠️ **교훈: 서버에서 `git checkout origin/main -- <file>` 직접반영 금지** — staged 잔재로 auto_deploy가 통째로 멈췄던 사고 원인(CLAUDE.md 배포규칙 #9). 이후엔 push만 하고 3분 크론 기다릴 것. **"AI 자유즉흥" 모드는 사용자가 불필요 확정(UI 미노출 유지).** 미결: script_extracts.category 옛행 NULL 백필은 안 하기로 결정(신선데이터 시드로 대체).

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

### ✅ 소재 고정 + 2모드 — 구현·배포·라이브검증 완료 (2026-07-15)
생성 모달을 2모드로 재편(커밋 `15bbfe99` `30222f8f` `cea4cb12` `8b3bf859`, 서버 배포됨).
- **♻️ remake(원본 소재 그대로)**: `detect_subject()`가 원본 대본에서 소재 한 줄을 Gemini로 뽑아
  `/api/wiki/subject`로 모달에 **자동 프리필** → 프롬프트에 `소재(고정):`으로 박힘. 제품·사실·장면은
  안 바꾸고 표현(훅·어휘·순서·말투)만 리라이트 = 중복 회피. stale 레이스 가드 있음(`window._genSC`).
- **🔀 transplant(내 제품 이식)**: 소재칸 숨고 내 제품칸 노출, subject 미전송. 구조만 빌려 이식.
- **라이브 검증(2026-07-15, shoppingshorts.duckdns.org/library)**: 홈에디터 감자튀김 카드로 실측정.
  프리필 = "튀기지 않은 건강한 감자튀김 만들기" 정상. remake 초안 2개 = 소재(감자튀김) 유지+주변인물
  (아이 친구 엄마·남편) 살린 채 표현만 새로. transplant("무선 창문 청소기") = 구조(옆집 언니 발견→남편
  검증→아이 반응, 개인일화형)만 빌리고 소재 완전 교체, 원본 소재 누출 없음. **프롬프트 튜닝 불필요 판정.**

### ⏭ 내일 이어서 (우선순위)
1. **믹스(Feature B)** — 도서관 카드 체크박스 → 2~3개 S급 선택 → 강점 조합(훅=A·전개=B·주변인물=C) → 생성. (`/api/wiki/mix` + `script_generate.generate_mix`)
2. **스타일 라이브러리** — 뽑아둔 `tone`(말투·어미)들을 모아 조합(사용자 요청 "스타일 규정을 만들어놓고 샘플 조합").
3. S급 더 담아 구조분석·생성 품질 점검(현재 위키 10개).

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
