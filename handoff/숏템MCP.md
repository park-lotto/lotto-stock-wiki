# 숏템MCP — 고객 PC 클로드형 설치팩·프리셋 옵션 페이지

> ⚠️ **2026-10-21 12시 — 집 PC(CH) 칼카피숏템엔진 세션이 이 트랙을 넘겨받았다(사장님 "그 세션을 덮어서 수정을 싹 하라, 왔다갔다하지 말고").**
> 볼케이노형(서버 지시서 do/review/next_payload + 회원 Claude 가 손·눈)으로 재설계·구현 중. **TheRose PC 세션은 이 브랜치에 push 하지 말고 이 파일 최신 절을 먼저 읽을 것.**

관제 카드 234(사장님 승인 2026-10-18 "멈추지말고 마지막까지 끝까지해" — 회원 데이터: 라이선스·기기 잠금·탐지 로그·채널 옵션)

- 설계: `docs/superpowers/specs/2026-10-18-숏템MCP-design.md` (4판, 미결 0)
- API 계약: `docs/superpowers/specs/2026-10-18-숏템MCP-api.md`

## 2026-10-18 (TheRose PC) 구현

### 만든 것
| 갈래 | 위치 | 주인 함수 |
|---|---|---|
| 서버 포털 | `shopping_shorts/claude_portal.py` · `channel_profile.py` · app.py 라우트 `/api/claude/*`·`/api/claude/me/*`·`/claude`·관리자 경보 · `static/claude.html` · `static/admin.html` 경보 칸 | assets_for · preview · lease · anomaly_check · channel_profile.merge |
| 서버 도구 | `tools/claude_portal/` sync_assets(원본 내용주소 등록) · build_previews(견본 굽기) · check_previews(견본 규격 검사) · issue_key · mutation_check | — |
| 고객 PC | `shortem_client/server/` Node stdio MCP, 도구 6개, 상태기계 9단계 | `engine/next_step.js:nextStep` |
| 설치팩 | `installer/` 윈도 NSIS exe(실행도구 6개 동봉) · .mcpb · Claude Code 플러그인 · 시작.md · 설치안내.html(11장) · 맥 build_mac.sh(미실측) | — |

스위치(전부 기본 끔 → 관리자만 쓰려면 "admin"): `claude_portal_enabled` · `claude_assets_enabled` · `license_kv` · `claude_presets_off` · `claude_min_engine` · `claude_min_installer` · `claude_anomaly_thresholds`.

### 실측(이 세션)
- 서버 시험 `py -m pytest shopping_shorts/tests/test_claude_portal.py` 21 통과 · 판단 8곳 망가뜨리기 → 8곳 다 실패 감지(mutation_check)
- PC 시험 `cd shortem_client/server && npm test` 16 통과
- 로컬 서버(127.0.0.1:8849, 시험 DB) ↔ **설치본**(NSIS 203.4MB, PATH 비우고 동봉 도구만) 로 1편 끝까지: 9/9 완료, 12.174초 1080x1920 -14.3 LUFS, 묶음 표식 comment, 자가점검 3종(목소리는 키 없어 건너뜀)
- 견본 223개 규격 검사 기준 밖 0 · 자산 assets 14개 sha 14/14 · 다른 기기 409 · Range 조각 403 · 페이지 응답 금지 키 0
- 설치 → 제거 잔해 0(폴더·제거 키·환경변수)

### 고친 결함(내가 프레임을 보고 잡은 것)
- 채널명을 넣으면 brand 자리 "[광고]" 표시가 지워짐 → `_is_disclosure` 로 보존
- banggu 게시글형 틀에 벤치 영상의 게시글 제목이 고정 글로 박혀 나옴 → 서버가 비우고 `fill: "title"`, PC 가 그 편 제목으로 채움
- rules.formula(공식 문장 원문)가 PC 로 내려감 → 안 보냄
- 라이선스 키를 채팅에 쓰라던 안내 → 설정 칸(.mcpb sensitive / 플러그인 옵션)으로

## 2026-10-19 02:20~03:00 라이브 실측 (TheRose PC)
- 배포: 8b633ed 는 10-18 22:31 재시작으로 반영. 스위치 `claude_portal_enabled=admin` · `claude_assets_enabled=admin`(관리자만, 고객 공개는 사장님 결정)
- 서버 `sync_assets.py --db shopping_shorts/data/reference.db`: font 88 · sfx 147 · bgm 24 · template 12 · **meme 1283** → 저장소 1,438 파일(`shopping_shorts/data/claude_store`, 570MB, 서버 디스크 여유 26GB)
- 견본: font 87 · sfx 21 · bgm 24 · template 12 · voice 79 · **짤 시트 32장(칸 합계 1,283 = 전부)** · `check_previews` 기준 밖 0
- **라이브에서 잡은 결함 2 → 고쳐 병합(dc0e5f770, 관문 통과)**
  1. `/claude` 프리셋 0개 — 틀(`channel/*/preset/**`, 148파일 2.8MB)이 칼카피숏템엔진 트랙에만 있었다(로컬 시험은 CLAUDE_CHANNEL_ROOT 를 엔진 트랙에 붙여 안 보였다). 엔진 같은 내용을 main 으로 + `tools/calcopy/sync_preset_ledgers.py:_preset_frames` 가 앞으로 틀 폴더도 옮긴다(엔진에서 지운 틀은 안 지움)
  2. `build_previews.meme_sprites` — 0.5초보다 짧은 짤은 ffmpeg rc 0 인데 그림이 없어 FileNotFoundError 로 전체 중단 → 0초로 다시 + OSError 건너뜀. 0.3초 시험 클립으로 고치기 전 실패·후 2칸 대조
