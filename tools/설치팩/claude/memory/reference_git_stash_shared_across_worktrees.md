---
name: reference_git_stash_shared_across_worktrees
description: "트랙 폴더(.tracks/*)는 git worktree라 refs/stash 스택을 전 세션이 공유 — git stash 쓰면 남의 stash를 뽑는다"
metadata:
  node_type: memory
  type: reference
  originSessionId: 251dca76-2bba-4629-a85d-5ea19f58901d
---

`로또의 주식`의 트랙 폴더 `.tracks/<트랙명>`은 각각 **git worktree**다. worktree들은 하나의
`.git/refs/stash` 스택을 **공유**한다 — 그래서 한 세션에서 `git stash`/`git stash pop`을 쓰면
**다른 세션이 방금 stash 해둔 것을 물리적으로 뽑아버린다**(자기 변경이 아닌데 워킹트리에 얹힘).

**실사고 2026-07-18**: 자막싱크 Task 4 구현자가 회귀 pre/post 비교하려고 `git stash`/`pop` 했다가
타세션(모션효과 `mix_pipeline`/`video_assemble`/`test_beat_timeline`, 장면라이브러리 `app.py`/`produce.html`)
stash를 잡음. 같은 날 장면라이브러리 세션도 독립적으로 같은 충돌을 겪음. 둘 다 dangling commit에서
복구했지만 워킹트리 작업 유실 위험이 컸다.

**How to apply:**
- 트랙 worktree 안에서 **`git stash`를 쓰지 마라.** 회귀 pre/post 비교가 필요하면 별도 임시
  worktree(`git worktree add`)나 별도 클론에서 하거나, 변경을 커밋해두고 비교해라.
- 서브에이전트 구현 브리프에 **"git stash 금지 — 회귀비교는 커밋 후 diff 또는 별도 워크트리"**를 박아라.
- 이미 충돌했으면 남의 stash는 **함부로 drop 하지 말고** 명확한 라벨로 다시 stash 해 `stash@{0}`에
  남겨 원주인이 되찾게 하고, 각 세션에 알려라(누구 것인지 확정 못 하면 판단은 사용자 몫).
- 관련: [[feedback_shared_worktree_branch_check]] · [[feedback_concurrent_session_commit_bundling]] · [[feedback_shared_file_hunk_isolation]]
