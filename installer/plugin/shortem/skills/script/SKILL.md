---
name: script
description: 숏템 대본 쓰기 지침 — shortem_make 가 대본 자리(need_input, 대본)에서 칸 수·칸 역할·길이 등급을 줬을 때 그 틀에 맞춰 대본을 쓰는 방법. 대본을 쓸 때만 쓴다.
user-invocable: false
allowed-tools: mcp__plugin_shortem_shortem__shortem_make
disallowed-tools: Bash PowerShell Write Edit NotebookEdit WebFetch
---

# 숏템 대본 쓰기

1. **틀을 그대로 지킨다.** 응답이 준 칸 수만큼, 칸 역할 이름(예: 상황 / 반전 / 감동 / 반응 / 덤) 순서대로 한 칸에 한 줄씩 쓴다. 칸을 더하거나 빼지 않는다.
2. **길이 등급을 따른다.** "짧게"면 한 호흡에 읽히는 짧은 줄, "보통"이면 조금 더 풀어 쓴다.
3. **말투는 프로필을 따른다.** 응답이 존댓말/반말을 정해 주면 끝까지 같은 말투로 쓴다.
4. **사실만 쓴다.** 소재(영상·기사)에 없는 사실·숫자·인용을 지어내지 않는다. 숫자를 쓰려면 소재에 그 숫자가 있어야 한다.
5. **베끼지 않는다.** 소재 문장을 통째로 옮기지 말고 내 말로 다시 쓴다.
6. **반려되면 방향대로만 고친다.** `hints` 가 "3번 줄 더 짧게"라고 하면 3번 줄만 짧게 고친다. 다른 칸은 건드리지 않는다.
7. 다 쓰면 사용자에게 보여 주고 확인받은 뒤 `shortem_make` 의 `payload` 로 보낸다.
