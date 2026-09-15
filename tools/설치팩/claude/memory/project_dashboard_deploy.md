---
name: project-dashboard-deploy
description: /market 대시보드 외부 배포(Lightsail+Apache+DuckDNS+SSL+로그인). 재배포·관리 방법
metadata: 
  node_type: memory
  type: project
  originSessionId: 81939269-3373-415b-b526-da1912c9f8ff
---

# 대시보드 지인배포 — https://stockbrain1.duckdns.org (2026-07-01 완료)

**Why:** 지인 몇 명이 폰/PC로 STOCK BRAIN 대시보드(수급빈집·강한섹터 빈집·컨센추이) 보게. 로그인 비공개.

## 접속
- URL: **https://stockbrain1.duckdns.org** (http→https 자동, Let's Encrypt 자동갱신)
- 로그인: **admin / 1234** (약함 — 강화 권장)

## 서버 구성 (Lightsail 3.39.179.148, ubuntu)
- 기존 서버가 **Apache로 80/443 점유(kmong 등)** → nginx 대신 **Apache 리버스프록시**로 공존
  - vhost: `/etc/apache2/sites-available/stockbrain.conf` (+certbot이 `stockbrain-le-ssl.conf` 생성) → ProxyPass to 127.0.0.1:8090
- 대시보드: **systemd `stockbrain`** 서비스 (venv `/home/ubuntu/venv`, WorkingDir `/home/ubuntu/lotto-stock-wiki`)
- 코드: `git clone park-lotto/lotto-stock-wiki`(공개). venv 의존성: fastapi uvicorn openpyxl requests python-dotenv
- **데이터**: taerini json은 repo커밋(pull로 옴). `raw/내 관심종목.xlsx`는 git미포함 → **scp로 수동 업로드 필요**

## 자격증명·키 (`/etc/stockbrain.env`, root:root 600, git 미포함)
- DASH_USER/DASH_PASS/DASH_SECRET(openssl rand -hex 32)
- **KIS_APP_KEY/SECRET = 서버 전용 새 앱키** (로컬과 별개! 같은키 공유하면 토큰 무효화로 양쪽 시세 끊김. [[project_kis_token_sharing]] 해결책이 이것)
- KIS_MODE=real

## 로그인 게이트 (dashboard/server.py)
- 미들웨어: DASH_PASS 있으면 인증 ON, 없으면 OFF(로컬 그대로). 쿠키+HMAC. /login·/api/login(body직접파싱, multipart불필요)·/healthz 예외

## 관리 명령 (SSH: ssh -i crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem ubuntu@3.39.179.148)
- 코드 갱신: `cd ~/lotto-stock-wiki && git pull && sudo systemctl restart stockbrain`
- 비번 변경: `/etc/stockbrain.env` 수정 → restart
- 로그: `journalctl -u stockbrain -f`
- 배포문서: repo `deploy/`(단, README는 nginx기준 — 실제는 Apache로 함)

## ⚠️ 운영 주의
- 접속자↑ → 서버 KIS 쿼터 소모(시세 끊길 수 있음). 지인 소수용.
- 수급빈집·태린이지표는 자산 — 공개범위 유의. [[project_service_direction]]

## ⚠️ 키움 API 서버 미등록 — market_flow 전체 KIS로 전환 (2026-07-02)
서버(`/etc/stockbrain.env`)에 **키움 API 키가 아예 없음**. `kiwoom_api.py`는 최신 REST(`api.kiwoom.com`, 리눅스도 가능)라 "리눅스라 안 됨"이 아니라 단순 키 미등록 — 근데 함수들이 실패해도 예외 삼키고 조용히 0/빈값 리턴해서 몇 시간째 화면 곳곳(코스피/코스닥 15분봉·투자자매매동향·프로그램매매·거래대금상위)이 비어있는 걸 스크린샷으로 하나씩 찾아 고침.
**KIS로 교체 완료**: `kis_api.get_index_minutebar`(KODEX ETF 프록시)/`get_market_investor`(TR FHPTJ04040000, inquire-investor-daily-by-market)/`get_program_trade`(TR FHPPG04600101, comp-program-trade-today)/`get_inquiry_rank`(TR FHPST01710000, volume-rank). 기존 kis_api에 있던 get_market_investor/get_program_trade는 **종목전용 TR을 지수코드로 잘못 호출**하던 버그였어서 TR_ID 자체를 교체함(KIS 공식 GitHub `koreainvestment/open-trading-api`의 `examples_llm/domestic_stock/` 예제로 정확한 TR_ID·파라미터 확인).
**재발 방지**: `dashboard/server.py` 부팅 시 `_check_datasource_availability()`가 `kiwoom_api._token()` 시도 → 실패하면 journalctl에 영향받는 기능 목록 출력. 새 기능을 kiwoom_api로 연결할 땐 반드시 서버에서 실데이터 확인할 것.
**미해결**: `get_stock_supply`(관심종목 개별 잠정수급, ka10059/ka90013)는 KIS `FHKST01010900`(inquire-investor, 종목코드 지정)로 대체 시도했지만 필드가 전부 빈 문자열 — 계정등급/구독 제한 가능성, 추가 조사 필요. `get_stock_candles`는 이미 KIS 폴백 있어서 안전.

