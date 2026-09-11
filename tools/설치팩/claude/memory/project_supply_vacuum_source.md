---
name: project-supply-vacuum-source
description: 수급빈집 판단 기준 데이터소스 확정 방침
metadata: 
  node_type: memory
  type: project
  originSessionId: c657b7ec-5429-41de-82c3-f64977acb62e
---

수급빈집 판단 기준: 외인기관수급오실레이터(오실레이터.xlsm)로 확정.

**Why:** 유동성.xlsm 통합순위 방식은 검증이 더 필요함. 오실레이터 방식이 현재 신뢰도 기준.

**How to apply:**
- 수급빈집 관련 기능 개발 시 → 오실레이터.xlsm 기준으로 먼저 구현
- 유동성.xlsm 통합순위는 보조 참고 or 나중에 믹스 (검증 완료 후)
- CLAUDE.md의 탑픽 스코어 #0(수급빈집) 계산도 오실레이터 우선 적용
- 두 방식이 충돌하면 오실레이터 우선, 유동성은 참고용으로만

[[project_oscillator_extraction]] 참고 (calc_oscillator.py 완성 2026-05-26)
