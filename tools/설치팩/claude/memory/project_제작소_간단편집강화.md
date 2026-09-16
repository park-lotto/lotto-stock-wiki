---
name: project
description: 제작소 웹편집 방향=캡컷클론 아니라 간단편집 버튼 강화. 문장별 트림 라이브했으나 발견성 문제로 약해보임
metadata: 
  node_type: memory
  type: project
  originSessionId: d688bc4e-9cd0-4808-a002-54409514a283
  modified: 2026-07-22T13:56:50.391Z
---

쇼핑쇼츠 제작소 웹 편집 방향 결정(2026-07-22). 트랙 `제작소트림`.

**문장별 트림(끝/앞 무음꼬리 자르기) 라이브 완료** — 비파괴 head_trim/tail_trim, 단일출처
`_beat_effective_dur`로 영상·자막·다음비트·캡컷 자동 동반. `POST /api/produce/mix/{job}/trim`.

**하지만 사장님 피드백 "기능 안 좋다".** 진단: 기능 로직보다 **발견성이 문제.**
편집 버튼(트림·🎞화면교체)이 **「영상 매칭」 단계 #mixReview 문장 카드에만** 있어, 완성본
(최종검수·렌더) 화면 보는 사장님 눈엔 안 보임 → "🎞 버튼이 어디?".

**방향 확정: 캡컷 클론(웹 타임라인 편집기) 아님.** 몇 주짜리 + 시니어 북극성과 반대라 기각.
대신 **간단편집을 버튼으로 채운다.** 다음 세션 우선순위(사장님 최종선택 대기):
①완성본 화면서 바로 편집(발견성-최대문제) ②글자 고치면 그 문장만 재녹음(resynth_one_beat 배관
있음, narration override만 추가) ③장면 순서바꾸기/빼기 ④트림 UI 다듬기.

교훈: 새 편집기능은 **사장님이 실제 보는 화면(완성본)에 붙여야** 쓴다. 앞 단계 카드에 숨기면
"기능이 안 좋다"로 돌아온다. 상세=핸드오프 `.tracks/제작소트림/handoff/제작소트림.md`.
[[project_scene_spine_2track]] [[feedback_ttalkkak_senior_northstar]] [[project_제작소_어긋남구제]]