## market_flow 그래프 "09:00부터 채워짐" 만들기 (2026-07-02, Opus)
사용자 요구: 코스피/코스닥 15분봉·투자자누적추이·프로그램 그래프가 **왼쪽=09:00 고정, 오른쪽=현재시각, 15:30까지 우측 진행**. Sonnet이 x축만 09:00~15:30 고정했으나 데이터가 09:00부터 없어서 라인이 붕 떠 보였음. 근본원인 2개:
1. **15분봉**: `get_minutebar`가 최근 30개(1분봉)만 → 09:00 미포함. 해결: `kis_api.get_intraday_series()` 신규 — KIS 분봉API(FHKST03010200)를 가장오래된시각으로 **페이지네이션**해 09:00까지 수집 후 15분 리샘플. `get_index_minutebar`가 이걸 사용. 오늘 즉시 09:00부터 완전 복구됨.
2. **투자자/프로그램**: KIS에 인트라데이 시계열 API 없음 → 1분폴링 누적이 유일한데 **서버 재시작마다 메모리 deque 소실**. 해결: `output/flow_history.json`에 매 폴링 원자적 저장(`_save_flow`)+부팅 시 오늘자면 복원(`_load_flow`). 재시작해도 09:00부터 이어짐(검증: 재시작 후 first_ts가 재시작이전값 유지 확인).
3. **프론트 축**(market.html): 축 왼쪽=09:00 고정, **오른쪽=현재(마지막 데이터) 시각 동적**(`_sessionEndMin`, 15:30 상한). renderMarketFlow가 매 렌더마다 0001/1001의 bars/investor/program 최신 시각으로 `_sessionEndMin` 갱신→`_sessionX`가 [540,_sessionEndMin]로 매핑→그래프가 폭을 꽉 채우며 시간 지날수록 오른쪽으로 늘어남(라벨도 11:16→…→15:30 동적). ⚠️축을 15:30 고정으로 하지 말 것(오른쪽이 비어 "붕 뜬" 것처럼 보여 사용자가 계속 지적함). `_seedOpen`으로 첫 실데이터가 09:05 이후면 09:00=0 기준점 앞에 붙임(누적순매수는 장시작 시 0이 정확). 15분봉 miniLine·투자자 invHistoryChart·프로그램 모두 실제 체결시각(t/ts) 사용. **글로벌지표 카드**(나스닥선물·유가·환율)는 24시간 등 각기 다른 시간대+bars에 타임스탬프 없음→시간라벨 아예 제거(gTimeRow="").
**매일 동작**: `_flow_day`가 날짜 바뀌면 09:00 첫 폴링에서 전날 데이터 clear→매일 새로 09:00부터 쌓임. 서버가 장 시작 전부터 계속 떠있으면 실데이터가 09:00부터 그대로(seed 불필요). 장중 재배포/재시작해도 영속화로 유지.
검증원칙: UI수정 후 `javascript_tool`로 SVG polyline points 좌표 직접 추출해 xFirst≈2(09:00) 확인 [[feedback_self_verify_before_reporting]].

