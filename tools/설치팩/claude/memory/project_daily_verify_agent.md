---
name: project_daily_verify_agent
description: "일일 검증 에이전트(daily_verify.py) v1 — [2026-07-05 대체됨] project_daily_ingest_autopilot(v2)가 크론자리 이어받음. 이 메모는 과거 설계 배경 참고용"
metadata: 
  node_type: memory
  type: project
  originSessionId: 567fdd93-64ca-4ff6-9309-c2360bd5e5b3
---

사용자 요청("텔레그램 필터에서 버그 3개 발견된 것처럼, 매일 자동으로 오류 검사·수정·보고하는
시스템을 만들자 — 이 프로젝트뿐 아니라 크롤링 등 다른 작업에도")으로 2026-07-03 신설·배포.

**구현**: `scripts/daily_verify.py` + `tests/test_daily_verify.py`(20테스트). 기존
`pipeline/atoms/daily_health.py` 패턴(수집→비교→카드→텔레발송, 14일 히스토리)을 확장.
- 크롤 신선도: raw/{telegram,news,report} 오늘자 파일수를 **같은 요일 최근 4주 평균**과
  비교(단순 어제대비 아님 — 주말/공휴일 오탐 방지가 핵심 설계결정)
- pytest 전체 회귀(FAILED + ERROR 둘 다 파싱, 실패목록만 보고 — AI 자동수정 안 함)
- stockbrain 서비스 상태(systemctl is-active, 죽어있으면 재시작 1회 자동시도)
- 원격서버 크론: `45 21 * * *`(마지막 인제스트 21:35 이후로 — 최초 21:30 오타로 잘못
  등록했다가 사용자가 "왜 21시반이야?" 질문으로 발견·수정됨)

**v1 범위 밖(명시적 결정)**: 서버 자체 외부 도달성(네트워크단 장애) 체크 — 같은 날 실제로
서버가 2번 다운됐는데, 온서버에서 도는 체커는 원리적으로 이걸 감지도 보고도 못 한다는 게
실증됨(네트워크 죽으면 텔레그램 알림도 못 보냄). UptimeRobot 같은 외부서비스 안내만 하고
구현은 안 함.

**실행검증 중 발견한 "체커 자체가 무력화되는" 심각버그 2개** (제일 위험한 유형 — 로컬에서는
안 보이고 실배포 후에만 드러남):
1. `python` 하드코딩 → 원격서버엔 `python` 명령어가 없음(python3/venv만 존재).
   `FileNotFoundError`가 "측정 실패=경보 아님" 예외처리에 조용히 삼켜져서, 체커가 아예 못
   돌고 있는데도 매일 "정상"으로 텔레 보고될 뻔함. → `sys.executable` 사용으로 수정.
2. pytest 출력 포맷 실측 오류 — "ERROR collecting X"로 가정했으나 실제 `-q` 모드 short
   summary는 "ERROR X"(collecting 단어 없음). 처음 고친 뒤에도 재배포·재검증에서 여전히
   빈 목록으로 나와서 두 번째로 발견.

**교훈**: 모니터링/검증 시스템은 mock 데이터로 유닛테스트만 통과시키고 끝내면 안 됨 —
실제 배포환경에서 진짜로 실행해서 로그를 봐야 "체커 자체가 죽어서 항상 그린으로 보이는"
최악의 실패모드를 잡을 수 있다. [[feedback_shared_worktree_branch_check]]의 배포패턴과
같이 씀.

**[2026-07-05] v2로 대체됨**: v1은 "발견만 하고 안 고침"이 한계였음 — 실제로 이 v1의 pytest
회귀체크가 07-03부터 key_vault msvcrt 크래시를 매일 텔레카드에 찍었는데도 아무도 안 고쳐서
서버 인제스트가 며칠 방치됐던 사례가 도화선이 돼 [[project_daily_ingest_autopilot]](채널단위
감지+claude -p 자동수정+안전게이트)으로 전면 교체. 서버 크론 자리(`45 21`)도 이어받음.
