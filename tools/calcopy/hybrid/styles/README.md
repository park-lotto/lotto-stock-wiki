# 판 설정 — `tools/calcopy/hybrid/styles/<판>.json` (판 등록 한 곳, 관제 097, 2026-10-19)

"키치잇 스타일로 만들어" = `py tools/calcopy/hybrid/run.py <연예인> render --version 키치잇판`. 판 목록 = 이 폴더의 `*.json`(밑줄 `_` 로 시작하는 파일 제외).
읽는 쪽: `run.py`(판 고르기·렌더러) · `render_bench.py`(벤치 판 그리기) · `placement.py`(배치 규칙) · `script_audit.py`(대본 검사) · `styles.py brief`(대본 지시문 판별 절) · `bench_check.py`·`compare_sheet.py`(검사).
`_common.json` 이 먼저 깔리고 판 파일이 덮는다(사전은 깊게 합침, 목록은 대신함). 판 이름 = 파일 이름 = `name` 칸.

## 칸 (★ = 필수)
| 칸 | 뜻 | 예(키치잇판) |
|---|---|---|
| ★`name` | 판 이름(파일 이름과 같다) | `"키치잇판"` |
| ★`renderer` | `bench`(벤치 판 공용 렌더러) · `itssum`·`jaemi`(옛 두 판, 동작 그대로) | `"bench"` |
| `bench` | 근거 경로: `ko`(계약 파일 효과 규칙의 채널 이름) · `channel` · `analysis` · `design` · `line_reads`(줄판독 폴더) · `src_dir`(벤치 원본) · `sfx_events`·`sfx_key`(효과음 신호 표) | `{"ko":"키치잇","line_reads":"channel/kitchit/줄판독",…}` |
| ★`voice` | `name` · `voice_id`(미나 `kr-mina-expressive` / 박창수 `tc_6059dad0b83880769a50502f`) · `candidates`(사장님 귀 확인 대기 후보, 자동 교체 아님) | |
| `cps_target` | 타입캐스트 목표 자/초(일레븐랩스는 서비스 배속 고정) | `6.9` |
| ★`bgm` | `id`(bgm_lib 파일, **사람이 고른다**) · `db_below_voice` · `duck_orig_db`(원음 줄에서) · `duck_narr_db`(나레 줄에서, 기본 0=없음 · `_common`) · `fade_out` · `candidates`(`bgm_pick.py recommend` 추천 상위 3 — 자동 교체 아님) | |
| ★`loudness` | `lufs`(−14 통일) · `tp` | `{"lufs":-14,"tp":-1.5}` |
| ★`length` | `min`·`max` 초 | `{"min":25,"max":30}` |
| `timing` | 줄 사이: `gap` 또는 `gap_after_tts`·`gap_after_orig`·`gap_oo` · 끝 여운 `tail` | |
| `frame` | `kind`(`window` 기본 · `post` 게시글형 · `full` 전체화면 — 아래 표) · `bg` · `window[x,y,w,h]`(full 이면 화면 전체라 안 적는다) · `title[]`(줄마다 font·px·`ink_top`|`center`|`box`+`box_color`·`shear`·`color`·`hi`(대본 'hi' 낱말 색)·`max_w` · 선택 `stroke{px,color}`·`shadow{dx,dy,color}`) · `logo`({text,font,px,x,y,rgba,stroke} 또는 {"kind":"spr_gold"} 또는 null) · `credit` · `watermark` · `comment`(댓글 카드 자리) · `flash_sec`(흰 번쩍 길이) · `post{…}`·`full{…}` | |
| `caption` | `pack`(자막팩 키, caption-motions.js PACKS) · `pack_default`(칸별 팩 기본 등장: narr/orig × first/rest) · `variant_for`(등장 → 팩 줄 변형) · `typing_variant` · `typing_cps` · `chunk_max_chars` | |
| `cuts` | `push_tts`·`push_orig`(컷 천천히 밀기 비율) · `transition{kinds,ms,why}`(장면 전환 — 아래 표, 기본 `{kinds:{cut:1.0},ms:0}` = `_common`) | |
| `sfx_files` | 효과음 종류 → 팩 파일 · `gain_db` | |
| `placement` | `rules`(손으로: 스티커 종류별 조건 lex·needs_key, 타이핑 따라붙는 스티커, 효과음 kind·max, 번쩍임 share) · `counted`(**도구가 씀** — `py tools/calcopy/hybrid/placement.py count <판>`: 벤치 편마다 칸별 등장·강조·스티커·변형·효과음) · `reference`(본보기 벤치 편 고정, 보통 비움) | |
| `render` | (itssum·jaemi 판만) 옛 렌더러 기본값 — 렌더러 DEF 의 주인 | |
| `title_form` | 제목 꼴 한 줄 | |
| ★`script` | `brief`(대본 지시문 판별 절 줄 목록) · `example`(예시 대본 경로) · `audit`(검사 규칙 목록 — 종류: engine·first_line·last_line·count·tts_chars·tts_total_chars·no_adjacent·ending·has_line·forbid_in·cap_chars·orig_span·narr_share·est_length, 꼴은 `script_audit.py` docstring) · `forbid`(_common) | |

