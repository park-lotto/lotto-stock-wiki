---
name: reference-3
description: 사장님 PC에서 캡처 이미지 Ctrl+V가 텍스트로 붙던 원인 3겹(ShareX F1·Windows Terminal·PowerToys Advanced Paste)과 판별 순서
metadata: 
  node_type: memory
  type: reference
  originSessionId: e3d0666d-5f69-4032-b622-be7185877ac6
  modified: 2026-09-04T01:16:11.484Z
---

2026-09-04 해결. "Ctrl+V가 텍스트로 붙는다"는 제보의 원인이 3겹이었고, 하나씩 걷어내야 했다.

1. **ShareX**: F1 단축키가 기본 설정을 안 쓰고 자기 AfterCaptureJob(파일저장+탐색기)만 있어 이미지가 클립보드에 안 감. 업로드 뒤 URL 텍스트가 클립보드를 덮음. → `Documents\ShareX\HotkeysConfig.json` 단축키별 AfterCaptureJob에 CopyImageToClipboard 추가·UploadImageToHost 제거. ★ApplicationConfig(기본값)만 고치면 F1엔 안 먹는다. ★ShareX는 종료 시 설정을 덮어쓰므로 Stop-Process 후 편집 → 재시작.
2. **Windows Terminal**: Ctrl+V가 PasteFromClipboard로 묶여 Claude Code에 키가 안 닿음 → unbound, 텍스트는 Ctrl+Shift+V. (`Packages\Microsoft.WindowsTerminal_*\LocalState\settings.json`)
3. **PowerToys Advanced Paste**: Ctrl+V(code 86)를 전역 훅 → 카톡 등 모든 앱에서 이미지가 텍스트로. → `AppData\Local\Microsoft\PowerToys\settings.json` enabled.AdvancedPaste=false, PowerToys 재시작.

Claude Code 쪽: `~/.claude/keybindings.json` Chat에 ctrl+v → chat:imagePaste (기본은 alt+v).

**판별 순서**: PowerShell -STA로 `Clipboard.GetDataObject().GetFormats()` 먼저 → 이미지 없으면 캡처 도구, 있으면 키 가로채는 상주 프로그램(tasklist에서 PowerToys·AutoHotkey·클립보드 매니저).
백업: 각 파일 `*.bak_claude_2026-09-04`.
