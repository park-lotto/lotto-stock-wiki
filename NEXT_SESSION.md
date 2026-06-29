# NEXT SESSION

날짜: 2026-06-29 (집PC)
세션 요약: KIS WebSocket 실시간 연동 구현

---

## ✅ 완료

- `scripts/kis_ws.py` 신규 생성 — KIS WebSocket 클라이언트
  - 코스피(H0UPCNT0/0001), 코스닥(H0UPCNT0/1001), 코스피200야간선물(H0ZFCNT0/101W9) 구독
  - 백그라운드 스레드 + 자동 재연결 + AES 복호화 지원
- `dashboard/server.py` 수정
  - 서버 시작 시 `kis_ws.start()` 자동 실행
  - 코스피/코스닥/야간선물: WebSocket 실시간값 우선, esignal 폴백
  - `/api/ws_status` 디버그 엔드포인트 추가

## 현재 상태

- WebSocket: connected=True, subscribed=[0001, 1001, 101W9] 확인
- 장중(09:00~15:30): 코스피/코스닥 실시간 0.1초 이내 예정
- 야간(22:30~ 미국 개장 후): 야간선물 실시간 예정
- 장외: esignal 15초 폴링 폴백 유지

## ⏳ 미결

- 내일 09:00 장 열리고 `/api/ws_status` live 데이터 실제 확인 필요
- 딸깍 장중 2단계 (한투 API 연동)
- 딸깍 마감 버튼
- NQ선물/WTI/원달러 실시간화 (Polygon.io $29/월 or KIS 해외선물 계좌 필요)

## 관련 파일

- `scripts/kis_ws.py` (신규)
- `dashboard/server.py` (수정)
- `dashboard/market.html`