## 새 판 만들기(벤치 채널 칼분석 → 판)
1. 벤치 8편 뜯기·스타일분석·줄판독(`briefs/line_read.md`) → `channel/<slug>/`
2. 이 폴더에 `<판>.json` — 위 칸을 채운다(틀 숫자는 스타일분석 실측, 자막팩 키는 caption-motions.js 에 그 채널 팩이 있어야 한다)
3. `py tools/calcopy/hybrid/placement.py count <판>` → counted
4. 예시 대본 1편 → `script_audit.py --version <판>` 통과 → `run.py <연예인> render --version <판>` → `bench_check.py` · `compare_sheet.py`(벤치 나란히, 눈 확인)

## 공용 렌더러 장치 칸(관제 263 지시서 02 — 표준 §3-3 A1·A4·B1) — 판 칸으로만 켜진다, 코드에 채널 이름 없음

| 칸 | 값 | 그리는 곳(render_bench) | 기본(`_common`) | 검사 |
|---|---|---|---|---|
| `cuts.transition.kinds` | 종류별 비율 `{cut, flash, zoomblur, black}` — `_common` 의 `cut:1.0` 은 깊게 합쳐져 남으므로 **cut 밖 종류만** 본다 | `transitions_of`(목록 한 곳) → 줌블러·검은 프레임 = `window_fx`(창 안) · 흰 번쩍 = `render_base`(화면 전체, 옛 길 그대로) | `{cut:1.0}` = 효과 없음 | `test_render_bench_devices.py` · CLI `blur` |
| `cuts.transition.ms` | 전환 길이 ms(0 이면 종류별 기본 flash 100·zoomblur 200·black 33) | 줌블러 = 경계 ±ms/2 동안 최대 12% 확대 + gblur 14 · 검은 = 경계 프레임부터 ms 만큼 | `0` | |
| (자리) | **어느 경계에 무엇** = `placement.place` 가 `placed.transitions:[{t,kind,ms}]` 로 준다(지시서 03). 안 주면 옛 `flashes` → flash, 그리고 cut 밖 한 종류가 비율 1.0 일 때만 모든 컷 경계에. 섞인 비율은 placement 를 기다린다(로그) | | | |
| `bgm.duck_narr_db` | 나레 줄 구간에서 BGM 을 더 줄이는 dB(음수) | `audio()` BGM volume 식(원음 덕킹 `duck_orig_db` 와 같은 식 안) · BGM 만 트랙 `render/bgm_bed.wav` | `0` = 없음(식이 예전과 같다) | `render_info.audio.bed{narr_db,orig_db,gap_db,narr_vs_gap}` · CLI `duck` |
| `bgm.candidates` | 곡 추천 상위 N(`bgm_pick.py recommend <판>` — 벤치 템포·밝기·화성 ↔ bgm_lib) | (렌더는 `bgm.id` 만 쓴다) | — | |
| `frame.kind` | `window` · `post` · `full` | `frame_png`(틀 한 장) · `frame_window`(창 자리 한 곳 — render_window·render_base 가 부른다) | `window` | CLI `postcmp`(설명서 렌더 ↔ 우리 0초 ±4px·ΔE<5) |
| `frame.post` | `head_bar{box,color,icons[bars{x,ys,w,h,color}·search{x,y,size,stroke,color}·text{…,from}]}` · `rules[{box,color}]`(가는 줄·띠) · `author_line{text,font,px,color,x|cx,cy|ink_top,word_spacing}` · `body_box{box,color,fade[위,아래 px],radius,rules[],text{…}}` · `views_line{…}` · `meme_slot{box[x,y,w,h]}` — 글은 대본 `post{brand,author,body,views,meme}` 가 있으면 그것 | `_draw_post` | — | |
| `frame.full` | `band{cy,h,rgba}`(가운데 자막 띠, 선택) — 창 = 화면 전체, 제목·로고·워터마크는 위에 얹힌다 | `_draw_full` | — | |

