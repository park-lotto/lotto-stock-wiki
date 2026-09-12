# 클로드코덱스 설치팩 — 새 PC를 사무실 PC와 똑같이

사무실 PC를 **2026-09-11에 실측**해서 만든 팩입니다. 짐작으로 적은 건 없습니다.

## 어디 있나

- **git**: 저장소 `tools/설치팩/` (2026-09-11 푸시). 집 PC에 저장소가 이미 있으면 `git pull` 뒤 이 폴더에서 바로 실행(4단계 clone은 이미 있으니 건너뜁니다).
- 저장소가 없는 새 PC: 사무실 바탕화면 `클로드코덱스_설치팩\` 복사본을 USB로 옮기거나 GitHub에서 이 폴더만 내려받아 시작.

## 쓰는 법 (새 PC, 3단계)

```
1. 이 폴더(클로드코덱스_설치팩)를 통째로 새 PC 아무 데나 복사  (USB·클라우드)
2. PowerShell 열기 (관리자 아님)  →  그 폴더로 이동
3.   Set-ExecutionPolicy -Scope Process Bypass -Force
     .\install.ps1
```

끝나면 화면에 **"사람이 직접 해야 하는 것"** 6개가 뜹니다. 그것만 하면 사무실과 같습니다.
몇 번 다시 돌려도 됩니다(이미 된 건 건너뜁니다).

## 스크립트가 하는 것

| 단계 | 내용 | 사무실 PC 실측값 |
|---|---|---|
| 1 | winget으로 Git · Node · Python · ffmpeg · gh · uv · bun | git 2.54 · node 24.15 · python 3.12.10 · ffmpeg 8.1.1 |
| 2 | Claude Code 공식 설치기 | 2.1.268, `~/.local/bin/claude.exe` |
| 3 | `npm i -g` @openai/codex · myagentmemory · @higgsfield/cli | codex-cli 0.154.0 |
| 4 | 저장소 clone + `pip install -r shopping_shorts/requirements.txt` + tzdata/playwright + `npm install` | 저장소 `Desktop\로또의 주식` |
| 5 | `~/.claude/` — settings.json(훅·권한·플러그인 켬 목록·모델) · 전역 CLAUDE.md · keybindings · dashboard 훅 · MCP 서버 5개 · **자동 메모리 236개** | |
| 6 | gstack clone + setup → `/codex` `/browse` `/review` 등 | garrytan/gstack 1.55.1.0 |
| 7 | After Effects MCP (선택) | Dakkshin/after-effects-mcp |
| 8 | `~/.codex/config.toml` · cmd 자동실행(레지스트리 AutoRun) · 바탕화면 `코덱스.lnk` | |
| 9 | Claude 플러그인 마켓플레이스 8개 등록 | |

## 사람이 직접 해야 하는 것 (스크립트가 못 하는 것)

1. **로그인** — `claude`(Anthropic 계정) / `codex login`(ChatGPT **Pro** — 아니면 gpt-6-astra가 안 뜸)
2. **Codex 첫 실행 샌드박스 승인** — `codex` → `1. Set up default sandbox` → 관리자 창 '예'. **집에서 "권한이 안 된다"의 정체가 이것**
3. **키 파일 2개 USB 복사** (팩엔 일부러 없음) — 저장소 `.env`(69줄) · `~/.config/watch/.env`
4. **Claude 플러그인 8개** — `claude` 열고 `/plugin`에서 설치. settings.json에 이미 "켬"으로 돼 있어 설치만 하면 됨
5. **크롬 확장 2개** — Claude in Chrome / Codex chrome (`codex plugin add chrome@openai-bundled`)
6. 확인 — cmd 열면 Codex가 바로 떠야 함

## 팩 안에 든 것

```
install.ps1                       ← 실행할 것
claude/settings.json.template     ← 사용자 경로만 __USERPROFILE__ 로 바꿔둠 (키 없음)
claude/CLAUDE.md                  ← 전역 규칙(한국어·fablize)
claude/keybindings.json
claude/mcpServers.json            ← MCP 4개 (firecrawl·browsermcp·elevenlabs·AfterEffects — notebooklm은 09-12 뺌: 로그인 크롬창 반복) — 키 없음
claude/dashboard/                 ← Stop 훅 스크립트(stop_hook.py 등)
claude/memory/                    ← 자동 메모리 236개 (사장님 개인 기록 — 남 주지 말 것)
claude/watch.env.template         ← GROQ_API_KEY= (비어 있음)
codex/config.toml.template        ← 권한·모델 (플러그인·MCP 절대경로 블록은 뺌 — Codex가 그 PC에서 새로 만듦)
codex/codex-autorun.cmd.template  ← cmd 열면 Codex
```

## 검증한 것 (2026-09-11 사무실 PC)

- `install.ps1` — PowerShell 파서로 문법 검사 통과(218줄). **UTF-8 BOM으로 저장**했습니다 — 한글이 든 .ps1은 BOM이 없으면 PowerShell 5.1이 파일을 깨뜨려 엉뚱한 줄에서 오류가 납니다. 메모장으로 고칠 땐 "UTF-8(BOM)"으로 저장하세요.
- 치환 로직 드라이런 — 가짜 사용자명(`집사용자`)으로 settings.json·mcpServers.json·config.toml·autorun.cmd를 만들어 JSON 유효성·경로 치환·cp949 저장을 확인. 사무실 절대경로 잔존 0.
- 새 PC에서 처음부터 끝까지 돌려본 것은 **아닙니다** — 실제 새 PC가 없어서. 돌리다 막히는 단계가 있으면 그 단계 이름과 화면 문구를 주시면 고칩니다.

## 알아둘 것

- **Codex 권한은 PC마다 따로**입니다. `config.toml`이 git에 안 담겨서 이 팩이 대신 옮깁니다.
  사무실 값 그대로 `:danger-full-access`(작업 폴더 밖까지 묻지 않고 접근)입니다 — 안전하게 두려면 그 줄만 주석 처리.
- **Codex 기본 모델은 사무실 현재값 `gpt-6-astra`**로 넣었습니다. 평소용은 `gpt-5.6-sol`, 대화 중 `/model`로 바꿀 수 있습니다.
- Claude Code의 `/codex`(gstack)는 **읽기 전용**이라 코드를 못 고칩니다. 고치게 하려면 cmd에서 `codex`를 직접.
- 사용자명이 `TheRose`가 아니어도 됩니다 — 경로는 전부 스크립트가 그 PC 기준으로 다시 씁니다(메모리 폴더 키까지).
- 프로젝트 안 규칙(`CLAUDE.md`·`AGENTS.md`·`트랙.bat`·`코덱스.bat`)은 git으로 따라오므로 팩에 없습니다.