- 라이선스: `/claude` 의 키 발급 API 를 관리자 세션으로 눌러 발급(58자, 만료 2027-10-18, 원문은 세션 임시 파일에만). 서버 `issue_key.py` 는 서비스 env 읽기가 권한 분류기에 막혀 안 씀
- 프로필: 라이브 `/claude` 에서 프리셋(banggu 게시글형 p_850f616631) 고르고 채널명 '썰풀다실측' 저장 → v1
- **e2e 라이브 1편**(`SHORTEM_E2E_BASE=https://shoppingshorts.duckdns.org`, 개발 도구 모드): 9/9 완료, 12.174초 1080x1920 h264+aac -14.3 LUFS, comment `shortem:e41635236030:j_…`. 프레임 3장 눈으로: 머리띠·작성자 줄에 '썰풀다실측', 게시글 제목 자리 = 이 편 제목, 자막 줄마다 바뀜. 경보 0 · 기기 1/2 · lease 해제됨
- 못 한 것: 통과작 견본 15편 — 원본 mp4 가 이 PC `C:/숏템_칼카피/…` 에 없고 외장 D 미연결(서버에도 없음) → D 연결 뒤 이 PC 에서 `build_previews.py --kinds result --store <임시>` 로 굽고 서버 `claude_store/preview/result/` 로 올림 · 설치팩 파일은 서버에 안 올림(페이지 '준비 중', 미서명 203MB — 배포 여부 사장님 결정)

## 2026-10-19 오후 (TheRose PC) — 5판 설계·엔진 고객 모드
- 사장님 결정: 고객 PC 에서 만든다(웹은 시각적 선택만) · 키는 고객 각자 · 제미나이 일 = 고객 Claude(하이쿠·소넷·오퍼스) · 받아쓰기 위스퍼(+스피치매틱스) · 이미지 생성 = 고객 버텍스 · 소재 = 우리 채널 목록+찾는 법+넓히는 법 · 서버 부담 0 · 처음 설치에 전부
- 설계: `docs/superpowers/specs/2026-10-19-숏템MCP-완본엔진-design.md` (진행 표·결함·한계·다음 포함)
- 엔진 트랙 커밋 4개(50b978f76·c45d3d261·3d62ddc00·38537600b, 원격 push) — 고객 모드 스위치에서만 동작
- 시안(웹 설정 페이지): `out/claude_설정화면_시안.html` · 아티팩트 VfjvoULjt3CJ1sdrzt6FSE — 사장님 지적 "템플릿 누르고 글꼴 바꾸면 안 됨(보여주기식)" → 실제 페이지는 같은 렌더러(showcase iframe + sceneStyle.load)로
- 도구: `tools/claude_portal/engine_trace.py`(엔진이 실제로 쓴 모듈·파일 기록)

## ⏭ 다음
- **타입캐스트 실제 합성 미실측**(이 PC 에 키 없음) — 키 있는 PC 에서 shortem_setup selftest 로 시험 목소리
- 미구현: 고객 채널명 PNG 견본 · 캐시 틀 ±1px 지터 · 자막 효과 2초 견본 · 대본 뒤 extra(짤·효과음) 요청 · 원음 깔기 · 템플릿 자산 사용
- A1 국가 조건은 nginx 에 GeoIP 가 없어 라이브에선 미발동(미등록 기기 조건은 됨)
- 서명: 윈도 코드서명 인증서·Apple Developer(연 99달러) 필요 — 지금 미서명(SmartScreen 경고)
- 맥: `installer/mac/build_mac.sh` 는 `bash -n` 만 통과. 맥 기기 2대에서 libass 정적 ffmpeg 빌드·서명·공증 실측
- Claude Desktop 에서 .mcpb 실제 설치 UI 시험 미실측

## 2026-10-19 (오후) — 1~3번: 엔진 묶음·편마다 프리셋 빌려주기·회원 PC 설정 화면