`render_info.json` 표식: `devices{transition{kinds_set,drawn,n}, duck_narr{db,bed}, frame_kind}` · `style_sha`(판 파일 sha256) · `style_sha_effective`(_common·base 합친 설정) · `renderer_sig`(렌더러 파일@sha) · `line_cps{줄: 자/초}` — 표식 주인 `render_bench.render_marks`(itssum·jaemi 도 부른다), 품질 관문(04)이 읽는다. 자막표.json 에 `transitions`(그린 목록).
시험 판(목록에 안 뜸): `_test_transition`(모든 경계 줌블러 200ms) · `_test_duck`(나레 −8dB) · `_test_post`(게시글형 = banggu 게시글형 훅 틀 좌표).

### 2차 장치 칸(관제 263 02 2차 — 07 `_pending` 요청) — 전부 칸이 없으면 옛 그림 그대로(22판 frame_png 픽셀 차 0 · 잇템로그 ep13 렌더 base·자막·소리 md5 같음)

| 칸 | 값 | 그리는 곳(render_bench) | 요청한 판(07 `_pending`) |
|---|---|---|---|
| `frame.segments[]` | `{t0, t1, frame{…덮을 칸}, captions show\|hide, body_text lines\|null, why}` — 시각 = 초 · `'<줄id>.start\|end'` · `'#k.start\|end'`(k번째 줄). 구간 안 틀 = 판 frame 에 구간 frame 을 깊게 덮은 것(kind·window·title·post… 전부) · `body_text:lines` = 그 구간에서 시작하는 나레·자막 줄 글을 게시글 본문(post.body) 자리에(훅 카드 흰 띠) · `captions:hide` = 그 구간 자막팩 자막 안 그림. 겹치면 멈춤 | 판단 주인 `frame_segments` → `seg_layers`(render_base — 구간 창 자리·크기가 다르면 창 영상을 채워 자른다)·`caption_hidden`·`devices.segments`·자막표 `segments` | 썰템홈샷판 hook_card · 맛템썰템판 hook_card · 썰템쇼판 · 트롯파파판 hook · 잇썸홈판·재미썸홈판 ①(A/B) |
| `caption.stack` | `{lines 2~4, break full\|line, y?, pitch?}` — 덩어리마다 앞 줄 밑에 덧붙이고(글 '앞\n새') lines 가 차면 지움 · `break:line` = 대본 줄이 바뀌어도 지움(문장 단위) · `y`(첫 줄 가운데 px)+`pitch`(그 자막팩 줄 간격 px, 팩 실측) 를 짝으로 적으면 첫 줄이 제자리(자막팩은 여러 줄 덩어리를 가운데 기준으로 세운다 — place y 를 쌓인 줄마다 pitch/2 씩 내림) | `stack_rows`(caption_rows 끝) · `devices.caption_stack` | 썰템홈샷판 page_clear · 맛템썰템판 accumulate · 썰템쇼판 |
| 대본 줄 `kind:"sub"` | `{id, kind:"sub", dur, caps[{text, s0?}…]}` — 나레 없는 자막 줄(TTS 안 부름). s0 = 줄 시작부터 덩어리 시작 초(없으면 글자 수 비례). 컷·자막 꼴은 나레 줄과 같은 길 | `timeline`(sub 줄) · `render`(tts 줄 0 이면 TTS 건너뜀) · `audio`(목소리 자리 무음 · 배경음 기준 = 원음 크기, 원음도 없으면 판 목표 음량 → `render_info.audio.bgm_ref`) · `devices.narration:0` | 신박판 · 도파민썰템A판 · 숏비타민c판(나레 첫 줄 뒤 원음만 = 지금 꼴로 됨) |
| `frame.title[].align`·`x`·`letter_spacing` | `align` center(기본)\|left\|right · `x` = left 왼쪽 끝·right 오른쪽 끝·center 가운데(기본 540) — 잉크(외곽선·그림자 포함) 상자 기준 · `letter_spacing` 글자 사이 px(음수 = 좁힘) | `_title_line` | 신박판 title_align_left·props letter_spacing · 맛템썰템판 `_align_left_x` · 썰템홈샷판 title_letter_gap |
| `frame.window_radius` | 둥근 창 모서리 px(full 은 무시) — 모서리는 틀 바탕이 덮는다(4배로 그려 줄임) | `frame_png` | 신박판 window_radius(frame.json video.radius 87) |
| 재료 컷 `pic`·`pic_bg` | `pic[x,y,w,h]`(창 안 px, 짝수로 내림) — 그 컷만 그 칸에 그림·나머지는 `pic_bg`(없으면 frame.bg). 자르기 비율도 그 칸 비율(얼굴·사진 가운데) | `pic_box`·`clip`(scale→pad) · `render_window` · `devices.pic_cuts` | 맛템썰템판 pic_box_per_cut |
| `post.head_bar.icons[] kind:image` | `{kind:"image", src(저장소 상대·절대), x, y, w, h}` — 그림 아이콘(글꼴에 없는 '≫'·포크 접시) | `_paste_image` | 맛템썰템판 head_icons |
| 글 칸 `stroke`·`glow`(머리띠 text 아이콘·author_line·views_line·body_box.text) | `stroke{px,color}` 외곽선 · `glow{px(번짐 반지름), color, strength}` 네온 — 자리는 글 잉크 기준 그대로 | `_draw_text`·`_glow` | 손 스크립트 make_썰템홈샷 민트 네온·make_맛템썰템 크림골드 네온(업그레이드 판 재료) |
| `frame.logo.glow` | 로고 번짐 `{px,color,strength}`(외곽선 = 옛 `stroke`·`stroke_rgba`) | `frame_png` 로고 | 같음 |

