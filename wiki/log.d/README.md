# wiki/log.d — 트랙별 작업 로그

`wiki/log.md`는 **동결된 아카이브**입니다(2026-07-15까지). 새 기록은 여기에 씁니다.

## 왜

여러 세션이 `log.md` 맨 위에 동시에 append하면 rebase 충돌이 100% 납니다.
실제로 2026-07-15 stash 복원이 타세션 기록 24줄을 지울 뻔했습니다.

## 규칙

1. 자기 트랙 파일만 수정: `wiki/log.d/<트랙>.md`
2. 한 줄에 한 항목: `- YYYY-MM-DD — 내용`
3. 합쳐 보기: `py tools/log_view.py --days 7` (읽기 전용, 파일 안 씀)
4. `git add wiki/log.d/<내트랙>.md` — `git add -A` 금지

설계: `docs/superpowers/specs/2026-07-15-동시세션-충돌차단-트랙격리-design.md`
