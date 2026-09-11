---
name: reference_shorts_key_403_permission_denied_rotation
description: "제작소 대본실패 \"키소진\"의 진짜 원인=403/401 죽은키 로테이션 트랩. is_account_disabled_error가 403 못잡던 버그"
metadata: 
  node_type: memory
  type: reference
  originSessionId: b76a184d-b439-406e-8f38-196ebc16d4da
  modified: 2026-08-10T11:19:51.885Z
---

2026-08-10 실사고. 제작소(EDL/run_mix_job→script_extract)가 "대본 추출 실패/키 소진"으로 죽었다. **쿼터 소진(429)이 아니었다** — SHORTS Gemini 28키 중 **27개가 401 UNAUTHENTICATED / 403 PERMISSION_DENIED "service account is deleted or disabled"** 로 사망(구글이 서비스계정 무더기 비활성화). 살아있는 건 오래된 키 1개(idx 2)뿐.

**왜 "로테이션이 바로 안 됐나"(진짜 버그):**
- `script_extract`는 `comment_gen._current_key_and_idx()` = **항상 `live[0]`**(라운드로빈 아님)을 잡는다.
- `key_vault.is_account_disabled_error`가 `UNAUTHENTICATED`(401)만 잡고 **403 PERMISSION_DENIED는 못 잡았다**. 403 키는 어느 판정(daily_exhausted/quota/account_disabled)에도 안 걸려 **소진표시가 안 붙고** 조용히 빈 결과로 떨어짐 → 다음 job이 같은 죽은 `live[0]`을 또 잡음 → 매 job 실패.
- 게다가 `max_retries=4`뿐이라 죽은 키가 27개면 살아있는 키에 닿기 전에 재시도 소진.

**고친 것(커밋 9d8d653b7, main 라이브):**
1. `is_account_disabled_error`: 403 `PERMISSION_DENIED` + `'service account is deleted or disabled'` 추가. 401/403 둘 다 즉시 영구 소진표시 → 로테이션.
2. `script_extract.extract_script`: for→while. 죽은키(account_disabled) 우회 continue는 **attempt를 안 올린다** → 살아있는 키까지 걸어감. 풀 전멸 시 `key is None`→KeyPoolExhausted, 안전상한 `_walk_cap`.

**즉시 복구법(코드 아닌 상태파일):** `shopping_shorts/data/shorts_gemini_state.json`의 `exhausted`에 죽은 키 인덱스를 다 넣으면 `_current_key_and_idx`가 살아있는 키를 `live[0]`으로 잡는다. 생사 판정은 앱 SDK로: `comment_gen._client_for_key(k).models.generate_content(...)`. ★raw HTTP `?key=`는 이 `AQ.Ab8…`(서비스계정) 키에 401 나므로 판정 불가 — SDK 경로로 찔러야 실제 생사가 나온다.

**★두 키풀 함정(2026-08-10 2차 규명):** 제작소 한 job이 **서로 다른 두 키풀**을 쓴다 — ①소스 대본 **추출**(script_extract)=SHORTS 전용풀 / ②**대본 쓰기**(edit_plan `_vault_call`→`build_scene_first_plan`/`build_edit_plan`)=**위키 예비풀** `key_vault.get_live_keys_cascade("general")`. 이날 위키 4그룹(general/ingest/embed/briefing) 전부 라이브0이 돼 ②가 None→scene_first 후보0→build_edit_plan beats0→"EDL 비어있음". 추출(①)은 SHORTS idx2로 멀쩡했는데 대본쓰기만 죽어 "키소진"으로 오인. **고침(커밋 68fe87182)**: `_vault_call`이 위키풀 전멸 시 SHORTS 살아있는 키로 폴백(같은 lite 모델). 재실행 job f5fcaa2f55d8 → status=ready_for_review 실측 성공. ⚠️ mix_job은 성공해도 `error` 컬럼의 옛 실패텍스트가 안 지워짐 — 판정은 `status`로.

**태깅이 죽인 게 아니다(추적 결론):** 오늘 준 새 키 6개(`_33~_38`, idx22~27) 전부 **401 계정비활성**이지 429 쿼터소진이 아니다. 태깅 사용량과 무관 — 구글이 서비스계정을 무더기 비활성화. `AQ.Ab8…`(무료 서비스계정 키)를 짧은시간에 여러개 만들면 어뷰징으로 정지됨. 생존 `_3`(idx2)은 오래전 따로 만든 것. 해법=`AIza…` AI Studio 표준키.

**남은 근본문제:** `AQ.Ab8…` 서비스계정 키가 무더기로 죽는다(오전에 만든 6개도 몇시간만에 401/403). 살아남은 idx2가 어떤 발급방식인지 확인해 안 죽는 방식으로만 재발급 필요. 예약(SHORTS_PRODUCE_RESERVED=3)은 태거 잠식만 막지 키 사망은 못 막는다. 관련 [[project_gemini_key_ops_2026_08_04]] · [[reference_silent_fallback_pipeline_undo]]
