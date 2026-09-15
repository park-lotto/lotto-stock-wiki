---
name: project-stockbrain-dashboard
description: SaaS 구독형 인사이트 대시보드 MVP 완성·배포. FastAPI:8080 + 검정골드 5탭. 다음=UI 변경
metadata: 
  node_type: memory
  type: project
  originSessionId: 567d161d-8ce0-4933-8eef-8b549da81628
---

크롤링봇 위에 얹은 **구독자 로그인형 SaaS 인사이트 대시보드** MVP 완성(2026-06-21). Kmong+유튜브 월구독 판매 목적. 정보 소비형(콘텐츠 생산 아님).

- **서버**: AWS Lightsail `ubuntu@3.39.179.148`, 코드 `/home/ubuntu/kmong/crawling_bot/` (SSH only, 키=C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem)
- **대시보드**: `api/dashboard_server.py`(FastAPI :8080) + dash_store/auth/feed/stats/briefing + `api/static/`(검정골드 HTML/JS, Chart.js). systemd `stockbrain-dash` 상시가동. 접속 http://3.39.179.148:8080 (Lightsail TCP 8080 Any IP 개방됨)
- **인증**: JWT, 아이디/PW + 텔레그램 매직링크, 구독 만료(expires_at) 차단. 임시 admin: `admin`/`stockbrain2026!`
- **수집 모델**: 합집합 수집 → 개인별 필터 발송 (이미 구현). 구독자가 키워드/채널 추가 시 자동 반영, 운영자 개입 0.
- **원칙 준수**: 기존 크롤링봇(main_v2)·원본 파일 일절 무수정, 전부 신규 파일. 서버 git init(.gitignore로 .env/users.db/세션 제외).
- **빌드 방식**: superpowers brainstorming→writing-plans→subagent-driven 13태스크, 30 테스트, opus 최종리뷰 통과.

**2026-06-22 — 피드/시그널 2서비스 분리 배포 완료:**
- **`/feed`**: 소스 단계별 Tier 1~5 잠금(뉴스→블로그→유튜브→텔레→리포트). 잠긴 탭 🔒. `dash_feed.filter_by_tier` + `feed_tier` 컬럼.
- **`/signal`**: 3단 깔때기(GO판정→섹터→종목 9점표). 독립권한 `signal_access`. `api/dash_signal.py`(스냅샷 로더) + `/api/signal` `require_signal` 게이팅. 프론트 `static/signal.html`·`signal.js`.
- 권한 컬럼 `feed_tier`·`signal_access`(가산 마이그레이션), 관리자 유저별 지정 UI(`/api/admin/users/{uid}/access`).
- 시그널 데이터 파이프: 로컬 `pipeline/build_signal_snapshot.py`(태린이 엑셀→`signal_snapshot.json`, 9점=빈집2+수출/컨센신고가/어닝서프 자동+판가/커플링/정책/D30 수동0) → `scripts/sync_signal.py` scp → 서버 읽기전용. 실데이터 363종목 검증.

**2026-06-22 추가 — 섹터태깅 + 매일 백테스팅:**
- 섹터: 루트 `sector_map.json`(515종목 마스터 종목명→섹터+코드) + 컨센파서 폴백 = build_signal_snapshot이 사용. 미상 42%(209/363 판별).
- 백테스트: `pipeline/backtest_signal.py` — 매일 score≥4 픽을 entry_close와 함께 `output/signal/picks_log.jsonl`(로컬, gitignore) 누적 → 최신 종가로 사후수익률 → 승률/평균 점수·빈집등급별 집계 → `backtest_summary.json`. 가격원=한국상대강도 종가시트(~150 대형주, 픽∩RS유니버스만 추적). 서버 `/api/signal/backtest` + /signal 성과표.
- 일일 runner `scripts/run_signal_daily.py`(스냅샷→백테스트→sync). **스케줄 미등록**(07:55 ingest 뒤 등록 예정).

**2026-06-22 대시보드 대확장 (서버 배포, 상세=docs/HANDOFF_대시보드_2026-06-22.md):**
- /feed 3컬럼(왼쪽 키워드 아코디언/가운데 다이제스트/오른쪽 한눈에) + 키워드 묶음 AI다이제스트(dash_digest.py qwen3 /no_think) + 클릭베이트·재료필터.
- **종목 통합카드**(dash_stock.py): 클릭→💡한줄AI판단+시그널9점+리포트목표가+뉴스(미등록종목은 구글뉴스 실시간). = "연결"=차별화 핵심.
- 텔레 명령봇: bot_commander_v2에 /go /signal /back 통합(notifiers/sig_commands.py). 별도봇 충돌정리.
- crawling_bot_data→서버 output/md 매시간 동기화(sync_crawl_to_server.py). keyword_news.py(서버 구글뉴스).
- 서버 systemd: stockbrain-dash·stockbrain-crawl(main_v2 nohup→systemd전환)·stockbrain-tgbot(mask).
- ⚠️ 서버에 **개발자 동시작업** 중 — 텔레 getUpdates 충돌. 만지기 전 조율.
- **전략결론(중요)**: 잘만들어짐≠잘됨(외부사용자0). 차별화해자2개 약함(①AI판단 generic=로또시각아님 ②백테스트검증0). **위키↔종목카드 AI판단 연결**하면 generic→로또시각=복제불가해자. 뉴스히스토리=중요종목(시그널픽)만. **검증=채널에 던지기**가 유일한 답.

**2026-06-22 STAGE1·2 실연동 완료:**
- STAGE1: `scripts/fetch_macro.py`(yfinance) — VIX·S&P·나스닥 → GO/경계/NO. 간밤이벤트=VIX급등/지수급락 정량감지. 오늘 라이브 GO(미장+1.5%,VIX16.4).
- STAGE2: 한국섹터 기준 미국 대장주 2~3개 매핑(`KOR_SECTOR_US_LEADERS`: 반도체=NVDA·MU·AVGO, 전력기기=GEV·ETN·VRT, 원전=CEG·VST·SMR 등) → 대장주 등락 평균=미국강세 → 미장강세×빈집 교집합이 STAGE2. 대장주 화면 노출.
- run_signal_daily = fetch_macro → build_snapshot → backtest → sync. 07:55 스케줄 등록됨.

**남은 작업**: ① Tier별 가격 ② 9점 수동4플래그(판가·커플링·정책·D30) 채우기 ③ 드릴다운 풀4섹션 ④ admin 비번 ⑤ 백테스트 가격원 확대(소형주) ⑥ 조선/방산 등 미국대장주 적합성 튜닝. 관련 [[project_taerini_pipeline]] [[project_mybox_automation]] [[project_투경_백테스팅]]

문서: docs/superpowers/specs|plans/2026-06-21-stockbrain-*. 관련 [[project_stockbrain_service]] [[project_crawling_pipeline]] [[reference_crawling_bot_data]]
