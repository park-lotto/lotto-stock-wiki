# PC가볍게 — 핸드오프 (관제 214)

## 2026-10-15 (TheRose PC)

### 실측
32GB 중 남은 4.6GB. Claude 창 12세션(유령 2개 = 세션 파일 없음·10-05 시작) 5.8GB, 관문 시험 일꾼 8개 4.3GB,
세션마다 뜨는 도구 서버(firecrawl 18·agentmemory 18·After Effects 9) 약 2.3GB.

### 한 것
- 유령 claude 2개 종료(+1.3GB). 도구 서버 firecrawl·AfterEffects·browsermcp 와 agentmemory 플러그인 끔
  (백업 `~/.claude/mcp_off_backup_20261015_134018.json` — 되살리기는 그 파일의 항목을 `~/.claude.json` mcpServers 에 다시 넣기).
- 점검기 `tools/pc_watch.py`: `status`(표) · `clean` · `tick`(5분 예약용) · `schedule`. 자동 정리는 부모 없는 node·관문 일꾼·세션 파일 없는 24시간+ 유령 claude 만.
  ★분리 실행 finish(부모 없이 도는 게 정상)는 절대 안 끈다 — 첫 시험에서 걸러 고침. 살아 있는 세션은 안 끄고 '쉬는 창'(2시간+)으로만 알린다.
- 시험 `tools/test_pc_watch.py`.

### 남은 것
- 윈도 알림(토스트)이 화면에 안 뜸 — 방해 금지 모드로 보임(알림 센터로만). 남은 메모리 3GB 미만 알림은 로그 `~/.claude/pc_watch.log` 에도 남는다.
