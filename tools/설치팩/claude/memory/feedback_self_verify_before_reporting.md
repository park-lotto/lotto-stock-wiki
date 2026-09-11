---
name: feedback-self-verify-before-reporting
description: UI/데이터 수정 후 스크린샷으로 보고하기 전에 브라우저 도구로 직접 검증할 것 — 사용자가 QA 루프 역할 하지 않게
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 174439c8-05f0-4472-9abf-783a04b1935b
---

대시보드(market.html 등) 수정 후 "됐다"고 보고하기 전에 Claude가 먼저 claude-in-chrome 도구(javascript_tool로 DOM/SVG 좌표·API 응답 직접 조회, computer screenshot)로 검증해야 한다.

**Why:** 여러 턴에 걸쳐 사용자가 매번 PowerToys 스크린샷을 찍어 "이거 안 됐잖아"를 반복 지적해야 했음 (2026-07-02, 로또의 주식 대시보드 세션). 결국 "너가 하고 확인을 좀 해라"는 직접적 피드백을 받음. 스크린샷을 눈으로 어림짐작하는 것도 부정확할 수 있음 — 실제로는 `document.querySelectorAll('svg polyline').getAttribute('points')`처럼 DOM에서 좌표를 직접 뽑아 계산하는 게 눈대중보다 훨씬 신뢰도 높았다.

**How to apply:**
- 배포/코드수정 후 "완료" 보고 전 반드시: (1) API 응답을 fetch로 직접 확인 (2) 필요하면 screenshot (3) 애매하면 DOM에서 실제 렌더링된 값(좌표·텍스트)을 javascript_tool로 추출해 기대값과 비교.
- 사용자가 스크린샷을 보내면 그건 "새로운 문제 제보"로 받아들이되, 내가 먼저 검증했다면 애초에 안 보내도 됐을 상황을 최소화한다.
- 특히 시각적 위치·비율·타이밍처럼 스크린샷만으로 판단하기 애매한 것은 반드시 수치로 검증한다.
