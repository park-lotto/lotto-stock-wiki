---
name: project_kis_token_sharing
description: KIS 앱키를 여러 PC·프로세스가 공유 → 토큰 서버측 무효화(EGW0012x) → 시세 전멸. kis_api에 자동재발급 패치함
metadata: 
  node_type: memory
  type: project
  originSessionId: e155a2ee-690c-4545-b6c6-86db585641ef
---

KIS OpenAPI 토큰은 **앱키당 1개만 유효**하고 새로 발급하면 기존 토큰이 서버측에서 죽는다. 이 프로젝트는 집PC·회사PC + 대시보드서버 + 예약작업(atom_pipeline·ingest 등)이 **같은 KIS_APP_KEY를 공유**해서, 한 곳이 토큰을 받으면 다른 곳 토큰이 EGW00123(만료)으로 거부된다. 또 발급은 **1분당 1회 제한**(초과 시 403).

증상: 딸깍 대시보드 섹터히트맵·ETF·순위가 "Failed to fetch"로 안 뜨고 PC가 느려짐. (코스피/코스닥은 localStorage SWR 캐시 때문에 떠 보여서 착시 — 서버가 죽거나 시세가 전멸해도 옛 데이터가 보임. 히트맵은 캐시 폴백 없어 바로 실패.)

**Why:** `scripts/kis_api.py _token()`이 로컬 만료시각(exp)만 믿고, KIS가 무효화한 토큰을 계속 재사용했음. EGW0012x를 만나도 재발급 안 함.

**How to apply:**
- 2026-06-30 패치: `_token(force=True)` 강제재발급 + `_authed_get` 헬퍼(EGW00121 무효/00122 누락/00123 만료 감지→재발급→1회 재시도) + issued_at 파일캐시(같은 PC 발급폭주 방지) + 재발급 실패 시 원응답 반환(크래시 방지). 현재 `get_price`·`get_daily_bars`에만 적용됨.
- **2026-07-04 업데이트**: get_index_price·get_overseas_price 등 나머지 KIS 엔드포인트도 전부 `_guarded_get`으로 통일 완료(raw `requests.get` 남은 곳 없음). `kiwoom_api`는 서버에 키 자체가 미등록이라 이 패턴과 무관 — 항상 실패로 취급됨.
- 근본해결 후보: **앱키를 PC별/프로세스별로 분리**하거나 단일 토큰 브로커 두기. 현재는 프로세스별 자동복구로 완화만 함.
- 진단 팁: `python -c "import sys;sys.path.insert(0,'scripts');import kis_api;print(kis_api.get_price('005930'))"` → price=0이거나 EGW00123 500이면 토큰 문제.
- **주의: 이 메모는 "토큰 무효화" 원인 전용.** KIS 서버 자체가 통째로 죽는(TCP 자체 불통) 다른 케이스는 [[project_kis_outage_2026_07_04]] 참조 — 거기서 서킷브레이커(`_down_until`/`_guarded_get`)로 근본 대응함.

관련: [[project_ttalkkak_dashboard]] (딸깍 대시보드 :8090) — market.html 시장패널은 localStorage SWR이라 서버 죽어도 화면 채워지는 착시 주의. [[project_kis_outage_2026_07_04]]