완료(트랙 커밋, 라이브 미반영):
- 서버 `claude_portal.preset_rent`/`rent` + `POST /api/claude/rent` — 관문 `_job_gate`(작업 권한·등급) 뒤 AES-256-GCM(aad=cid|job) 꾸러미. 프로필 없이 `preset`(고객용 id)로도 빌린다. PC 1대(DEVICES_MAX=1).
- 라이선스 응답 `presets:[{id,name,desc}]` — 이름 주인 = 관리자 설정 `claude_preset_names`(없으면 틀 설명). ★5개 이름(제품비하인드썰형 등)↔프리셋 짝은 아직 안 넣음 — 사장님 확인 필요.
- PC `preset_rent.js` — 메모리 열쇠로 풀어 엔진이 도는 동안만 `engine/channel`(표식 .rented), 끝나면 지우고 권한 반납. 설정 화면 미리보기는 kind=ui(10분 무사용 반납, 제작이 오면 넘김). 시험 rent.test.js 4개 + 실물 썰풀다 꾸러미 19파일 엔진 원본과 sha 일치.
- 엔진 `tools/calcopy/preview_request.py`(엔진 트랙) — preview/catalog/check. merge_preset_pack·title_text·to_snapshot·context_for 를 그대로 부름(새 판단 없음).
- PC `local_settings.js`(~/.shortem/settings.json 한 곳 — 화면·Claude·제작 공용) · `local_ui.js`(127.0.0.1·토큰 쿠키·Host 검사) · `ui/index.html`(프리셋·화면·자막·소리·완성본 탭) · MCP `shortem_settings`(open/get/set/select) · `shortem_make` 가 로컬 설정 프리셋 사용.
- 검사 도구 `shortem_client/test/ui_check.js`(+ui_vs_render.py): 실제 크롬으로 단추 11개 누름 → 저장·그림 바뀜, **화면 미리보기 = 공식 render_layer_one 차이 0.00%(장면 1·2)**, 렌더러 스타일 글 일치.
  ★첫 실행은 '그림 바뀜'이 거짓 통과였다(미리보기가 '불러오는 중' 상태). 눈으로 보고 잡음 — 렌더러 export 스타일·sceneStyleExporting 을 그대로 입혀 고침.

⏭ 다음:
- 완성본 '지금 설정으로 다시 만들기'(엔진 재렌더 명령) — 화면은 미리보기까지만.
- 숏템메이커 템플릿(썰20·고정20) 선택 — merge_preset_pack 이 아직 템플릿 칸을 모른다.
- 외곽선 슬라이더 0~20: 검정 글자+검정 외곽선 10px 이면 글자가 뭉개진다(실측 그림) — 색 칸 또는 상한 조정 검토.
- 4번(클로드형 서버 부담 0) — 조사 결과 아래.
- MCP 응답 최소화·설치팩(의존성·Nuitka·자동 업데이트)·깨끗한 PC 시험.

### 서버 부담 조사(읽기만, 2026-10-19)
- 렌더 계열(`video_assemble.assemble`·`scene_style`·캡컷)은 Store 참조 0~1건 → PC 이전 쉬움.
- `mix_pipeline.py` Store 참조 113건(진행·과금·공용 추출 캐시) → 가장 어려움.
- 막는 것 3: ①인스타 다운로드가 서버 로그인 세션·유튜브 서버 프록시에 묶임(media_download.py:439·:258) ②Gemini 가 회원 키도 공용 풀로 서버에서 돎(config.refresh_member_gemini_keys :218, keyroute :511) ③진행·과금이 서버 DB·공용 캐시에 붙음.
- 서버에 남아야 하는 것: 화면·로그인/등급·프리셋 임대·상태 기록·랭킹 DB와 수집기(공용).

## 2026-10-19 (저녁) — 남은 4건 처리
- 프리셋 이름 5개: `shopping_shorts/claude_preset_names.json`(짝 근거 브랜드.json·결과물.json) — 제품비하인드썰형=banggu/게시글형 · 샤크탱크+리뷰형=foreignshowshow/샤크탱크_검정띠2줄 · 해외핫영상+리뷰형=hottemreport/검정띠 · 연예인상품+후기형=mantem/얜샷템 · 연예인레시피+후기형=yummyknow/게시글형(★짝 확인 필요). 관리자 설정 claude_preset_names 가 칸 단위로 덮는다.
- 숏템메이커 템플릿(썰20·고정20): 엔진 `to_snapshot.template_snapshot` 한 곳(merge_preset_pack 이 frame.shortem_template 표식). 채널명·[광고] 표시 유지(첫 렌더에서 '숏템메이커'·광고 사라짐 실측 → 고침). 견본 그림은 벤치 화면이라 고객에게 안 보냄.
- 외곽선: 색 칸(outline_rgb) 추가, 화면 막대 0~12.
- 완성본 다시 만들기: 엔진 `calcopy_make.restyle` + make.py restyle + MCP step=restyle + 화면 버튼. 실측: 원음형 1편 209초, AI 요청 0, 템플릿·채널명·[광고]·글꼴 반영 확인(프레임 대조).
- 점검 도구: ui_check.js 18칸 전부 통과(템플릿 화면=렌더 0.03%). ★거짓 통과 2번째를 잡음 — '그리는 중' 표시만 기다려 저장 전 그림을 찍었다 → 다 그린 횟수(__drawn)로 기다리게. template_render_check.py(compose 경로).

