# 관제 보드 (자동 생성 — 손으로 고치지 마라. `py tools/control.py board`)

갱신: 2026-09-29 22:57 · 카드 36장

상태 흐름: 등록 → 분배 → 수리 → 로컬검증 → 병합 → 서버반영 → 라이브실측 → 완료  (예외: 승인대기 · 회귀)

## 등록 (21)

| 번호 | 제목 | 분배 | 승인 | 판단 주인 | 됐다의 기준 | 최근 |
|---|---|---|---|---|---|---|
| [002](cards/002-영향_지도_tools_impact.py_—_.md) | 영향 지도 tools/impact.py — 호출 그래프로 소비처·검사·승인·병합 묶음 명세서, finish 가 diff 와 대조 | - | - | tools/impact.py(신설) | 주인 함수 하나 넣으면 소비처 N·검사 M·승인 여부가 나오고, 손대지 않은 소비처는 카드에 '영향 없음 — 이유'가 없으면 finish 거절(테스트로 실패→통과) | 2026-09-28 23:38 등록 |
| [003](cards/003-라이브_실측_파이프라인_tools_live_.md) | 라이브 실측 파이프라인 tools/live_check.py --card N + 관리자 버튼 + 반영 뒤 첫 고객 job 자동 1회 실측 | - | - | tools/live_check.py(신설) | 카드 층에 맞는 도구(영상·소리·자막·캡컷)를 실제 job 에 돌려 숫자·사진이 카드에 붙고, 기준 미달이면 상태 회귀 + 관리자 쪽지 | 2026-09-28 23:38 등록 |
| [004](cards/004-관리자_페이지_관제_보드_탭_+_승인_버튼.md) | 관리자 페이지 관제 보드 탭 + 승인 버튼 | - | **필요** | shopping_shorts/app.py(관리자 라우트) · 보드 렌더는 control.render_board 한 곳 | 관리자 페이지에서 BOARD.md 와 같은 내용이 보이고 승인 버튼이 카드의 승인 칸을 채운다(라이브에서 눌러 확인) | 2026-09-28 23:38 등록 |
| [005](cards/005-트랙_대청소_—_51개_→_한_자릿수(닫기_.md) | 트랙 대청소 — 51개 → 한 자릿수(닫기 후보표 → 사장님 확정 → close) | - | **필요** | tools/track.py:close · 기준 docs/superpowers/specs/2026-09-27-트랙대청소표.md | 열린 트랙 수 ≤ 9, 닫은 트랙은 미병합 0 확인 뒤에만, 살릴 트랙은 카드 연결 | 2026-09-28 23:38 등록 |
| [006](cards/006-효과음_타점_두_벌_—_sfx_events_.md) | 효과음 타점 두 벌 — sfx_events_for 'last' 에 cap_lead·cap_offset 반영, sfx_pack.plan_events 에 absorb 전달 (#9-①④·#11) | - | **필요** | shopping_shorts/video_assemble.py:sfx_events_for | tools/final_audio_audit.py 효과음 시각차 0 (cap_lead>0 칸 포함) | 2026-09-28 23:38 등록 |
| [007](cards/007-효과음·BGM_볼륨_기본값_상수_하나_—_c.md) | 효과음·BGM 볼륨 기본값 상수 하나 — capcut_draft 리터럴 15/60 네 곳 (#12) | - | - | shopping_shorts/video_assemble.py:_burn_captions | capcut_draft 에 볼륨 리터럴 0, 값 불변(캡컷 초안 볼륨 = 렌더 기본값) | 2026-09-28 23:40 등록 |
| [008](cards/008-청소_크레딧_추정_위임·죽은_clean_ba.md) | 청소 크레딧 추정 위임·죽은 clean_base_preview 정리 (#16-②·#18-①) | - | - | shopping_shorts/mix_pipeline.py:clean_charge_plan | app._clean_credit_est 가 clean_charge_plan(mode=button)['credits'] 만 부름 · clean_base_preview 호출처 0 확인 뒤 제거 | 2026-09-28 23:40 등록 |
| [009](cards/009-fill_위치·번호_혼용_·__hook_de.md) | /fill 위치·번호 혼용 · _hook_delta Path 결함 · app.py 22060 음성표 tts_paths_of (#21·#27) | - | - | shopping_shorts/store.py:dedupe_beat_idx · shopping_shorts/video_assemble.py:_apply_hook_inpoint · shopping_shorts/mix_pipeline.py:tts_paths_of | 칸 지운 job 에서 /fill 폴백이 같은 칸 길이 · _hook_delta 가 dict 를 받아 0 아닌 값 · 22060 경로가 칸 번호 겹침 차단을 탐(테스트) | 2026-09-28 23:40 등록 |
| [010](cards/010-소스_길이_표·probe_공용_—_실패_처리.md) | 소스 길이 표·probe 공용 — 실패 처리(None/0/예외) 통일 (#22) | - | - | shopping_shorts/mix_pipeline.py:_src_durs_for · shopping_shorts/video_assemble.py:_probe_duration | ownership audit 에서 #22 예외 3곳(frame_extract·export_bundle·app) → 0, 값 불변 | 2026-09-28 23:40 등록 |
| [011](cards/011-편집_화면_DATA.tts_dur_를_트림_.md) | 편집 화면 DATA.tts_dur 를 트림 반영 길이로 — 화면 컷 = 완성본 컷 (#6) | - | **필요** | shopping_shorts/video_assemble.py:_beat_effective_dur | 트림 칸 수 실측 → tools/editor_vs_final_video.py 밀림 감소, 화면 컷 경계 = 완성본 | 2026-09-28 23:40 등록 |
| [012](cards/012-beats_preview_API_가_capt.md) | beats_preview API 가 caption_rows 를 싣고 produce.html 은 그 값만 (#9-③) | - | **필요** | shopping_shorts/video_assemble.py:caption_rows | produce.html 의 _cutForSegOf 자체 계산 0 · 꾸미기 미리보기 자막 시각 = 완성본(tools/final_caption_audit.py) | 2026-09-28 23:40 등록 |
| [013](cards/013-화면에_보일_청소_파일_한_함수_—__cle.md) | 화면에 보일 청소 파일 한 함수 — _clean_frame_src·_thumb_clean_background·스타일랩 흡수 (#17) | - | - | shopping_shorts/mix_pipeline.py:clean_route | 썸네일·꾸미기 배경 프레임의 청소 파일 = 완성본이 쓴 것(같은 job 대조 0 불일치) | 2026-09-28 23:40 등록 |
| [014](cards/014-캡컷_소스_복사_범위_=_render_cut.md) | 캡컷 소스 복사 범위 = render_cut_plan 이 실제 쓴 video_id (#23·#25) | - | - | shopping_shorts/mix_pipeline.py:export_sources_for | tools/capcut_export_audit.py 미디어 누락 0 | 2026-09-28 23:41 등록 |
| [015](cards/015-음성_지문·서명_한_함수_—_plan_sig.md) | 음성 지문·서명 한 함수 — plan_signature/_pvproxy_tts_stamp/timing_signature (#20) | - | - | shopping_shorts/mix_pipeline.py:plan_signature | 성우 바꾸면 청소본·합본·꾸미기 세 산출물이 동시에 낡음 처리(실측 job) | 2026-09-28 23:41 등록 |
| [016](cards/016-화면_길이_예산_모델을_화면_계획_결과로_(.md) | 화면 길이 예산 모델을 화면 계획 결과로 (#29) | - | - | shopping_shorts/mix_pipeline.py:beat_screen_budget | 콘폼(재TTS) 발생 건수 전/후 실측, 못 채운 칸 0 | 2026-09-28 23:41 등록 |
| [017](cards/017-파이썬_예비_컷_계획_축소_—_화면_데이터_.md) | 파이썬 예비 컷 계획 축소 — 화면 데이터 없는 옛 job 전용 + 경보 (#1) | - | - | shopping_shorts/static/scene_play.js:planClips | FALLBACK 경보 건수 7일 0 · ownership 예외(video_assemble 예비 계획) 삭제 | 2026-09-28 23:41 등록 |
| [018](cards/018-캡컷_이동(pan)·기본_확대_반영_+_꾸미.md) | 캡컷 이동(pan)·기본 확대 반영 + 꾸미기 프레임 구도를 frame_vf 로 (#5) | - | - | shopping_shorts/video_assemble.py:frame_vf | 확대·이동 준 칸의 캡컷 위치 = 완성본(좌표계 실측) · 꾸미기 배경 프레임 구도 = 완성본 | 2026-09-28 23:41 등록 |
| [019](cards/019-캡컷_자막_위치·폰트_—_cap_xy_cap.md) | 캡컷 자막 위치·폰트 — cap_xy/cap_pos·폰트 동봉 (#10) | - | - | shopping_shorts/video_assemble.py:_beat_cap_style | 캡컷 초안 자막 위치 = 완성본(좌표계 실측), 폰트 동봉 | 2026-09-28 23:42 등록 |
| [020](cards/020-컷_규칙_상수_한_곳_+_MAX_SLOWMO.md) | 컷 규칙 상수 한 곳 + MAX_SLOWMO 서버 주입 (#30·#4) | - | - | shopping_shorts/config.py(상수) → scene_play.js DATA 주입 | MAX_SHOT/MIN_CLIP/CUT_MIN/MAX_SLOWMO 정의 1곳, ownership 예외(edit_plan·config·scene_play) 삭제 | 2026-09-28 23:42 등록 |
| [021](cards/021-고질병_선별_—_find_work.py_로_.md) | 고질병 선별 — find_work.py 로 증상어 재발 횟수 세어 재발 순 카드화 | - | - | tools/find_work.py | 후보 9개(자막 먼저 뜸·칸 길이 올림·서명 재과금·인스타 세션·beat_idx·데코레이터 밀림·검정 프레임·미리보기만 바뀜·정지 컷) 각각 '지금도 재발하나' 실측 → 카드 또는 완료 표시 | 2026-09-28 23:42 등록 |
| [022](cards/022-옛_규칙_정리_—_도구가_강제하게_된_CLA.md) | 옛 규칙 정리 — 도구가 강제하게 된 CLAUDE.md 문장 삭제·요약 (설계 §5-7) | - | - | CLAUDE.md | CLAUDE.md 길이 감소, 삭제한 문장마다 대신 강제하는 도구 이름이 핸드오프에 적힘 | 2026-09-28 23:42 등록 |

## 분배 (5)

| 번호 | 제목 | 분배 | 승인 | 판단 주인 | 됐다의 기준 | 최근 |
|---|---|---|---|---|---|---|
| [026](cards/026-TopView_Higgsfield_비교_HT.md) | TopView Higgsfield 비교 HTML | topview-higgsfield-html | - | Codex:HTML 보고서 제작 | 비교 HTML 작성·검증·배포 | 2026-09-29 11:58 분배 → topview-higgsfield-html |
| [027](cards/027-Higgsfield_API_내부_시험_생성.md) | Higgsfield API 내부 시험 생성 | higgsfield-api-pilot | 2026-09-29 14:09 · 사장님 | Codex | 관리자 전용 이미지→영상 시험 화면, 서버측 API 키, 예상 포인트, 성공 차감·실패 환불, 테스트 통과 | 2026-09-29 14:09 승인: 사장님 |
| [028](cards/028-신규_회원_시작_안내_공개_페이지_start.md) | 신규 회원 시작 안내 공개 페이지 /start_guide.html | 시작안내페이지 | 2026-09-29 13:46 · 사장님 구두 2026-09-29 '서버에 있어야 계속 쓸 수 있는 거 아닌가' | shopping_shorts/app.py:_AUTH_ALLOW | 비로그인 curl 200, 링크 클릭 동작, 라이브 주소를 사장님이 카톡 전송 | 2026-09-29 13:46 승인: 사장님 구두 2026-09-29 '서버에 있어야 계속 쓸 수 있는 거  |
| [033](cards/033-장면_반복·소스_쏠림_—_장면_고정이_같은_.md) | 장면 반복·소스 쏠림 — 장면 고정이 같은 근거컷 재사용 | 장면반복 | - | shopping_shorts/backbone.py:finalize_scenes | 같은 재료 재생성 시 한 편 안 같은 컷 재사용 0, 소스 편중 완화 — 결과 영상 프레임 대조 | 2026-09-29 21:31 판단 주인: shopping_shorts/backbone.py:finalize |
| [036](cards/036-장면꾸미기_썸네일_동일_그림자·대상별_분리.md) | 장면꾸미기 썸네일 동일 그림자·대상별 분리 | 장면폰트 | 2026-09-29 22:57 · 사장님 — 썸네일 측정 후 동일 효과·대상별 분리 요청 (2026-09-29) | out/precision20-ui.js:drawFontSets | 썸네일 그림자 공식과 장면꾸미기 100값의 픽셀 오프셋·번짐이 일치하고 채널명/큰 제목/작은 제목/자막을 각각 독립 조절, 미리보기·렌더·캡컷·썸네일 픽셀 변화 확인 | 2026-09-29 22:57 승인: 사장님 — 썸네일 측정 후 동일 효과·대상별 분리 요청 (2026-09 |

## 병합 (6)

| 번호 | 제목 | 분배 | 승인 | 판단 주인 | 됐다의 기준 | 최근 |
|---|---|---|---|---|---|---|
| [023](cards/023-저장_층(C_D)_관제_—_외장_D_숏템_을.md) | 저장 층(C/D) 관제 — 외장 D:\숏템 을 지도(관제/storage.json)로 나누고 tools/storage.py 가 status/plan/apply | 관제 | - | tools/storage.py:plan | C 여유가 경고선 15GB 위로 올라오고 유지 · 옮긴 것마다 D 에 bundle/파일이 있고 C 에 두 벌 없음 · 다른 세션 경로 깨짐 0 | 2026-09-29 00:42 병합 5bd6c66612 ← 트랙 관제 (반영됨·미검증 — 라이브 실측 전) |
| [025](cards/025-심효진(451)_음성_차단_면제_—_사장님_.md) | 심효진(451) 음성 차단 면제 — 사장님 일레븐 키 개방 | 음성면제_심효진 | 2026-09-29 11:43 · 사장님 구두 2026-09-29 '내꺼 일레븐 랩스 키 심효진님한테 열어줘 쓸수있게' | shopping_shorts/keyroute.py:is_block_exempt | 라이브에서 cid 451 음성 생성 요청이 402 need_own_key 없이 200 · 서버 로그 tts 호출 1건 이상 | 2026-09-29 14:29 병합 28e9cdad51 ← 트랙 음성면제_심효진 (반영됨·미검증 — 라이브  |
| [030](cards/030-장면꾸미기_글자_두께·그림자_슬라이더·수치.md) | 장면꾸미기 글자 두께·그림자 슬라이더·수치 | 장면폰트 | 2026-09-29 16:21 · 사장님 — 올려 (2026-09-29) | out/precision20-ui.js:drawFontSets | 폰트 탭에 두께·그림자 각각 −/슬라이더/＋/현재 수치가 보이고 조절값이 저장·재열기·렌더 레이어·썸네일·최종 합성에 동일 반영 | 2026-09-29 20:54 병합 689478d8c6 ← 트랙 장면폰트 (반영됨·미검증 — 라이브 실측 전 |
| [031](cards/031-job_실패_시_1단계_잠금_문구_대신_실패.md) | job 실패 시 1단계 잠금 문구 대신 실패 사유 표시 | 잠금사유 | 2026-09-29 16:20 · 사장님 | shopping_shorts/static/produce.html:stepLockMsg | status=failed job에서 잠긴 단계 클릭 시 job.error가 보인다(라이브 확인) | 2026-09-29 18:44 병합 406e99cf5c ← 트랙 잠금사유 (반영됨·미검증 — 라이브 실측 전 |
| [032](cards/032-새_편집기_채널명_기본값=계정_내_채널명(프.md) | 새 편집기 채널명 기본값=계정 내 채널명(프리셋 적용 시 숏템메이커로 돌아감) | 채널명기본 | 2026-09-29 18:48 · 사장님 | shopping_shorts/scene_style.py:account_channel | 새 작업을 새 편집기로 열면 채널명이 계정 채널명(오탐구)으로 뜬다(라이브 확인) | 2026-09-29 22:35 병합 7510c94fda ← 트랙 채널명기본 (반영됨·미검증 — 라이브 실측  |
| [035](cards/035-서버_디스크_가득_참_재발_방지(find_f.md) | 서버 디스크 가득 참 재발 방지(find_frames 청소·디스크 경보·traceback import) | 디스크방지 | 2026-09-29 21:53 · 사장님 | shopping_shorts/disk_cleanup.py:run | find_frames가 매일 청소되고, 여유 15% 미만이면 관리자 경보가 뜨며, 앱 기동이 롱폼 실패로 죽지 않는다(서버 실측) | 2026-09-29 22:19 병합 b677097441 ← 트랙 디스크방지 (반영됨·미검증 — 라이브 실측  |

## 라이브실측 (4)

| 번호 | 제목 | 분배 | 승인 | 판단 주인 | 됐다의 기준 | 최근 |
|---|---|---|---|---|---|---|
| [001](cards/001-관제_시스템_1차_구축(카드·보드·승인·선점.md) | 관제 시스템 1차 구축(카드·보드·승인·선점·소유권 관문) | 관제 | - | tools/control.py:finish_gate · tools/ownership_check.py:compare_texts | 실제 저장소에서 ①카드 없는 start 거절 ②finish 관제 관문 통과·카드에 병합 기록 자동 ③test_control 29건 green | 2026-09-29 00:42 병합 5bd6c66612 ← 트랙 관제 (반영됨·미검증 — 라이브 실측 전) |
| [024](cards/024-장면꾸미기_글자_두께·그림자_설정([폰트]_.md) | 장면꾸미기 글자 두께·그림자 설정([폰트] 탭, 영상 전체) | 장면폰트 | 2026-09-29 00:16 · 사장님 구두 2026-09-29 00:00 '올려봐 라이브후에 랜더랑 캡컷 확인하고' | out/precision20-ui.js:TEXT_WEIGHTS/TEXT_SHADOWS CSS(글자층 data-tw/data-ts) | tools/scene_font_research/check_text_look.py 전부 통과 + 라이브 실제 job 렌더·캡컷에서 글자 달라짐 확인 | 2026-09-29 20:54 병합 689478d8c6 ← 트랙 장면폰트 (반영됨·미검증 — 라이브 실측 전 |
| [029](cards/029-대본_영어모드로_변환하기_—_확정_한국어_대.md) | 대본 영어모드로 변환하기 — 확정 한국어 대본을 문장별 영어로 번역(TTS·자막 영어) | 영어모드변환 | 2026-09-29 14:49 · 사장님 구두 2026-09-29 '영어모드로 변환하기 이런거' | shopping_shorts/script_translate.py:to_english | 격리 시험 실재료 10편: 번역 줄수=원문 줄수, 영어 비율≥95%, 일레븐 TTS 정상, 자막 줄 영어, 타입캐스트 성우는 영어모드에서 차단. 사장님 승인 후 라이브 | 2026-09-29 20:42 병합 cee8e5d354 ← 트랙 영어모드변환 (반영됨·미검증 — 라이브 실측 |
| [034](cards/034-타입캐스트_키_없는_회원의_기본_성우_자동_.md) | 타입캐스트 키 없는 회원의 기본 성우 자동 일레븐 대체 — 3단계 막힘 해소 | 영어모드변환 | 2026-09-29 19:52 · 사장님 구두 2026-09-29 '먼저 수리하고 잘린 사람들 유료키 있으면 일레븐으로 자동 지정 / 일레븐 유료 안 된 사람은 내 거로 쓰게 하지 말고' | shopping_shorts/typecast_tts.py:use_fallback | 라이브: 580 배승훈 새 3단계 작업이 TTS 통과(ready_for_review), 기본 성우 타입캐스트+일레븐키 회원 6명 새 작업 실패 0 | 2026-09-29 21:15 상태 병합 → 라이브실측 |
