---
name: project
description: 판매용 티어 접근 게이트(체험→무료→pro)+구글OAuth. 라이브 배포됨. admin 백도어 교훈·deny-by-default·node flaky 주의
metadata: 
  node_type: memory
  type: project
  originSessionId: aadb7cc8-62ea-4e87-a1d0-4414d82775d0
  modified: 2026-07-19T12:58:10.104Z
---

쇼핑쇼츠(shoppingshorts.duckdns.org)를 유튜브로 팔려고 "레퍼런스 랭킹 맛보기(무료)→체험(전기능)→결제 시 pro" 티어 게이트를 구현·**라이브 배포 완료**(2026-07-19, 트랙 `유료게이트`, main 병합). 설계 `docs/superpowers/specs/2026-07-19-유료게이트-design.md`, 핸드오프 `handoff/유료게이트.md`(git추적=집PC서도 보임).

**구조**: 계정에 `plan(free/pro)`+`full_access_until`. 단일 판정 `app.access_level(cid)`: pro거나 체험중이면 full, 아니면 ranking_only. 사장님 cid0=영구 admin+full. 가입시 체험 자동시작(`trial_days` 설정, 기본7). 크레딧·체험일수는 `/admin` 설정값(하드코딩X).
- **게이트=deny-by-default 미들웨어**(app.py `_auth_guard`): ranking_only는 `_FREE_EXACT_GET`(GET /api/reference·thumb·video·/)만, 나머지 402. 새 유료 엔드포인트 깜빡해도 자동차단. `_FREE_EXACT_ANY`(로그인폼)·`_FREE_PREFIX`(/static/·/auth/google/).
- **비용방어**: 계정별 일일 크레딧 `check_and_count(cid,op)` op=lens/render/script + 전역상한+텔레알림. 렌즈·렌더 배선됨. **대본추출은 미배선(캐시미스 지점에만 카운트해야, 후속)**.
- **구글 OAuth**(라이브러리 없이): `/auth/google/login`(state쿠키 CSRF)→`/callback`(code→token→userinfo, id_token JWT검증 대신 우리 secret으로 token교환+userinfo. audience는 code-exchange라 내재). `get_or_create_by_google(sub)` 매칭키=google_sub(email 아님=탈취방지). 로그인페이지 다크카드+구글버튼, 운영자=비번 접이식.
- **키**: 서버 `/etc/shopping-shorts.env`에 `GOOGLE_CLIENT_ID`·`GOOGLE_CLIENT_SECRET`(콘솔 발급, redirect=`https://shoppingshorts.duckdns.org/auth/google/callback`). config.py에 GOOGLE_*.

**★교훈(Opus 리뷰 2회가 잡음)**:
1. **admin 백도어**: `_AUTH_ON=DASH_PASS or GOOGLE_CLIENT_ID`로 바꾸니, 구글만 켠 배포(DASH_PASS 빈값)서 `user=admin·pass=빈값`이 `compare_digest("","")=True`로 사장님 세션 탈취. → `/api/login` 레거시admin분기에 `if DASH_PASS and ...` 가드 필수. **라이브는 DASH_PASS 있어야 admin 접근됨**.
2. **fail-open**: DASH_PASS 빈값이면 인증·게이트 통째 OFF(전원 full). 시작 stderr 경고 추가.
3. **email_verified 미검증 이메일은 신뢰배제**(email=None), 매칭은 sub로.
4. **기존고객 무통보 강등 방지**: 마이그레이션(ALTER full_access_until) 첫 추가 시 기존 cid≠0에 유예체험 부여.
5. `access_level`이 요청마다 Store()→매요청 스키마 재마이그레이션(멱등)=P1 성능. 경로별 1회 가드는 **마이그레이션 의존 테스트를 깨서 보류**(소규모라 허용).

**★회귀 주의**: 전체 pytest 병렬 실행 시 `test_produce_*`·scene·pick_log 등 **node 서브프로세스 JS-슬라이스 테스트가 flaky 무더기 실패**(단독은 92개 전부 통과). finish 게이트는 기준선8 비교라 통과했음. flaky로 막히면 해당파일 단독 재실행으로 확인. [[reference_python_path_windows_stub]]

**다음(집PC)**: ①라이브 로그인 실측(구글=체험고객 / 운영자=비번=admin /admin) ②시각 그라운딩=ranking_only 계정으로 🔒메뉴·D-N배너·만료모달 육안 ③대본추출 크레딧 배선 ④결제자 나오면 /admin서 pro 승격. 되돌리기=revert. [[feedback_sdd_reviewer_model_opus]] [[reference_deploy_truth_branch_ssh]]
