# Skill Routing — 전체 스킬 활용 맵

> CLAUDE.md에서 분리. 작업 시작 전 이 파일 참조해 최적 스킬 선택.
> **규칙**: 요청이 아래 조건과 일치하면 즉시 해당 스킬 호출. 의심스러우면 호출.

---

## Superpowers × Gstack 역할 분담

| 단계 | Superpowers (사고/프로세스) | Gstack (도구/실행) |
|------|--------------------------|-----------------|
| 설계 | `brainstorming` | `office-hours` (아이디어 검증) |
| 계획 | `writing-plans` | — |
| 구현 | `executing-plans` | — |
| 확인 | `verification-before-completion` | `qa` (브라우저 실제 확인) |
| 검수 | — | `design-review` · `review` |
| 배포 | `finishing-a-development-branch` | `ship` |
| 디버그 | `systematic-debugging` | `investigate` |
| 병렬 | `dispatching-parallel-agents` | — |

## 업무별 추천 스킬 조합

| 업무 | 조합 |
|------|------|
| 새 기능 설계+구현 | `brainstorming` → `writing-plans` → `executing-plans` → `qa` |
| 영상 제작 | `brainstorming` → `executing-plans` → `videoagent-*` → `qa` |
| 오류 수정 | `systematic-debugging` → `investigate` → `verification-before-completion` |
| HTML 결과물 | `executing-plans` → `qa` → `design-review` |
| 커밋/배포 | `verification-before-completion` → `review` → `ship` |

---

## 🧠 Superpowers — 사고·프로세스 규율

| 트리거 | 스킬 |
|--------|------|
| 새 시스템·기능·영상 기획 시작 | `superpowers:brainstorming` |
| 설계 끝나고 구현 계획 작성 | `superpowers:writing-plans` |
| 계획대로 코드 실행 | `superpowers:executing-plans` |
| 에러·버그·오작동 | `superpowers:systematic-debugging` |
| 작업 완료 전 최종 체크 | `superpowers:verification-before-completion` |
| 씬 여러 개 동시·파이프라인 병렬 | `superpowers:dispatching-parallel-agents` |
| 대형 작업 서브에이전트 분산 | `superpowers:subagent-driven-development` |
| 새 슬래시 명령어 만들기 | `superpowers:writing-skills` |
| 브랜치 마무리·PR 준비 | `superpowers:finishing-a-development-branch` |
| 코드 리뷰 요청 | `superpowers:requesting-code-review` |
| 코드 리뷰 받기 | `superpowers:receiving-code-review` |
| 테스트 기반 개발 | `superpowers:test-driven-development` |
| 병렬 브랜치 작업 | `superpowers:using-git-worktrees` |

---

## 🛠 Gstack — 브라우저·QA·배포·검수

| 트리거 | 스킬 |
|--------|------|
| HTML 결과물·사이트 실제 확인 | `qa` |
| 버그만 찾고 수정 안 할 때 | `qa-only` |
| 디자인·UI 시각적 검수 | `design-review` |
| 디자인 시스템 전체 설계 | `design-consultation` |
| 디자인 여러 시안 비교 | `design-shotgun` |
| 프로덕션용 HTML/CSS 생성 | `design-html` |
| 코드 diff 리뷰 | `review` |
| 보안 취약점 점검 | `cso` or `security-review` |
| 커밋+PR+배포 한번에 | `ship` |
| 머지+배포+검증 통합 | `land-and-deploy` |
| 배포 후 모니터링 | `canary` |
| 버그·오류 심층 조사 | `investigate` |
| 아이디어 빠른 CEO 검증 | `office-hours` |
| 아키텍처 설계 검토 | `plan-eng-review` |
| 전체 리뷰 자동 파이프라인 | `autoplan` |
| 문서 신규 생성 | `document-generate` |
| 성능 회귀 측정 | `benchmark` |
| 웹 스크래핑 | `scrape` |
| 앱 실행 및 동작 확인 | `run` |
| 권한 프롬프트 최소화 | `fewer-permission-prompts` |

---

## 🎬 영상 제작 파이프라인

> **진입점**: 항상 `yt-make-video`부터. 절대 중간 단계부터 시작하지 말 것.

| 트리거 | 스킬 |
|--------|------|
| "영상 만들자" / `/make-video` | `yt-make-video` (전체 파이프라인 오케스트레이터) |
| "소재 찾자" / `/소재찾기` | `yt-content-research` (YouTube 리서치 → 주제 선정) |
| "기획서 써줘" / "씬 짜줘" | `yt-planner` (씬 구성 + 이슈 타이밍 체크) |
| "리서치해줘" / `/리서치` | `yt-gemini-pipeline` (브리프 → Gemini → 대본) |
| "대본 써줘" / `/script` | `yt-gemini-pipeline` |
| 대본 완성 후 Remotion 제작 | `remotion-best-practices` → `videoagent-director` |
| 씬 이미지 생성 | `videoagent-image-studio` |
| 음성·음악 처리 | `videoagent-audio-studio` |
| 최종 영상 합성 | `videoagent-video-studio` |
| "편집해줘" / 녹음 끝난 후 | `yt-editor` (Whisper 싱크 + 렌더) |
| "업로드해줘" | `yt-publisher` (YouTube + 텔레그램) |

**이슈 타이밍 원칙**: 이슈 후 3일 지나면 → 각도 변경 or 새 소재

---

## 🧬 Agentmemory — 세션 간 기억

| 트리거 | 스킬 |
|--------|------|
| 과거 세션 내용 검색 | `recall` |
| 중요 내용 저장 | `remember` |
| 잘못된 메모리 삭제 | `forget` |
| 세션 이력 확인 | `session-history` |
| 다른 에이전트에 인계 | `handoff` |

---

## 🔍 Understand-anything — 코드베이스 이해

| 트리거 | 스킬 |
|--------|------|
| 새 프로젝트 구조 파악 | `understand-anything:understand-onboard` |
| 코드에 대해 질문 | `understand-anything:understand-chat` |
| 특정 파일·함수 설명 | `understand-anything:understand-explain` |
| 코드 변경 분석 | `understand-anything:understand-diff` |

---

## ⚙️ Context-engineering

| 트리거 | 스킬 |
|--------|------|
| 대화가 너무 길어질 때 | `context-engineering:context-compression` |
| 멀티 에이전트 설계 | `context-engineering:multi-agent-patterns` |
| 메모리 시스템 설계 | `context-engineering:memory-systems` |

---

## 🎨 기타 전문 스킬

| 트리거 | 스킬 |
|--------|------|
| 영상 자막 처리 (Whisper) | `watch:watch` |
| raw/ 파일 → wiki 처리 | `ingest` |
| 아침 노트 / 소재 탐색 | `morning-note` |
| 장전 브리핑 | `morning-brief` |
| 세션 마감·인계 | `session-close` (없으면 CLAUDE.md 저장 트리거 참조) |
| Claude API 개발·최적화 | `claude-api` |
| 코드 리뷰 (ultra 딥리뷰) | `code-review` |
| 설정 파일 변경 | `update-config` |
| 키바인딩 설정 | `keybindings-help` |
| 변경사항 실제 동작 검증 | `verify` |
