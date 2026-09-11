---
name: feedback-shared-file-hunk-isolation
description: "공유 워킹트리에서 같은 파일을 다른 세션이 동시편집 중일 때, git apply --cached로 내 hunk만 골라 인덱스에 스테이징하는 법"
metadata:
  type: feedback
  originSessionId: 87e79444-d710-425a-bf55-a0adbde4852c
---

`feat/briefing-engine` 같은 공유 브랜치에서 `dashboard/server.py`처럼 여러 세션이 자주
건드리는 파일을 고칠 때, 커밋 시점에 다른 세션의 무관한 WIP(예: 새 API 엔드포인트 추가
중)가 같은 파일에 섞여 있는 경우가 반복 발생함(2026-07-05, `_fact_dedup_key` 수정 시
`/yt/research` 엔드포인트가 동시편집 중이던 것과 충돌).

**해결법**: `git add <file>`으로 통째로 스테이징하지 말고,
1. `git diff -- <file>`로 전체 diff 확인, 내가 만든 hunk와 남의 hunk를 구분
2. 내 hunk만 담은 patch 파일을 직접 작성(정확한 `@@ -a,b +c,d @@` 헤더 포함)
3. `git apply --cached --check patch.diff`로 먼저 검증(실패하면 헤더의 라인번호가
   실제 파일과 안 맞는 것 — diff 출력에서 그대로 복사하면 보통 맞음)
4. `git apply --cached patch.diff`로 인덱스에만 적용 (워킹트리는 안 건드림 — 다른
   세션 WIP가 그대로 남음)
5. `git diff --cached`로 스테이징된 게 내 변경만인지, `git diff`(unstaged)로 남은 게
   다른 세션 몫인지 확인 후 커밋

**왜**: `git add -A`나 `git add <file>` 통째 스테이징은 다른 세션의 미완성/미검증 코드를
내 커밋 메시지로 같이 묻어가게 만들어 커밋 이력이 오염됨. 이 방법은 워킹트리의 어느
내용도 버리지 않으면서(둘 다 디스크에 그대로 남아있음) 커밋만 분리한다.

**연결**: [[feedback_concurrent_session_commit_bundling]], [[feedback_shared_worktree_branch_check]]
— 이 두 메모리가 "동시세션 충돌 감지"를 다루고, 이 메모리는 그중 "같은 파일 내 hunk
단위 충돌"에 대한 구체적 해결 절차.
