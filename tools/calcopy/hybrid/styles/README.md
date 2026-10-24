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
