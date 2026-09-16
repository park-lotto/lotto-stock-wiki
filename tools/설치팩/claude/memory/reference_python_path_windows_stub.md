---
name: reference_python_path_windows_stub
description: "이 PC에서 python/python3 명령이 윈도우 스토어 스텁으로 잡히던 문제 — PATH 재정렬로 조치, 재시작 필요"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ffe97202-d509-482a-96cd-93fd19c2b969
---

이 PC(TheRose)에서 bash 세션의 `python`/`python3` 명령이 실제 인터프리터가 아니라 윈도우 App Execution
Alias 스텁(`AppData\Local\Microsoft\WindowsApps\python[3]`)으로 연결돼 있었다. 실행하면 아무 것도 안 하고
"Python"만 찍고 종료(exit 49류). 진짜 인터프리터는 `AppData\Local\Python\bin\python.exe`
(pythoncore-3.14-64 라우팅용 shim)에 있는데, User PATH에서 WindowsApps 항목이 그보다 앞서 있어 매번
스텁이 먼저 매칭됐다.

**영향받은 곳**: 1) 내가 직접 `python -m pipeline...` 실행할 때(전체경로로 우회 필요했음),
2) fablize 플러그인의 `UserPromptSubmit`/`PostToolUse`/`Stop` 훅(`hooks.json`)이 전부 `python3 ...`로
호출해서 매 프롬프트마다 "UserPromptSubmit hook error" 발생.

**조치(2026-07-05)**: `[Environment]::SetEnvironmentVariable('Path', ..., 'User')`로 User PATH에서
`AppData\Local\Python\bin`을 `AppData\Local\Microsoft\WindowsApps`보다 앞으로 재정렬. 레지스트리엔
반영됐지만 **이미 떠 있는 프로세스(현재 세션 포함)는 옛 PATH를 메모리에 들고 있어 즉시 적용 안 됨** —
Claude Code(및 그 하위 훅 프로세스)를 완전히 재시작해야 새 PATH가 적용된다.

**다음 세션에서 확인**: `which python3`가 `AppData\Local\Python\bin\python3.exe`로 뜨는지, fablize 훅
에러가 재발하는지. 재발하면 윈도우 설정(앱 → 고급 앱 설정 → 앱 실행 별칭)에서 python.exe/python3.exe
자체를 끄는 게 더 확실한 조치.
