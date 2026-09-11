---
name: reference
description: SVG 아이콘은 코드로 못 판단한다 — 실제 크기로 확대해 봐야 뭉친 게 보인다(8단계 해시가 ≠로 읽힌 실측)
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca533dce-2a08-471e-8432-fea7aeb13bb4
  modified: 2026-08-26T01:16:16.924Z
---

2026-08-26 단계바 도크 작업 실측: 8단계 "제목·태그" 아이콘으로 해시(#)를 그렸는데,
세 줄 + 해시 마크가 24x24 안에서 겹쳐 **`≠` 처럼 읽혔다**. SVG path만 보면 멀쩡했고,
전체 스크린샷에서도 46px이라 안 보였다. `zoom`으로 확대하고서야 발견했다.

**How to apply**: 아이콘을 새로 그리면 **반드시 실제 렌더를 확대해 눈으로 본다**
(claude-in-chrome `computer` action=zoom). 코드 리뷰·전체 스크린샷은 관찰이 아니다.
특히 24x24처럼 작은 캔버스에 요소를 2개 이상 넣을 때 뭉친다 — 하나만 크게 그리는 게 낫다.

관련: [[feedback_mockup_is_source_of_truth]] [[feedback_self_verify_before_reporting]]
