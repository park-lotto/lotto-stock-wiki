---
name: reference_deploy_truth_branch_ssh
description: "대시보드 서버 배포 진실 — 서버는 main 브랜치 추적, SSH키 위치, git pull 배포법. feat에 push하면 서버 안 감(왜 안고쳐지나 원인)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: c68e1198-2af7-44fa-875d-a5d4962ee779
---

라이브 대시보드(stockbrain1.duckdns.org)는 **git으로 배포**한다. 핫패치 금지(안 남음).

- **서버**: `ubuntu@3.39.179.148`, repo `/home/ubuntu/lotto-stock-wiki`, systemd `stockbrain.service`(:8090)
- **SSH키**: `C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem` (user=`ubuntu`, bitnami 아님)
- **서버가 추적하는 브랜치 = `main`(=origin/main)**. ⚠️ `feat/briefing-engine`은 origin/main보다 113앞/37뒤인 거대 별도 피처브랜치 — **여기 push하면 서버에 영영 안 감**. 2026-07-06 "왜 안고쳐지나" 사건의 원인이 이것(fix를 feat에 커밋→서버는 main).
- **배포법**: origin/main에 push → 서버에서 `git pull --ff-only origin main && sudo systemctl restart stockbrain` → `curl -s localhost:8090/healthz` = `{"ok":true}`. feat 워킹트리 안 건드리려면 임시 worktree(`git worktree add --detach <scratch> origin/main`)로 main에 얹어 push.
- **CRLF 오염 근본차단(2026-07-06)**: `.gitattributes`(`* text=auto` + 코드 `eol=lf`) 추가 + 서버 `core.autocrlf=input`/로컬 `false`. 이전엔 파일이 CRLF로 뒤집히면 `@@ -1,N +1,N @@` 전체가 diff로 잡혀 "서버에 안 한 코드수정이 쌓인 것처럼" 보였음(실제 변경 0줄, `git diff --ignore-all-space`로 판별).
- **남은 숙제**: `raw/**/*.json`·`pipeline/taerini_stock.json`·`stock_sector_map.json`·`health_history.json` 등 데이터가 아직 git추적 → 워킹트리 늘 dirty(pull은 안 막음). atoms.db·output json·pyc는 이미 8563c7dd로 추적해제됨. raw/ 추적해제는 사용자 아카이브 정책 결정 필요.
- **같은 서버·같은 repo에 서비스 2개**: `shopping_shorts/`는 별도 systemd `shopping-shorts`(:8849, shoppingshorts.duckdns.org). 같은 `auto_deploy.sh` 크론이 변경 경로 prefix로 어느 서비스를 재시작할지 결정(`dashboard/|scripts/`→stockbrain, `shopping_shorts/`→shopping-shorts).
- **2026-07-14 실사고 — 서버 워킹트리 staged 오염으로 배포 전면정지**: 서버(`/home/ubuntu/lotto-stock-wiki`)에 `shopping_shorts/app.py`·`collection.html`·`seed_baseline.py` 등 여러 파일이 **커밋 안 된 staged 상태**로 남아있어서 `auto_deploy.sh`의 `git pull --ff-only`가 매번 실패(`/tmp/auto_deploy.log`: "pull실패(작업트리충돌?) 스킵"). 로컬에서 정상적으로 커밋+push해도 서버가 조용히 못 받아감 — 로그를 직접 안 보면 "배포됐겠지" 착각하기 쉬움. 원인(누가/무엇이 서버에서 git add 했는지)은 미확인, 사용자가 "나중에 확인"으로 보류. **서버는 pull 전용, SSH로 git add/commit 절대 금지**를 CLAUDE.md §9로 명문화. 발견해도 임의로 stash/reset 하지 말고 사용자 확인 먼저.

관련: [[project_dashboard_deploy]] [[feedback_deploy_discipline_during_incident]] [[project_kis_token_sharing]]
