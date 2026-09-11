---
name: reference
description: "자막제거 전/후 비교가 장면편집 뒤에 또 갈렸다 — 청소본(final_clean_{sig}.mp4)의 초는 청소 그 시점 편성의 좌표. 지금 편성 시각을 옛 파일에 대면 딴 장면. 처방=편성 스냅샷+정본 함수 하나"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 9247e81a-7f93-41db-a404-47d3fab6c64f
  modified: 2026-09-03T07:57:37.350Z
---

**증상(2026-09-03, job fb62adf0aad0)**: BEFORE 줄무늬 셔츠 여성 / AFTER 보라 옷 여성. 08-27 컷단위 짝맞춤은 살아 있었다.

**뿌리**: 10:23 청소 → 16시 scene_lab apply 30회로 편성 서명이 바뀜(길이 22.55→20.42초).
`clean_thumb`가 **지금 편성**의 컷 시각을 **옛 청소본**에 댔다. 파생 파일(청소본·완성본)의
초는 그 파일을 만든 시점 편성의 좌표다 — 편성이 바뀌면 그 초는 아무 뜻이 없다.
09-01에 꾸미기 컷 카드용 신선도 판정(`clean_final_matches_plan`)이 이미 있었는데 이 화면은 안 썼다
(같은 판정이 한 화면에만 적혀 있던 것 = 0순위-B).

**처방**: 청소본 옆에 그때 편성 스냅샷 `final_clean_{sig}.plan.json` 저장 →
`mix_pipeline.clean_compare_clips` 한 곳이 "어느 파일을 어느 편성으로 펼지" 정한다.
스냅샷 없는 옛 job은 404 reason=stale(틀린 그림 대신 사실).

**적용법**: "좌우/전후가 다르다" 제보엔 먼저 **파생 파일 mtime vs 편성 변경 시각**(scene_lab apply·voice·beat delete 로그)을 대조하라.
비교 넘기기는 소스 수가 아니라 컷 수(실측 4소스→23컷). 프레임은 ffmpeg 1회라 유료 재호출 0.

관련: [[reference_scene_dup_by_desc_not_phash]] [[reference_silent_fallback_pipeline_undo]]
