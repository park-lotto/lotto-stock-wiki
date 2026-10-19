---
name: setup
description: 숏템 준비 점검 — 라이선스·기기 등록·실행 도구·API 키 파일을 확인하고 자가점검(시험 렌더·시험 목소리·시험 다운로드)을 돌린다. 사용자가 "숏템 준비", "숏템 설치 확인", "/shortem:setup" 이라고 할 때.
argument-hint: "[자가점검 생략은 quick]"
allowed-tools: mcp__plugin_shortem_shortem__shortem_setup mcp__plugin_shortem_shortem__shortem_presets
disallowed-tools: Bash PowerShell Write Edit NotebookEdit
---

# 숏템 준비 점검

1. `shortem_setup` 도구를 부른다. 인자 `$ARGUMENTS` 가 `quick` 이면 `{"selftest": false}`, 아니면 `{"selftest": true}`.
2. 결과를 사용자에게 **한국어로 짧게** 알린다 — 항목마다 "됨 / 안 됨" 한 줄씩.
   - 안 된 항목이 있으면 도구가 돌려준 `fix` 문장을 그대로 전한다. 다른 해결책을 지어내지 않는다.
   - 도구가 "설치팩을 먼저 설치하세요"라고 하면: 숏템메이커 페이지에서 설치팩을 받아 설치한 뒤 Claude Code 를 완전히 껐다 켜라고만 안내한다.
   - 라이선스 키가 없다고 나오면: `/plugin configure shortem@shortem` 을 입력해 키를 붙여 넣으라고 안내한다. **키를 채팅에 붙여 넣으라고 하지 않는다.**
3. 다 됐으면 `shortem_presets` 로 쓸 수 있는 내 채널 프로필 이름만 보여 주고, 다음 한 줄을 안내한다:
   `/shortem:make <프로필 이름> <유튜브 주소 또는 소재>`

지키는 것: 셸 명령을 직접 실행하지 않는다(점검은 전부 `shortem_setup` 안에서 돈다). API 키 값은 묻지도 보여 주지도 않는다.