## ⭐ 그래프 짧아졌다 복구 반복 = 지수 15분봉 소스 교체가 진짜 근본 (2026-07-02)
증상: 코스피/코스닥 15분봉이 13~14개→3개로 짧아졌다 ~10초뒤 복구 무한반복(어제부터). **진짜 원인**: `get_index_minutebar`가 KIS 분봉을 09:00까지 **15번 연속 페이지네이션**했는데, 중간에 순간실패(레이트/타임아웃)하면 최근 3개만 받고 끝남 → 3개도 비어있진 않아 last-good 통과. **근본조치**: `kis_api.get_index_minutebar`를 **네이버 fchart 단일호출**(`naver_api.minute_candles(proxy,15,count=500)` 오늘치 필터)로 교체. KODEX200(069500)/코스닥150(229200) 프록시. KIS 페이지네이션은 폴백. + `_serve_mf`에 bars 급감방어(직전 절반 미만이면 이전 bars 유지). ⚠️절대 KIS 15콜 페이지네이션으로 되돌리지 말 것.
**추가 재발원인 제거**: `scripts/.kis_token_cache.json`이 git 추적돼 서버 pull마다 충돌+저장소 stale토큰이 서버 유효토큰 덮어쓸 위험 → gitignore+추적제거.

## 그래프 사라짐 재발 방지 = last-good 서빙 (2026-07-02)
증상(어제부터 반복): 상단 ETF바·코스피/코스닥 15분봉·투자자·프로그램 그래프가 30초 갱신 중 가끔 사라졌다 ~10초 후 복구. 원인: KIS 순간 실패/타임아웃 시 서버가 빈·열화 데이터 반환→프론트가 공백 렌더→다음 갱신때 복구. **근본조치**: server.py `_serve_mf`+`_last_good_mf`/`_last_good_etf` — bars+가격 정상일 때만 캐시·last-good 갱신, 열화/예외 시 직전 정상응답 유지(글로벌·순위만 최신 덮어씀). 프론트도 빈 응답이면 렌더 스킵(이중). 이제 KIS가 순간 죽어도 그래프 안 사라짐. ⚠️KIS키 여러곳 공유 시 장기 토큰무효화는 last-good도 결국 stale — 서버 전용키 격리 유지 필수 [[project_kis_token_sharing]].

## 히트맵 큐레이션 도구 완성 (2026-07-02)
- **분할**: SPLIT_SECTORS(sector_heatmap)로 대섹터를 서브타일로 쪼갬 — 에너지신재생→수소·SOFC·태양광·풍력, 전선변압기→변압기·전선, AI보안양자→보안·양자, 우주방산→방산·우주, 로봇→삼성향/현대향/의료용/엑츄에이터 등(무명서브는 대섹터명). SURFACE와 함께 `_emit_sub_tiles`로 공용화.
- **타일 ✕삭제/복원**: 타일마다 ✕→hidden_sectors, undo토스트+편집탭 복원. **이름변경**: sector_custom.sector_rename{원본:새이름}→build가 disp필드로(name은 원본유지=키일관성). ✎모달에 이름변경칸.
- **세부섹터도 extra/removed 반영**: 초기버그(코인 종목추가 안됨)→`_emit_sub_tiles`에 오버레이 적용. 편집목록(api_sector_names)에 surfaced_sub_names 포함해야 복원가능.
- **스냅샷 백업/복원**: 저장할때마다 자동백업(server `_snapshot_sector_custom`, sc_TS_label.json 최근60개). `/api/sector_custom/snapshots|snapshot|restore`. 편집탭 "🕐백업·복원" 섹션(지금백업·시점복원, 복원전 현재도백업).
- ⚠️**sector_custom.json 추적해제**(gitignore+`git rm --cached`): 원래 git추적돼 배포시 사용자편집 덮일뻔. 이제 런타임데이터. **안전배포 필수절차**: `cp pipeline/sector_custom.json /tmp/sc_live.json` → `git checkout -- pipeline/sector_custom.json`(단일파일! 결합checkout은 안먹음) → `git pull` → `cp /tmp/sc_live.json 복원`. snapshots폴더도 gitignore.
- ⚠️**브랜치 계속 바뀜**: 다른 세션이 feat/person-brain→feat/person-brain-mvp 생성중. 커밋 전 `git branch --show-current` 확인, 배포브랜치=main이라 cherry-pick 필요.
- 원본마스터=`raw/내 관심종목.xlsx`(읽기전용, 5/27자) 절대안건드림. 편집은 전부 sector_custom.json 오버레이.