## 2026-10-19 (밤) — 인스타·틱톡·유튜브 회원 PC 받기(사장님 "본인 PC 에서 되게 설정도 팩에 / 우리도 처음에 내 PC 안에서")
- 우리 PC 방식 그대로: 로그인 브라우저 쿠키 → yt-dlp + 인스타 세션 파일. 받는 판단 주인 = media_download.download_any(숏템메이커와 같은 것).
- PC `logins.js` + MCP `shortem_login`(open/status) + 설정 화면 '영상 받기 계정' — 숏템 전용 크롬 프로필(~/.shortem/browser), 회원이 직접 로그인 후 창 닫기(구글이 원격 제어 창 로그인을 막아서 보통 창). 만들기 전마다 같은 프로필에서 쿠키 다시 뽑기(0.6초 실측).
- 엔진 yt-dlp 호출 전부에 쿠키: XDG_CONFIG_HOME/yt-dlp/config(--cookies) — exe·파이썬 모듈 둘 다 읽음 실측.
- 엔진: 유튜브 밖 참고 영상 → ref_facts 가 media_download.probe_grab_meta, 재료 = 그 영상(url: 질의 → remake.download_url).
- ★결함 잡음: media_download 가 핀터레스트 판별에 app.py 를 불러 회원 PC(app 없음)에서 틱톡·유튜브 받기가 통째로 막힘 → 주소 목록을 shopping_shorts/grab_domains.py 한 곳으로(app 도 거기서 import).
- 묶음: media_download·grab_domains·frame_extract·instagram_parse·douyin_fetch·threads_parse 추가, 서버 수집기(channel_archive·instagram_playwright·apify_client·store) 금지.
- 실측(서버 모듈 막은 회원 PC 조건, 로그인 없음): 인스타 4.4MB·틱톡 17MB·유튜브 OK, 엔진 재료 단계 틱톡 후보 시트까지 rc=2.
- ⏭ 실제 로그인 창 시험(사장님 계정으로 '로그인만') — 인스타 1080p·비공개 막힘 상황에서 쿠키 효과 확인. 핀터레스트는 pinterest_crawl 미포함(필요하면 추가).

## 2026-10-19 (밤 2) — 남은 것 끝까지(설치팩·숨김·자동 업데이트)
- 설치팩: 엔진 묶음(173+데이터) · 엔진 패키지 49개 해시 고정(requirements-engine-py312-win.txt) · 받아쓰기 모델 whisper small 486MB · 렌더러 puppeteer 연결(engine/node_modules/puppeteer → 설치 크롬) · 효과음 팩 147개+장부(build_packs) · app_version.json. 설치 폴더 약 1.8GB.
- ★결함 2: (1) 묶음에 목소리 목록·배경음악·효과음 팩이 빠짐(파이썬 추적에 안 잡히는 파일) → DATA_EXTRA. (2) 오늘 이 PC 완성본 효과음 file=None — 우리 팩 장부(C:/숏템_칼카피/packs)가 이 PC 에 없고 서버 scene_assets 에도 그 번호 없음 → 설치본은 동봉 팩 장부, 고객 기본 팩은 팩01 오프너·뽁·띵. 짤 팩은 아직(번호가 우리 서버 것).
- 설치본 점검 test_engine_installed.py(설치 폴더 도구만): 렌더 잉크 0.476 · 틱톡 받기 3.8MB · 위스퍼 구절 5 OK, 목록(catalog)만 빨강 → 데이터 넣고 재빌드 중.
- 숨김: MCP 서버 instructions · 실패 글 경로 지우기(cleanWhy) · 응답에서 내부 프리셋 경로 제거 · AI 요청에 '내부 지시' 표시 · 플러그인 안내서 make/script/setup 새 흐름(Read/Glob/Grep 막음).
- 자동 업데이트: 서버 update_info(+오래된 엔진 허용) · publish_update.py · PC updater.js(받아 _update/<판>) · launcher applyPending(다음 켤 때 바꾸기·되돌리기).
- 프리셋 꾸러미 16개 빌드(스크래치 preset_packs_all) — 서버 claude_store/preset_packs/ 업로드는 승인 뒤.
- 숏템메이커 서버 부담 0: 설계·결정 3(설계 문서 끝). 렌더 run_render 는 DB 12곳·키 0 실측.
⏭ 최종 빌드 → 설치 시험(test_install + test_engine_installed) · 로그인 실측(사장님) · 하이쿠 1편 · 짤 팩 · 병합 전 승인.

