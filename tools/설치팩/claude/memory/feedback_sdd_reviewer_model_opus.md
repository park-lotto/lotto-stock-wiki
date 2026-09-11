---
name: feedback_sdd_reviewer_model_opus
description: subagent-driven-development에서 태스크 리뷰어는 Opus로 디스패치할 것(중요 판단 필요시)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 661ff3d8-37ef-4a0f-9903-231faed71867
---

subagent-driven-development(SDD)로 구현 태스크를 실행할 때, 태스크 리뷰어(spec compliance + code quality 검토) 서브에이전트는 Sonnet 대신 **Opus**로 디스패치해야 한다. 사용자가 "오푸스가 검토하고 해야할때 바꿔서해야대"라고 명시적으로 교정함.

**Why**: SDD 스킬의 Model Selection 가이드는 "review 태스크는 diff 크기·복잡도·리스크에 맞춰 판단"이라고만 돼있어 애매한데, 사용자는 리뷰(특히 판단이 중요한 검토)는 항상 Opus급으로 하길 원함. 구현(implementer)은 태스크 성격에 따라 haiku/sonnet 등급을 낮춰도 되지만, 검토는 더 신뢰도 높은 모델을 쓰길 원하는 걸로 이해.

**How to apply**: SDD/코드리뷰 워크플로에서 Agent 디스패치 시 `model` 파라미터를 리뷰어 역할이면 기본값을 `opus`로. 최종 whole-branch review는 스킬 문서 자체도 "가장 강력한 모델"을 명시하고 있어 일관됨. 구현자(implementer) 모델 선택은 기존 가이드(기계적=cheap, 판단필요=standard) 그대로 유지하되, 리뷰어만 opus로 상향.

**업데이트(2026-07-14 세션 후반)**: 사용자가 메인 모델을 Opus 4.8(1M)로 전환하고 "지금부터 오푸스가 테스크에 맞게 하이쿠나 소넷배치"라고 지시. 즉 컨트롤러=Opus가 오케스트레이션하고, 서브에이전트는 **구현=태스크 성격 따라 haiku(기계적/계획서에 코드완비)·sonnet(통합/판단), 리뷰어=opus**로 배치. 컨트롤러가 직접 구현하지 말고 SDD식으로 위임 유지.
