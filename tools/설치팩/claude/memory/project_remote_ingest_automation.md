---
name: project-remote-ingest-automation
description: 원격 Lightsail 서버(stockbrain1.duckdns.org)에 매일 인사이트 인제스트 자동화 크론 신설 완료 (2026-07-03)
metadata: 
  node_type: memory
  type: project
  originSessionId: 188541e8-71ec-47fc-ab9b-89b775b6e3cb
---

원격 서버(3.39.179.148, `/home/ubuntu/lotto-stock-wiki`)는 dashboard(systemd `stockbrain`)와 크롤봇(`kmong/crawling_bot`)이 같이 도는데, 배포 이후 telegram/report/blog/news/youtube를 atoms.db로 채우는 자동화가 **아예 없었다** — "오늘의 시그널"이 항상 "집계 없음"이었던 이유. 2026-07-03에 발견·해결.

**Why**: 크롤은 원격에서 계속 됐지만(`kmong/crawling_bot/output/md/{date}/{category}/`), 그걸 dashboard가 읽는 `raw/{category}/`로 옮기고 atoms.db에 넣는 파이프라인이 크론에 없었음. 로컬 PC의 `atom_pipeline.py`/`sync_crawling.py`는 윈도우 경로(`crawling_bot_data`) 전제라 원격에서 못 씀.

**How to apply**:
- 신규 스크립트 `scripts/remote_daily_ingest.py` — 원격 전용, 크롤봇 출력을 직접 raw/로 복사 후 텔레그램→리포트→블로그→유튜브→뉴스 **순차** 실행(동시 실행하면 SQLite 쓰기가 조용히 유실되는 사고 있었음, 원인 미상이나 재현됨).
- crontab에 `35 8,12,15,18,21 * * *`로 등록 (로컬 인제스트 :10과 25분 간격 — 같은 Gemini 키 풀 공유라 겹치면 429 몰림).
- 로컬↔원격 Gemini 키 6개(`GEMINI_API_KEY`/`_2`, `GEMINI_INGEST_KEY`~`_4`) 완전 동일 — 분리 안 하면 한쪽이 몰아쓰면 다른 쪽도 막힘. 아직 미분리, 다음 개선 후보.
- `pipeline/atoms/atoms.db`가 git 추적 대상이라 로컬/원격 둘 다 독립적으로 원자를 넣으면 다음 `git pull` 때 충돌·덮어쓰기 위험 — atoms.db는 `.gitignore` 처리하는 게 근본 해결책(아직 안 함).
- 관련: [[feedback_server_dashboard_only]]
