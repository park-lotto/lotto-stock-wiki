---
name: feedback-break-long-tasks
description: 긴 작업은 조각내서 해야 실수 줄어듦 — 긴 파일 작성 전 중간 확인 필수
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d6141d13-6265-4abd-b1b7-5846b9c7a690
---

긴 코드 작성 작업은 한 번에 몰아쓰지 않고 중간중간 잘라서 진행한다.

**Why:** 호흡이 긴 작업에서 실수가 반복됨. 한 번에 많이 쓰면 오류 감지가 늦어짐.

**How to apply:**
- 큰 컴포넌트 재작성 시: Phase별로 나눠 작성하고 각 단계마다 TSC 확인
- 5개 이상 변경이 필요하면 3개씩 끊어서 확인 후 진행
- 자막/타이밍 수치 변경은 한 씬씩 처리하고 바로 검증