## 뉴스요약 쿼터·히트맵 세부테마 (2026-07-02)
- **AI요약 429 쿼터초과**: 프리워밍이 19섹터 계속 호출→무료쿼터 소진. 조치: `_summary_keys()`(대화형+INGEST 키 6개 총동원)+캐시 15→30분+gemini-2.5-flash 우선+프리워밍 사이클 5분·429백오프. 서버에 GEMINI_INGEST_KEY* 4개 추가함.
- **히트맵 세부테마 다꺼내기**(사용자 "일단 다 꺼내고 내가 편집"): `sector_heatmap.build_heatmap`이 SURFACE_THEME_PARENTS(반도체테마별·블랙테마원자재·코인/STO·메타버스6G·코로나·가구·정책·대왕고래)의 서브섹터를 전체탭 별도타일로 노출→39→73개. CXL·HBM·액침냉각·온디바이스AI·희토류·금·구리·코인·XR 등. 이미추출된 STO·광통신 중복제외, 편집탭 hidden 존중, 이름이 코드뿐인 깨진타일 제외. 사용자가 편집탭서 원하는것만 정리.
- ⚠️**브랜치 주의**: 로컬 repo가 한때 `feat/person-brain`(다른워크스트림 "사람브레인" 문서)로 바뀌어 커밋이 거기 감. **배포브랜치=main**이라 cherry-pick으로 main에 올려야 서버 pull됨. 커밋 전 `git branch --show-current` 확인.

## 종목 캔들 분봉 다일치 + 프로그램 스파이크 (2026-07-02)
**분봉**: KIS `inquire-time-itemchartprice`는 당일만+1콜 30개. 종목캔들 분봉이 오늘치만 나와 "훨씬 많아야" 요청. → `naver_api.minute_candles()` 신규: **네이버 fchart**(`fchart.stock.naver.com/sise.nhn?symbol=CODE&timeframe=minute&count=3000&requestType=0`, EUC-KR, `data="YYYYMMDDHHMM|o|h|l|c|v"` 형식이나 **분봉은 OHLC null·종가만**)를 tf분 버킷으로 리샘플해 OHLC 근사(open=첫종가,high=최대,low=최소,close=막종가). 다일치(6일~) 확보. server.py `api_stock_candles` 분봉 브랜치: fchart 다일치 + 오늘 버킷만 KIS 정밀 OHLC로 덮어씀, fchart 실패시 KIS 폴백. 프론트: 저장뷰 키 v1→v2(옛 좁은범위 폐기), 분봉 기본표시=최근 ~180봉(며칠치). 일/주/월봉=KIS `get_daily_ohlc` 500개(원래정상).
**프로그램/투자자 스파이크**: `get_program_trade`가 KIS 빈응답때 {합계:0} 반환→이력에 0 저장돼 급등스파이크(11:33 확인). `_poll_flow`에서 all-zero append 스킵 + `_build_market_flow_result` 서빙시 all-zero 필터.

## 글로벌 지표 데이터소스 (2026-07-02)
`scripts/global_api.py`. 나스닥선물/코스피선물/야간선물/유가(WTI)=esignal cache js(`https://esignal.co.kr/data/cache/{nq|kospif_day|kospif_ngt|oil}.js`, 실시간, `{open,data:[[ts,price]]}`). **원달러환율**: 기존 open.er-api.com은 일단위라 종일 1553/0.00% 고정 버그 → **네이버 하나은행 고시**(`https://api.stock.naver.com/marketindex/exchange/FX_USDKRW/prices?page=1&pageSize=3&category=exchange`, raw배열, closePrice/fluctuationsRatio/fluctuationsType.name)로 교체(인트라데이 갱신+전일종가대비 등락률). ⚠️`m.stock.naver.com/front-api/marketIndex/prices`는 pageSize작으면 400. KIS FX(FHKEF00104200)는 0 반환=미작동. global_api 수정은 서버재시작 필요하나 flow 영속화 있어 안전.

## 추가 기능 (2026-07-01 오후)
- **릴레이**: 서버 키움 없음 → 로컬 `scripts/push_flow.py`가 market_flow를 `/api/push_market_flow`(헤더 X-Push-Token, env PUSH_TOKEN)로 전송. server.py `SERVE_PUSHED=1`이면 전송분 서빙. ⚠️ push_flow는 장중 상시 실행 필요(작업스케줄러 등록 미완)
- **뉴스**: server 백그라운드 스레드 20분 → `/api/news_feed`. `/api/sector_detail?etf=|codes=`. NAVER_CLIENT_ID/SECRET 서버 env 등록됨. [[project_news_matching]]
- **콜아웃**: `/api/callout`(강한섹터×빈집 Top3 동결), `/api/callout_history`(성과). 프론트 미연결
- env 항목 총 10개(DASH_*3 + KIS_*3 + PUSH_TOKEN + SERVE_PUSHED + NAVER_*2)
