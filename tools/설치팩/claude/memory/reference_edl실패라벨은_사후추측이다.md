---
name: reference_edl실패라벨은_사후추측이다
description: EDL 실패의 extract_empty/plan_empty는 사후 추측 라벨 — 진짜 원인은 그 시각 _vault_call 로그(429·401)에 있다
metadata:
  type: reference
---

2026-08-31 실사고. 김종룡(cid 193) job이 `extract_empty`(소스 대사 0자)로 떴다.
나는 라벨을 믿고 **"대사 없는 영상이라 안 된다"고 사장님께 잘못 보고**했다.
사장님이 "외국 영상만으로도 나는 되던데"라고 해서 다시 봤더니 —

실제 로그: `_vault_call: 키 4개를 다 돌았는데 결과 없음 → 429 + 401 UNAUTHENTICATED`.
**키가 다 튕긴 게 원인**이었다. 대사 없는 소스여도 확정 대본이 있으면 `scene_desc`로
정상 매칭된다(`_build_inventory`는 text가 비어도 seg_map을 만든다).

**뿌리**: `_edl_empty_reason`은 beats가 0이 된 **뒤에** 손에 있는 것(소스 글자수)만
보고 이름을 붙인다. 원인을 아는 게 아니라 **추측**한다. 소스 글자수가 0이면
무조건 `extract_empty`가 된다 — 진짜 원인이 키든 파싱이든 상관없이.

**판정 순서**: EDL 실패 제보를 받으면
1. 라벨을 믿지 말고 그 job의 **그 시각 `_vault_call` 로그**를 봐라
   `sudo journalctl --since '<시각>' | grep -a '<job_id>\|_vault_call'`
2. 429(분당/하루)·401(계정사망)·503(과부하)·파싱실패 중 무엇인지 가른다
3. 소스 글자수는 참고일 뿐이다

관련: [[reference_edl_plan_empty_rpm_429]] · [[reference_catchall_bucket_hides_regression]] · [[reference_나머지통_이름이_회귀를_숨긴다]]
