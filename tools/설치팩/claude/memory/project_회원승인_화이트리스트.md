---
name: project
description: "shopping_shorts 회원 승인제(대기실). 화이트리스트+회원관리+무료체험이벤트(24h) 라이브. 후속=최종렌더 실패 환불"
metadata: 
  node_type: memory
  type: project
  originSessionId: c890cb0d-635b-4978-9317-60ba84134999
  modified: 2026-07-22T01:55:33.761Z
---

shopping_shorts(숏템탑스)에 "사장님 승인한 사람만 사용" 게이트 추가. 트랙 `회원승인`, 브랜치 `track/회원승인`(origin 백업됨). SDD 서브에이전트 방식.

**설계 확정**: 대기실 방식(미승인도 로그인은 되되 전면차단→사장님 admin에서 [승인]) + 기존계정 자동승인(라이브 안 깨짐) + 체험은 승인 시점 시작. 단일컬럼 `customers.approved_at`(NULL=대기/값=승인시각). `access_level`에 3번째 상태 `pending` 추가(plan/체험보다 우선). 세션 무상태 쿠키라 승인 즉시 반영.

**진행(2026-07-21)**: Task1~6 완료·리뷰통과, 40 passed. 1=컬럼+백필 2=create_customer(approved=) 3=access_level pending 4=가입2경로 대기계정화 5=approve_customer(멱등)+POST /api/admin/approve 6=미들웨어 pending게이트+대기실HTML. **남음: Task6 재리뷰 / Task7(/api/grab pending구멍 !=full) / Task8(admin 대기명단 UI) / 최종리뷰 / finish**.

**교훈**:
- `create_customer` 기본 `approved=True` 유지 → 기존 직접호출 테스트(access/admin/gate/usage) "체험중=full" 전제 보존. 공개가입 2경로(get_or_create_by_google·/api/signup)만 approved=False.
- `/logout` 백엔드 핸들러가 **원래 없었다**(HTML 링크만, 404). Task6에서 pending 탈출구로 신규 추가.
- 페이블 검토가 잡은 핵심: `/api/grab`은 _AUTH_ALLOW 우회라 자체게이트 `==ranking_only`가 pending 통과시킴 → Task7에서 `!=full`로.

**🆕 무료체험 이벤트(24h 맛보기, 2026-07-22 라이브)**: 신규 미승인 가입자에게 가입 후 24h 전기능 맛보기(담기·렌즈·제작소) + 완성 렌더 **1회** 상한. 만료/미승인=대기실(pending). SDD 5태스크·최종 opus 리뷰 READY TO MERGE·라이브(18d98b345).
- 표현: `customers.trial_ends_at`(epoch, NULL=창없음·하위호환). 설정 `trial_event_hours` 기본24. `access_level`: 미승인 AND now<trial_ends_at→full, 아니면 pending(2군데 손대는 설계: access_level + check_and_count).
- 렌더 1회: check_and_count가 체험 유저 render를 영구 `"trial"` 버킷으로 카운트(날짜리셋 안 됨). 실패환불=`render_charge_day="trial"` 센티넬로 계정@trial+전역@today 되돌림.
- ★admin 정교화: 이벤트 체험자는 `level='full'`이라 옛 대기명단 필터(`level==='pending'`)에서 빠져 **사장님이 승인 못 함** → 필터를 `approved_at==null`로 바꿔 미승인 체험자도 대기명단에 넣고 🎁체험중 배지. 브라우저 그라운딩 실측 확인.
- **후속(미완, 병합 후)**: 체험 1회 환불이 `run_mix_job` 초기단계 실패에만 걸림. `run_render`(최종 자막제거·ffmpeg)·`retype_mix_job` 실패엔 미환불→체험자 1회 소진 잠김(기존 유료와 동일·회귀아님). fix=그 실패경로에 trial 한정 환불 추가.

문서: `docs/superpowers/{specs,plans}/2026-07-21-회원승인-*` + `2026-07-22-무료체험이벤트-*`. 핸드오프: `handoff/회원승인.md`. 상위 유료게이트=[[project_유료게이트]]. 브랜드=[[project_brand_name_shottemtops]].
