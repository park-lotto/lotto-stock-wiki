# 관제 보드 (자동 생성 — 손으로 고치지 마라. `py tools/control.py board`)

갱신: 2026-09-28 23:40 · 카드 7장

상태 흐름: 등록 → 분배 → 수리 → 로컬검증 → 병합 → 서버반영 → 라이브실측 → 완료  (예외: 승인대기 · 회귀)

## 등록 (6)

| 번호 | 제목 | 분배 | 승인 | 판단 주인 | 됐다의 기준 | 최근 |
|---|---|---|---|---|---|---|
| [002](cards/002-영향_지도_tools_impact.py_—_.md) | 영향 지도 tools/impact.py — 호출 그래프로 소비처·검사·승인·병합 묶음 명세서, finish 가 diff 와 대조 | - | - | tools/impact.py(신설) | 주인 함수 하나 넣으면 소비처 N·검사 M·승인 여부가 나오고, 손대지 않은 소비처는 카드에 '영향 없음 — 이유'가 없으면 finish 거절(테스트로 실패→통과) | 2026-09-28 23:38 등록 |
| [003](cards/003-라이브_실측_파이프라인_tools_live_.md) | 라이브 실측 파이프라인 tools/live_check.py --card N + 관리자 버튼 + 반영 뒤 첫 고객 job 자동 1회 실측 | - | - | tools/live_check.py(신설) | 카드 층에 맞는 도구(영상·소리·자막·캡컷)를 실제 job 에 돌려 숫자·사진이 카드에 붙고, 기준 미달이면 상태 회귀 + 관리자 쪽지 | 2026-09-28 23:38 등록 |
| [004](cards/004-관리자_페이지_관제_보드_탭_+_승인_버튼.md) | 관리자 페이지 관제 보드 탭 + 승인 버튼 | - | **필요** | shopping_shorts/app.py(관리자 라우트) · 보드 렌더는 control.render_board 한 곳 | 관리자 페이지에서 BOARD.md 와 같은 내용이 보이고 승인 버튼이 카드의 승인 칸을 채운다(라이브에서 눌러 확인) | 2026-09-28 23:38 등록 |
| [005](cards/005-트랙_대청소_—_51개_→_한_자릿수(닫기_.md) | 트랙 대청소 — 51개 → 한 자릿수(닫기 후보표 → 사장님 확정 → close) | - | **필요** | tools/track.py:close · 기준 docs/superpowers/specs/2026-09-27-트랙대청소표.md | 열린 트랙 수 ≤ 9, 닫은 트랙은 미병합 0 확인 뒤에만, 살릴 트랙은 카드 연결 | 2026-09-28 23:38 등록 |
| [006](cards/006-효과음_타점_두_벌_—_sfx_events_.md) | 효과음 타점 두 벌 — sfx_events_for 'last' 에 cap_lead·cap_offset 반영, sfx_pack.plan_events 에 absorb 전달 (#9-①④·#11) | - | **필요** | shopping_shorts/video_assemble.py:sfx_events_for | tools/final_audio_audit.py 효과음 시각차 0 (cap_lead>0 칸 포함) | 2026-09-28 23:38 등록 |
| [007](cards/007-효과음·BGM_볼륨_기본값_상수_하나_—_c.md) | 효과음·BGM 볼륨 기본값 상수 하나 — capcut_draft 리터럴 15/60 네 곳 (#12) | - | - | shopping_shorts/video_assemble.py:_burn_captions | capcut_draft 에 볼륨 리터럴 0, 값 불변(캡컷 초안 볼륨 = 렌더 기본값) | 2026-09-28 23:40 등록 |

## 분배 (1)

| 번호 | 제목 | 분배 | 승인 | 판단 주인 | 됐다의 기준 | 최근 |
|---|---|---|---|---|---|---|
| [001](cards/001-관제_시스템_1차_구축(카드·보드·승인·선점.md) | 관제 시스템 1차 구축(카드·보드·승인·선점·소유권 관문) | 관제 | - | tools/control.py:finish_gate · tools/ownership_check.py:compare_texts | 실제 저장소에서 ①카드 없는 start 거절 ②finish 관제 관문 통과·카드에 병합 기록 자동 ③test_control 29건 green | 2026-09-28 23:38 등록 · 분배 → 관제 |
