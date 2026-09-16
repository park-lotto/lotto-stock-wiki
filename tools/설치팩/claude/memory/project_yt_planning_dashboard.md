---
name: project_yt_planning_dashboard
description: "유튜브 영상제작 통합 대시보드(/yt) 진행상황 — ①기획단계 SDD Task 1-4 완료, Task 5(HTML) 남음"
metadata: 
  node_type: memory
  type: project
  originSessionId: 188541e8-71ec-47fc-ab9b-89b775b6e3cb
---

유튜브 영상제작 전체(기획→대본→리모션→녹음→자막→렌더)를 하나의 웹 대시보드로 묶는 프로젝트.
**완전 독립 페이지** `/yt`로 확정(STOCK BRAIN 공통 네비 탭에 안 넣음 — 사용자가 명시적으로 정정).
기존 `scripts/yt_agents/pipeline.py`(6단계 CLI, 체크포인트/QC재작업 로직 완성돼 있음)를 그대로
재사용하고, `dashboard/studio.html`의 SSE 진행상황 패턴을 재사용.

이번 스펙 범위는 **①기획 단계만** — 나머지 5단계는 이후 별도 스펙으로 확장 예정.

**Why:** "기획/레퍼런스/대본/자막/리모션/이미지 여러 AI프로그램을 합쳐서 만들거야" 요청에서 시작.
사용자가 "이 기획페이지에서 어떻게 되는지 이것부터 완성하면서 다음단계 넘어가자"고 스코프를
명시적으로 좁힘. "터진 영상" 위젯은 ViewTrap(app.viewtrap.com) 실제화면 스크린샷을 근거로
**기여도 = 그 영상 조회수 ÷ 그 채널 최근 N개 영상 평균조회수(채널 자체 평균 대비 %)** 방식으로
확정 — 단순 조회수÷구독자 비율이 아님. 범위는 "영상 검색(기여도·성과도)만"으로 명시적 축소
(채널분석·컬렉션·핫비디오브라우징은 제외).

**How to apply:**
- 스펙: `docs/superpowers/specs/2026-07-03-yt-기획단계-대시보드-design.md`
- 계획: `docs/superpowers/plans/2026-07-03-yt-기획단계-대시보드.md` (5 task, 전체 코드 포함)
- 원장: `.superpowers/sdd/progress.md` (Task별 리뷰이력 상세)
- **Task 1** 완료: `scripts/yt_agents/hot_clips.py` — find_hot_clips() 등. 자기영상 제외 평균계산
  버그를 2번 재발견(캐싱+제외로직 조합 문제)해서 raw fetch캐시+Python exclusion분리로 근본수정.
- **Task 2** 완료: `POST /yt/hot_clips` — dashboard/server.py. 무관코드 삭제사고를 리뷰가 복구.
- **Task 3** 완료: `scripts/yt_agents/plan_stage.py` — run_plan_stage(). 계획서의 import패턴 자체가
  깨진 코드였음을 리뷰가 실행검증으로 발견, 패키지import로 우회+주석 보강.
- **Task 4** 완료: `POST /yt/generate_plan` — 코드 자체는 검증완료(Approved)이지만 다른 세션이
  동시에 같은 걸 구현해서 무관한 커밋(`c0e426f9`)에 섞여 들어온 상태로 발견됨
  ([[feedback_concurrent_session_commit_bundling]] 참고).
- **Task 5** 미시작: `dashboard/yt.html` + `GET /yt` 라우트. HTML/CSS/JS는 계획서에 이미 작성돼
  있어 구현자는 transcription+테스트만. render 산출물이라 실제 브라우저 구동 확인 필수.
- 세션 종료 시점(2026-07-03 밤): git push만 완료, 서버(Lightsail) 배포는 안 함 — 미완성 기능이라
  로컬/다른PC 이어가기 용도로 push만으로 충분.

관련: [[feedback_concurrent_session_commit_bundling]], [[feedback_shared_worktree_branch_check]]
