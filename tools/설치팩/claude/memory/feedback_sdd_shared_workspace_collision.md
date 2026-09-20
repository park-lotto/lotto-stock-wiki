---
name: feedback_sdd_shared_workspace_collision
description: subagent-driven-development 스킬의 .superpowers/sdd/ 작업공간이 태스크번호만으로 파일명을 지어서 동시실행중인 다른 플랜과 충돌함 — 고유 접두사로 우회
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1578286d-3f02-415e-9424-f884ac90a76a
---

superpowers:subagent-driven-development 스킬의 `task-brief`/리뷰 산출물은 기본적으로
`.superpowers/sdd/task-N-brief.md`, `task-N-report.md`처럼 **태스크 번호만으로** 파일명을 짓는다.
이 저장소는 여러 PC/세션이 동시에 작업하는 게 일상이라(레포 전체 관례), 다른 세션이 같은
순간에 자기 플랜의 "Task 1"을 실행 중이면 파일이 서로 덮어써진다 — 2026-07-05 실발생: 인용스튜디오
플랜의 task-1-brief.md가 자동점검파이프라인 플랜의 것과 충돌(리뷰어가 엉뚱한 브리핑을 받아
스스로 원본 계획서에서 재발견해야 했음).

**Why**: `task-brief` 스크립트는 3번째 인자로 커스텀 OUTFILE 경로를 받을 수 있음(`scripts/sdd-workspace`
가 디렉터리만 보장, 파일명 충돌 방지는 호출자 책임).

**How to apply**: subagent-driven-development로 여러 태스크를 돌릴 때, `task-brief PLAN N`을
그냥 쓰지 말고 `task-brief PLAN N ".superpowers/sdd/<플랜고유접두사>-task-N-brief.md"`처럼
플랜마다 고유한 접두사(예: 기능명 축약)를 명시적으로 지정할 것. 리포트 파일 경로도 디스패치
프롬프트에 같은 접두사로 직접 지정. review-package는 BASE/HEAD 해시로 자동 유니크하므로 이
문제 없음 — task-brief와 구현자가 쓰는 report 경로만 주의.

관련: [[project_daily_ingest_autopilot]](이 문제가 실발생한 프로젝트) [[feedback_concurrent_session_commit_bundling]](같은 근본원인의 다른 증상 — 동시세션 자체는 못 막지만 산출물 충돌은 이렇게 회피)
