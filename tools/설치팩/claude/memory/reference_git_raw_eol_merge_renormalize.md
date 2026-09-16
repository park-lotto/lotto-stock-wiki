---
name: reference_git_raw_eol_merge_renormalize
description: 트랙 finish가 raw/*.md 수백건 병합충돌로 막히면 = CRLF/LF eol-only 충돌. git config merge.renormalize true로 해소
metadata: 
  node_type: memory
  type: reference
  originSessionId: d11e8d74-e12a-41a9-908f-cfb8eabd7de6
---

트랙 `finish`가 `raw/telegram·report/*.md` 수백~수천건에서 병합 충돌을 내고 재시도(1/3~3/3)를
다 소진하며 실패하면, 십중팔구 **내용 충돌이 아니라 CRLF vs LF eol-only 충돌**이다.

**진단**: `git diff --ignore-all-space --name-only HEAD origin/main -- raw/ | wc -l` 이 **0**이면
전부 eol-only(내용 동일, 줄끝만 다름). `git rev-parse HEAD:raw` ≠ `git rev-parse origin/main:raw`인데
`--ignore-all-space`는 0 → tree OID가 eol 때문에만 다르다.

**근원**: 크롤봇이 서버(Linux)에서 raw를 커밋하는데 origin/main의 raw blob이 **CRLF**로 저장돼 있다.
로컬 `.gitattributes`의 `raw/ eol=lf`가 내 git을 LF로 강제 → 내 raw tree는 LF(예 6dc6d7c), origin은
CRLF(예 9138fd2)라 **영영 안 맞는다**. `git checkout origin/main -- raw/`, `git add`, `git restore --staged`
전부 clean 필터로 **LF 재정규화**돼서 origin의 CRLF OID를 로컬 커밋에 담을 수 없다(실측 2026-07-18, 4회 시도 실패).
git의 line 기반 3-way 병합은 CRLF≠LF라 매 줄이 달라 충돌 → main에 새 raw가 올 때마다 재발.

**해결**: `git config merge.renormalize true` (공용 `.git/config`에 쓰면 `git worktree` stage들도 상속 →
finish의 임시 stage 병합·재시도까지 커버). 병합 시 양쪽을 정규화 후 비교 → eol-only 충돌 자동해소.
설정 직후 최신 origin/main 병합이 충돌 0으로 통과함(실측). **shopping_shorts를 건드리며 raw churn 중에
finish하는 모든 트랙에 사실상 필수.** 로컬 config라 tracked 파일·`.gitattributes` 안 건드림, 되돌리기 쉬움.

관련: [[reference_deploy_truth_branch_ssh]] (CRLF는 .gitattributes로 봉인됐다지만 raw는 여전히 발산),
[[feedback_shared_worktree_branch_check]]. 사고 맥락: 대본믹스통합 D안 병합(2026-07-18).
