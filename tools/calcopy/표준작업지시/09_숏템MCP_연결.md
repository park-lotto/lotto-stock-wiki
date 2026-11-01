# 09 숏템MCP 꾸러미·이름·설치본·실전 — "잇템로그 스타일로 만들어줘" 한 줄 (표준 §7·§3-3 C3 · 08 뒤 · **다른 워크트리**)

## 목표
회원이 `shortem_make(preset_name="잇템로그 스타일로…")` 한 줄로 시작해 완성본까지. 프리셋 이름·line.json·꾸러미(판 설정+벤치 자료)·형식(fmt)·설치본을 잇고 `live_episode.js` 로 **라이브 서버·설치본·진짜 키** 경로 1편 완주 → 페이블 눈 검수. 라이브 배포(finish·설치본 업로드)는 사장님 승인 뒤(관제 263 승인 사유: 회원 데이터·꾸러미 재배포).

## 실측 배경(10-24)
- 숏템MCP 트랙 `.tracks/숏템MCP`(최근 32f9b12a7, 33커밋 미병합·설치본 1.0.10·라이브 서버 꾸러미는 10-20 상태). `shopping_shorts/claude_preset_names.json` 5개(제품비하인드썰형=banggu/게시글형 · 샤크탱크+리뷰형 · 해외핫영상+리뷰형=hottemreport/검정띠 · 연예인상품+후기형=mantem/얜샷템 · 연예인꿀맛=yummyknow/게시글형) — **잇템로그 없음**. 4개는 옛 preset_make 길(line.json 없음), 1개(mantem/얜샷템)만 `line.json {line:hybrid, version:키치잇판}`.
- 서버 `claude_flow.step`: `_line(preset_dir)` 가 line.json 을 읽어 `flow.start(url, version, sid, product)` — 08 이 `fmt` 인자를 더한다. `claude_portal.preset_rent` 꾸러미 = `preset_pack.tech_files`(판 설정·벤치 자료만, 코드 금지). `engine_bundle.HAND`(실행기·렌더·검사만 설치본에).
- 입구 `shortem_client/server/make_flow.js`(rentPreset → startFlow) · `flow_driver.js startFlow({preset, video, product})` · 시험 `shortem_client/test/live_episode.js --say "…"` · 로컬 시험 서버 `tools/claude_portal/local_server.py --engine <엔진 트랙>`.
- 회원 키: 유라(타입캐스트) = 회원 본인 키 · 스피치매틱스 선택 · 쿠팡 파트너스 · VMake 는 회원 칸 없음(08 이 blur 대체).

## 만질 파일(독점 — 숏템MCP 워크트리 `.tracks/숏템MCP`, 브랜치 track/숏템MCP)
`shopping_shorts/claude_preset_names.json`(→ **프리셋.json `member.preset_name` 에서 생성하는 도구** `tools/claude_portal/preset_names_sync.py` 신설 — 손으로 두 벌 적지 않는다) · `shopping_shorts/claude_flow.py`(`fmt` 전달·`claude_flow_runs.fmt`) · `tools/claude_portal/preset_pack.py`(tech_files 에 `styles/<판>.json`+`base` 판+`bench.line_reads`·`_kal/규칙빈도.json`·썸네일 규칙 — 코드 0) · `shortem_client/server/make_flow.js`·`flow_driver.js`(preset_name → id, fmt 표시 한 줄) · `shortem_client/test/live_episode.js`·`answer_key` 잇템로그 · 설치본 빌드(`engine_bundle.HAND` 에 08 의 `vmake_clean`·`ititemlog_make`·`quality_gate` 추가)
엔진 트랙(경로 지정 커밋): `channel/ititemlog/preset/잇템로그/line.json`(새 `{line:"hybrid", version:"잇템로그판_v2", fmt:"해외원본형", _from:"channel/프리셋.json"}`) · `channel/프리셋.json` ititemlog `member` 3칸 값 · `channel/ititemlog/_kal/회원실측.json`(live_episode 결과 — 01 카드 L4 가 읽는다)
## 안 만질 파일
엔진 `flow.py`·`runner_ops.py`(08) · `render_bench`·`quality_gate` · 라이브 서버(승인 전) · 다른 프리셋 line.json(만템 것 그대로).

## 순서
1. `preset_names_sync.py` : 프리셋.json `presets[*].member.preset_name` 이 있는 slug → `claude_preset_names.json`(키 `<slug>/<틀>`) 생성 · 기존 5개와 diff 0 인지 먼저 확인(사보타주: 프리셋.json 이름 하나 바꾸면 diff 1).
2. 잇템로그 이름(사장님 결정 전 가칭 **"해외반응+리뷰형"** — 회원 화면에 '현장썰' 금지) · line.json · 꾸러미 빌드(`preset_pack` 로 `잇템로그판_v2`+base `잇템로그판`+줄판독 6편+규칙빈도) · sha 대조.
3. 로컬 시험 서버(진짜 app·시험 DB) + 개발 MCP + `claude -p opus` 로 `flow_episode.js --say "잇템로그 스타일로 만들어줘 <한국 재편집 쇼츠 주소>"` 완주(유튜브 캐시 모드).
4. 설치본 1.0.11 빌드(HAND 추가분) → `noexe_install_check` → `test_engine_installed` → **깨끗한 가짜 PC** 에서 `live_episode.js`(라이브 서버는 승인 뒤 — 그 전엔 로컬 시험 서버 주소로) 1편.
5. 완성본 + `품질관문.json` + `eye/` 묶음 → 페이블 눈 검수(E1~E8) → 통과면 사장님께 영상·표 → 승인 뒤 두 트랙 finish·`upload_release.py`(꾸러미·설치본).

## 합격 검사
1. 이름 생성기 diff 0(기존 5개 보존) + 잇템로그 1개 추가 · 서버 라이선스 응답 `presets[]` 에 뜬다(로컬 시험 서버).
2. 회원 경로 1편: 1080×1920 · `quality_gate` 1단 ○ 전부 · 정답지(원본 id·제품) 일치 · 진행 안내는 서버 message 한 줄만(세부 0) · 서버 DB 에 요약만(영상·대본 본문 0).
3. 꾸러미 안에 코드 파일 0(`.py`·`.js` 0) · 판 설정 sha = 엔진 트랙 파일 sha.
4. 페이블 눈 검수 E1~E8 ○(`channel/ititemlog/_kal/회원실측.json` 에 결과·영상 경로·sha).
5. 사보타주: line.json 의 `fmt` 를 지우면 서버가 400(조용한 기본값 금지).

## 보고 형식
`커밋 해시(두 트랙) / 이름 diff / 꾸러미 파일 목록·sha / 회원 경로 완주 로그(단계·시간·AI 요청·키 호출 수) / gate 표 / 페이블 눈 검수 결과 / 승인 대기 항목(finish·업로드) / 못 한 것`
