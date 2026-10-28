# 008 · 청소 크레딧 추정 위임·죽은 clean_base_preview 정리 (#16-②·#18-①)

- 쉬운 설명: 청소 크레딧 계산을 한 곳으로(화면 숫자와 실제 과금이 갈릴 여지 제거)
- 상태: 등록
- 등록: 2026-09-28 23:40
- 제보: 함수전수표
- 판단 주인: shopping_shorts/mix_pipeline.py:clean_charge_plan
- 분배: 
- 됐다의 기준: app._clean_credit_est 가 clean_charge_plan(mode=button)['credits'] 만 부름 · clean_base_preview 호출처 0 확인 뒤 제거
- 승인 필요: 미정(finish 가 diff 로 판정)
- 승인: 
- 병합: 
- 서버 반영: 
- 라이브 실측: 
- 재발: 

## 요청

(원문 없음)

## 이력

- 2026-09-28 23:40 등록
- 2026-10-01 00:38 쉬운 설명: 청소 크레딧 계산을 한 곳으로(화면 숫자와 실제 과금이 갈릴 여지 제거)