## 2026-10-19 (밤 3) — 멈춘 자리(사장님 "지금 하는 거까지 하고 커밋·푸시, 이어서 할 거야")
- 모델 배분: 엔진 client_llm.tier_of 기본 = opus(사장님 "하이쿠·소넷은 완전 단순·품질 무관만, 품질은 오푸스"). 실측 요청 꼬리표(score·ocr0·support·draft·rewrite·bench) 전부 opus. 플러그인 make/script 안내서: opus 요청은 오푸스가 — 지금 모델이 아니면 Agent(model=opus)에게.
- 인스타 로그인 실측(사장님 계정, 숏템 전용 프로필 scratchpad/login_home): 연결됨 true. yt-dlp -F 에 쿠키 넣으면 1080x1920 형식이 보인다(없으면 최대 720). ★그런데 media_download 경로는 쿠키를 넘기는데도(564B) 720p 를 받는다 → 원인 후보: _download_ytdlp 형식 고르기(1080 이 vp9 이라 h264 선호에서 밀리나?) — 다음에 형식 문자열·고른 format_id 를 찍어 확인.
- 최종 설치 exe 빌드 = 이번에 압축까지 끝났는지 확인 필요(scratchpad/installer_build/build_final.log). 끝났으면: test_install.py(/SANDBOX) → 설치 폴더에 _engine_test 섞였는지 확인(섞였으면 재빌드 — 점검 도구는 이미 밖으로 옮김) → test_engine_installed.py → 하이쿠 1편(scratchpad/haiku/prompt.txt, 시험 서버 FAKE_RENT_*).
- 그 뒤: 짤 팩 동봉, 숏템메이커 서버 부담 0(결정 3 사장님), 프리셋 꾸러미 16개 서버 업로드(승인), 병합(승인).
- 최종 빌드 끝(10-19 21:5x, 1271초): 설치 exe 805.9MB 미서명 · 설치 폴더 1809MB · 바이너리 237개 sha. ★빌드 폴더에 _engine_test(점검 도구가 만든 시험 파일)가 남아 있어 exe 에 섞였을 수 있다 → 설치 시험 때 설치 폴더에 _engine_test 있으면 지우고 재빌드.

## 2026-10-20 (오전) — exe 없이 깔기 · 인스타 1080 · 이름 연예인꿀맛
- 사장님 결정: ①이름 연예인레시피+후기형 → **연예인꿀맛**(claude_preset_names.json) ②인증서 없이 스타터킷처럼 → exe 내리고 연결 파일+자동 받기 ③1차로 내고 2차 병합에 짤·핀터레스트/샤오홍슈/도우인 검색 ④숏템회원 PC 이전 결정 3개(설계 문서 '사장님 결정 2026-10-20').
- 됨(실측): 빈 PC 폴더에 연결 파일만으로 설치 30초(로컬 시험 서버) → 다시 켜면 숏템 도구 9개 · 키 저장 · 시작.md · 찌꺼기 0 (`node shortem_client/test/noexe_install_check.js --zip …`). 깔린 폴더로 test_engine_installed 통과(글꼴 86·템플릿 40·목소리 8·렌더 잉크 0.476·틱톡 3.8MB·받아쓰기 5구절). _engine_test 없음.
- 됨: 빌드가 설치 폴더 맨 위 정한 이름 밖은 걷어냄(STAGE_TOP) · 설치 묶음 zip(987MB, 45초)·Claude Code 꾸러미(35MB, 플러그인 검사 2개 통과) 만드는 단계 · 서버 /api/claude/install(시험 26 통과) · 페이지 ④를 연결 파일 두 칸으로(브라우저로 그려 확인) · 시험 31 통과.
- 엔진 트랙: 인스타 받기 형식 bestvideo → bv*(1080x1920 소리 섞인 원본) `5253f8e6b`. 다른 PC 가 같은 트랙에 10커밋 올려 그 위에 얹었다.
- ⏭ 다음: ①최종 빌드(최신 엔진 = 인스타 수정 포함, 새 연결 파일) → noexe_install_check + test_engine_installed 다시 ②하이쿠/실제 1편(fake_server FAKE_RENT_* + FAKE_INSTALL_ZIP) ③승인 받을 것: 서버에 설치 묶음·연결 파일·프리셋 꾸러미 16개 올리기(publish_update.py --install, installers/manifest.json 에 desktop·code-win-x64) + finish(병합·라이브).
- 알아 둘 것: 서버가 1GB 묶음을 회원마다 내준다(설치 1회). 부담이 크면 asset_url 한 곳만 R2/S3 서명 주소로 바꾸면 된다.

