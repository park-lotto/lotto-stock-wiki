---
name: feedback-server-dashboard-only
description: 사용자는 로컬 대시보드(localhost:8090)를 쓰지 않고 stockbrain1.duckdns.org(원격 Lightsail systemd 서비스)만 씀
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 188541e8-71ec-47fc-ab9b-89b775b6e3cb
---

로컬 대시보드 서버(localhost:8090)는 신경쓰지 않아도 된다 — 사용자가 "로컬은 이제 안써 서버대시보드만 쓰는거야"라고 명시.

**Why**: 2026-07-03 세션에서 로컬 서버가 백그라운드 프로세스로 4번 연속 죽는 문제(nohup을 걸어도 이 환경 특성상 정리되는 걸로 추정, 에러 로그도 안 남음)를 Task Scheduler 등록으로 해결하려 했으나 Windows 권한(UAC) 문제로 막혔음. 사용자가 애초에 로컬을 안 쓴다고 확인하면서 이 이슈는 무의미해짐.

**How to apply**:
- 로컬 대시보드(`dashboard/server.py`, localhost:8090) 상태 체크·재시작 시도 불필요 — 요청받지 않는 한 건드리지 않는다.
- 실제 운영 대시보드는 `stockbrain1.duckdns.org` → Lightsail(3.39.179.148) → systemd 서비스 `stockbrain`. 여기가 유일한 확인 대상.
- 원격 서버 재시작: `ssh -i crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem ubuntu@3.39.179.148` → `cd ~/lotto-stock-wiki && git pull && sudo systemctl restart stockbrain`
- 관련: [[project_dashboard_deploy]], [[project_remote_ingest_automation]] (원격 인제스트 자동화 크론)
