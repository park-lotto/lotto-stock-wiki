---
name: feedback_origin_main_broken_by_half_commit
description: origin/main이 병렬세션 반쪽커밋으로 깨질 수 있음 — force-deploy 전 import 검증
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 88d72866-689f-457e-8752-65fd55277ee6
---

동시세션 환경에서 origin/main이 **깨진 채로 푸시**돼 있을 수 있다. 사례(2026-07-13):
병렬세션이 `app.py`에 `translate_keyword` import·엔드포인트는 커밋했는데,
정의 함수(video_analysis.py)는 미커밋이라 origin/main이 ImportError 상태.
서버는 auto-deploy가 크롤 dirty로 막혀 **옛 정상커밋에 정체**돼 안 터지고 있다가,
`git reset --hard origin/main` force-deploy가 이걸 노출시켜 503 크래시.

**Why:** 서버가 옛 커밋에 정체 = 방패이자 함정. force-deploy는 그 방패를 걷어냄.

**How to apply:**
- 서버 `git reset --hard origin/main` 재시작 **전**, 로컬에서
  `python -c "import shopping_shorts.app"`로 부팅 import 검증(내 워킹트리엔 함수가
  있어 로컬 서버는 멀쩡해도 origin은 깨졌을 수 있음 — 반드시 `git show origin/main:파일`로 확인).
- 깨졌으면 포워드픽스: 누락된 반쪽(함수+상수)을 커밋해 origin 복구. 순수 추가(+만)면 안전.
- 근본: auto_deploy가 깨진 커밋을 배포 안 하도록 import 스모크체크 게이트 추가 검토.

관련: [[reference_deploy_truth_branch_ssh]] [[feedback_deploy_discipline_during_incident]] [[feedback_concurrent_session_commit_bundling]]
