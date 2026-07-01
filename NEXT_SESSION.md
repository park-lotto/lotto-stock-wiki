# NEXT_SESSION

- **날짜**: 2026-07-01
- **PC**: DESKTOP-T8CB1GG (데스크탑)

## 오늘 한 것
1. **대시보드 외부 배포** → https://stockbrain1.duckdns.org (지인/멤버십·유튜브용)
   - Lightsail(3.39.179.148) + **Apache 리버스프록시**(기존 kmong과 공존) + DuckDNS + Let's Encrypt SSL
   - 로그인 게이트 **admin / 1234** (server.py 미들웨어, `/etc/stockbrain.env`)
   - **서버 전용 KIS 새 앱키**(로컬과 분리 → 토큰충돌 없음)
   - 상세·관리법: memory `project_dashboard_deploy.md`
2. **모바일 수정**: 반응형, 차트 탭(위임클릭), 캔들 KIS 폴백(일봉 500개), 지표패널 스크롤, no-cache
3. **로컬→서버 market_flow 릴레이** (서버 키움 없음): `scripts/push_flow.py` → `/api/push_market_flow`(SERVE_PUSHED). 지수15분봉·투자자·프로그램·거래대금
4. **뉴스 매칭 시스템** (핵심):
   - `scripts/news_feed.py`: 섹터=네이버검색API(테마+**must필수어**+호재랭킹+노이즈컷), 종목=네이버증권 종목뉴스API(키불필요)
   - 서버 백그라운드 스레드(20분) + `/api/news_feed`, `/api/sector_detail`
   - **📰 뉴스 탭**(강한섹터+빈집+뉴스), **ETF칩·히트맵타일 클릭 팝오버**(섹터뉴스+빈집+종목뉴스 펼침)
   - 매핑·튜닝: `pipeline/sector_news_keywords.json` (섹터별 q·must)
5. **오늘의 빈집 콜아웃 백엔드**(미완결): `/api/callout`, `/api/callout_history` (강한섹터×빈집 Top3 동결+성과추적) — **프론트 카드 미연결**

## ⚠️ 미완료 / 다음 할 것
- **[중요] push_flow.py 영구실행**: 지금 CLI 백그라운드로만 돎(세션 끝나면 멈춤). **Windows 작업 스케줄러**에 등록해야 장중 서버 데이터 계속 갱신됨 (`python scripts/push_flow.py`)
- **콜아웃 프론트 미연결**: 백엔드는 됨. "오늘의 빈집 Top3" 히어로 카드 UI + 성과탭 만들어야
- **장전 빈집 예측 엔진(큰 그림, 보류중)**: 지금 콜아웃은 "장중 이미 간 섹터×빈집"이라 취지와 다름. 원하는 것 = **9시 전** 예측(전일섹터힘+NXT장전반응+미국섹터+뉴스+**기준봉 축적**). 기준봉 정의는 "지금 복잡하니 보류"
- **뉴스 옵션**: 히트맵 커스텀타일 섹터뉴스(타일명 검색), opendart 공시 결합
- 오매칭 더 있으면 `sector_news_keywords.json`의 must에 종목명/테마어 추가

## 서버 관리 (SSH)
`ssh -i /c/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem ubuntu@3.39.179.148`
코드갱신: `cd ~/lotto-stock-wiki && git pull && sudo systemctl restart stockbrain`
