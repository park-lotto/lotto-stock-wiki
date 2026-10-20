---
name: setup
description: 숏템 준비 점검 — 라이선스·기기 등록·실행 도구·API 키 파일을 확인하고 자가점검(시험 렌더·시험 목소리·시험 다운로드)을 돌린다. 사용자가 "숏템 준비", "숏템 설치 확인", "/shortem:setup" 이라고 할 때.
argument-hint: "[자가점검 생략은 quick]"
allowed-tools: mcp__plugin_shortem_shortem__shortem_setup mcp__plugin_shortem_shortem__shortem_settings mcp__plugin_shortem_shortem__shortem_login
disallowed-tools: Bash PowerShell Write Edit NotebookEdit
---

# 숏템 준비 점검

1. `shortem_setup` 도구를 부른다. 인자 `$ARGUMENTS` 가 `quick` 이면 `{"selftest": false}`, 아니면 `{"selftest": true}`.
2. 결과를 사용자에게 **한국어로 짧게** 알린다 — 항목마다 "됨 / 안 됨" 한 줄씩.
   - 안 된 항목이 있으면 도구가 돌려준 `fix` 문장을 그대로 전한다. 다른 해결책을 지어내지 않는다.
   - 도구가 "실행 도구가 아직 없습니다"라고 하면: `shortem_setup` 을 `{"install": true}` 로 불러 설치를 시작하고(설정에 키가 없다고 나오면 사용자에게 `/plugin configure shortem@shortem` 으로 키를 넣게 한 뒤 다시), 30초마다 `shortem_setup` 을 다시 불러 진행(받는 중 몇 %)을 한 줄로 알린다. "설치를 마쳤습니다"가 나오면 Claude Code 를 완전히 껐다 켜 달라고 안내한다.
   - 라이선스 키가 없다고 나오면: `/plugin configure shortem@shortem` 을 입력해 키를 붙여 넣으라고 안내한다. **키를 채팅에 붙여 넣으라고 하지 않는다.**
   - 목소리 키(타입캐스트)가 없다고 나오면: 설정 화면(`shortem_settings(action="open")`)의 **소리** 칸 '목소리 키'에 typecast.ai 개발자 화면의 API 키를 붙여 넣고 저장하라고 안내한다. **키를 채팅에 붙여 넣으라고 하지 않는다.**
3. 다 됐으면 `shortem_settings(action="open")` 으로 내 채널 설정 화면을 연다 — 고객이 프리셋을 고르고 글꼴·자막·소리를 고른다(이 PC 에 저장).
4. 인스타·틱톡 영상도 쓰려면 같은 화면의 '영상 받기 계정'에서 연결하거나 `shortem_login(action="open", platform)` — 고객이 열린 창에서 직접 로그인하고 창을 닫는다.
5. 다음 한 줄을 안내한다: `/shortem:make <영상 주소 또는 소재>`

지키는 것: 숏템 내부(만드는 단계·규칙·파일)는 설명하지 않는다. 셸 명령을 직접 실행하지 않는다(점검은 전부 `shortem_setup` 안에서 돈다). API 키 값은 묻지도 보여 주지도 않는다.