## 2026-10-20 (오전 2) — 완성본 텔레그램 + 구글 드라이브 자동 저장
- 사장님: "완성본은 텔레그램으로 받고 구글드라이브에 자동으로 저장" / "카톡으로는 못받겠지"
- 판단 주인 = `shortem_client/server/deliver.js` 한 곳. make_flow 가 완성본을 작업 폴더에 복사한 직후 `deliverInBackground`(완성 응답을 안 늦춤). 같은 파일은 두 번 안 보내고(<영상>.sent.json), 다시 만들면 다시 보낸다.
- 텔레그램 = **고객 본인 봇**(@BotFather 토큰을 회원 PC 설정 화면 '완성본' 칸에만 넣음 → 봇에게 말 걸기 → 확인). 50MB 넘으면 영상 대신 알림 글(봇 올리기 한도).
- 구글 드라이브 = 'Google Drive 데스크톱'의 내 드라이브/숏템완성본 에 복사(그 앱이 올림 — 구글 로그인 창·앱 검수 없음). 이 PC 찾기 실측 `G:\내 드라이브`. 없으면 설치 링크.
- 시험: deliver.test.js 4 · deliver_ui_check.js(실제 크롬으로 토큰→연결→확인→드라이브→시험 보내기, 받은 영상 1·복사 크기 같음·화면에 토큰 없음) · 전체 35 통과(첫 회 rent.test 파일 하나가 내용 없이 실패, 단독·재실행 2회 통과 — 빌드가 같이 돌던 때. 재현 안 됨)
- ⏭ 실물 텔레그램은 사장님 봇 토큰으로 한 번 보내 봐야 끝(가짜 봇 API 로만 확인함). 실물 드라이브 복사는 아직 안 함(폴더 찾기만).
- 카톡: 카카오 '나에게 보내기'는 글·링크 틀만이고 영상 파일을 붙이는 틀이 문서에서 확인되지 않음 → 영상은 못 보내고 링크만 가능(+카카오 앱 등록·고객 카카오 로그인 필요). 안 만듦.
- 폰: Claude 앱의 Code 탭 = ①클라우드(우리 PC 도구 못 씀) ②Remote Control(PC 에서 `claude --rc` 또는 /rc → 폰 Code 탭에서 그 세션 이어 쓰기, PC 켜져 있어야, Pro/Max 이상·API 키 안 됨). /plugin 은 폰에서 안 됨. Desktop 의 Dispatch 는 .mcpb 확장이 붙는지 문서 미확인.
- 10-20 최신 빌드(보내기·인스타 수정 포함, exe 생략): 설치 묶음 987.2MB sha 42e1efca… · 빈 PC 설치 30초·도구 9개·deliver.js 들어감 · 엔진 시험 통과(글꼴 87·렌더 잉크 0.476·틱톡 3.8MB·받아쓰기 5구절).
  인스타 DGzf060SVR_ 로 받기 시험 = 11.6MB 받음(시험 환경엔 로그인 쿠키가 없어 720x1280 — 1080 은 고객 로그인 쿠키가 있을 때, 10-20 쿠키로 실측 1080). 그 릴은 노래(영어 가사)라 받아쓰기 0구절이 정상(음성 거르기 끄면 가사 4줄) — 시험 영상은 말소리 있는 것으로.

## 2026-10-20 (낮) — 서버 디스크 정리(관제 243, 이 트랙에 같이 실음)
- 실측: 새벽 04:00 여유 0.0GB(꽉 참) → janitor 16.3GB → 낮 12~13GB(99%). mix_jobs 377GB 중 7일 넘은 작업 263GB(완료 2,365건 147.8GB · 검토대기 1,355건 115GB).
  원인 = 청소 이름 목록에 새 파일(final_clean_*·beatframes·capcut_*…)이 빠짐 + 검토대기 작업은 두 청소기 모두 안 건드림.
- 사장님 10-20 선택: 완료 7일+ 영상·조각·원본(s0~)·VMake 합본(join) 다 / 검토대기 30일+ / 매일 적용.
- 고침: `tools/disk_janitor.py plan()`(판단 주인) 규칙 E(완료 7일+ BIG_RE)·F(검토대기 30일+ 같은 큰 파일, 폴더·json·썸네일 남김). 시험 test_disk_janitor 4 통과 · 고치기 전 코드로는 3 실패(시험이 잡는다).
- 한 번 실행(사장님 승인): 새 janitor 를 서버 /tmp 에 올려 계획(158.6GB) → --apply: **지움 158.6GB · 실패 0 · 여유 12.1→170.8GB(73%)** · 보고서 서버 ~/disk_janitor/2026-10-20_1142.txt. 사이트 200·서비스 active·5분 오류 0 · 지운 작업 영상 = "7일만 보관해서 정리됐어요" 안내 정상(관리자로 확인).
- ⏭ 병합(finish) 전까지 매일 04:00 은 옛 규칙. 병합되면 E·F 가 매일 돈다(관제 243 '됐다' = 다음 날 보고서에 E·F).
- 알아 둘 것: shopping_shorts/disk_cleanup.py(daily_batch)도 따로 이름 목록을 갖고 있다 = 청소 판단 두 벌. 다음에 janitor 한 곳으로 합칠 것.

