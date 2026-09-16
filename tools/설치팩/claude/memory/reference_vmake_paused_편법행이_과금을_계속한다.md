---
name: reference_vmake_paused_편법행이_과금을_계속한다
description: 고객 키를 service='vmake_paused'로 바꿔 끄던 옛 편법 행이 남아 있으면 시스템이 "키 없음"으로 보고 본사 키로 돌며 포인트를 계속 깎는다
metadata:
  type: reference
---

`customer_keys.service`를 `vmake_paused`로 바꿔 키를 끄던 **옛 편법**이 남은 행은
`keys_for(SVC_VMAKE)`가 아예 못 찾는다 → "키 없음" 판정 → **본사 키**로 돌면서
`should_charge=True` → 매 호출 포인트 차감. 고객은 키를 등록해뒀다고 믿는데 계속 깎인다.

2026-08-25에 정식 스위치(`status='off'` + `/api/admin/customer/key_toggle`)를 만들었지만
**이미 이름이 바뀐 옛 행은 자동으로 안 돌아온다.** cid 57이 그 상태로 방치돼 잔액이
2.1P까지 닳고 자막제거가 통째로 막혔다(2026-08-26).

복구는 그 행을 `service='vmake', status='ok'`로 되돌리면 된다. 관리자 API에는
service명을 고치는 경로가 없어 DB UPDATE가 필요하다.

**검수는 서비스와 같은 환경에서 해라.** 그냥 SSH 셸에서 `keys_for`를 부르면
`BYOK_MASTER_KEY`가 없어 복호 실패가 뜨는데, 이건 키가 깨진 게 아니라 **env 미적용**이다.
`sudo bash -c 'cd <repo>; set -a; . /etc/shopping-shorts.env; set +a; PYTHONPATH=<repo> python3 <script>'`
로 확인하고, `app`은 임포트하지 마라(fastapi가 root python에 없다) — DB 경로를 직접 준다.
확인할 값은 셋: 복호된 키 개수 / `is_user` / `should_charge`.

관련: [[reference_shopping_shorts_admin_dual_identity]] · [[project_유료게이트]]
