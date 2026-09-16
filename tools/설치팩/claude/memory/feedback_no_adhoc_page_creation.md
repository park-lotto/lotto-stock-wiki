---
name: feedback_no_adhoc_page_creation
description: 종목 페이지 없는 크롤링 자료는 즉석 생성 말고 _pending에 모아둔다
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca2599eb-ffdc-49ee-bb3f-1a1dffb96b8c
---

오늘 크롤링에 LS전선 리포트가 들어왔는데 위키에 LS전선 페이지가 없자, Claude가 즉석에서 페이지를 생성하려 함. 사용자가 "종목에 없는건 다른 곳에 모아두는 규칙 적용했어?"라며 제지.

**Why:** 매핑 안 되는(=위키 페이지 없는) 자료를 바로 페이지로 만들면 일관성·품질이 깨진다. 규칙은 _pending에 모아두고 페이지 신규 생성은 별도 절차(사용자 확인 또는 원자 누적)를 거치는 것. spec 수신워커도 "매핑 안 되면 _pending/unmapped 적재".

**How to apply:** 크롤링/원자가 가리키는 종목 페이지가 위키에 없으면 → **즉석 페이지 생성 금지**. `wiki/_pending/수동확인필요/{날짜}_페이지생성필요.md` (또는 `_pending/unmapped/`)에 모아둔다. 페이지 신규 생성은 사용자 확인 후. [[feedback_keep_going_autonomous]]의 자율 진행도 이 규칙은 못 건너뛴다 — 새 자산(페이지) 생성은 항상 규칙·확인 우선.
