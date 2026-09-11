---
name: reference_track_finish_no_overlap
description: "track.py finish는 겹쳐 돌리면 공용 _merge 스테이지서 레이스, prune는 폴더를 안 지운다"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7ca931b0-f8e7-4854-b022-24ceea4e5428
  modified: 2026-07-24T08:37:07.624Z
---

`py tools/track.py finish <트랙>`은 `.tracks/_merge-<트랙>` worktree를 스테이지로 쓴다(트랙마다 고정 이름).

**2026-07-24 업데이트: finish에 전역 순번 락 추가(`_finish_gate_lock`, tools/track.py).** 세션 여럿이
동시에 finish하면 각자 전체 pytest 게이트를 병렬로 돌려 CPU 포화로 전부 기어간다(실측 5개 동시→20분+).
이제 OS 파일락으로 **한 번에 하나의 게이트만** 돈다(뒤는 `[대기] 순번 대기`→앞이 끝나면 자동 이어받음,
프로세스 죽으면 커널이 락 자동해제=스테일락 없음). **세션끼리 수동으로 "끝났으니 시작" 신호 줄 필요 없음.**
⚠️ 락을 급히 살리려 **main 폴더 tools/track.py를 cp로 덮지 마라** — 워킹트리 오염(`M tools/track.py`)으로
다음 병합이 "Please commit/stash before merge"로 깨진다(2026-07-24 실사고). 락은 정상 finish로 main에
들어가고 `_sync_main_folder`가 main 폴더를 자동 갱신한다.

- **finish를 겹쳐 돌리지 마라.** 같은 트랙의 finish 두 개가 같은 `_merge-<트랙>`를 동시에 열어
  서로 밟으면 "MERGE_HEAD exists"/병합충돌처럼 보이는 **가짜 실패**가 난다(진짜 충돌 아님).
  첫 finish 완료 알림을 기다린 뒤 다음을 돌린다(2026-07-21 실사고: 안 기다리고 2번째 돌려 3사이클 날림).
- **`git worktree prune`은 admin 항목만 지우고 디스크 폴더는 남긴다** → 다음 finish의 `worktree add`가
  `'_merge-<트랙>' already exists`로 막힌다. 해결: `rm -rf ".tracks/_merge-<트랙>"` 후 `git worktree prune` 재실행.
- **게이트 실패 vs 레이스 구분**: 출력에 `게이트 실패 ? 병합을 버렸다` + 구체 테스트명이 있으면 진짜
  실패(코드/테스트 고쳐라). `MERGE_HEAD exists`/`already exists`면 스테이지 오염(위 정리 후 재시도).
- **라이브 안전 확인은 origin/main으로**: `git merge-base --is-ancestor <내커밋> origin/main`. finish가
  push 못 했으면 main 불변 = 라이브 무사. finish의 exit 0도 "nothing/raced"일 수 있으니 커밋 조상여부로 확정.

이름 규칙 등 **의도한 동작 변경**은 옛 규칙을 검증하던 기존 테스트를 깬다 — 게이트가 그걸 신규실패로
잡으면 그 테스트를 새 동작에 맞춰 갱신하는 게 정답(게임하는 것 아님). 관련: [[reference_git_stash_shared_across_worktrees]] · [[feedback_auto_commit_staged_conflict_broke_live]]
