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
| ★`bgm` | `id`(bgm_lib 파일) · `db_below_voice` · `duck_orig_db`(원음 줄에서) · `fade_out` | |
| ★`loudness` | `lufs`(−14 통일) · `tp` | `{"lufs":-14,"tp":-1.5}` |
| ★`length` | `min`·`max` 초 | `{"min":25,"max":30}` |
| `timing` | 줄 사이: `gap` 또는 `gap_after_tts`·`gap_after_orig`·`gap_oo` · 끝 여운 `tail` | |
| `frame` | `bg` · `window[x,y,w,h]` · `title[]`(줄마다 font·px·`ink_top`|`center`|`box`+`box_color`·`shear`·`color`·`hi`(대본 'hi' 낱말 색)·`max_w`) · `logo`({text,font,px,x,y,rgba,stroke} 또는 {"kind":"spr_gold"} 또는 null) · `credit` · `watermark` · `comment`(댓글 카드 자리) · `flash_sec` | |
| `caption` | `pack`(자막팩 키, caption-motions.js PACKS) · `pack_default`(칸별 팩 기본 등장: narr/orig × first/rest) · `variant_for`(등장 → 팩 줄 변형) · `typing_variant` · `typing_cps` · `chunk_max_chars` | |
| `cuts` | `push_tts`·`push_orig`(컷 천천히 밀기 비율) | |
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
