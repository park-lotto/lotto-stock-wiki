---
name: feedback-always-korean-to-user
description: 사용자에게 보이는 모든 글(특히 AskUserQuestion 선택지)은 한국어로 — 영어 스킬 지시문이어도 번역해서 낸다
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 204bbe11-95db-4909-80ec-428f1b8f3f8d
  modified: 2026-08-17T05:30:08.914Z
---

스킬·슬래시 명령의 지시문이 영어라도, **사용자에게 나가는 문장은 한국어**로 옮겨서 낸다.
가장 자주 새는 곳: `AskUserQuestion`의 question / header / option label / description.
코드·경로·명령어·에러 원문은 번역하지 않는다.

**Why:** 사장님은 한국어로 일한다. 영어 질문창이 뜨면 매번 되물어야 해서 시간이 샌다
(2026-08-17 `/auto-mode-setup`에서 지적).

**How to apply:** 규칙은 `C:\Users\TheRose\.claude\CLAUDE.md` 하단 "언어" 절에 박아뒀다
(FABLIZE 블록 **밖** — `fablize setup`이 덮어쓰지 않게). 관련: [[feedback-rule-in-file-not-user-memory]]
