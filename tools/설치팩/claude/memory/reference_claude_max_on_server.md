---
name: reference_claude_max_on_server
description: "서버에서 Opus/Sonnet을 Max 구독으로 호출하는 법(claude -p, API 아님) + 토큰 스테일 리스크·우아폴백"
metadata: 
  node_type: memory
  type: reference
  originSessionId: bef0f865-73ea-4703-b022-c6f64924acb0
---

**목적**: Anthropic API 과금 없이 Max 구독으로 서버에서 Claude(Opus/Sonnet) 호출. API 대신 `claude` CLI 헤드리스 모드가 구독 인증을 씀.

**셋업**(2026-07-04 Lightsail 서버 stockbrain1.duckdns.org에 구축·검증):
1. 서버에 CLI 설치: `sudo npm install -g @anthropic-ai/claude-code` (Node 필요, /usr/bin/claude).
2. **Max OAuth 토큰 복사**: 로컬 `~/.claude/.credentials.json`(`claudeAiOauth`: accessToken/refreshToken/expiresAt/subscriptionType) → 서버 `/home/ubuntu/.claude/.credentials.json`, `chmod 600`.
3. 호출: `claude -p "<프롬프트>" --model opus --output-format json --permission-mode bypassPermissions`. 출력 JSON의 `.result`가 모델 응답. `modelUsage`에 실제 모델ID(claude-opus-4-8 등).
4. **전용 최소 cwd**(`/home/ubuntu/briefing_agent`)에서 실행 → 프로젝트 CLAUDE.md 오염·토큰오버헤드 최소화.
5. 서버에 `ANTHROPIC_API_KEY` **없어야** OAuth(Max) 인증 사용 → API 과금 아님. `total_cost_usd`는 참고표시일 뿐.

**⚠️ 핵심 리스크 — 토큰 스테일(실발생)**: 로컬 Claude Code와 서버가 **같은 Max 계정 토큰 공유**. accessToken 만료 시 refreshToken으로 갱신하는데, **로컬 Claude Code가 갱신하면 refreshToken이 로테이션돼 서버 복사본이 무효화**("Not logged in"). 2026-07-04 실발생(로컬=지금 돌리는 나, 20:36 만료 후) → 재복사로 복구.
- **미확정**: 서버가 자체 refresh로 유지되는지 vs 계속 스테일되는지 장기관측 필요.
- **완화책**: 호출 실패 시 Gemini로 **우아 폴백**(기능 안 죽음, 품질만 하락). 로그에 어느 모델 썼는지 기록해두면 스테일 여부 추적 가능.
- **지속대안**(스테일 반복 시): 서버 전용 별도 계정/토큰, 로컬PC 켜졌을 때 주기적 재복사, 또는 서버만 API로.

**보안**: Max 토큰(계정 전체 접근권)이 서버 파일로 저장됨 — 서버 침해 시 계정 노출. 사용자 승인 하 진행.

관련: [[project_briefing_weather_engine]](이 방식의 첫 실사용) [[feedback_simple_before_complex]](로컬 토큰파일 복사부터)
