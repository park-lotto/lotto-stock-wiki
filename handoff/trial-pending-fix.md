# trial-pending-fix

## 한 일

- 운영 회원 cid 475가 `plan=trial`인데도 `approved_at=NULL` 분기에 먼저 걸려 `pending`이 되는 현상을 확인했다.
- 운영 DB에서 해당 회원의 `trial_ends_at`을 이미 설정된 `full_access_until`과 맞춰 즉시 `ranking_only`로 복구했다. `approved_at`과 결제 기록은 변경하지 않았다.
- `access_level()`에서 관리자 지정 `plan=trial`을 미승인 가입 체험 판정보다 먼저 처리하도록 수정했다.
- 만료된 미승인 회원을 관리자 API로 체험판 지정하는 회귀 테스트를 추가했다.

## 확인

- `py -m pytest shopping_shorts/tests/test_paywall_admin.py shopping_shorts/tests/test_paywall_access.py shopping_shorts/tests/test_trial_event.py -q`
- 결과: 38 passed

## 다음 할 일

- main 병합·서버 반영 후 cid 475의 라이브 등급이 `ranking_only`인지 다시 확인한다.
