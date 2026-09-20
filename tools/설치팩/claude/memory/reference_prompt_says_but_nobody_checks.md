---
name: reference_prompt_says_but_nobody_checks
description: "프롬프트가 \"그대로 써라\"라고 두 번 말해도 지켰는지 검사하는 곳이 없으면 안 지켜진다 — 출구 불변식으로 막아라(2026-08-18)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: c46bf31a-3df5-4ecf-be48-8b015e97a2e9
  modified: 2026-08-18T14:08:50.480Z
---

**사례**: 3단계 EDL이 확정 대본에 **없는 문장**을 지어냈다(실측 job `c7e208afb699` — 7비트 중
훅·중간 2개가 장면 설명 말투로 창작, 대본의 미끼·반전 후반부는 화면에서 통째로 누락).
`edit_plan._SCRIPTED_PROMPT`는 "이 문장들을 그대로 사용해라 / 표현·어미 바꾸지 마라"를
**두 번** 명시하고 있었다. 지켜졌는지 **검사하는 코드가 한 줄도 없었다.**

**처방**: 프롬프트를 더 세게 쓰는 건 두더지잡기다(사장님 "안 생기게 해야지").
**저장 출구**에 불변식을 건다 — `store._ensure_screen_time` 안에서
`edit_plan.enforce_scripted_narration(beats, given_script)`:
- 비트 narration의 정규화 문자열이 대본 정규화 문자열에 없으면 = 창작
- **아직 안 쓰인 대본 문장**으로 순서대로 되돌린다(`narration_restored`)
- 되돌릴 재료가 없으면 표시만 남기고 지우지 않는다(`narration_invented`) — 지우면 화면 길이가 무너진다

**출구 게이트 패턴**(이 프로젝트에서 반복 채택): 계획을 만드는 경로는 여럿이고 앞으로 더 생기지만
저장은 `store.update_mix_job` 하나를 지난다. 만드는 쪽마다 채우면 반드시 한 곳이 빠지고,
채운 뒤 도는 후처리(재픽)가 되돌리면 그것도 못 잡는다. 같은 자리에 이미 화면길이 보정·
출처장면(src_seg) 적용이 산다. **fail-open** — 보장 실패가 저장을 막으면 안 된다.

**일반화**: LLM에게 시킨 제약은 전부 이 질문을 붙여라 — "지켰는지 누가 보나?"
안 보면 안 지켜진다. 검사는 프롬프트 옆이 아니라 **데이터가 나가는 단일 출구**에 둔다.

관련: [[feedback_verify_with_real_data]] · [[reference_silent_fallback_pipeline_undo]] · [[project_생성순응검열]]