잇썸홈판·재미썸홈판 → bench 수렴 판단(02 2차, 10-25): **아직 못 옮긴다.** 07 사유 ① A/B 두 틀 = `frame.segments` 로 틀·창 바꾸기는 된다. 남은 것 — ①' 두 구간의 **자막 그리기가 다르다**(A = calcopy_frame 스냅샷 + `narr_video.emph_png` PIL 자막, B = preset_save 프리셋 스냅샷의 가운데 자막) · bench 는 편 하나에 자막팩 스냅샷 하나(`burn_captions` → `scene_style.compose` 한 번) → 구간별 자막팩 칸이 더 필요 ② 대본 꼴(seg·pieces·mute·tts_override·tts_spans·tts_pauses) 변환기(08 flow 와 같이) ③ 소리(원음 조각 pad/gap 묶음·mute 경사·tts_override·줄별 ±10% 당김·−8.6 LUFS 마스터) 가 bench `audio` 에 없음. 셋 다 들어오기 전엔 같은 입력 bench 렌더 대조를 할 수 없다.

2차 시험 판: `_test_hook`(잇템로그판 목소리 + 본문 = 썰템홈샷판 틀 · 0초~첫 줄 끝 = 방구석 훅 카드 · 자막 2줄 쌓기) · `_test_sinbak`(신박판 + 제목 왼쪽 x97·자간 −2.1 · 둥근 창 87) · `_test_neon`(썰템홈샷판 + 손 스크립트 샘플 B 민트 네온 머리띠). 시험 = `shopping_shorts/tests/test_render_bench_devices.py`(2차 11개).

## `packs` 칸 — 프리셋 = 숏템메이커 팩에서 고른 기본 선택(관제 263 지시서 11 — 표준 §10-2·§10-3)

**packs 가 정본, 옛 칸(`caption.pack`·`sfx_files`·`bgm.id`·`bgm.candidates`·`placement.rules.meme.tone/pack`)은 `styles.load` 가 packs 에서 채운다**(주인 `pack_map.apply_to_style`). 판 파일에 옛 칸도 남아 있으면 같아야 한다 — 다르면 load 가 `PackError`(두 벌 불일치). 칸은 사람이 손으로 적지 않고 `py tools/calcopy/hybrid/pack_map.py <판> --write`(벤치 측정 → 팩 항목, 근거 `from`·없는 것 `gap` + `channel/<slug>/_kal/팩요청.md`).

