---
name: feedback_keep_going_autonomous
description: "작은 결정마다 멈춰 묻지 말고, 추천대로 자율 진행하라"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca2599eb-ffdc-49ee-bb3f-1a1dffb96b8c
---

위키 3워커 엔진 1단계 구현 중, 매 단계 사용자 확인을 받으려 멈추자 "일단 끊기지 말고 계속 진행해"라고 지시.

**Why:** 사용자는 큰 방향만 정해주면 나머지 실행 디테일은 Claude가 추천안대로 밀고 나가길 원함. 사소한 분기마다 멈추면 흐름이 끊기고 답답함.

**How to apply:** 방향이 정해졌으면 작은 결정(칸 강등, false positive 처리, 다음 종목 확장 등)은 추천안대로 바로 실행하고 진행. 멈춤은 (a) 진짜 되돌리기 어려운 결정 (b) 그릇/설계 자체가 갈리는 분기 일 때만. 그 외엔 진행하면서 한 일을 요약 보고. [[feedback_break_long_tasks]] 와 균형 — 분할은 하되 매번 승인받지는 않음.

**강화 (2026-06-23):** "묻지 말고 계속 진행해. 어차피 너가 지금 설계하는 거고, 완성되면 내가 수정 볼 거야." → 설계·구현 단계에선 **AskUserQuestion 금지**. 마일스톤까지 자율로 밀고 나가 완성본을 만들고, 사용자는 완성된 결과를 리뷰·수정한다. 중간 확인보다 완성본 제시가 사용자 선호.
