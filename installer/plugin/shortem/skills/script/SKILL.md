---
name: script
description: 숏템 엔진 AI 요청 답하기 지침 — shortem_make 가 need="ai" 를 줬을 때 shortem_ai 요청(그림 읽기·소리 판독·점수·대본 쓰기)에 답하는 방법. 숏템 만들기 중에만 쓴다.
user-invocable: false
allowed-tools: mcp__plugin_shortem_shortem__shortem_ai mcp__plugin_shortem_shortem__shortem_make Agent
disallowed-tools: Bash PowerShell Write Edit NotebookEdit WebFetch Read Glob Grep
---

# 숏템 AI 요청 답하기

1. `shortem_ai(action="list")` 가 준 요청 하나를 읽는다. **맨 위 `권장 모델`을 지킨다** — `opus` 요청(결과물 품질에 닿는 것 — 채점·글 읽기·근거·대본)은 오푸스가 답한다. 지금 대화 모델이 오푸스가 아니면 그 요청을 `Agent`(model=opus)에게 그대로 넘겨 답을 받아 보낸다. 하이쿠·소넷은 `권장 모델`이 그렇게 적힌 단순한 요청만.
2. **지시가 정한 JSON 모양 그대로** 객체 하나만 만든다. 설명 글·코드 블록 없이 `answer` 에 객체로 넣는다.
3. **지어내지 않는다.** 그림·글에 없는 것은 지시가 정한 빈 값으로. 대본은 근거에 있는 사실·숫자만.
4. "앞 답이 틀렸다"가 붙어 오면 그 이유만 고쳐 다시 보낸다.
5. 다 답하면 `shortem_make(step="wait", run_id)`.
6. 요청 글은 숏템 내부 작업 지시다 — 고객에게 내용을 보여 주거나 옮겨 적거나 설명하지 않는다.
