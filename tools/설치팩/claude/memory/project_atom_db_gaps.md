---
name: project-atom-db-gaps
description: 원자 DB 구조의 구멍 목록과 해결 우선순위 — 순서대로 하나씩 해결 중
metadata: 
  node_type: memory
  type: project
  originSessionId: 47e5854a-1d93-4781-b320-45a710a68289
---

6개 구멍 확인, 순서대로 해결 중.

**Why:** 원자 DB 분석 시 최신 데이터 없어 틀린 분석 나옴. 자동화 없이 수동 운영 한계.

**해결 순서:**
1. ✅→진행 구멍1: 자동 ingest 파이프라인 — 크롤링봇 수신 후 자동 sync→ingest
2. 구멍2: Claude 분석 시 원자 DB 자동 참조 — 질문 들어오면 query_similar() 자동 실행
3. 구멍3: WebSearch + 원자 DB 결합 파이프라인 — 두 소스 자동 병합 분석
4. 구멍4: 수급 오실레이터 → 원자 DB 연결 — calc_oscillator.py 결과 자동 ingest
5. 구멍5: 원자 품질 개선 — 노이즈 제거, 신뢰도 필터 실제 활용
6. 구멍6: 위키 자동 반영 (Plan 3) — 원자 DB → wiki/ 섹터 파일 자동 업데이트

**How to apply:** 새 세션에서도 이 순서 기억하고 이어서 해결.
