---
name: project_shopping_shorts_code_audit
description: "쇼핑쇼츠 P0 보안·비용 점검 트랙 — P0 5건 라이브 반영 완료, 남은 항목은 회원가입 정책 결정 대기"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4e773050-3c7d-4319-b867-6492560ffe5c
---

쇼핑쇼츠 코드점검(지시서 `shopping_shorts/docs/OPUS_지시서_코드점검_2026-07-17.md`,
4개 리뷰 에이전트 종합). 트랙 `코드점검`, 인계 `handoff/코드점검.md`.

**2026-07-17 완료·라이브 반영**: P0-1(DASH_SECRET 하드코딩) · P0-2(프록시 SSRF 부분문자열
매칭) · P0-3(SSRF 가드 확산) · P0-5(최종렌더 중복예약=VMake 이중과금) · P0-6(Apify 실패전파).
회귀테스트 `tests/test_p0_security_guards.py` 25건.

**Why (다음 세션이 반복 안 하게)**:
- **지시서의 처방·심각도를 그대로 믿지 마라 — 실측으로 갈렸다.**
  ① P0-6 "FAILED면 즉시 포기"를 그대로 따르면 2026-07-09 계정소진 사고(도중 소진 →
     다음 토큰으로 복구)가 재발한다. run status만으론 '도중 소진'과 '입력오류'가 구별 불가.
     → 로테이션 **횟수 제한**(30run→2run)으로 절충. 두 사고를 다 막는다.
  ② P0-1은 "Critical 인증 전면 우회"로 적혀 있었으나 서버 `/etc/shopping-shorts.env`에
     `DASH_SECRET`이 이미 있었다 → 활성 취약점이 아닌 잠재 지뢰였다.
- 기준선 실패 11건은 내 변경 전부터 깨져 있고, `test_produce_*` 23건은 **플레이키**
  (단독 통과·전체 스위트에서 갈림). 회귀 판정은 개수가 아니라 **실패집합 차집합**으로 볼 것.

**How to apply**: 다음 착수는 **P0-7 프론트 저장형 XSS**(결정 불필요, `esc()`가 index.html:420에
이미 있고 outreach.html의 `ITEM_MAP[sc]` 패턴을 따르면 된다). 그 외 P0-4/P0-8은
**회원가입 정책(공개 유지 vs 초대제) 사장님 결정**이 선행돼야 한다. P1-4(디스크 고갈)가
Critical로 남아 있다. 관련: [[feedback_verify_with_real_data]]
