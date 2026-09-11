---
name: feedback_deploy_discipline_during_incident
description: "실서비스 핫픽스 중 배포규율 3가지 — 재시작 타이밍 데이터유실 위험, 배포경로 확인 필수, 새 파일도 같이 배포"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bef0f865-73ea-4703-b022-c6f64924acb0
---

2026-07-04 KIS 장애 핫픽스 세션에서 겪은 3가지 사고. 다음에 프로덕션(stockbrain1.duckdns.org) 핫픽스할 때 반드시 지킬 것.

**1. 서비스를 반복 재시작하면서 사용자가 동시에 그 페이지를 쓰고 있으면 데이터 유실 가능.**
관심종목 저장 API가 "브라우저가 기억하는 전체 목록"을 통째로 덮어쓰는 구조라서, 재시작 3초 순간에 사용자가
종목을 추가하면 브라우저의 로컬상태가 비어있는 채로 저장돼 기존 8개 목록이 통째로 날아갔음(두 번 발생).
**Why:** 클라이언트 풀오버라이트 패턴은 서버 가용성 순간공백에 취약함.
**How to apply:** 핫픽스 중 짧은 간격으로 여러 번 재시작해야 한다면, 사용자에게 "지금 페이지 조작하지 말아달라"고
먼저 알리거나, 재시작 텀을 넉넉히 둘 것. 근본 대응으로 `.bak` 백업을 저장 API에 추가해뒀지만(1세대만 보존),
예방이 먼저다.

**2. scp로 배포하기 전에 systemd 유닛의 실제 `WorkingDirectory`/`ExecStart`를 확인할 것 — 저장소 경로를 추측하지 말 것.**
서버에 저장소가 2개(`/home/ubuntu/kmong/crawling_bot`=별개 크롤봇, `/home/ubuntu/lotto-stock-wiki`=이 대시보드)
있는 걸 모르고 처음에 엉뚱한 쪽에 배포 → 몇 번 재시작해도 옛 코드가 계속 돌아서 한참 헤맴.
**How to apply:** `cat /etc/systemd/system/<service>.service`로 `WorkingDirectory` 먼저 확인 후 그 경로로 배포.

**3. 수정한 파일만 배포하면 안 됨 — 그 파일이 새로 import하는 파일도 같이 배포해야 함.**
`dashboard/server.py`를 배포했는데 서비스가 `ImportError: cannot import name 'key_vault'`로 크래시루프 —
로컬 저장소엔 (다른 동시세션이 만든) `pipeline/atoms/key_vault.py`가 있었지만 서버엔 없었음. `git status`/
`git diff`로 로컬에 어떤 새 파일이 추가돼 있는지 먼저 확인하고, 의존관계 있는 새 파일까지 함께 배포할 것.

관련: [[project_kis_outage_2026_07_04]], [[feedback_shared_worktree_branch_check]](비슷한 동시세션 사고 패턴)
