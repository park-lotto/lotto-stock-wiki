---
name: project_kis_outage_2026_07_04
description: 2026-07-04 KIS 오픈API 서버 자체장애(주말탓 아님) — kis_api.py에 서킷브레이커+naver_api 폴백을 히트맵·ETF바·관심종목·차트·리포트탑픽 전체에 배선해 근본 해결
metadata: 
  node_type: memory
  type: project
  originSessionId: bef0f865-73ea-4703-b022-c6f64924acb0
---

## 무슨 일이었나
2026-07-04(토) 대시보드(stockbrain1.duckdns.org) 히트맵·ETF바·관심종목·종목차트가 전부 ±0.00%/빈값으로 나옴.
1차 진단(Sonnet)은 "주말이라 KIS가 원래 안 됨"이었는데 **틀렸음** — 사용자가 반박해서 Opus로 재진단.

**진짜 원인**: KIS 오픈API 서버(`openapi.koreainvestment.com:9443`) 자체가 **2026-07-03(금) 15:47부터** 완전 불통
(TCP 자체가 refused/timeout — 토큰 문제 아님). 3개 독립 네트워크(서버·해외샌드박스·사용자 집)에서 동일하게 KIS API만
막히고 KIS 일반 홈페이지는 정상 — IP밴·우리쪽 문제 다 아니고 KIS 서버 인프라 이벤트 확정.
**"지난 토요일엔 이런 에러 없었다"는 비교는 무효** — 그 에러를 로그로 남기는 `kis_ws.py` 자체가 2026-06-29에야
추가돼서 그 전 주 데이터가 아예 없었음. 진짜 주말 정책 여부와 무관한 1회성(추정) 서버측 장애.

## 근본 수정 — kis_api.py 서킷브레이커 (가장 중요)
`scripts/kis_api.py`에 `_down_until`/`_raise_if_down`/`_mark_down`/`_guarded_get` 추가. 연결실패 1번 확인되면
20초간 재시도 없이 즉시 예외 → 기존 호출부의 `except Exception`이 그대로 받아 빈값 처리. **이게 없으면 KIS가
죽을 때마다 이 모듈을 쓰는 모든 API(관심종목·차트·히트맵·시장흐름 등)가 8~90초씩 통째로 멈춘다** —
실제로 관심종목 저장이 "안 되는 것처럼" 보이던 사고도 이 멈춤 때문이었음(→ [[feedback_deploy_discipline_during_incident]]).
`_authed_get`·`_token`·그리고 raw `requests.get` 쓰던 나머지 함수들(get_overseas_price·get_night_futures_price·
get_usdkrw·get_inquiry_rank·get_night_futures_minutebar·get_minutebar·_minutebar_page·get_market_investor·
get_program_trade·get_program_trade_series·get_index_price) 전부 `_guarded_get`으로 통일.

## 폴백 — naver_api.py (신선도용, 인증 불필요, KIS와 별개 데이터소스)
`scripts/naver_api.py`에 `daily_candles(code)`(일봉), `last_session(code)`/`last_session_batch(codes)`(마지막 거래일
세션을 등락률+스파크라인으로 재구성, 직전 거래일 종가 대비 계산) 추가. 배선한 곳:
- `dashboard/server.py` `/api/etf_bar` — last-good 없으면 네이버로 등락률·스파크라인 재구성(평소 화면과 동일하게 보임)
- `dashboard/server.py` `/api/watchlist` — 시세+잠정수급 둘 다 가드
- `dashboard/server.py` `/api/stock_candles` — tf=D일 때 KIS도 죽어있으면 네이버 일봉
- `scripts/sector_heatmap.py` `build_heatmap()` — 전종목 price=0 전멸 감지되면 네이버 배치로 통째 교체
- `dashboard/briefing_collect.py` `recent_topick_mentions` — 오늘자 없으면(주말 등) 최근 거래일로 폴백
- `dashboard/server.py` `/api/watchlist` POST — 저장 전 `.bak` 백업(재발 방지, 위 사고 대응)

## 확인 안 된 것 / 남은 문제
`stockbrain.service`가 SIGTERM에 KIS_WS 스레드가 안 죽어서 90초 후 SIGKILL→자동재시작을 반복하는 버그는
**안 고침**(KIS 복구되면 덜 두드러지겠지만 근본 원인 남아있음). 재발하면 `journalctl -u stockbrain.service`에서
"State 'stop-sigterm' timed out" 패턴 확인.

관련: [[project_kis_token_sharing]](다른 원인·같은 파일), [[feedback_deploy_discipline_during_incident]]
