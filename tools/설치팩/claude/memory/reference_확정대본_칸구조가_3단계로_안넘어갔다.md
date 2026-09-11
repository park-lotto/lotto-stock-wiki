---
name: reference-3
description: 2단계 B안 칸(첫말/문제…)이 공백 통짜로 3단계에 가서 훅에 두 줄이 뭉쳤다 — 줄=칸 단위로 고침(2026-09-03)
metadata: 
  node_type: memory
  type: reference
  originSessionId: 43d02dbc-95c7-4a7a-a409-6cae3d833815
  modified: 2026-09-03T10:40:22.599Z
---

**실사고(2026-09-03, job 8b86200f50b3)**: 사장님 "대본이 후킹이랑 문제가 믹스에서 합쳐진다".
B안 8줄인데 `given_script`는 개행 0인 통짜(`script_gate.py` full=" ".join). EDL이 마침표로
9칸 재분리 → 훅 한 칸에 첫말+문제(5.5초). `enforce_script_order`는 글자만 대조해 "제자리"로 통과.

**처방(뿌리=단위)**: 확정 시 칸을 `\n`으로 넘김(`s2ScriptLines`) → `script_sentences`는 개행 2줄+면
줄이 단위 → 프롬프트 "줄 하나=비트 하나 N개" → 저장출구는 칸 수≠줄 수면 `_rebuild_beats_by_lines`.

**How to apply**: "칸이 합쳐진다/갈린다" 제보엔 서버 DB `mix_jobs.given_script`에 개행이 있는지부터.
글자 대조만 하는 검사는 칸 수 어긋남을 못 잡는다 — 판정축에 **개수**를 넣어라.
관련: [[reference_구어체대본_문장분리_2덩이]] [[reference_판정축_하나면_교정이_통째로죽는다]]
