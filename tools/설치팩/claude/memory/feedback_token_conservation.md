---
name: feedback-token-conservation
description: "토큰 절약 최우선 규칙 — 불필요한 테스트/출력 금지, Gemini·Haiku 적극 위임"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f1922404-cc27-4cc2-9850-17c86f63f8dd
---

토큰 절약은 1번 규칙. 함부로 소모하지 마라.

**Why:** 불필요한 테스트 실행, 긴 Bash 출력 그대로 인용 등으로 컨텍스트를 낭비하면 세션이 빨리 압축되고 비용이 증가한다.

**How to apply:**
- 코드 작성 후 검증 테스트는 최소 1회, 가장 작은 케이스로만
- 이미 성공한 테스트 후 추가 테스트 절대 금지
- Bash 출력 50줄 초과 시 반드시 1줄 요약으로 축약
- 단순 작업(파일 탐색·로그 기록·index 업데이트·파일명 추출 등)은 Haiku 서브에이전트에 위임
- 대량 텍스트 처리·요약·분류는 Gemini Flash Lite에 위임
- Sonnet(나 자신)은 분석·판단·창작·WebSearch 결합만 직접 처리

[[feedback_model_switching]]