## 2026-10-20 (오후) — 라이브 설치형 끝까지 성공(1.0.3)
- 병합(사장님 finish 12:16)·DEPLOY_NOW → 13:03 라이브 /api/claude/install 열림. 서버 디스크 정리(관제 243) 158.6GB → 여유 171GB.
- 라이브 올리기 도구 upload_release.py(설치 묶음·연결 파일·프리셋 16·자동 업데이트). 1.0.0→1.0.1→1.0.2→1.0.3 올림, 자동 업데이트 실측(1.0.0→1.0.1, 1.0.1→1.0.2).
- 고객처럼 한 편(live_episode.js, claude -p opus)으로 찾아 고친 결함 7: 틱톡 소재 벤치 0편(참고영상=첫 벤치·검색 넉넉히) · 프리셋 편마다 숫자값(calcopy_frame/per_video.fill_defaults, preset_save 는 고객 묶음 금지라 옮김) · 출처 칸 '$per_video' 글자(칸 뺌) · 원본 영상 없음(원본컷 시트·대조 생략·검사 단계) · ★응답 가르기가 sid·need·next 를 버려 사인 불가(firewall.shape) + 사인 때 대본 보이기 · 목소리 모듈 빠짐(실행 추적 customer_narr) · 나레 받아쓰기가 서버 제미나이 키(고객=위스퍼).
- 최종: **손대지 않은 새 가짜 고객 PC에 라이브에서 1.0.3 설치(132초) → 한 편 완성 1080x1920 17.1초 소리 있음 → 구글 드라이브 숏템완성본 저장 확인.** 영상 사장님께 틀어 드림.
- ⏭ ①영상 품질: annapick 자막 흰 글자가 흰 바탕 위(외곽선이 고객 기본 팩 outline_px 로 지워진 것으로 보임 — 미확인) ②텔레그램은 사장님이 마지막에 연결 ③회원 PC 프로그램 수정은 설치 묶음으로 이미 나감 — 이 트랙 남은 커밋(firewall·make_flow·도구) 병합은 다음 finish 때 ④시험 파일이 가끔 통째 실패(rent·assets_lease, 재실행 통과) 원인 조사 ⑤맥 묶음 ⑥다른 PC 설치(사장님).

## 2026-10-20 (저녁) ~ 10-21 (TheRose PC) — 회원 PC 재정비: 집 PC 제작순서 그대로 + 한 줄 요청 + 진행 한 줄

### 사장님 결정(이 구간)
- "집에서는 한마디면 영상이 만들어지는데 여기서도 똑같애야 된다" / "모든 걸 재정비해" → 회원 PC 도 집 PC 제작순서(`channel/칼카피_제작순서/00~13`) 그대로.
- 진행 안내 = 볼케이노 MCP 처럼 **지금 단계 한 줄만**(세부 금지).
- 미나 = 회원 본인 일레븐랩스 키 · 받아쓰기 = 위스퍼만 · 쿠팡 = 회원 파트너스 키, **키 없는 사람만 본인 PC 크롬** · 제작 라인(hybrid 코드) = 프리셋처럼 **편마다 빌려주기**.
- 프리셋 기본값 = **그 프리셋 원본 영상**(모든 프리셋), 회원이 바꾼 칸만 회원 값. 남 목소리 = 박창수, 얜샷템 = 문정(타입캐스트). 필재 금지.
- 연예인 장면은 **반드시 찾은 원본에서만** — 다른 채널 연예인 영상 그대로 쓰기 절대 금지. 원본 찾기 = **연예인 본인 채널 1순위**, 남의 쇼츠 '출처:' 글자 활용.
- 원본에 상표가 안 보이면 포털·유튜브로 이름 찾기 → 그래도 없으면 쿠팡 같은 종류 중 후기 많은 것 + 대본에 "똑같은 건 없어서 후기 많은 걸로 써 봤다".
- 등장인물 주인공은 화면 가운데.
- 오류는 그날 바로 `channel/칼카피_제작순서/98_오류기록.md` 에 적는다.

### 이 트랙(숏템MCP)에서 한 것 — 커밋 ca89684f7 ~ 10597b31b
- 한 줄 요청: `shortem_make(preset_name=…)` — 고객이 말한 프리셋 이름으로 골라 저장 후 시작, 목록이 없으면 서버에서 다시 받기(1.0.5·1.0.6).
- 프리셋 기본값: 빌드 때 `tools/calcopy/preset_defaults.json`(엔진 `preview_request.preset_defaults` — 글꼴·외곽선 = frame.json, 목소리·빠르기·음악·자막 쌓기 = defaults.json) · `local_settings.packFor` = 엔진 기본 ← 프리셋 ← 회원 칸.
- 회원 키 칸 4개: `voice.js KEY_SERVICES`(typecast·elevenlabs·coupang_access·coupang_secret) — 화면(`/api/key/<서비스>`)·저장(0600)·엔진 환경변수(`engine_bridge keyEnv`). 실제 크롬으로 4칸 확인(key_ui_check.js).
- 하이브리드 연결: `make_flow` 가 빌린 프리셋 line.json 이 hybrid 면 엔진 `make.py hybrid start --ref … --version <판>` · 사인(approve)·retry(resume)·status · 진행 `stage/step/step_total` 한 줄(firewall 통과, 세부 없음) · wait 는 셸 sleep 금지.
- 기술 꾸러미: `preset_pack.tech_files`(hybrid 프리셋이면 엔진 hybrid·yanshot 코드 46파일) · `preset_rent.js` 가 `.rented` 표식으로 풀고 끝나면 지움(진짜 코드는 안 덮음) · `engine_bundle` 목록 추가 · 설치본 파이썬 playwright(해시 고정).
- 시험 도구: `test/hybrid_dev_run.py`(엔진 회원 모드 + Claude CLI opus 가 AI 요청에 답함). ★10-21 질문을 명령줄로 넘겨 4.2만 자에서 답하는 쪽이 조용히 죽음 → 표준입력으로(10597b31b).
- 올린 설치본: 1.0.4 ~ 1.0.10(1.0.10 = 그림 칸 box_top). **하이브리드 라인이 든 판은 아직 안 올림.**

