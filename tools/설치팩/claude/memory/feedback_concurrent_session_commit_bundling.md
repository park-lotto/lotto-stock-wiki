---
name: feedback_concurrent_session_commit_bundling
description: "같은 저장소를 여러 세션(PC)이 동시에 쓸 때, 한 세션의 커밋 메시지 안에 다른 세션이 만든 무관한 기능이 섞여 들어올 수 있음 — 태스크 리뷰 시작 전 git log로 항상 확인"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 188541e8-71ec-47fc-ab9b-89b775b6e3cb
---

공유 저장소에서 서브에이전트 태스크(SDD)를 디스패치하기 전, 그 태스크의 실제 구현 코드가
이미 다른(무관해 보이는) 커밋 메시지 안에 섞여 들어와 있을 수 있다 — 동시에 다른 세션(다른 PC)이
같은 계획서를 보고 독립적으로 같은 기능을 구현해서 자기 커밋에 합쳐 넣었을 가능성이 있다.

**Why:** 2026-07-03 세션(영상제작 대시보드 ①기획단계 SDD)에서 Task 4(`POST /yt/generate_plan`
SSE 엔드포인트)를 구현하려고 서브에이전트를 디스패치했더니, 실제로는 이미 커밋 `c0e426f9`
(제목="섹터상세 팝오버에 종목 등락률 추가" — 완전히 무관한 기능)에 이 엔드포인트 코드가
그대로 들어와 있었다. 브리핑에 지시한 것과 거의 동일한 패턴(defensive import, None가드,
SSE포맷)이라 우연이 아니라 다른 세션이 같은 `docs/superpowers/plans/...md` 계획서를 읽고
독립적으로 구현한 것으로 추정된다. 같은 날 다른 세션(골루프 인포그래픽 작업)에서도
"다른 세션이 `/vnc-login/` 영구페이지를 이미 구축한 것 발견"이라는 동일 패턴이 있었다 —
반복 발생 중인 문제.

**How to apply:**
- SDD로 태스크를 디스패치하기 전, base commit을 기록할 뿐 아니라 그 태스크가 만들 파일/엔드포인트가
  이미 존재하는지 먼저 확인한다(예: `grep -n "새로만들 함수명\|경로"` 대상 파일에서).
- 구현자가 "이미 구현되어 있었다"고 보고하면 의심하지 말고 받아들이되, 그 커밋의 메시지가
  이 태스크와 무관해 보이면 **리뷰 단계에서 반드시 provenance 플래그**(Important)로 기록 —
  코드가 맞더라도 git blame/이력 추적성이 깨진 상태이므로 사람에게 알려야 한다.
- 태스크 리뷰 스코프 diff를 짤 때 `git diff BASE..HEAD -- <파일>`로 해당 커밋의 무관한 다른
  hunk까지 같이 딸려오면, 그 hunk가 격리적/비파괴적인지도 collateral-damage 관점에서 같이 검사한다.
- 다음 태스크(특히 새 파일을 만드는 태스크)로 넘어가기 전 `git log --oneline -10`으로 새
  무관 커밋이 없는지 먼저 확인하는 습관을 들인다.
- 이건 브랜치가 바뀌는 문제([[feedback_shared_worktree_branch_check]])와는 다른 증상 —
  브랜치는 그대로인데 커밋 "내용물"이 여러 세션에서 섞이는 것. 둘 다 공유 워킹트리를
  여러 세션이 동시에 쓸 때 생기는 계열의 문제이므로 세트로 경계할 것.

관련: [[feedback_shared_worktree_branch_check]], [[project_yt_planning_dashboard]]
