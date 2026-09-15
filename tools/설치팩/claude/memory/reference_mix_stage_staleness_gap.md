---
name: reference_mix_stage_staleness_gap
description: mix job 단계별 무한 멈춤 = staleness 가드 누락. 재시작이 BackgroundTask 죽이면 상태 영구고착
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3a4e4fe8-65b3-4ceb-9dd8-a578fbdee899
  modified: 2026-07-23T09:59:00.426Z
---

쇼핑쇼츠 제작소 단계가 "무한 진행중"에 멈추면 십중팔구 **staleness 복구 가드 누락**이다.

**메커니즘**: 매칭·미리보기·자막제거(clean)·렌더는 FastAPI BackgroundTask로 돌고 상태를
DB(mix_jobs)에 쓴다(`status`/`preview_status`/`clean_status`). **배포 재시작**(auto_deploy 크론
3분, shopping_shorts 변경 시 systemd 재시작 — 자주 일어남)이 진행 중 태스크를 죽이면 `except`가
못 돌아 그 상태가 **영원히** DB에 남는다. TTL·하트비트 없음 → 프론트 폴러가 무한 스피너.

**탈출구**: `app.py:_render_is_stale(job)` — `updated_at` vs `_PREVIEW_STALE_SEC`(=600초=**10분**),
단계무관·timestamp 기반. `api_mix_status`(GET)가 이 판정으로 응답에서만 `failed`로 알린다(DB 불변
— 재시도가 유일 복구). 그러면 프론트 폴러가 실패 브랜치로 "다시 시도" UI를 연다.

**함정 = 단계마다 따로 붙여야 함**. 이 가드는 각 status 필드에 개별로 걸어야 한다:
- `status`(매칭/렌더): 2026-07-18에 추가됨(app.py:1804).
- `clean_status`(2단계 자막제거)·`preview_status`(1단계): **2026-07-23에야 추가**(내가 고침).
  clean에 안 붙어 있어 "AI가 자막 영역을 복원하는 중" 무한멈춤 재발(트리거=내 레퍼런스랭킹
  배포 재시작이 진행 중 clean 태스크를 죽임). run_clean_sources는 예외 시 failed로 바꾸므로
  (멈춤=예외 아님) 이 가드 누락이 유일 원인이었다.

**새 단계(예: 썸네일·SEO가 BackgroundTask化)를 추가하면 그 status에도 이 가드를 잊지 말 것.**
테스트 패턴: `monkeypatch.setattr(appmod,"_render_is_stale",lambda job:True)` → status GET이
failed 반환하는지(test_app_clean.py 참고). [[reference_deploy_truth_branch_ssh]]
