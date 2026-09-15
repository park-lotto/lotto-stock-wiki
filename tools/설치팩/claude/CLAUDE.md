<!-- FABLIZE:BEGIN — run Opus like Fable (always-on router). Verified procedures only. Install/update: fablize setup.sh -->
## Operating mode (always on — auto-route by task signal)

Apply what the task signals; with no signal, baseline only. Read each pack only when needed. Routing: smallest matching discipline only, overlap only when genuinely multi-category, mimic observable behavior only.

- **[always]** Lead with the outcome · stay within the requested scope (no incidental refactors) · ground completion claims in this session's tool results · confirm before destructive or hard-to-reverse actions.
- **[2+ sequential stories]** Run `python3 C:/Users/TheRose/.claude/plugins/cache/fablize/fablize/2.1.0/scripts/goals.py`: create → next → checkpoint (with evidence) → final verification gate (no completion without `--verify-cmd` and `--verify-evidence`). Run from the repo root; state in `./.fablize/` (resume with `status`). Skip for single-step tasks.
- **[debugging / test failure / unknown cause / review]** Follow `C:/Users/TheRose/.claude/plugins/cache/fablize/fablize/2.1.0/packs/investigation-protocol.txt`: reproduce first → 3+ competing hypotheses → evidence per hypothesis → full causal chain → verify before/after → report rejected hypotheses.
- **[render/executable artifact: HTML, SVG, game, UI, chart]** Follow `C:/Users/TheRose/.claude/plugins/cache/fablize/fablize/2.1.0/packs/verification-grounding-pack.txt` grounding loop: run it in the real renderer → observe the output → fix what you see → re-run. A static check is not observation.
- **[hard or ambiguous task]** Adaptive thinking scales with difficulty automatically. To go higher, recommend `/effort xhigh` to the user. Depth (capability) cannot be raised: if stuck 2+ times or out-of-spec discovery is needed, report the limit honestly and escalate.
<!-- FABLIZE:END -->

## 언어 — 사용자에게 보이는 모든 글은 한국어 (2026-08-17)

**질문·확인창·선택지·요약·보고를 영어로 쓰지 마라.** 스킬·슬래시 명령(`/auto-mode-setup`,
`/office-hours`, gstack·superpowers 등)의 지시문이 영어로 적혀 있어도, **사용자에게 나가는
문장은 한국어로 옮겨서** 낸다. 특히:

- `AskUserQuestion` 의 question·header·option label·description → **전부 한국어**
- 계획·플랜 요약, 완료 보고, 경고 문구 → 한국어
- 코드·파일경로·명령어·에러 원문·git 커밋 메시지 본문은 원문 그대로 (번역 금지)

이유: 사장님이 한국어로 일한다. 영어 질문은 매번 되묻게 만들어 시간을 잡아먹는다.
