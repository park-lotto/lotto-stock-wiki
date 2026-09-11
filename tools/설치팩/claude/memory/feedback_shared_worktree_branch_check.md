---
name: feedback_shared_worktree_branch_check
description: 공유 워킹트리에서 커밋 전 반드시 git branch --show-current 확인 — 동시 세션이 브랜치를 바꿔놔서 커밋이 엉뚱한 브랜치에 쌓일 수 있음
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 567fdd93-64ca-4ff6-9309-c2360bd5e5b3
---

공유 워킹트리(같은 프로젝트 폴더를 여러 Claude Code 세션이 동시에 쓰는 구조)에서
`git commit`을 반복 실행할 때, 매 커밋 전에 `git branch --show-current`로 현재 브랜치를
확인해야 한다.

**Why:** 2026-07-02 세션에서 subagent-driven-development로 10태스크를 main에 순차
커밋하던 중, 동시에 돌던 다른 세션이 같은 워킹트리에서 `git checkout -b
feat/goal-loop-morning-brief`로 브랜치를 새로 만들어 체크아웃했다. 이후 내 서브에이전트들이
`git add <파일> && git commit`을 실행할 때마다 커밋이 (내가 의도한) main이 아니라 그
브랜치에 쌓였다 — `git log --oneline base..HEAD`로 확인할 때 HEAD가 이미 다른 브랜치를
가리키고 있었는데 이를 눈치채지 못했다. 결과: Task 6~9와 최종 리뷰 수정 커밋 5개가
main에서 사라진 것처럼 보이는 사고 발생. 최종 통합 리뷰(전체 브랜치 diff 확인) 단계에서
`git merge-base --is-ancestor <커밋> main`으로 뒤늦게 발견, `git cherry-pick`으로 5개
커밋을 main에 복구해서 해결했다(다행히 파일 겹침 없이 깔끔하게 복구됨).

**How to apply:**
- 서브에이전트를 반복 디스패치하며 각 태스크 커밋을 만들 때, 컨트롤러(나)가 다음 태스크로
  넘어가기 전 매번 `git log --oneline -1` 뿐 아니라 `git branch --show-current`도 함께
  확인해서 여전히 의도한 브랜치(보통 main)에 있는지 검증한다.
- 만약 브랜치가 바뀌어 있는 걸 발견하면: 밀린 커밋들의 해시를 `git log`로 모으고,
  올바른 브랜치로 `git checkout` 후 `git cherry-pick <해시들>` 순서대로 적용, 전체 테스트
  재실행으로 검증한다. 원래 브랜치(다른 세션 것)는 그대로 두고 삭제하지 않는다 — 그 세션의
  작업일 수 있으므로.
- 이 문제는 CLAUDE.md에도 "동시 세션 자동커밋 주의" 메모가 있지만, 브랜치 전환까지는
  다루지 않았음 — 커밋 스윕(다른 세션 파일이 내 커밋에 끼는 것)뿐 아니라 브랜치 자체가
  바뀌는 것도 감시 대상.

**원격서버 배포 시 안전 패턴(2026-07-03 반복 검증):** stockbrain1.duckdns.org 배포 전
`git pull`이 다른 세션의 동시 커밋과 매번 충돌한다. 항상 `git stash push -u -m "..."`
(**-u 필수** — untracked 파일도 포함, 안 하면 "untracked files would be overwritten"로
pull 자체가 중단됨) → `git pull --no-rebase` → `git stash pop` 순서. 충돌 나면(주로
`atoms.db`/`*.json` 같은 자동갱신 데이터 파일) `git checkout --ours -- <파일>`로 현재
워킹트리(=pull한 최신) 쪽을 유지하고 `git add`+`git reset HEAD`로 정리 — 코드 파일은
이 세션 내내 충돌난 적 없었음(항상 데이터 파일만). pop 후 남아있는 다른 세션 소유
stash(`stash@{1}`, `stash@{2}` 등)는 절대 건드리지 않는다.

관련: [[project_person_brain]], [[project_daily_verify_agent]]
