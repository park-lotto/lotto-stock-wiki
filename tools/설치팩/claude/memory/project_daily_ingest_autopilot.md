---
name: project_daily_ingest_autopilot
description: "크롤링 인제스트 자동점검·자동수정 파이프라인(v2) — daily_verify.py(v1) 대체, 서버 크론 가동중, 실전 dry-run 안전장치 검증 완료"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1578286d-3f02-415e-9424-f884ac90a76a
---

2026-07-05 완성·배포. "매일 내가 확인해야 하냐"는 사용자 요청으로 daily_verify.py(v1, 소스단위
합계 신선도+보고만)를 채널단위 자동수정 시스템으로 전면 재설계.

**핵심 아키텍처**: 서버(`/home/ubuntu/lotto-stock-wiki`)에서 크론 실행(`50 8,12,15,18,21 --slot`,
`45 21 --daily-summary`) — 텔레그램 채널별 raw 파일명 날짜로 신선도 판정(atoms.db `created_at`은
재처리시 착시 일으켜서 안 씀) → 이상 있으면 `claude -p` 2단계(진단전용 Edit권한없음 → 수정
Edit권한) → pytest 전체스위트 게이트 → 배포(로컬 코드=git commit+push+조건부 재시작, 원격 크롤러
코드=`/home/ubuntu/kmong/crawling_bot` 파일 직접교체, 같은 박스라 SSH 불필요) → 헬스체크 실패시
자동롤백(git revert 또는 백업파일 복원) → 텔레그램. 파괴적 작업/코드로 못고치는 진단은 무조건
에스컬레이션(사용자 설정과 무관한 고정 하한선). 미해결 항목은 해결될 때까지 매일요약에서
빠짐없이 노출(스로틀은 진단 호출에만, 보고에는 안 걸림).

**신규 파일**: `scripts/autopilot_{freshness,state,diagnose,fix,deploy,report}.py` +
`scripts/daily_ingest_autopilot.py`(오케스트레이터) + `pipeline/atoms/telegram_registry.py`의
`resolve_channel_key`. 스펙=`docs/superpowers/specs/2026-07-05-일일-크롤링-인제스트-자동점검-design.md`,
계획=`docs/superpowers/plans/2026-07-05-일일-인제스트-자동점검-파이프라인.md`(10 task, 84테스트).

**실전 dry-run 검증(2026-07-05)**: 11개 채널 이상감지(당시 key_vault 버그로 서버인제스트가 며칠
막혀있던 여파, 정상) → 11/11 에스컬레이션, 그 중 2개는 실제로 크롤러 코드 수정 시도까지 갔으나
안전게이트에서 막혀 전부 자동롤백 확인(백업 vs 라이브파일 diff 0, crawlingbot 서비스 active 유지).
아직 자동수정 "성공" 사례는 관찰 못함 — 다음 세션에서 확인 필요.

**알려진 한계(문서화, 급하지 않음)**: pytest 게이트가 remote_crawler 수정엔 실질적 검증력 없음
(위키레포 테스트만 돎, 크롤러 코드는 안 봄).

관련: [[project_daily_verify_agent]](v1, 이 프로젝트가 대체함) [[project_kis_outage_2026_07_04]](비슷한 서버쪽 실전장애 대응 패턴)