### 엔진 트랙(칼카피숏템엔진)에서 한 것 — 회원 라인 `tools/calcopy/hybrid/customer.py` (커밋 5ccac145c ~ f5fbecaa6, 전부 push)
- 12단계: bench → origin → product → research → material → asr → script → sign(사인) → plan → render → check → done. 입구 `make.py --json hybrid start|approve|resume|status`.
- 판단 주인 함수: `source_rule_bad`(출처 규칙·남의 영상 장면 전환·다른 출연자 샷) · `origin_offset`(받은 원본 파일 0초 = 원본 몇 초, 잰다) · `shot_table`/`fill_shot_max`(원본 샷 표·샷 끝 max·주인공 가운데 크롭) · `_name_hints`/`PRODUCT_TALK`(상표 없을 때) · `_caps_vs_tts` · `client_llm.PROMPT_MAX`(4만 자).
- 문서: 제작순서 00·02·03·05 갱신, **98_오류기록.md 신설(18건)**, 트랙 CLAUDE.md 회원 PC 절.
- 시험: test_source_rule.py · test_client_llm_size.py · test_eleven_direct · test_box_top · test_preset_defaults 등.

### 실물로 만든 것(이 PC, 회원 모드 + 개발용 쿠팡·미나 서버 길)
1. **이미도 르주르 리무버**(연예인상품+후기형/키치잇판): 29.2초 −14.0 LUFS 자동 6/6 · 드라이브 `칼카피영상/2026-10-21_회원PC_재정비샘플/` 업로드(20,682,904B). 눈 검수 미통과 — 17초 별 전환·장갑 손(둘 다 남의 리뷰 영상 '리뷰여왕'에서) → 출처 규칙이 생긴 계기. 다시 만들지 않았다.
2. **선우용여 눈청결티슈**(키치잇 7위 cNo91ddBwB8, 원본 KBS Entertain qjqSW39Idsw 옥탑방의 문제아들 2025-06-26): 원본 찾기 4번째에 확정(영어 제목·검색어 흔들림·대조 자리 밀림 수리) · 제품 = 대체(alt) 코튼데이 아이원 눈청결티슈 7510883640 · 사인 → 계획 검수 5번째 ok → 렌더 완성, **눈 검수 미통과**(원음 줄 소리≠자막 = 원본 시작 시각 20초 어긋남 · N3 자막≠목소리 · N4 남의 편집 자막 · N7 화면). 원본 시작 339.82초로 재고 **조사 단계부터 다시 돌릴 준비까지**(done 에서 research 이후 지움, approved 지움) — 아직 다시 안 돌림.

### 왜 집 PC 는 되는데 회원 PC 는 처음처럼 틀리나(사장님 10-21 질문)
- 집 PC 는 Claude 워커가 문서를 보며 **손·눈으로 판단**(원음 자리·컷·크롭). `run.py` 엔 그 판단이 코드로 없다(원본 시작 시각 재기도 없음 — 확인).
- 회원 PC 는 그 손 판단을 `customer.py` 가 새로 자동화 → 손 단계를 처음 자동으로 만들 때마다 처음 나는 오류. 문서엔 겪은 함정만 있고 손 판단은 없다.
- 제안(사장님께 드림): 집 PC 세션이 `customer.py` 를 자기 손 순서와 한 단계씩 대조·소유하고 98_오류기록에 적어 커밋·푸시. 이 트랙은 MCP·설치본·회원 키를 맡는다.

### ⏭ 다음
1. 선우용여 편 `resume` → 조사부터(잰 원본 시작 사용) → 대본 사인 전 원음 줄 소리·자막 대조 → 렌더 → 눈 검수 ok 확인 → 드라이브 같은 폴더 업로드·틀기.
2. 이미도 편 새 규칙(원본 제품 장면 먼저·출처 규칙)으로 다시.
3. 대체 제품 '후기 많은 것': 쿠팡 상품 페이지에서 후기 수 읽기(지금 서버·파트너스 길엔 칸 없음).
4. 소재 고르기(제작순서 01, 키치잇 인기순·이미 만든 것 빼기)를 회원 엔진에 — 손님이 "다음꺼 만들어줘"가 되게.
5. 설치본 1.0.11(하이브리드 라인·기술 꾸러미·playwright·얼굴 모델 onnx + CALCOPY_FACE_MODEL) 빌드 → 프리셋 꾸러미 다시(얜샷템+tech) → live_episode 로 진짜 설치본 MCP 경유 완주.
6. 나머지 프리셋(제품비하인드썰형·샤크탱크·해외핫영상·연예인꿀맛)은 집 PC 제작 문서가 없다 — 집 PC 세션이 프리셋별 제작순서를 적어 올리면 옮긴다.
7. 회원 키 실제 호출 미실측(일레븐랩스·쿠팡 파트너스) · 크롬 쿠팡 길은 이 PC 가 쿠팡에 막혀 미검증.
8. 병합: 두 트랙 모아서 한 번(finish 는 사장님). 텔레그램 연결은 사장님이 마지막에.
