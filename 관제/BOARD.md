# 관제 보드 (자동 생성 — 손으로 고치지 마라. `py tools/control.py board`)

갱신: 2026-09-28 23:42 · 카드 19장

상태 흐름: 등록 → 분배 → 수리 → 로컬검증 → 병합 → 서버반영 → 라이브실측 → 완료  (예외: 승인대기 · 회귀)

## 등록 (18)

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

## 분배 (1)

| 번호 | 제목 | 분배 | 승인 | 판단 주인 | 됐다의 기준 | 최근 |
|---|---|---|---|---|---|---|
| [001](cards/001-관제_시스템_1차_구축(카드·보드·승인·선점.md) | 관제 시스템 1차 구축(카드·보드·승인·선점·소유권 관문) | 관제 | - | tools/control.py:finish_gate · tools/ownership_check.py:compare_texts | 실제 저장소에서 ①카드 없는 start 거절 ②finish 관제 관문 통과·카드에 병합 기록 자동 ③test_control 29건 green | 2026-09-28 23:38 등록 · 분배 → 관제 |