| 요소 | 칸 | 팩(읽기만) | 렌더가 쓰는 곳 |
|---|---|---|---|
| `caption` | `pack`(자막팩 키) · `stand_in`(벤치와 같은 팩이 없어 임시) · `rank`(측정 거리 1~3위, 항목별 1.0 = 같음 문턱: 글꼴 같음·잉크 ±10%·ΔE<5·테 ±3px·자리 ±2.5%) · `enter_cover`(벤치 등장 분포 ↔ 팩 등장 이름표) | `caption-motions.js` /*PACKS*/ | `caption.pack` → `render_bench.snapshot` captionPack |
| `motion` | `pack` = **등장 효과팩 번호** `off`·`1`~`20`(/*MPACKS*/ — `snapshot.motionPack` 이 받는 값) · `graphics` = 모션그래픽팩 `off`·`dynamic_pop`·`minimal_chic`(assets/motion/packs.json) | MPACKS · motion/packs.json | `pack_map.snapshot_fields` → motionPack. ★자막팩에 `motion`(등장)이 있으면 팩이 이긴다(motionPlan) — 칼카피 6팩은 번호가 안 먹는다. ★`graphics` 는 render_bench 가 못 그린다 → off 아니면 거절 |
| `sfx` | `pack`(팩NN) · `map{종류: 한글 slot}`(뽁·띠링·휙·둥·오프너·틱·딸깍2 = 파일 pop·ding·whoosh·dung·opener·tick·click2) · `outside{종류: 팩 밖 파일}`(표시된 임시 + gap) · `gain_db` · `ncc`(벤치↔팩 파일 상관 요약) | `assets/sfx_packs` | → `sfx_files{종류: 팩NN/파일.wav}` |
| `bgm` | `id`(사람이 고른 곡) · `candidates`(bgm_pick 상위 3) | `bgm_lib/catalog.json` | → `bgm.id`·`bgm.candidates` |
| `meme` | `pack` = `local`(칼카피 로컬 짤 팩 — 기본)·`server`(회원 prefs — 칼카피 길 미연결, 짤 규칙 있는 판이면 거절)·`none` · `tone`·`dir`(있으면 `placement.rules.meme.tone/pack` 로) | 로컬 짤 팩 | placement.meme_step. **빈도 `rate` 는 `placement.rules.meme.rate`(뼈대)** — packs 에 안 적는다(두 벌 금지) |

- **자막 크기·줄 간격의 주인 = 자막팩(표준 §11-3 ㉑)** — 판 `caption` 에 크기·간격 칸을 만들지 않는다. 다르게 하려면 `packs.caption.variants{size: …, line_pitch: …}` 로 **팩에 있는 변형**을 고른다(없는 변형 = load 거절). 팩에 없으면 `pack_map` 이 `팩요청.md`(관제 235)+`gap` 을 쓴다: 업그레이드 판 상위 편 p75 잉크가 팩보다 10%↑ → size 변형 요청(잇템로그판_v2 89 vs 74px) · 여러 줄 자막 피치가 팩 기본 줄 높이(글꼴 ascent+descent)와 10%↑ 다름 → line_pitch 변형 요청(썰템쇼·썰템홈샷·트롯파파). 1차 판은 벤치 실측 그대로.
- 합치기 = `pack_map.merge(엔진 기본 ENGINE_DEFAULT, 판 packs, 회원 patch.packs)` 한 곳 — `styles.load(판, patch={"packs": …})`. 회원 patch 는 지금 `packs` 만(다른 칸은 지시서 12 `apply_patch` — 그 전엔 거절). 없는 팩 항목은 거절(`check`).
- 상속 판(`base`): packs 는 바탕 판과 **다른 요소만** 적는다(`연예인레시피판` = caption 만, `잇템로그판_v2` = 없음). 목록 칸 `script.audit`·`brief` 도 통째로 못 적고 `audit_patch`·`brief_patch{add,remove,replace}` 만(⑰ — 통째면 load 거절).
- 카드(01) 레코드 키 제안: `pack_item` = `"caption:<packs.caption.pack>"` · `"motion:<pack>/<graphics>"` · `"sfx:<pack>/<map>"` · `"bgm:<id>"` · `"meme:<pack>"`, 임시면 `stand_in` 표시.

