---
name: project-yt-pipeline
description: YouTube 영상 제작 파이프라인 현황 — yt-content-research(소재탐색) → yt-gemini-pipeline(대본) 2단계 구조. Gemini Deep Research Python 스크립트 완성.
metadata: 
  node_type: memory
  type: project
  originSessionId: cc8315d0-431d-42da-b49c-2203d181793a
---

## YouTube 파이프라인 (2026-06-04 업데이트)

**채널명**: 로또의 주식인사이트

### 파이프라인 구조
**1단계: yt-content-research** (Claude + WebSearch)
- 브레인스토밍 확인 → 핫이슈 스캔(WebSearch) → YouTube 포화도 체크 → 오염체크 → 종목 검증 → 브리프 생성
- ⚠️ 소재 찾기는 Gemini 호출 안 함. Claude+WebSearch만.

**2단계: yt-gemini-pipeline** (Gemini Deep Research)
- Claude 브리프 → `python scripts/gemini_yt_deep_research.py brief_{파일명}.md` → Claude 검수
- Gemini Interactions API (deep-research-preview-04-2026) 사용
- 소요: 약 6~7분

**Why:** Claude 기억 기반 대본 오염 방지. Gemini가 현재 시점 데이터로 대본 작성.
**How to apply:** "영상 만들자" → yt-content-research 스킬 → 브리프 → gemini_yt_deep_research.py

### Gemini 연동 방법 3가지
1. **MCP A** (gemini-research): uvx gemini-research-mcp — 재시작 필요
2. **MCP B** (gemini): @rlabs-inc/gemini-mcp — 재시작 필요, 메인으로 사용 예정
3. **Python 스크립트**: `scripts/gemini_yt_deep_research.py` — .env 직접 읽음, 재시작 불필요 ← 현재 동작

MCP 활성화 방법:
```powershell
$key = (Get-Content ".env" | Select-String "^GEMINI_API_KEY=").ToString().Split("=",2)[1]
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $key, "User")
# Claude Code 재시작
```

### 완성된 첫 영상 (2026-06-04)
- 주제: "삼성전자가 빠진 날 소부장이 30% 오른 이유 — 자금 순환의 법칙"
- 종목: 원익IPS(240810) + 유진테크(084370)
- 최종 대본: `channel/yt/script_소부장자금순환_20260604_final.md`
- 다음 단계: yt-planner → Remotion 영상 제작
