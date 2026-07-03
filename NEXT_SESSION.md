# NEXT_SESSION — 영상제작 대시보드 ①기획단계 (Task 1-4 완료, Task 5 남음)

**날짜**: 2026-07-03 · **주제**: 유튜브 영상제작(기획→대본→리모션→녹음→자막→렌더) 통합 대시보드의
첫 단계인 "①기획" 페이지를 Subagent-Driven Development로 구현 중. main에 직접 커밋(사용자 동의 확인됨).

## 이번 세션 요약

### ✅ 완료: 브레인스토밍 → 설계 → 계획 → Task 1~4 구현

- 스펙: `docs/superpowers/specs/2026-07-03-yt-기획단계-대시보드-design.md`
- 계획: `docs/superpowers/plans/2026-07-03-yt-기획단계-대시보드.md` (5 task, 전체 코드 포함)
- 핵심 결정: `/yt` **완전 독립 페이지**(STOCK BRAIN 네비 탭 아님), 기존 `scripts/yt_agents/pipeline.py`
  6단계 CLI를 재사용(체크포인트/QC재작업 로직 그대로), `studio.html`의 SSE 패턴 재사용.
  "터진 영상" 위젯은 ViewTrap 실제화면 근거로 **채널 자체 평균 대비 %** 방식 확정(구독자 비율 아님),
  범위는 영상검색(기여도·성과도)만으로 명시적 축소.

**Task 1** (`scripts/yt_agents/hot_clips.py`, 유튜브 Data API 기반 기여도·성과도 계산) — 3라운드 리뷰
끝에 완성. 자기영상 제외 평균 계산 버그를 2번 재발견해서 근본구조(raw fetch 캐시 + Python에서
영상별 exclusion 계산 분리)로 수정. 12/12 테스트, 네트워크 호출 없음 확인.

**Task 2** (`POST /yt/hot_clips`) — 무관한 기존 코드(`generate_picks = None` 폴백) 실수로 삭제된 것을
리뷰가 발견·복구, defensive import 패턴 적용.

**Task 3** (`scripts/yt_agents/plan_stage.py`, 기획 QC재작업 루프를 SSE이벤트로 감싸는 러너) — 계획서에
적힌 import 패턴 자체가 깨지는 코드였음을 리뷰 실행검증으로 발견(agent_plan.py가 상대import를 씀),
구현자가 올바르게 패키지import로 우회했으나 문서화 안 해서 주석 보강.

**Task 4** (`POST /yt/generate_plan` SSE 엔드포인트) — 완료했지만 특이사항 있음: 실제 코드가 이 태스크의
SDD 디스패치가 아니라 **커밋 `c0e426f9`(제목="섹터상세 팝오버에 종목 등락률 추가", 무관함)에 이미
섞여 들어와 있었음**. 다른 세션(PC)이 같은 계획서를 보고 독립적으로 같은 기능을 구현해 무관한 커밋에
합쳐 넣은 것으로 추정. 구현자가 중복구현 대신 테스트만 추가, 리뷰가 실코드는 브리핑과 정확히 일치함을
확인(Spec ✅/Approved). 코드결함은 아니지만 **동시세션 조율 문제**로 기록.

### 🚨 동시세션 충돌 패턴 (반복 발생 — 다음 세션 주의)

오늘 같은 날 다른 세션(골루프 인포그래픽 작업)에서도 "다른 세션이 `/vnc-login/` 영구페이지 이미
구축"을 발견한 바 있음. 오늘 여러 PC/세션이 같은 저장소에서 겹치는 작업을 동시에 진행 중이었을
가능성이 높음. **Task 5 시작 전 `git log --oneline -10 -- dashboard/`로 새 무관 커밋이 없는지
먼저 확인할 것.**

## 미완료 / 다음 할 것

- [ ] **Task 5** (`dashboard/yt.html` + `GET /yt` 라우트): 미시작. 전체 HTML/CSS/JS는 계획서에
      이미 작성돼 있어 구현자는 transcription+테스트만 하면 됨. **render 산출물이라 verification-
      grounding-pack 규칙대로 실제 브라우저 구동 확인 필수**(자동테스트만으로 완료 처리 금지).
- [ ] Task 5 리뷰 → 전체 브랜치 최종 리뷰(가장 강력한 모델) → `superpowers:finishing-a-development-branch`
- [ ] 이번 계획 범위 밖: ②대본 ③리모션 ④녹음 ⑤자막 ⑥렌더 — ①기획 실동작 확인 후 각각 별도
      스펙+계획+구현 사이클로 확장 예정

## 관련 파일

- 스펙: `docs/superpowers/specs/2026-07-03-yt-기획단계-대시보드-design.md`
- 계획: `docs/superpowers/plans/2026-07-03-yt-기획단계-대시보드.md`
- 원장: `.superpowers/sdd/progress.md` (Task 1-4 상세 기록)
- 구현: `scripts/yt_agents/hot_clips.py`, `scripts/yt_agents/plan_stage.py`, `dashboard/server.py`
  (`/yt/hot_clips`, `/yt/generate_plan`), `tests/yt_agents/`, `tests/test_yt_dashboard.py`

## 배포 관련

`git push`만 완료 — Lightsail 서버(stockbrain1.duckdns.org) 배포는 **안 함**. 이 작업은 아직
미완성 기능(Task 5 남음)이라 로컬/다른PC에서 이어서 개발하는 용도로 git push만으로 충분함.
서버 배포는 ①기획 페이지가 실제로 브라우저에서 동작 확인된 뒤, 완성된 기능만 별도로 진행.
