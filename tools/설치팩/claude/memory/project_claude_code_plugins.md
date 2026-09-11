---
name: project-claude-code-plugins
description: 설치된 Claude Code 플러그인·스킬·MCP 전체 목록 및 주의사항
metadata: 
  node_type: memory
  type: project
  originSessionId: 9ebb5c07-073b-49c4-b73e-fc66cb059618
---

## 설치 완료 목록 (2026-06-03)

### 플러그인 (claude plugin install)
| 플러그인 | 마켓플레이스 | 주요 스킬 |
|---------|------------|---------|
| superpowers | claude-plugins-official | systematic-debugging 등 14개 포함 |
| prompt-architect | ckelsoe/prompt-architect | 프롬프트 최적화 |
| frontend-design | claude-plugins-official | UI 설계 |
| context-engineering | muratcankoylan/Agent-Skills-for-Context-Engineering | 컨텍스트 엔지니어링 |
| watch (claude-video) | bradautomates/claude-video | `/watch` 영상 분석 |
| understand-anything | Lum1104/Understand-Anything | 코드→지식그래프 |
| agentmemory | rohitg00/agentmemory | AI 에이전트 영구 메모리 |

### 스킬 (직접 설치, ~/.claude/skills/)
| 스킬 | 출처 | 내용 |
|------|------|------|
| gstack (40개 스킬) | garrytan/gstack | YC CEO 가리탄 셋업. `/office-hours` `/plan-ceo-review` `/review` `/qa` `/browse` 등 |
| pexo-agent, videoagent-* (5개) | pexoai/pexo-skills | AI 영상/이미지/오디오 생성 |

### MCP 서버 (~/.claude.json)
| MCP | 명령어 | API 키 | 상태 |
|-----|--------|--------|------|
| firecrawl-mcp | npx -y firecrawl-mcp | FIRECRAWL_API_KEY ⚠️ 미설정 | 미연결 |
| browsermcp | npx @browsermcp/mcp@latest | 불필요 | ⚠️ 크롬 확장 없어서 미연결 |
| elevenlabs-mcp | uvx elevenlabs-mcp | ELEVENLABS_API_KEY ⚠️ 미설정 | 미연결 |
| **playwright** | npx -y @playwright/mcp@latest | 불필요 | ✅ 2026-06-04 추가 — Gemini 웹 자동화 목적 |

### 신규 설치된 의존성
- **Bun** v1.3.14 → `C:\Users\TheRose\.bun\bin\`
- **uv/uvx** v0.11.18 → `C:\Users\TheRose\.local\bin\`
- **Playwright Chromium** → `C:\Users\TheRose\AppData\Local\ms-playwright\`

## 주의사항

**Why:** VS Code 확장 환경에서 `/plugin install` 슬래시 명령어가 작동 안 함.

**How to apply:** 플러그인 설치/관리는 Bash에서 `claude plugin ...` 명령어로 실행하거나 Claude에게 요청.

**API 키 미설정 항목:**
- Firecrawl: `.env` 또는 환경변수에 `FIRECRAWL_API_KEY=...` 추가 필요
- ElevenLabs: 환경변수에 `ELEVENLABS_API_KEY=...` 추가 필요

**gstack 업데이트:** `~/.claude/skills/gstack` 에서 `./setup` 재실행 또는 `/gstack-upgrade` 스킬 사용
