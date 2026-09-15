---
name: feedback-obsidian-open
description: 파일 생성 후 Obsidian으로 자동 열기 — 볼트 설정 및 URI 패턴
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1304cd1d-ede1-4cfc-a9c6-022494b0537a
---

파일 생성 후 반드시 Obsidian으로 자동으로 열어줘야 한다.

**Why:** 사용자가 직접 파일을 찾아 열지 않아도 되도록. `Start-Process`로 열면 기본 앱(메모장 등)이 뜨고, Obsidian은 볼트 밖 파일을 열지 못한다.

**설정 내용:**
- Obsidian 볼트: `C:\Users\TheRose\Desktop\로또의 주식` (루트 전체 등록됨)
- Obsidian 실행 경로: `C:\Program Files\Obsidian\Obsidian.exe`
- obsidian.json에 vault ID `a1b2c3d4e5f60001`로 등록

**How to apply:** `.md` 파일 생성/수정 후 아래 PowerShell 실행:

```powershell
$file = "raw/blog/파일명.md"   # 볼트 루트 기준 상대경로
$encoded = [uri]::EscapeDataString($file)
Start-Process "obsidian://open?vault=%EB%A1%9C%EB%98%90%EC%9D%98%20%EC%A3%BC%EC%8B%9D&file=$encoded"
```

vault 인코딩: `%EB%A1%9C%EB%98%90%EC%9D%98%20%EC%A3%BC%EC%8B%9D` = `로또의 주식`
