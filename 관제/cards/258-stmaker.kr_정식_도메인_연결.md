# 258 · stmaker.kr 정식 도메인 연결

- 쉬운 설명: 
- 상태: 회귀
- 등록: 2026-10-23 16:45
- 제보: 사장님
- 판단 주인: shopping_shorts/app.py:_google_redirect_uri
- 분배: 도메인전환
- 됐다의 기준: https://stmaker.kr 접속 200·구글 로그인 성공, duckdns 로그인도 그대로
- 검사: url /login 로그인
- 승인 필요: 미정(finish 가 diff 로 판정)
- 승인: 
- 병합: 76e5444e12 2026-10-24 15:38 (도메인전환)
- 서버 반영: 
- 라이브 실측: 2026-10-24 18:05 ✅ stmaker.kr 실제 구글 로그인(parklotto21) → dash_auth 쿠키 stmaker.kr · /welcome 도착 / 콜백 stmaker.kr↔duckdns 각자 / 옛 /surl/O/3068 → 302 /pay/toss
- 재발: 

## 요청

(원문 없음)

## 이력

- 2026-10-23 16:45 등록 · 분배 → 도메인전환
- 2026-10-24 15:38 병합 76e5444e12 ← 트랙 도메인전환 (반영됨·미검증 — 라이브 실측 전)
- 2026-10-24 15:58 라이브 실측 시도: 서버 미반영(HEAD 에 76e5444e12 없음 — 자동배포 시간창 02~06시 또는 DEPLOY_NOW)
- 2026-10-24 16:41 라이브 실측: 2026-10-24 16:41 ❌ 실패 · url https://stmaker.kr/login → HTTP 0 · 병합 76e5444e12
- 2026-10-24 16:41 상태 병합 → 회귀
- 2026-10-24 17:50 검사: url /login 로그인
- 2026-10-24 17:50 라이브 실측: 2026-10-24 18:05 ✅ stmaker.kr 실제 구글 로그인(parklotto21) → dash_auth 쿠키 stmaker.kr · /welcome 도착 / 콜백 stmaker.kr↔duckdns 각자 / 옛 /surl/O/3068 → 302 /pay/toss
