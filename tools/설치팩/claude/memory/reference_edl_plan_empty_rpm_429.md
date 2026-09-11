---
name: reference_edl_plan_empty_rpm_429
description: "편집안(EDL)이 비었습니다 [생성기=legacy]"의 원인은 대개 Gemini 분당(RPM) 429 — 대기가 없어 키를 순식간에 태우고 포기했다
metadata:
  type: reference
---

2026-08-31 실사고(job 498afe4046a3, 13:28:01~02). `code=plan_empty sources=1 chars=234`.

**뿌리**: `edit_plan._vault_call`이 429를 만나면 `is_quota_error` → `continue`만 하고
**대기가 없었다**. 그때 살아있는 general 키가 4개뿐이라 **0.7초 안에 4키를 전부 429로
태우고 포기** → beats 0 → 운영사고. 그런데 그 429는 **분당(RPM)** 한도였다 —
20여 초만 쉬면 저절로 풀리는 것을 영구 실패로 보고한 셈이다.

**고침**: `_vault_call_once` + 라운드 래퍼. 마지막 사유가 분당 한도일 때만 22초 쉬고
최대 3라운드 재시도. 일일 소진·403 계정차단은 즉시 포기(무의미한 대기 금지).

**교훈 — 429를 뭉개지 마라.** 분당 한도는 쉬면 풀리고, 일일 소진·403은 안 풀린다.
같은 "429"로 묶어 처리하면 전자를 후자처럼 버린다.

**진단 순서**: 운영사고 문구만 보지 말고 워커 로그에서 `_vault_call: 키 N개를 다 돌았는데`
바로 위의 실제 에러 문자열을 봐라 — 거기에 `per minute` / `per day` / `PERMISSION_DENIED`가 갈려 있다.
키풀 실측은 서버에서 `keyroute.gemini_keys('general')` 길이로.

관련: [[reference_shorts_key_403_permission_denied_rotation]] · [[reference_gemini_key_rotation_never_ran]] · [[reference_server_ip_2026_08_31]]
