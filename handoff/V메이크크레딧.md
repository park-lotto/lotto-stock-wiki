# V메이크크레딧 — 회사 VMake 키 빌려주기 + 크레딧 한도 (관제 277, 2026-10-26)

## 무엇을
- 사장님: "강태경님한테 우리 v메이크 포인트 200크레딧 쓸 수 있게 / 매일 안 물어보게".
- 강태경 cid 412 (river7084). 본인 vmake 키(id 1144)도 있음.
- 회사 키(사장님 관리자 페이지 새 키 82705453…, 지문 a3802069…)를 412 계정에 추가(id 1222, 라벨 "지원 200크레딧").
  최신 키라 keys_for 가 먼저 씀(SINGLE_KEY 역순). 옛 키 219a88 행(1220)은 삭제.

## 장치(주인 함수 keyroute.lent_key_charge)
- 설정 lent_cap::<지문>=200, lent_used::<지문> 누적(store.lent_key_bump, UPDATE 한 줄 원자적).
- vmake_client.remove_subtitles 의 _consume_permission(과금 순간) 감싸기 → _lent_charge → clean_credit_estimate(초×2/4).
- used>=cap → 회원 쪽 그 키 status off(사장님 cid 0 행 제외) + ops_alert lent_key_cap. 라벨에 "남은 N".
- 다른 회원에게 빌려줄 때: 회사 키를 add_customer_key 로 넣고 lent_cap::<지문> 설정만 걸면 됨.
- ⚠️ 마지막 한 건은 한도 초과 가능(업체가 먼저 과금).

## ⏭ 다음
- 배포 후 412 실제 자막지우기 1건으로 lent_used 증가·라벨 갱신 라이브 실측 → 카드 277 기록.
- 배포 전(19:25~배포) 사용분은 자동 집계 안 됨 → 서버 로그로 확인해 lent_used 에 보탠다.
- 관리자 설정 vmake_api_key 는 아직 옛 키(219a88). 옛 키 폐기했으면 교체 필요(사장님 답 대기).

## 20:2x 실측
- 워커 12개 20:15 새 코드로 재시작(자막지우기는 워커 task=clean 에서 돈다).
- 배포 전 412 사용: 19:35 = 옛 키(219a88) 잔액 0(60002) → 과금 없음. 19:44 = 새 키 basic 27.7초 성공 → 56크레딧.
  배포된 lent_key_charge 로 수동 반영 → 56/200, 라벨 "지원 200크레딧 · 남은 144".
- ⏭ 다음 412 자막지우기 때 자동으로 늘어나는지 확인(서버 journal 에 "[lent_key]" 줄).
