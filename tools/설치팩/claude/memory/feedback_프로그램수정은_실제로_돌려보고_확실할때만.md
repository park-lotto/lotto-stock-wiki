---
name: feedback
description: "★사장님 규칙(2026-09-04): 프로그램 수정 요청은 실제 환경에서 끝까지 돌려보고 결과를 눈으로 확인한 뒤에만 '됐다'. 정적검토·테스트·가짜응답 검증은 확인 아님"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 50bfe5b4-1d96-41a5-904f-3ce0cb3dbe70
  modified: 2026-09-04T10:34:56.483Z
---

사장님(2026-09-04): "너가 실제로 돌려보라고. 매우 중요한 규칙인데, 앞으로는 프로그램 수정을 내가 요청하면
실제 확인까지 돌려보고 확실할 때 해준다는 걸 규칙에 명시해." → 프로젝트 CLAUDE.md **0순위-A1**로 박음.

**Why:** 같은 날 세 번 "고쳤다"가 틀렸다.
- 내클론음성 '내 성우로 추가' 버튼: 09-02 구현 뒤 한 번도 안 눌러봄 → onclick 큰따옴표로 무반응인 채 이틀.
- 미리보기 지문(RENDERED_SIG): 배포 뒤 실측하니 여전히 0(DATA 로드 전에 계산 실패).
- 낡음 판정을 fetch 가짜 응답으로만 검증하고 실제 저장·렌더는 안 돌림 → 사장님 "너가 실제로 돌려보라고".

**How to apply:**
- 고친 기능을 라이브 브라우저에서 **실제 job으로 끝까지** 돌린다(진짜 저장·진짜 렌더·결과물 대조). 주입·스텁·문법검사·pytest는 중간 단계.
- 배포가 끼면 배포본에서 다시 확인. 낮엔 시간창(2~6시) 때문에 `[긴급]` 커밋 제목이 필요하다.
- 못 돌려보면(키 없음·SSH 막힘) 보고 첫 줄에 "어디까지 확인됐는지"를 갈라 적는다.
- 관련: [[feedback_verify_before_claim_and_act]] [[feedback_self_verify_before_reporting]] [[feedback_no_unverified_flag_in_live]]
