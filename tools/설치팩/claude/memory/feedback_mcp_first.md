---
name: feedback-mcp-first
description: 어떤 작업이든 MCP 최우선 사용. Python/Bash는 MCP 불가 시에만.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f99cedc3-9610-4514-a79c-5adf85a06a97
---

## 규칙: MCP 최우선 사용

**Why:** 효율성. MCP는 Claude가 직접 호출해 즉시 처리. 스크립트 작성·실행 불필요.

**How to apply:**

| 작업 | MCP 우선 | 스크립트는 |
|------|---------|-----------|
| 웹 크롤링·URL 읽기 | Fetch MCP | MCP 불가 시만 |
| 브라우저 자동화 | Playwright MCP | MCP 불가 시만 |
| 데이터 저장·조회 | SQLite MCP | MCP 불가 시만 |
| 지식 메모리 | Memory MCP | MCP 불가 시만 |
| 복잡한 연산·파일 처리 | — | Python/Bash 사용 |

**현재 설치된 MCP**: fetch / sqlite / memory / playwright (세션 재시작 후 활성화)
