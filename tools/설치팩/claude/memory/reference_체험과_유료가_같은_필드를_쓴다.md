---
name: reference_체험과_유료가_같은_필드를_쓴다
description: full_access_until은 체험 창이 아니라 입금 승인으로 주는 유료 이용 기간이다 — '체험 없애기'로 그 분기를 지우면 결제 고객이 랭킹만으로 떨어진다
metadata:
  type: reference
---

`customers.full_access_until`은 **`approve_customer(period_days, amount, method)`가
입금 승인 때 세우는 유료 이용 기간**이다. 이름이 체험처럼 보이지만 아니다.

2026-08-26 "체험중을 없애라" 작업에서 이걸 체험 창으로 오인해
`access_level`의 `free + full_access_until 미래 → full` 분기를 지웠다가 되돌렸다.
그대로 뒀으면 **돈 내고 승인받은 고객이 전부 ranking_only로 떨어졌다.**
테스트(`test_member_mgmt::test_approve_sets_start_end_and_payment`)가 잡아줬다.

**체험과 유료가 같은 필드를 공유한다.** 그래서 등급을 없앨 땐 필드를 읽는 쪽(판정)이
아니라 **결제 없이 그 필드를 채우는 쪽(부여 경로)** 을 막아야 한다. 부여 경로는 셋이었다:

1. `access_level`의 미승인 체험창(`trial_ends_at`) 분기 → `ranking_only`로 변경
2. `store.ack_customer`("확인" 버튼) — 남은 체험을 `full_access_until`로 **이관**하던 것 제거.
   ★진짜 범인. 버튼 한 번에 결제 0원 계정이 전기능이 됐다(cid 221~232 실측).
3. `_admin_set_plan`의 `free + days` — (구)전기능 체험 창. 폐지, 기간은 `plan="trial"`로.

**강등할 땐 `payments`에 기록이 없는 계정만 골라라.** 결제 고객을 같이 내리면 사고다.

관련: [[project_유료게이트]] · [[project_회원승인_화이트리스트]]