## 판 목록(관제 263 지시서 07 — 표 줄만, 칸 문서는 위 02 표가 주인)
| 판 | 벤치(slug) | 틀 kind | counted 편 | 틀 대조(벤치 프레임 ↔ frame_png) | 손 스크립트 | 큰 _pending |
|---|---|---|---|---|---|---|
| 잇템로그판 | 잇템로그(ititemlog) | window | 6 | ep13 렌더: 줌블러 그림 3.57~3.64초 라플라시안 66→3 · 효과음 pop 1발 | (scratchpad mk_v3·vmake → 08) | targets 는 _v2 · cps_target 근거 칸(뿌리) |
| 썰템홈샷판 | 방구석(banggu) | post | 6 | 제목 y0 0·h −4 · letter_gap ✗ | make_썰템홈샷.py·하이브리드/make.py `_deprecated` | 자막팩 없음·훅 카드 틀 바꾸기·페이지 쌓기 |
| 맛템썰템판 | 맛있는 친구들(yummyknow) | post | 6 | 제목 y0 +2·h −3 · cx +95(왼쪽 정렬) | make_맛템썰템·rerender_* `_deprecated` | 자막팩·제목 왼쪽 정렬·게시자 줄 칸·표지 카드 |
| 썰템쇼판 | 재밌쇼(humorshowshow) | post | 0(옛 꼴) | 제목 y0 −1·h +1 · cx −7 | preset/hs_*.py `_deprecated` | 줄판독 새 꼴(06)·조회수 줄(가짜 지표 → 사장님) |
| 숏템리폿판 | 핫템리포트(hottemreport) | window | 6 | 제목 1줄 y0 −1·h 0·ΔE 0 / 2줄 y −1·h 0 | make_frame/make_render 숏템리폿·현장썰 `_deprecated` | 원음 색 기울임 자막팩·효과음 종류 |
| 신박판 | 신박발견(sinbak) | window | 6 | 제목 y0 +1·h +4 · cx +35(왼쪽 정렬) | sinbak_preset·measure·시험편1 `_deprecated` | 나레 없는 편·둥근 창·창 안 색 글씨 |
| 트롯파파판 | 울지마트로트(uljimatrot) | window | 10 | 줄판독 픽셀: 제목 180~264/322~407 vs 178~265/325~409 | _tools/make_trotpapa.py `_deprecated` | 훅 누끼·CTA·가격 카드(금지선 → 사장님) |
| 만템판 | 만템(mantem) | window | 0 | 제목 1줄 158~259 vs 158~258 | preset/mt_preset.py `_deprecated` | 줄판독 0(06) |
| 아이템홈판 | 아이템홈(itemhome) | window | 0 | framecmp 통과급(y0 +3·h −3) | 1편 make_render·ih_preset `_deprecated` | 줄판독 0(06)·브랜드 미정 |
| 안나픽판 | 안나픽(annapick) | window | 0 | framecmp 통과(y0 −1·h +1) | 1편 make_plan/make_render·ap_preset `_deprecated` | 줄판독 0(06)·브랜드 미정 |
| 도파민썰템A판 | 썰풀다 자막만(sseolpulda) | window | 0(섞인 폴더) | 제목 223~304/318~398 = 벤치 | — | 갈래별 줄판독 폴더(06)·나레 없는 편 |
| 도파민썰템B판 | 썰풀다 나레(sseolpulda) | window | 0(섞인 폴더) | 제목 105~227 vs 102~221 · 폭(자간) ✗ | — | 갈래별 폴더·표본 3편 |
| 뜨거운사람들판 | 뜨거운사람들(hotpeople) | window | 0 | (벤치 영상 로컬 없음) | — | 줄판독 0·목소리·길이 손 상수 |
| 숏비타민c판 | 숏비타민c(shortvitc) | window(틀만) | 0 | (벤치 영상 로컬 없음) | — | 틀만 — 자막·소리 06 |
| 잇썸홈판·재미썸홈판 | 두유노·이븐쇼핑 | itssum·jaemi | — | (bench 전환 불가 판단) | — | _pending.bench_migration(A·B 두 틀·대본 꼴·소리 규칙) |
판 설정 초안 변환기 = `tools/calcopy/hybrid/frame_import.py <frame.json> --kind post|full|window [--frame body|hook]`(한 번 돌리고 끝, 판 파일이 주인).
