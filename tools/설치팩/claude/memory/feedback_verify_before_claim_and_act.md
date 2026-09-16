---
name: feedback_verify_before_claim_and_act
description: 상태 진단·주장 전에 충분한 표본으로 실측하라. 성급한 단정·파괴적 조작 금지
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a63a86bf-1587-4dd9-944a-3dcf24287cfa
  modified: 2026-07-25T10:35:39.282Z
---

사장님 피드백(2026-07-25): "계속 이상한걸 하는데 확실하게 검증해." 배포큐 정체 대응 중
process를 짧은 관찰(40초)로 "hang이다" 단정하고 **실제로 진행 중이던(CPU 45→75s 증가) 게이트를 죽임**.
반복적으로 검증 없이 움직여 신뢰를 깎았다.

**Why:** 프로세스 CPU가 잠깐 안 오르는 건 I/O 대기일 뿐 hang이 아니다. 짧은 창으로 판단하면
정상 작업을 오진해 죽인다(파괴적·비가역). 또 "고쳤다/됐다"를 실측 없이 주장하면 사장님이
직접 확인해야 해 시간을 뺏긴다.

**How to apply:**
- 진단은 **충분한 표본**으로. CPU 정체 판정은 최소 2~3분 연속 관찰 후. 한 번 낮다고 hang 단정 금지.
- **파괴적 조작(kill·reset·삭제) 전 재확인** + 되도록 안 죽이고 기다린다. 특히 남의 세션 프로세스.
- 완료/작동 주장은 **직접 호출·DB·origin 조상 확인 등 실측 근거**를 붙인다(추측 금지).
  예) 엔드포인트=서버서 curl/직접호출, 배포=origin merge-base + 서비스 재시작시각, 데이터=DB 카운트.
- "unauthorized" 같은 응답은 버그가 아니라 페이월 정상동작일 수 있으니 raw 응답부터 본다.
- 관련: [[feedback_self_verify_before_reporting]] · [[feedback_verify_with_real_data]] · [[reference_track_finish_no_overlap]]
