---
name: project_scene_spine_first
description: 장면 스파인 먼저 재설계 — 카테고리 스파인 슬롯순서로 장면 먼저배치→대본 나중(라이브)
metadata: 
  node_type: memory
  type: project
  originSessionId: e3200863-e835-4820-8646-1363404cefa8
  modified: 2026-07-29T10:07:49.688Z
---

**장면 스파인 먼저 → 대본 나중** 재설계 라이브 배포(2026-07-29, origin/main 70fe7e58d, 모션레벨훅 트랙).

**뿌리**: 라이브 대본경로(`edit_plan._scene_first_candidates`)가 이름만 scene_first고 실제론 **narration-first** — 제미니가 멘트 쓰며 장면을 골라붙이고, 사후 `ping_pong_reconcile`/`order_by_backbone`가 재정렬. → 장면↔멘트 어긋남·비트순서 뒤죽박죽(사장님 실측 e5840bfe: "완성돼요" 멘트에 기계뚜껑잠금 화면, CTA 5초중간).

**사장님이 그린 맞는 구조**: ①파이썬 컷분할(ffmpeg scene_cut, 이미있음) ②제미니 태깅(shot_role/is_key/scene_desc, 이미있음) ③**장면 스파인 먼저 확정** ④대본을 뼈대에 얹음. 장면이 운전대.

**구현**(edit_plan.py, script_extract.py, app.py):
- `VIDEO_TYPES` 2개→**5개**(recipe/kitchen_tool/beauty/cleaning/generic) 각 `spine`(슬롯 순서 배열) 신설. `_DEFAULT_TYPE=generic`.
- 옛 key(recipe_secret→recipe, product_reveal→generic) `_normalize_video_type` fail-open — detect/build/app result/retype 전배선.
- `shot_role` enum 확장: 조리/완성/기타 → **before/사용중/after/완성/문제/기타**. 옛 '조리'→'사용중' 마이그레이션(`_norm_shot_role`).
- `_build_scene_spine(seg_map, video_type)`: 태깅장면을 카테고리 스파인 슬롯 순서로 배치(장면순서 확정). `_spine_order_block`이 "순서 고정" 하드제약으로 프롬프트 주입.
- **기본경로(backbone_base off=라이브 기본)만 스파인**, opt-in 백본모드는 기존 백본블록 유지(분리 안하면 test_backbone_base 깨짐 — 게이트가 1차로 잡아 라이브 지킴).

**미완(후속·리스크)**: ping_pong 사후재정렬(order_by_backbone) 제거는 안 함 — dedup/balance 얽혀 리스크. 스파인은 생성시 슬롯별 장면↔멘트 짝을 고정하므로 핵심 어긋남은 이미 잡음.

**검증 남음**: 새로 담아 믹스 재렌더 → 자막순서 스토리일관 + CTA마지막 + 장면멘트싱크 육안. 설계문서 `docs/superpowers/specs/2026-07-29-장면스파인-먼저-재설계-design.md`. [[project_scene_spine_2track]] 원래 2트랙 설계의 실배선.
