# API관측판 — 작업 로그

## 2026-09-01
- API 관측판(/apiwatch) 신설 — api_health.py(이벤트·스냅샷·판정·예산) + MeteredClient
  성공·실패 배선(34개 호출부 자동) + 무음폴백·잠금·되살림·하트비트 이벤트 + 5분 크론 무인경보.
- 관측 사각 수리 4건: /api/refs/api_usage exhausted 항상 0(TypeError) ·
  product_facts 미계측 · serpapi 소진 미분류 · tts 무음폴백 무기록.
- 실측: 08-31 제미니 429 워커 2,524건 / SHORTS 풀 사장님 1+회원 58 / 두 env 파일에 풀이 갈려 삶.
