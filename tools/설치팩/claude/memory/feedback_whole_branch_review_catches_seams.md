---
name: feedback_whole_branch_review_catches_seams
description: SDD 최종 whole-branch 리뷰는 생략 금지 — 개별태스크 리뷰가 구조적으로 못 보는 통합 seam을 잡는다
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 661ff3d8-37ef-4a0f-9903-231faed71867
---

subagent-driven-development에서 **최종 whole-branch 리뷰(가장 강력한 모델)를 절대 생략하지 말 것.** 개별 태스크 리뷰가 아무리 꼼꼼해도(각 태스크 opus 리뷰 통과해도) 구조적으로 못 보는 게 있다: **태스크 사이의 배선(seam)**.

**Why (실사례 2026-07-14 쇼핑쇼츠 꾸미기 단어별강조)**: 6태스크 전부 개별 opus 리뷰 Approved, 실렌더 grounding도 통과했는데, 최종 whole-branch 리뷰가 Critical을 잡음 — `highlight_rules`를 UI는 `deco`에 저장하는데 렌더러는 `headcopy`/`caption_style`에서 읽어서, **강조 단어가 브라우저 미리보기엔 나오지만 실제 MP4엔 안 나옴**. 각 유닛테스트는 `_segmented_drawtext`에 규칙을 **직접 전달**해서 통과했고(payload 경로 우회), 내 렌더 grounding도 함수를 **격리**해서 호출해 이 gap을 못 건드림. 아무도 "저장→렌더" 전체 경로를 한 번에 안 봤기 때문. `_burn_captions`에 `_merge_highlight_rules` chokepoint로 해결.

**How to apply**:
1. SDD 마지막에 whole-branch 리뷰 반드시 실행(opus/최강모델). 리뷰 프롬프트에 "개별 태스크 리뷰가 못 본 것 — 태스크 사이 배선/데이터흐름 통합"을 명시적 focus로.
2. **grounding/검증 시 격리 호출 말고 실제 payload 경로로**: 함수에 인자 직접 넘겨 테스트하면 "저장 위치 ≠ 읽기 위치" 같은 배선버그를 못 잡는다. 실제 데이터가 흐르는 경로(UI저장→DB→파이프라인→렌더)를 재현해서 grounding.
3. end-to-end 테스트 1개는 필수 — "기능이 저장되는가"(T5식)만으로 부족, "저장된 게 최종 산출물에 반영되는가"까지. [[feedback_verify_with_real_data]] [[feedback_self_verify_before_reporting]]
