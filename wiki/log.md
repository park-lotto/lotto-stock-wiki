- 2026-07-07 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-07-07.md
- 2026-07-06 — [구현·배포] **대시보드 실장 튜닝 대량**(DESKTOP): ①배포인프라 정비 — "장시작 차트깨짐 fix가 안 먹힘" 근본원인=fix를 feat브랜치에 커밋(서버는 main만 추적) → main통일·feat은퇴(archive)·CRLF봉인(.gitattributes)·**자동배포크론(auto_deploy.sh 3분, push만하면 자동반영)**·서버고아커밋 복구. ②뉴스타임라인 대개편 — 2타임라인분리(시장상황/뉴스이슈)·**강한텔레원문 직접노출(_surface_strong_news)**·관심종목매칭(부분문자열오탐제거)·중복제거(같은종목통합)·**중요도=상승기여도(맨앞🔥고정)**·출처없는 ai_brief제외·당일필터. ③차트 등락률%표시·ESC닫기·우/하엣지리사이즈. 미완=순환매감지기(섹터맵+Claude+트리거·급등게이트)·P1공시형enrich(DART 계약÷매출, 기가비스실데이터확인). 메모리 `reference_deploy_truth_branch_ssh`·`project_news_timeline_enrich`. 상세=NEXT_SESSION.md 최신세션.
- 2026-07-04 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·쏠림지수·액티브ETF·일정·투자아이디어 → ingest_report_2026-07-04.md
- 2026-07-04 — [구현] **YT 대시보드 ①기획단계 Task5 완료+실브라우저 버그 2건 수정**(DESKTOP): `/yt`(hot_clips 실시간탐지+SSE 기획생성)는 다른/자동 세션이 이미 커밋(b2f6c702), 실브라우저+실API 검증 중 진짜 버그 2건 발견 — ① YouTube 제목 HTML엔티티(`&#39;`)가 Gemini 프롬프트까지 오염(html.unescape로 수정), ② 그 수정으로 표면화된 2차버그: 디코딩된 apostrophe가 encodeURIComponent 미이스케이프로 onclick 속성 깨뜨려 "담기" 버튼 SyntaxError로 조용히 죽음(인덱스기반 조회로 수정). 19/19 테스트 통과, main push 완료(5b8d5744). 서버배포는 안 함. 상세=NEXT_SESSION.md 세션D.
- 2026-07-03 — [구현] **텔레그램 뉴스릴레이 파이프라인 실전검증 + 일일검증 에이전트 신설 + 대시보드UI 3건**(DESKTOP): 신규 4채널(주식픽 등) 실채널 데이터 검증으로 진짜 버그 5개 발견·수정(중복게시·언론약칭·stock_sector_map자기참조오탐·섹터키워드오탐2건). 크롤주기 하루5번→15분마다 상향+전용동기화스크립트. 사용자 요청으로 daily_verify.py(크롤신선도+pytest회귀+서비스상태) 신설·크론등록·배포, 실행검증 중 "체커자체가 조용히 무력화되는" 심각버그 2개 추가발견(sys.executable 등). 대시보드: 종목등락률+팝오버확장, KIS500재시도, Gemini→STOCK BRAIN 브랜딩, AI요약 유튜브프레이밍제거, **텔레그램뉴스 date필드누락으로 AI요약 "오늘자만"필터에서 통째로 빠지던 버그**(세션 마지막 발견). 전부 배포·검증 완료. 상세=NEXT_SESSION.md 세션B.
- 2026-07-03 — [구현] **pytest 수집버그 4건 수정 + 브랜드 스타일 인포그래픽 3종 확정**: 일일검증 텔레알림 fail/ok 오간 원인 = pytest collection 에러(수동스크립트 오수집·pandas 미설치·sys.path 누락)로 전체 테스트가 통째로 실패 처리되던 것 → conftest.py 수정+pandas 설치로 해결(7 failed, 446 passed로 정상화). 골루프 인포그래픽에 `brand=` 파라미터 추가(기존엔 커스텀 스타일도 항상 라임그린 HUD랑 섞이는 버그) — `claude`/`claude_terminal`/`clay` 3종 프리셋 실제 생성·텔레확인 완료(clay는 clay.com 실이미지 3장을 노트북소스로 추가해서 성공, secondary계정 활용). 상세=NEXT_SESSION.md, `project_brand_style_infographics` 메모리.
- 2026-07-03 — [구현] **영상제작 대시보드 ①기획단계 Task 1-4 완료(SDD, main 직접)**: 브레인스토밍→설계→계획(5task)→구현. `/yt` 독립페이지, 기존 6단계 CLI파이프라인 재사용, "터진영상" 위젯(ViewTrap 실측근거로 채널자체평균대비% 방식 확정)+SSE 진행상황. Task1 hot_clips.py(자기영상제외 평균계산 버그 2회 재발견→근본수정, 12/12테스트), Task2 `/yt/hot_clips`(무관코드 삭제사고 리뷰가 복구), Task3 plan_stage.py(계획서의 import패턴 자체가 깨진코드였음을 리뷰가 발견), Task4 `/yt/generate_plan`(**다른 세션이 동시에 같은 기능을 무관한 커밋에 섞어넣은 것 발견** — 코드는 검증완료·Approved, 동시세션 조율 이슈로 기록). Task5(yt.html+GET /yt)는 다음세션. git push 완료(서버배포는 안함, 미완성기능). 상세=NEXT_SESSION.md.
- 2026-07-03 — [구현] **골루프 인포그래픽 카드 완성+서버배포+실전검증**: 클로드식 그라데이션 히어로 제거+NotebookLM 인포그래픽 병행발송(5태스크, main 병합 5aa88d8e). Gemini 나노바나나 8키 전량 429(무료티어 구조적제한) 실측 확인 후 결정. 실전검증 성공(라임그린 HUD 스타일, 텔레그램 전송까지 확인, 151초). **서버 인프라 3건 발견·수정**: nlm CLI 미설치→설치, 서버 스왑 0바이트→2GB 추가(재부팅 2회 유발), nlm PATH 재부팅시 소실→/usr/local/bin 심볼릭링크. **미해결**: NotebookLM 인포그래픽 생성만 이 서버에서 rate limit 추정(노트북4·스타일2·계정2 전부 시도, 일반기능은 정상). 다른 세션이 `/vnc-login/` 영구페이지 이미 구축한 것 발견(중복작업 가능성, 다음세션 조율 필요). GOAL_LOOP_ENABLED 여전히 OFF. 상세=NEXT_SESSION.md, `project_goal_loop_orchestrator` 메모리.
- 2026-07-03 — [ingest] **엔터 섹터 갱신(WebSearch, 5주 공백 해소)**: `wiki/L5_섹터/엔터/엔터index.md` 오늘의 한줄·일일분위기로그·지속영향이벤트 업데이트. BTS 완전체 컴백(3월 앨범)+월드투어 발표 후 하이브 주가 급등락(1월+4%→3월-14~24%) 이어 최근 "극단적 저평가" 반등(에스엠+8%·하이브+6%) 확인, 4대 기획사 2026 합산 영업이익 컨센서스 +6% 상향에도 밸류에이션 눌림 국면 반영. 대장주 현황·기술적 분위기는 price ingest 필요라 미반영.
- 2026-07-03 — [ingest] **미용 섹터 갱신(WebSearch, 5주 공백 해소)**: `wiki/L5_섹터/미용/미용index.md` 오늘의 한줄·일일분위기로그·지속영향이벤트 업데이트. 상반기 화장품 수출 70억달러(+27.3%YoY) 역대 최대·6월만 +42.5% 확인+반영, 미국 비중 20%↑ 최대시장 굳히기+유럽(러·영·폴·네덜란드) 급증 지속, 미용기기 3사(파마리서치·클래시스·에이피알) 2026년 영업이익 +32~52% 전망에 클래시스 미국 직접진출(초음파·고주파 동시론칭)을 신규 이벤트로 추가. 대장주 현황·기술적 분위기는 price ingest 필요라 미반영.
- 2026-07-03 — [ingest] **원전 섹터 갱신(WebSearch, 5주 공백 해소)**: `wiki/L5_섹터/원전/원전index.md` 오늘의 한줄·일일분위기로그 업데이트. 체코 두코바니 5·6호기 주기기 본계약 체결 완료(2025-12, 5.6조, 두산에너빌리티) 확인+반영, 2026 수주전망 14.3조 상향(원자력5.8조+가스터빈5.3조), 美 대형원전·SMR 수주 확대 모멘텀 지속. 대장주 현황·기술적 분위기는 price ingest 필요라 미반영.
- 2026-07-03 — [정리] **건강검진 후속조치 완료**: ① `raw/캡처본`(오타폴더, 파일1개) → `raw/캡쳐본`(정본)으로 이동 후 폴더 삭제. ② 원전·엔터·미용 3개 섹터 5주 공백 해소(WebSearch 갱신, 별도 로그 참조). ③ `BRAIN_INDEX.md`의 L1~L6 인덱스 링크 6개 전부 깨져있던 것 발견·수정 — `{레이어}/index.md`가 아니라 실제로는 `{레이어}/{한글이름}index.md` 명명규칙이라 전부 불일치했음. ④ `wiki/stock_현대백화점_20260507.md`(루트 고아 파일, TP리비전 표만 있고 헤더 없음)를 `L5_섹터/소비내수/stock/stock_현대백화점.md`로 정식 이전+표준 헤더(탑픽스코어·종합스토리 틀) 추가.
- 2026-07-03 — [건강검진] **위키 종합검진**: ① ingest 커버리지 — raw 크롤은 07-03까지 정상 유입인데 **위키 콘텐츠(섹터/종목 페이지) ingest 로그가 07-01 이후 없음**(대시보드 개발에 밀려 위키 반영 정체). ② 공백 페이지 — `L5_섹터/{원전,엔터,미용}` 5주+(5/27~) 무업데이트, 원전은 오늘도 히트맵에서 활발히 움직이는데 공백. ③ 고아 페이지 — BRAIN_INDEX.md가 참조하는 `wiki/L5_섹터/index.md` 실존 안 함(깨진 링크), `wiki/stock_현대백화점_20260507.md`가 정위치(L5_섹터/*/stock/) 아닌 루트에 혼자 떨어져 있음. ④ 영상 주제 3개 — "반도체·로봇 동반급등 원인"/"전선·변압기 진짜 대장주"/"HBM 데이터센터 TP상향 종목". ⑤ 정리 후보 — `raw/캡처본`(오타 폴더, 파일1개)을 `raw/캡쳐본`(정본,560개)으로 합치고 삭제 권장. 파일 삭제·이동은 사용자 확인 후 진행 예정.
- 2026-07-03 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·쏠림지수·액티브ETF·일정·투자아이디어 → ingest_report_2026-07-03.md
- 2026-07-02 — [구현] **원자추출 프로파일 재설계 10태스크 완료**(회사PC): structured_fields컬럼+유튜브 데이트레이딩프로필+리포트/텔레그램 구조화저장+insight유실복구(leading_sectors/noise_ratio/quote)+슬롯유실 정적체크+채널온보딩스킬(`.agents/skills/channel-onboard/`). subagent-driven-development, 리뷰과정에서 quote슬롯유실 패턴 3회 반복발견→선제수정. **사고발견·복구**: 동시세션이 워킹트리에서 브랜치전환해서 커밋5개가 main아닌 다른브랜치에 쌓였던걸 최종검증중 발견→cherry-pick으로 main 복구, 153테스트 통과. 이어서 텔레그램 2채널(태린이아빠 주식투자/요약하는 고잉) 온보딩 착수 — 태린이아빠는 실시간포지션추적+리포트릴레이 혼합이라 신규프로필 필요, 질문지 v2까지 Gemini시험(daily_prep_note/position_changes 슬롯). **`pipeline/people`(사람브레인) 프로젝트와 개념적으로 겹침 발견** — 이 신규슬롯을 사람브레인 데이터소스로 연결할지 결정 필요(다음세션). 상세=NEXT_SESSION.md.
- 2026-07-02 — [구현] **사람 브레인(Person Brain) — 채널 사고 복제 시스템 완성**: 브레인스토밍→설계→계획→서브에이전트 구현으로 로드맵 A~E 전 단계 완성. `pipeline/people/`(registry·people_query·build_brain·brain_view·funnel·rs_data·sortino_data·track·persona) + 대시보드 🧠브레인탭(:8090/brain, 2축=데이터·통계/인사이트·사고복제). **질의엔진**(persona: "이 종목/시장 태린이라면?" → 판정+[데이터]/[추론]/[발언] 라벨, LLM없이 결정론적), **종목선정 퍼널**(빈집×컨센×주도주RS×소라티노 4축, 적중률0.15→0.25), **오늘의 루틴 재구성**, **검증+추세+자동스냅샷**(atom_pipeline STEP7), **3버킷**(시장인사이트27·방법·재료검색), **2호채널 pokara61**(발언만으로 복제=범용스키마 검증). **다운로드 근본수정**: download_mybox.mjs python3(Store스텁)→실제인터프리터 자동탐색, 소라티노/RS 파일 복구. tests 46/46. 상세=`project_person_brain` 메모리·NEXT_SESSION.md. (핵심발견: 스탠스=stance_key, 층=asset_level; RS=주도주찾기시트, 소라티노=etf상대강도데이터.xlsx)
- 2026-07-02 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·쏠림지수·액티브ETF·일정·투자아이디어 → ingest_report_2026-07-02.md
- 2026-07-01 — [구현] **API에러 텔레 알림+뉴스 교차키워드 크롤+텔레6월 복구**(집PC): atomizer._tg_alert(키로테이션⚠️/전소진🚨/RuntimeError❌), news_keywords.json(A×B 교차키워드·광고필터·하루2회 다이제스트), report_relay 외국주 드롭버그 수정(telegram_questionnaire.py), 요약하는고잉 insight 재분류, 6월 60파일→339원자 복구. Gemini Omni 오디오I/O 활용 방향 논의.
- 2026-07-01 — [구현] **크롤+인제스트 슬롯 스케줄 개편**(집PC): ① 서버 config.yaml 크롤주기 변경 — 텔레·유튜브(영상+게시물)·블로그=`0 8,12,15,18,21`(기존 텔레 */30, 유튜브·블로그 9시→8시), 리포트=`0 8,11`(기존 7,10 평일→매일), 뉴스 유지. crawlingbot.service 재시작→새 스케줄 로드 확인. ② 결합방식=서버크롤 독립+로컬 인제스트(PC꺼져도 크롤됨). `scripts/slot_ingest.py` 신규(--cats telegram,youtube,blog,report / sync_crawling --overwrite로 raw동기화→카테고리별 원자화, 텔레는 --force-date로 당일 append분 재처리 / **완료 후 텔레 보고**: 신규원자 소스별·섹터TOP5·종목TOP6 요약 발송, --no-report로 생략). `sync_crawling.py`에 --overwrite 추가. ③ Windows작업 2개 등록: `LottoStock_SlotIngest_Main`(텔레·유튜브·블로그, 8:10·12:10·15:10·18:10·21:10), `LottoStock_SlotIngest_Report`(8:40·11:10, DB충돌 시차). 기존 07:00 atom_pipeline(뉴스·엑셀·위키반영)은 유지. **미결: 딸깍 서버 market_flow 14워커 thundering-herd 버스트 미수정(사용자 보류).**
- 2026-07-01 — [수정] **텔레 크롤 hang 영구방지**(집PC): 서버 `crawlers/telegram_crawler.py`에 3중 타임아웃 — ①채널당 40초(asyncio.wait_for로 _collect_channel 래핑, 초과 시 그 채널만 건너뛰고 계속) ②연결(client.start) 30초 ③전체 900초 하드캡(_guarded). 원인=get_entity/iter_messages/download_media에 타임아웃 없어 한 채널 먹통→전체 hang→APScheduler max_instances=1로 이후 전부 skip(06-30 22:30~11h 공백 사례). 백업 후 패치·py_compile OK·서비스 재시작·크롤 완주 검증(count=4).
- 2026-07-01 — [복구] **텔레 세션 재로그인 + 크롤 hang 해소**(집PC): 어제 18:20 세션 무효화→tg_login.py로 재로그인(빅팜). 06-30 22:30 "하나차이나" 수집 중 hang→APScheduler max_instances=1로 23:00~09:30 전부 skip(11시간 공백). crawlingbot.service 재시작으로 복구(09:38 정상). 딸깍 대시보드 CPU폭주(구 인스턴스 busy-loop 25446s 누적)도 재시작으로 해소.
- 2026-07-01 — Excel ingest 완료:  → ingest_report_2026-07-01.md
- 2026-06-30 — [ingest] **오후 크롤+원자 ingest(블로그·유튜브·텔레)**(집PC): 서버크롤 재트리거(신규0=스케줄러가 이미 수집)→sync_crawling 140개 raw/동기화→원자ingest. 블로그8개=45생성, 유튜브3편=37생성, 텔레PM2채널=13생성(오전13채널 기처리). DB 오늘 총 268원자. **버그2건 근본수정**: ① `telegram_ingest.ingest_telegram` — 한 채널이 여러 섹터 다루면 extract_telegram이 questionnaire **list** 반환 → 단일 dict 가정 크래시(한화철강). list 정규화+서브별 ID salt(INSERT OR REPLACE 덮어쓰기 방지), 단일dict 경로 하위호환. ② `post_questionnaire.post_trust` — blog_registry가 `{trust,url}` dict인데 dict 통째 반환 → `_strength`에서 unhashable. dict면 trust필드 추출(문자열 registry 호환). **남은일: 텔레 Telethon 세션 인증만료(.telegram_session 무효화)→재로그인(폰+코드) 필요, 다음 크롤부터 영향. Gemini키·블로그·유튜브는 정상.**
- 2026-06-30 — [디버그] **딸깍 대시보드 버그 5건 근본수정**(집PC): 캡쳐 진단으로 순차 수정. ① **히트맵 빈화면**: KIS 시세가 EGW00123(만료토큰) 500 → 583종목 전부 실패. `kis_api._token()`이 로컬 exp만 믿고 서버측 무효화 토큰(여러PC·프로세스 앱키 공유) 재사용이 원인 → `_token(force)`+`_authed_get`(EGW00121/122/123 감지→재발급→재시도)+issued_at 파일캐시+우아처리. ② **섹터 0.00% 깜빡**: KIS 초당한도 **EGW00201** 초과(583종목 동시) → 전역 레이트게이트 15건/초 추가 → 2회 연속 583/583 안정. ③ **30초 새로고침 멈춤**: 클라 180초 메모리캐시가 자동갱신 단락 → `autoRefreshActive()`로 캐시우회+prewarm sleep 60→15초(체감 ~55초). ④ **글로벌 환율 멈춤**: yfinance USDKRW=X 'delisted' → `global_api.get_usdkrw` 무료 FX API(open.er-api.com)로 교체(esignal엔 환율 없음 확인). NQ·코스피·WTI는 원래 esignal 라이브였음. ⑤ **순위 가격 불일치**(인기검색=네이버 vs 거래대금=키움): `_enrich_rank_prices`로 둘 다 KIS 시세로 통일 → 공통5종목 불일치 0. 검증=전부 실측. 변경=kis_api.py·global_api.py·market.html·server.py(미커밋). **남은일: 지수값 3중소스 스케일불일치(키움137k/KIS8.4k/WS2.8k, WS로 화면은정상=latent)·index/overseas/kiwoom 토큰 동일패치·앱키 PC별분리.**
- 2026-06-30 — Excel ingest 완료:  → ingest_report_2026-06-30.md
- 2026-06-29 — [분석] **NotebookLM 텔레그램 인사이트 Q1~Q7**(집PC): nlm-mcp-cli Python 정착. 12개 소스→수급이동/TP표/재료TOP3/HBM체인/비철조선방산/중국변수/이번주이벤트 전량 추출. 집에서 HTML브리핑 저장 예정.
- 2026-06-29 — [구현] **KIS WebSocket 실시간 연동**(집PC): `scripts/kis_ws.py` 신규(코스피H0UPCNT0/코스닥/야간선물H0ZFCNT0 구독, 백그라운드 재연결, AES복호화). 서버 시작 시 자동 가동, 장중 0.1초 이내 반영, 장외 esignal 15초 폴백. `/api/ws_status` 디버그 엔드포인트 추가. connected=True·subscribed 3개 확인. 내일 09:00 live 데이터 검증 필요.
- 2026-06-29 — [구현] **딸깍 대시보드 시장패널 완성**(집PC): 분봉/누적추이/프로그램/글로벌차트 X축 시간레이블 추가, 섹터카드 스파크라인 우상단 배치(KIS일봉), 더보기/접기 행동기화, localStorage stale-while-revalidate+서버논블로킹으로 로딩속도 해결, 프로그램순매수 레이블중복 제거, 투자자누적추이 빈공간 안내문구.
- 2026-06-29 — [패치] **NotebookLM MCP 한국어 셀렉터 패치**(회사PC): selectors.js 3곳(addButton·sourceTypeText·insertConfirm) 한국어 추가("소스 추가"/"복사된 텍스트"/"삽입"/"확인"). MCP 재등록 완료. Claude Code 재시작 후 소스 자동 추가 가능. 노트북 13개 파일 로딩 대기.
- 2026-06-29 — [구현] **크롤링 인사이트 허브(/insights) 완성**(회사PC): `dashboard/insights.html` 신규(유튜브/텔레/리포트 카테고리→채널→문서→상세 드릴다운 SPA). `doc_summary.py`(AI 요약 생성+캐시, 6~8항목+highlights). `server.py` 9개 신규 API 라우트+sys.path 수정+doc_title 추출. 딸깍/섹터맵/인사이트 3페이지 네비게이션+뒤로가기(History API). youtube_ingest.py deeplink 버그 수정. telegram_ingest.py --force-date 추가(오전→오후 2회 ingest 지원). 다음=오후재ingest 딸깍버튼+구버전 요약 일괄재생성.
- 2026-06-29 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-29.md
- 2026-06-28 — [구현] **딸깍 대시보드 ⚙️편집탭 완성**(회사PC): `market.html`에 섹터 숨기기(36개 체크박스·취소선), 섹터 종목 추가(드롭다운+오토컴플릿), 커스텀 섹터 생성/삭제, 💾저장/초기화·토스트 알림. 백엔드=`sector_custom.json` 오버레이(`sector_heatmap.py`+4 API 엔드포인트). race condition 버그 2개 수정(renderOverview/Tab에 guard, 숨긴 섹터 포함 전체 섹터 항상 로드).
- 2026-06-28 — [구현] **크롤 소스관리 대시보드+서버연동+유튜브 자막 파이프라인 A단계**(회사PC): ① 소스관리 대시보드(`크롤링소스관리.bat`→8090/sources): 텔레·유튜브·블로그·뉴스 추가/삭제(링크or이름)→**로컬+Lightsail서버 config.yaml 자동연동**(서버에 `add_source.py`/`del_source.py`/`crawl_run.py` 설치). 버튼=받아오기·소스동기화·전체크롤·채널별크롤. 소스동기화로 등록=실제 일치(텔레19·뉴스4·블로그4·유튜브5). ② **유튜브 자막 파이프라인 A**: yt-dlp 자막이 서버(데이터센터IP) YouTube 봇차단으로 막힘→**Gemini 영상직접시청 타임스탬프 발언**으로 피벗(`gemini_summarizer.py` 프롬프트). 영상당 `[mm:ss] 화자: 발언원문` 8~16개(검증). ③ 시황부장 챗봇+마스코트(`스탁브레인.bat`/`스탁브레인_부장.bat`, claude -p). 다음=B(원자추출)·C(발언카드+/영상기획) 집PC. 상세 NEXT_SESSION.md + spec `2026-06-28-유튜브-자막-원자-파이프라인-design.md`.
- 2026-06-28 — Excel ingest 완료:  → ingest_report_2026-06-28.md
- 2026-06-27 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·RS·쏠림지수·액티브ETF·일정·한국ETF_RS·투자아이디어 → ingest_report_2026-06-27.md
- 2026-06-26 — [구현] **삼프로TV 크롤러+리포트**(회사PC): 3시간 크롤러(`3pro_crawl.py`)+8코너 테스트+VTT 스토리보드 생성. 마켓인사이드 3종 결과물(518블록 전문·6씬요약·경량HTML리포트). 완료3코너(아침N투자·클로징벨·마켓인사이드), 미완5코너(Gemini KEY_3 추가 필요).
- 2026-06-26 — [구현] **딸깍 대시보드 1단계(🌅장전 버튼) 완성**(회사PC): `dashboard/server.py`(FastAPI:8090)+`index.html`(검정골드). 딸깍→signal_snapshot+미국증시브리핑 한 화면(매크로게이트 GO/주도섹터 A·B/종목9점표 498중40/브리핑접이식). 브라우저 렌더 검증. 설계=`docs/superpowers/specs/2026-06-26-딸깍-대시보드-design.md`. 서브에이전트3개로 작업스케줄러16잡 산출물 전수조사. 발견=①신호잡 6/22후 4일멈춤(수동복구)②market_data.js 5/24죽음③9:30배치 태이버아닌 @futuresnow중복④**섹터라벨 정합성문제: 통신A진입했으나 미장(코닝광통신)·소르티노(네트워크인프라ETF)·빈집(KTcs·KT서브마린)이 같은'통신'라벨이나 실체불일치**. 다음=장중2단계(한투)+신호잡복구+섹터라벨분리.
- 2026-06-26 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·RS·쏠림지수·액티브ETF·일정·한국ETF_RS·투자아이디어 → ingest_report_2026-06-26.md
- 2026-06-24 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·RS·쏠림지수·액티브ETF·일정·한국ETF_RS·투자아이디어 → ingest_report_2026-06-24.md
- 2026-06-23 — [분석] 태린이아빠 투자메커니즘 역설계(06-03~23 텔레 18일 전수, 병렬12에이전트): 시간대별 5슬롯 루틴+핵심7지표+의사결정3공식 보고서 → out/태린이아빠_투자메커니즘_벤치마크_2026-06-03_to_06-23.md. 핵심=장전/장후 고정발신+주도업종 Triangulation+오실레이터 연동 현금비중.
- 2026-06-23 — [구현3] **컨센표준화+등급자동+B형그릇**(집PC): ① 컨센 형식 표준화 — 대표행 [컨센] 15/185뿐 발견, `sector_table.py` 폴백(증권사별 행→범위 자동산출)으로 170종목 페이지수정0으로 커버. ② 등급 자동산정 `scripts/gen_tiers.py`(atoms.db 종목별 원자수→hot 5+/watch 2~4)→ stock_tiers.yaml 자동(hot6·watch36, HD현대중공업 정적탈출). 진단 일감 4→75건(핫·워치 빈칸 일감화). ③ 조선 섹터에 횡단 비교표 삽입=B형그릇 적용. 발견=asset명↔페이지명 불일치(현대차/현대자동차) 정규화 일감. 다음=종목명 정규화·수신워커·능동워커 리서치확장.
- 2026-06-23 — [구현] 위키 3워커 1단계+능동워커 골격(집PC): 스키마 9칸+등급프로파일(`wiki/_schema/`) / 진단엔진 `scripts/wiki_diagnose.py`(전섹터 215종목 검증, 등급도입 432→9 정밀화) / SK하이닉스 다관점 3섹션 삽입 / 능동워커 `scripts/worker_active.py`(검증→통과패치/미달_pending, 코드결손 9건 중 5채움·4보류). 다음=능동워커 리서치칸 확장→종합워커(서브에이전트+Write). 상세 NEXT_SESSION.md.
- 2026-06-23 — [구현2] **종합워커+섹터그릇**(집PC): ① 종합워커 `scripts/worker_synth.py`(파괴방지 게이트: 길이·필수섹션·학파수·요약문 4검사) — 서브에이전트가 SK하이닉스 다관점에 실뉴스(마이크론 6/24·HBM완판) 3곳 통합, 검증통과→원본반영, **파괴0**. ② 섹터 스키마 `sector_page_schema.yaml`+횡단표 생성기 `scripts/sector_table.py`(종목페이지서 컨센TP·이벤트·다관점 자동수집→비교표). 조선 6종목 표 생성(`out/sector_table_조선.md`). 발견=**종목페이지 컨센형식 제각각([컨센]/[기존 컨센]/없음) → 표준화 필요**. 다음=수신워커·능동워커 리서치확장·등급 자동산정.
- 2026-06-23 — [브레인스토밍] 위키 종합엔진 단순화 재설계 완료(spec: `2026-06-23-위키-3워커-엔진-design.md`). 핵심: ① 그릇 yaml 스키마로 명시 → 빈칸=일감 ② 3워커(수신·능동리서치·종합) 24h 풀가동 ③ claude -p 폐기→서브에이전트+Write ④ 다관점 학파·충돌·썰 보존(SK하이닉스 데모 검증: `out/wiki_v2_demo_SK하이닉스_다관점.md` + `out/로또의_SK하이닉스_관점.md`) ⑤ 섹터 횡단 그릇으로 B형 질문("조선 어디?") 답 ⑥ 3단 검증·시간축 누적 보존. 다음=writing-plans→1단계(스키마+진단) 구현.
- 2026-06-22 — [브레인스토밍] 태린이 파일 활용 메뉴얼 80% 합의: "3단 깔때기 탑다운 스토리" 컨셉 확정(STAGE1 GO판정→STAGE2 섹터좁힘→STAGE3 종목픽업) + 드릴다운 4섹션 + 9점표 v1 채용. 다음세션 결정3개(GO룰/섹터매핑/펼침방식) 남김. NEXT_SESSION 2트랙(대시보드개편+태린이)으로 통합.
- 2026-06-22 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-22.md
- 2026-06-21 — 5소스 원자 파이프라인 완성: 뉴스 인제스트(post_sources news 추가)·daily_health MVP(텔레카드 실발송 확인)·리포트 섹터 통일(resolve_sector)·채널간 이벤트 병합(비파괴 A안)·7AM 작업스케줄러 등록 완료. 모델=Sonnet으로 전환.
- 2026-06-21 — 카카오EP1 모드C 전환 완료(S4·S6·S11·ChannelSting·EndSting) + ColdOpen 제거 + 아웃트로 이음새 처리 + **최종 렌더 완료**(kakao_ep1_final.mp4, 210.9MB, 11분18초)
- 2026-06-21 — Plan B 3단 자동 검증 구현: verify_questionnaire.py(㉠인용대조·㉡wisereport정답지·㉢구조룰), trust_score→strength_score 조정, report_ingest 연결. 20 tests pass.
- 2026-06-21 — report_ingest --all 모드 + atom_pipeline.py STEP3 교체(pdf_ingest→report_ingest). 미처리 MD 자동탐색 가능.
- 2026-06-21 — codemap KRX 통합: KRX KOSPI+KOSDAQ 2605종목 HTTP 연동(krx_codes.json 7일 TTL). 두산로보틱스·HD현대중공업 등 이전 누락종목 인식 가능. 6 tests pass. (LIG넥스원은 KRX 공식명 변경→LIG디펜스앤에어로스페이스, alias 별도)
- 2026-06-21 — 리포트 질문지 추출 시스템 구축(Plan A): questionnaire.py·report_ingest.py·codemap.py 신규. fan-out 3타입(stock/sector/market). 6 tasks 완료, main merge push 완료.
- 2026-06-21 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-21.md
- 2026-06-20 — 카카오EP1 튜토리얼 액션줌 완성 + 모드C 착수: S7 카톡창 중앙줌(translate+scale), S8/S9/S10 액션줌 재작성, S2 Whisper재전사(1752f·1191오류정정), shake버그({x,y}) 수정. **S3 모드C 골든레퍼런스**(FlowField·9비트 대사싱크·거대타이포). 다음(집PC): S3 톤확정 → S4/S6/S11/콜드오픈/스팅 모드C. 상세=NEXT_SESSION.md
- 2026-06-20 — 카카오EP1 S5 버그픽스: 화면짤림(fy/SC 수치 조정) + 사인파 떨림 제거(Math.sin 삭제·damping 강화). 다음: S5 최종컨펌 → S7~S10·S2 액션줌
- 2026-06-19 — 카카오EP1 Remotion LIFE 3.0 재설계: DESIGN.md(3씬모드)+life.tsx 신규. 인트로/아웃트로 Whisper자막+음성정렬 확정, S5 풀스크린 액션줌 v3(자막 23세그 1:1 싱크). 다음(집PC): S7~S10·S2 액션줌 적용 → S3/S6/S11 모드C. 상세=NEXT_SESSION.md
- 2026-06-19 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-19.md
- 2026-06-18 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-18.md
- 2026-06-17 — 카카오클로드 EP1 씬폴더 재구조화(미디어타입→씬별) + design.md/script.txt 전체 생성 + OBS·VLC 세팅. 다음: 음성·화면 녹화 → 소넷 검수 → 오푸스 TSX 설계
- 2026-06-17 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-17.md
- 2026-06-16 — 카카오클로드 EP1 에셋 폴더 구조 완성: productions/kakao_ep1/ 전체 설계, 씬별 대본 txt, Veo+Remotion 오버레이 확정, S2 화면녹화 방식 변경. 다음: 녹화 후 오푸스로 Veo TSX 3종 설계
- 2026-06-16 — 카카오클로드 v7 대본 확정 + Remotion 공통 인프라 구축: theme.ts+SceneBase.tsx 생성(씬 350줄→80줄), KK_S6_MCP.tsx(900f MCP개념 4페이즈) + 템플릿 완성. 3레인 구조+Veo 8초 공식+북엔드 AI여자 앵커 설계. 다음: Veo 클립 8개 + 전환컷 설계
- 2026-06-16 — S5 Remotion 완성: KK_S5_L30(풀스크린 5Phase 오버레이·38MB) + KK_S5_PiP(발표자 우측9:16 PiP·spring전환·LIVE배지·좌측 화면녹화 플레이스홀더). 다음: s5_screen.mp4 연결
- 2026-06-16 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-16.md
- 2026-06-15 — 카카오클로드 S2·S3 Remotion 완성: Whisper 실제 대본 추출 후 그래픽 카드 일치. S2(656f·22s·페인포인트), S3(1212f·40s·AI신화파괴+진짜이유). KK_S2_L30.tsx·KK_S3_L30.tsx 생성. 다음: 씬 검토 + 다음 씬 작업(대본 함께 제공)
- 2026-06-15 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-15.md
- 2026-06-14 — 카카오클로드 영상 Remotion S1·S2 완성: S01_Hook(카톡 알림→자동 임팩트, 540f), S02_PainPoint(5카드 X슬라이드·정보소비 클라이맥스·관망 훅), PostFX 후처리, 전체 13씬 대본 1차 확정. 다음: 스타일 다듬기 + S3·S4·S6·S11·S12·S13 제작
- 2026-06-14 — STOCK BRAIN 시그니처 인트로 완성 (StockBrainIntro.tsx): 스캔라인 빌드업+스크램블 리빌+글리치 버스트 8초 | 카카오클로드 대본 v5 완성: v3+v4 통합+S0-A/S0-B 오프닝 추가 (15씬 ~12분) | Remotion 효과 3종 커밋 (DocHighlight/FocusZoom/TechFeed)
- 2026-06-14 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-14.md
- 2026-06-13 — 신채널 브레인스토밍: AI+주식 별도 채널 설계 착수 | B안(내 시스템 공개) 확정 | 레벨 5단계 주제 구성 완료 | 미결: 채널명·첫 영상 기획 → docs/superpowers/specs/2026-06-13-ai주식-신채널-design.md
- 2026-06-13 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·RS·쏠림지수·액티브ETF·일정·한국ETF_RS·투자아이디어 → ingest_report_2026-06-13.md
- 2026-06-12 — Excel ingest 완료: 컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·액티브ETF·일정·투자아이디어 → ingest_report_2026-06-12.md
- 2026-06-11 — 비즈니스 모델 확정: 강의(30~50만원)+구독서비스 | 핵심 컨셉: "요약→추출" 할루시네이션 없음=와우 모먼트 | 섹터 시그널 파이프라인 3개 파일 설계 완료 | 집에서: sector_signal_ingest·sector_master_update·stock_wiki_update 구현
- 2026-06-11 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·액티브ETF·일정·투자아이디어 → ingest_report_2026-06-11.md
- 2026-06-10 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·액티브ETF·일정·투자아이디어 → ingest_report_2026-06-10.md
- 2026-06-09 — 아침 브리핑 파이프라인 설계 1단계 완료 | telegram_digest.py · morning_sector_pick.py · scan_sortino.py(ETF구성종목서칭) | 유동성→소라티노ETF교차→빈집 3단계 확정 | 2번파일~부터 집에서 이어서
- 2026-06-09 — 블로그 ingest 완료 (Gemini flash-lite 자동처리 28개→25개 인제스트·3개 스킵) | 신규: RFHIC·엘앤씨바이오·에이피알·아이티센글로벌 | 추가: SK하이닉스·삼성전기·주성엔지니어링·HD현대중공업·반도체index | 반도체index: 인텔-구글TPU·DRAM시장+62%·메타유증 추가
- 2026-06-09 — 블로그 ingest 완료 (Gemini API 불가로 Claude 직접 처리) | 반도체: SK하이닉스(젠슨황HBM4파트너십·베라루빈탑재확정)·주성엔지니어링(CXMT PO수주)·삼성전기(Si-Cap ASP 10배) | 조선: HD현대중공업(CLSA TP100만) | 방산: RFHIC 신규(GaN 2026매출2637억+42%·OPM20.7%) | 바이오: 엘앤씨바이오 신규(리투오+930%·OPM22.5%) | 화장품: 에이피알 신규(ROE86%·미국+251%·영업이익6700억) | 총 8개 파일 업데이트/신규
- 2026-06-09 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·쏠림지수·액티브ETF·일정·투자아이디어 → ingest_report_2026-06-09.md
- 2026-06-09 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급(700)·중소형주수급(695)·가속화모멘텀·쏠림지수·액티브ETF·일정·투자아이디어 → ingest_report_2026-06-09.md | 카드뉴스TOP3: 신세계·현대차·삼성전기 | 텔레그램 10건 발송 | ⚠️ 한국상대강도·소라티노ETF 누락(서브폴더 인덱스 불일치)
- 2026-06-09 — 조선 섹터 마스터 페이지(ship_master.html) 완성 | 반도체 마스터와 동일 UI(사이드바+7탭+모바일하단탭바) | 7탭: 오늘핵심·종목워치·이벤트캘린더·밸류체인·미반영·리스크역발상·로그 | 5프레임 분석카드·종목클릭상세패널·D-155카운트다운 | GitHub Pages 배포 완료 | 다음: 딥리서치로 placeholder 채우기
- 2026-06-09 — 반도체 브리핑 인사이트 추출 시 Gemini vs Claude 비교 검토 | Gemini CLI or API 호출로 동일 프롬프트 비교 가능 | 다음세션 테스트 예정
- 2026-06-08 — 수급오실레이터700 엑셀 완전 해독 | 22개 시트 구조·합산공식(외국인+기관매도대금 단순합산)·K~X열구조(PERCENTILE통계·RS강도테이블헤더8개)·관심도db API코드(I101200~U117120) | 업데이트시각: 관심도db=18:46·매도데이터=18:52·파일저장=18:57 KST | VBA p-code 한계: oletools 읽기 불가 (Excel VBA편집기 직접확인만 가능)
- 2026-06-08 — 레이아웃 A/B/C 3안 비교 → A안(탭네비) 확정 | GitHub Pages 호스팅 완료 (.github/workflows/pages.yml) | semi-master.html 모바일최적화 | URL: park-lotto.github.io/lotto-stock-wiki/out/semi-master.html | 서비스방향: 정보정리+수급빈집+주도섹터강도가 핵심차별점 확정
- 2026-06-08 — 반도체 섹터 마스터 v2 완성 | Gemini 5프롬프트 결합 | 8카테고리 히트맵+시장미반영인사이트5개+밸류체인맵(숨은수혜주)+H2이벤트캘린더+리스크역발상(과공포vs과소평가)+종목포지셔닝7개 | 생성파일: out/sector_반도체_v2.html
- 2026-06-08 — 기판 섹터 딥리서치 v3 완성 | 방법: Gemini 2.5 Pro(4토픽)+Naver News API(91건) | 핵심수치: GB200 MLCC 40만개(스마트폰 400배)·베라루빈 60만개·골드만삭스 2030년 4.3배·ABF 아지노모토 95%독점+T글라스이중병목·삼성전기사장 수요초과 50%직접발언·CCL +74.5%YoY·이수페타시스OP3090억(+51%) | 생성파일: out/기판_딥리서치_v3.html·pipeline/기판_deep_research.py·raw/news/2026-06-08_기판_뉴스수집.md·out/딥리서치/기판_01~04.md
- 2026-06-08 — 섹터 지식베이스 서비스 설계 + 조선 마스터페이지(sector-v5.html) 뼈대 완성 | 2레이어 아코디언(카테고리→이벤트→5프레임토글)+ETF기준선+4박스종목그리드 | 미국법안 카테고리 딥리서치 완료(Section301+SHIPSAct+한화제재) | analysis_rules §-1 "시간과고급정보를판다" 원칙 추가 | 평가: 구조맞음·콘텐츠10%·내일조선섹터전체딥리서치로채우기
- 2026-06-08 — Excel ingest 완료: 추정이익변경 → ingest_report_2026-06-08.md
- 2026-06-07 — 섹터 브리핑 4개 완성(조선·반도체·전력기기·항공우주방산) | 타임라인+모멘텀 구조·소스 인용 방식 확정 | 서비스 방향: 리딩 대신 "나는 이렇게 본다" 시각 판매 | 핵심 갭: 매매 원칙 정립 필요 (브리핑→행동 다리 없음)
- 2026-06-07 — 경쟁채널 분석 완료 | "로보, AI 활용해서 살아남기" 17개 VTT 전수 분석 | 수익모델 역설계(4가지 강의+1:1코칭+카카오단톡방 DB수집) | 17편 영상제작플랜 1:1 매핑 완성 | 고객전달 3단계모델(텔레채널→캐시봇→개인화) 전략 확정 | 생성파일: competitor_analysis_로보·상세·영상제작_플랜_로보벤치마킹
- 2026-06-07 — 원자 DB 6개 구멍 전부 해결 | 구멍5: 노이즈 원자 99개 비활성화+query.py --trust/--min-length 필터 추가 | 구멍6: wiki_update.py 완성(atom DB→sector_*.md 자동갱신 섹션) + atom_pipeline STEP5 추가 | 반도체·로봇·바이오·2차전지·조선 wiki 즉시 갱신
- 2026-06-07 — Excel ingest 완료:  → ingest_report_2026-06-07.md
- 2026-06-06 — 채널 방향 전환 결정 | 슈퍼샘플 개념(베끼는시대) 분석 → "STOCK BRAIN 개발 과정을 500만원 실전으로 검증하며 공개" 방향 확정 | 출처 오픈 원칙(태린이지표·텔레채널·리포트 출처 명시) | 쇼츠+커뮤니티 선행→롱폼 순서 결정 | 생성파일: 500만원챌린지_공개규칙·EP0기획서·포트폴리오트래커·채널방향doc갱신
- 2026-06-06 — 장전 브리핑 자동화 시스템 구축 | collect(wiki→Gemini이슈추출)+bot(텔레브리핑+자유판단)+card_gen(HTML카드)+publish(Playwright+채널전송)+run_briefing.bat | assistant_bot(/s /ask /brief /enhance /wiki, Gemini어시스턴트) | Task Scheduler 전체 7개 평일(월~금)만 실행으로 변경 | 다음: assistant_bot 상시실행 Task Scheduler 등록 + 첫 브리핑 풀플로우 검증(6/8 월)
- 2026-06-06 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·액티브ETF·일정·투자아이디어 → ingest_report_2026-06-06.md
- 2026-06-05 — daily_scenario.py 완성 | wisereport+텔레그램+블로그 3소스 종합 → 브리핑 카드 시나리오 | 포맷: 카드형+주린이 말투(ETF→펀드 등) | ingest_record/blog/analyze_blog.py 구축 | insights.json dry run 53건·blog dry run 29건 | 실제 저장은 다음 세션
- 2026-06-05 — 섹터 브리핑 카드 v1(로봇/반도체/우주) + v2 구조 시안(판단배지+SIGNAL BAR+주가반응+진입조건) | v2도 "와닿지 않는다" 피드백 → 내일 컨셉 재정립
- 2026-06-05 — telegram ingest 4차 완료 | 신한리서치+하나차이나+하나반도체+리포트요약 처리 | 반도체index(TSMC CEO 3대발언·Broadcom AI네트워크30→40%·모건스탠리마이크론TP1050·키옥시아Capex66%↑·한국이익일본추월·광섬유프리폼550%↑·XPU칩리스크)+로봇(시선AI+유온로보틱스1.5조)+에치에프알AT&T벤더확인 | 전채널 완료 (17개)
- 2026-06-05 — crawling_bot+태린이아빠+미래시황+blog ingest 3차 최종 | 반도체(브로드컴-12.6%·삼전닉스-6~8%·VeraCPU LPDDR5X·덕산담합⚠️·소부장2027·삼성전기Si-Cap ASP10배·ETF리밸런싱6/11~18·시총5위·5월코스피28.45%)+로봇(현대모비스TP120만+60%·감속기+15%)+바이오(한미수급빈집·릴리신고가·HUM/ELV중간선거수혜·ADA학회)+통신(광섬유2027수주Sold-out·ETF10일선원칙)
- 2026-06-05 — telegram+report ingest 2차 | 전력index 업데이트(가온전선AI DC350억·대한전선영국1000억·EU DC 2030년 28GW·LS TP59만)+통신index(광섬유프리폼+550%·라이콤상한가)+반도체(브로드컴콘콜 OpenAI1.3GW·Meta3GW) | 텔레그램 전채널 완료
- 2026-06-05 — telegram+report ingest (6월5일 폴더) | 반도체(브로드컴쇼크-11.8%·MRVL부각·젠슨황HBM4E·삼성전자HBM5HPB·최태원캐파2배·난야+730%·피에스케이상한가·삼성전기TP210만·5월수출877억역대최대)+조선(삼성중공업FLNG4.3조확정·FDC·한국카본TP61K·모잠비크입찰·미군함2.8조검토)+방산(LIGD&A×젠슨황·캐나다잠수함·스웨덴K2·APS시험)+우주(SpaceXIPO$190억·스타링크V3 1Tbps) | pdf_summarize 완료(18개) | 전력(가온전선350억·대한전선1000억) 미착수
- 2026-06-05 — wisereport+crawling_bot ingest | 기업25+산업22+종목/산업2 | 반도체(LG이노텍TP200만↑·피에스케이Capex·Computex·KB기판공급절벽) / 통신(무선장비주도주·라이콤) / 로봇(KH바텍·세나테크) / 조선(해운기회) / 바이오(아이엠바이오) / 소비내수(카지노5월) / 이차전지(삼성SDI⚠️) 7섹터
- 2026-06-05 — ingest | raw/wisereport/2026-06-04~05_parsed.json → 우주index(서브섹터10개+밸류체인+기술드라이버 전면 재구축)+방산index(KAI하반기+137%·한화에어로+62.7%·LIG방공우주)+stock_AP위성(신규) | 블루오리진폭발→SpaceX독점강화 반영. 과거≠현재 구분 원칙 적용
- 2026-06-05 — 섹터 파일 컴팩트화 | 삭제17개(빈껍데기5+위성중복12) | 방산타임라인→방산index 편입 후 삭제 | 통신index.md 신규 생성 | 확정구조: 섹터당 최대2파일(index+sector_)
- 2026-06-05 — ingest | raw/blog/2026-06-05_우주항공관련주_블로그검색.md → wiki/L5_섹터/우주/market_우주항공관련주_SpaceXIPO_20260605.md | SpaceX 6.12 IPO 임박, 우주ETF 1조8천억 자금 쏠림·선반영 고점 논란·국내 수혜주 분석
- 2026-06-05 — 폴더 정리+건강검진 | 삭제: wiki/wiki(중복)·out구폴더3개·demos | 이동: raw/투경→pipeline/투경 | 통합: raw/리모션영상→raw/리모션/ | 이동: raw/미국장→raw/L2_미국시장 | 이름정리: 매일엑셀/크롤링/테마맵/캡처본 공백·오타제거 | 오타수정: 유뷰트→유튜브 | 방치섹터: 철강·우주·2차전지ESS
- 2026-06-05 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·액티브ETF·일정·투자아이디어 → ingest_report_2026-06-05.md
- 2026-06-05 — yt-trend 2026-06-04 파이프라인 완전 재실행 | API 키 갱신(YOUTUBE+GEMINI AQ.형식) | step2 Python 신규·step3/4 google.genai 마이그레이션 | 대본 완성(소부장 3근거: 일본TEL선행+최태원증산+TSMC팹) | S1/S3/S5/S7 디벨롭 완료 | 다음: yt-planner → Remotion
- 2026-06-04 — Smart App Control 차단 해제 | 집PC Python 실행 차단 원인: SAC(VerifiedAndReputablePolicyState=1) | 관리자 레지스트리 변경으로 0 세팅 완료 | 재시작 후 yt-trend 파이프라인 처음부터 재실행 예정 (오늘 폭락 반영 대본 목적)
- 2026-06-04 — Gemini 딥리서치 파이프라인 구축 완료 | gemini_yt_deep_research.py 완성(Interactions API) | .mcp.json MCP A/B 등록 | yt-content-research 실전실행: 소부장자금순환 각도 → 원익IPS+유진테크 → Gemini 대본 완성 → 검수PASS | 파일: script_소부장자금순환_20260604_final.md | 다음: yt-planner → Remotion
- 2026-06-04 — 채널 인사이트 시스템 완성 | ingest_crawl.py: coupling타입+Pass2(인사이트추출) 추가 | channel_registry.json 생성 | wiki/insights/ 폴더 구조 완성 | 텔레6채널 인제스트(sector16/stock21/coupling16) | 반도체 핵심인사이트: 낸야테크+730%·젠슨황HBM4E증산요청·브로드컴가이던스미달·TEL+13%→장비주상한가
- 2026-06-04 — ingest | raw/telegram/2026-06-03_태린이아빠_유튜브.md → wiki/외부인사이트/태린이아빠.md | 광통신 군집 신고가·HBM4 가격협상·TGA 유동성 경고·삼성전기 TP320만원
- 2026-06-04 — crawling_bot_data ingest 파이프라인 설계 착수 | B안 확정: pdf_summarize.py(Gemini Flash) + ingest_crawl.py(Haiku) + crawl_ingest_state.json | 투경 관리 12종목 완성 | Task Scheduler 5개 python경로 수정 | yt 주제확정: 반도체독주→순환매 6월핵심
- 2026-06-04 — yt-gemini-pipeline 파이프라인 재설계 시행착오 | SKILL.md 종목선정 5단계 규칙 정립 | 영상주제_후보풀.md 생성(세트1) | LIG D&A Deep Research 리포트 확보 | 핵심학습: Claude=편집장(리서치X), Gemini Deep Research 활용 방향 확립
- 2026-06-04 — yt-gemini-pipeline 완료 — 순환매 후보 3선 | 스토리: 불안공감→3중필터 공개→TOP3 선정→리스크→결론 | 파일: script_순환매_final.md / yt_순환매_기획서.md
- 2026-06-04 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·액티브ETF·일정·투자아이디어 → ingest_report_2026-06-04.md
- 2026-06-04 — 다채널 집계 파이프라인 설계+구현 + 스킬 설치 (집PC 세션)
  [구현] scripts/channel_pipeline/ 10개 파일 완성 (커밋 4627295)
    · agent_A(Gemini), agent_B(Sonnet 토론), agent_C1(승격판단), agent_D(wiki), agent_E(브리핑)
    · models.py + trust_tracker.py + file_manifest.py + cost_estimator.py + pipeline.py
  [구조] wiki/채널토론/ + raw/inbox/ + pipeline/channel_trust.json 신규
  [스킬설치] 집PC에 gstack+superpowers+understand-anything+agentmemory+context-engineering+claude-video
  [다음] Claude 재시작 → inbox 테스트 → 스킬 활용 검증 (plan-eng-review → superpowers:brainstorming)
- 2026-06-03 — YouTube 영상 파이프라인 전면 재설계 세션
  [작업] yt-content-research + yt-gemini-pipeline 스킬 완성 + 소재 탐색 실전 진행
  [핵심 변경]
    · 채널명 → 로또의 스탁브레인
    · 파이프라인: Claude(소재발굴) → Gemini(딥리서치+스토리+대본) → Claude(검수)
    · yt-content-research: 브레인스토밍 확인 → 정량 이슈 스캔 → YouTube 실사 → 오염체크
    · yt-gemini-pipeline: 브리프 생성 → Gemini 3단계(딥리서치/스토리설계/대본) → 검수
  [소재 탐색 결과]
    · 주제 확정: "반도체 독주 끝나면 다음 주도주 — 6월 순환매 후보"
    · 이슈 온도: 🔴 코스피 8800, ADR 최저, MBC 핫이슈 영상 5/30
    · 브리프 파일: channel/yt/brief_순환매_20260603.md
  [미결] Gemini API 호출 (집에서 이어서 진행)
  [다음 할 일] yt-gemini-pipeline 실행 — brief_순환매_20260603.md → Gemini → 대본

- 2026-06-03 — 아침 브리핑 HTML 디자인 시스템 구축 세션
  [작업] 스킬 파이프라인 실험 + 브리핑 v2 레이아웃 완성
  [스킬 순서] design-consultation → design-html → design-review (3단계 검증)
  [핵심 결론] 레이아웃 = 정보 순서. 결론 먼저(탑픽) → 근거(수급+섹터) → 맥락(글로벌) → 리스크
  [디자인 확정] 검정(#080808) + 골드(#e8b84b) + Instrument Serif + Geist
  [파일 위치]
    · out/morning_briefing_final.html — 기존 레이아웃 (디자인 완성본)
    · out/morning_v2.html — 새 레이아웃 (결론 먼저 구조, 리서치 기반)
  [v2 레이아웃 구조]
    1. 헤더 (브랜드+날짜, 얇게)
    2. 오늘의 판단 (한 줄 콜 — 가장 크게)
    3. 탑픽 3개 카드 (이유 포함) ← 결론 먼저
    4. 수급 방향 + 섹터 온도 (왜 맞나)
    5. 글로벌 수치 한 줄 (맥락, 아래로)
    6. 리스크 경고 1줄
  [리서치 근거] 한국 개인투자자 10분 미만 아침 준비, 82% 종목 하락 속 집중 필요
  [미결] v2 레이아웃 사용자 피드백 반영 후 완성 → 자동 생성 파이프라인 연결
  [다음 할 일] v2 수정 → DESIGN.md 작성 → 자동화 스크립트 연결

- 2026-06-03 — 금양 상폐 투경 교육 대본 v2 작성
  [파일] channel/yt/yt_금양상폐_투경교육_대본v2.md
  [변경] v1 대비 톤 전면 수정: 위로+교육 톤 / 금지 표현 제거 / 70/20/10 비율 재구성
  [구성] 8씬 / 총 9분 / S1~S6 정보(72%) / S7 간접(17%) / S8 CTA(6%)
  [핵심변경] S1: "막을 수 있었다" → "앞으로를 위한 이야기" / S7: 시스템명 제거, 방법론만
- 2026-06-03 — 영상 제작 파이프라인 전체 가동 세션 (스킬 기반 3영상 동시 기획+대본)
  [스킬 신규] yt-content-research / yt-planner / yt-make-video (.agents/skills/)
  [스킬 업데이트] CLAUDE.md 전체 스킬 라우팅 맵 + 영상 파이프라인 섹션 추가
  [소재탐색] 백지 YouTube 조회수 실사 → 3단계 필터 → 3개 소재 확정
    · 기준: ① 고조회수 ② 이벤트 생존 ③ 채널 적용 가능성
  [기획서 완성] 에이전트 3개 병렬 → 3개 모두 9/9점
    · A: yt_시황보는시대끝났다_기획서.md (상시)
    · B: yt_금양상폐예방법_기획서.md (⚠️ 6/7 업로드 데드라인)
    · C: yt_수급빈집역발상_기획서.md (상시)
  [대본 완성] 에이전트 3개 병렬 → 3개 모두 완성
    · A: yt_시황보는시대끝났다_대본.md (8분15초)
    · B: yt_금양상폐_투경신호_대본.md (9분30초)
    · C: yt_수급빈집역발상_대본.md (8분30초, S5·S6 플레이스홀더)
  [미완] B: 6/7까지 Remotion+촬영+녹음 필요 / C: calc_oscillator.py 당일 실행 필요
- 2026-06-03 — 수급빈집역발상 영상 대본 작성 완료
  [파일] channel/yt/yt_수급빈집역발상_대본.md
  [구성] 8씬 / 총 8분30초 / 기획서 기반 대본 완전 작성
  [미완] S5·S6 플레이스홀더 — 업로드 당일 calc_oscillator.py 결과로 채울 것
  [다음] Remotion 씬 제작 (S3 빈집인포그래픽·S4 등급표·S7 체크리스트) + S5 실화면 촬영
- 2026-06-03 — agentmemory 백엔드 서버 미실행 확인
  [진단] MCP 클라이언트(@agentmemory/mcp) 연결 ✅ / 백엔드 서버(localhost:3111) ❌ 미실행
  [원인] myagentmemory 전역 CLI 미설치 → 서버 미구동으로 메모리 조회 결과 0건
  [해결] npm install -g myagentmemory → myagentmemory 실행 후 Claude Code 재시작 필요
- 2026-06-03 — Claude Code 플러그인/스킬 대규모 설치 세션
  [설치완료] superpowers(14개스킬포함) / prompt-architect / context-engineering / frontend-design
  [설치완료] Firecrawl MCP / Browser Use MCP / ElevenLabs MCP (uv 신규설치)
  [설치완료] Pexo 5개스킬 / claude-video(/watch) / Understand-Anything / agentmemory
  [설치완료] gstack (YC CEO 가리탄 셋업, 40개스킬, Bun 신규설치, Playwright Chromium 포함)
  [보류] context-engineering → muratcankoylan/Agent-Skills-for-Context-Engineering 으로 최종 설치
  [주의] /plugin 슬래시명령어는 VS Code 확장에서 작동 안함 → Bash로 실행 필요
  [미설정] Firecrawl API키(FIRECRAWL_API_KEY) / ElevenLabs API키(ELEVENLABS_API_KEY) 추후 등록 필요
- 2026-06-03 — SpaceX IPO 영상 소재찾기 + 대본 완성 (집PC 세션)
  [소재찾기] 5단계 루틴 실행 — WebSearch + YouTube Playwright 분석
  [핵심소재] "젠슨황 가고 머스크 온다" 내러티브 확정
    · LG그룹 +30% (젠슨황 방한 6/4~5) → SpaceX IPO D-9 (6/12) 사이클
    · 우주항공 ETF +81% / 스피어 +214% 이미 고점 vs 수급 빈집 종목 찾기
    · 빈집+주도 시그니처 각도로 차별화
  [대본] channel/yt/yt_SpaceX_젠슨황머스크_대본.md 신규 — 11씬 7~8분
  [미완] 씬7·9 수급 데이터 빈칸 → calc_oscillator.py 우주항공 종목 실행 필요
- 2026-06-03 — 장전브리핑 5문5답 시스템 완성 + 07:40 자동 스케줄 등록
  [CLAUDE.md] /morning-brief 명령어 + 5문5답 체계 (글로벌/미국섹터/이슈/주도업종/탑픽) 추가
  [스케줄] trig_01S8QRBwMDjFwYVEqUxB6Mez — 매일 07:40 KST (cron 40 22 * * 0-4)
  [ingest_excel.py] SECTOR_FOLDER_MAP(24섹터) + IDEA_SHEET_SECTOR_MAP + find_stock_page 캐시화
  [헬퍼] get_sector_folder() / get_stock_sector() 추가
  [브리핑] 2026-06-03 장전 브리핑 수행: 반도체>자동차>조선 / 탑픽: 코리아써키트·제주반도체(투경해제) / 에스비비테크
- 2026-06-02 — 자동화 스케줄 전면 재편: 다운로드 20:10이동, 투경크롤링/해제판단/와이즈리포트 신규 등록 (총 5개 스케줄)
- 2026-06-02 — check_투경_해제.py 신규 작성: 3조건 판단 → 내일 시가베팅 후보 텔레 발송
- 2026-06-02 — 정보수집 프레임워크 정립: 텔레(인사이트)·유튜브(내러티브레이더)·블로그(컨텍스트)·뉴스(스크린)
- 2026-06-02 — 종목선정 4단계 필터 wiki/rules 저장 + ingest_rules.md 태린이 파이프라인 전체 반영
- 2026-06-02 — 세션 마무리: 태린이 파이프라인 교차분석 + 투경 해제공식 백테스팅 완료
  [교차분석] ingest_excel.py에 _build_교차분석_tg() 추가 — 수급빈집×RS×가속화 3중/2중 교집합 → 텔레 자동 발송
  [자동화] 업종오실레이터(scan_업종오실레이터.py --tg) + 카드뉴스(viz_card.py TP상향TOP3) ingest에서 subprocess 자동 실행
  [투경관리] wiki/L6_수급/투경관리.md 전면 재작성 — Gemini딥리서치 기반
    · 분류기준 수정: 코스피/코스닥 → 지정유형(급등형×160/200% / 불건전형×145/175%)
    · 재지정 메커니즘 추가: 해제 후 10거래일 4조건 (지정전일초과·해제전일초과·2일40%·시총100위밖)
    · 2026-05-27 개정: 시총100위 이내 대형주 투경 원천배제
    · 2025-12-29 개정: 장기지표 시장지수 초과분 200%로 변경, 재지정방지 60영업일
  [버그수정] fetch_투경_kind.py MARKET_THRESH 미정의 버그 → TYPE_THRESH로 교체
  [신규] 투경_재지정검증.py — KIND 크롤링 + 해제후 10거래일 4조건 일별 체크
  [백테스팅] 공시 직접 확인 → 올바른 배수 적용 → 4/4 일치 (합격)
    · 민테크/미래반도체/TPC로보틱스 = 급등형(×160/200%), 5/29 판정 → 6/1 해제 ✅
    · 네오티스 = 불건전형(×145/175%), 5/29 판정 → 6/1 해제 ✅
    · 제주반도체 = 초장기상승+불건전형(×145/175%) — KIND공시 직접 확인
    · 공시 지정사유 항목에 "불건전" 명시 + 특정계좌 관여율 수치 = 불건전형 판별법 확립
- 2026-06-02 — 종목선정 4단계 필터 프레임워크 정립 → wiki/rules/종목선정_4단계필터.md 저장
- 2026-06-02 — 컨센 종합 탑픽 빌더 완성: 수급상태 4분류(바닥턴중·바닥하락중·꽉참상승중·꽉참턴중) + 10점 스코어링 텔레 자동 발송
- 2026-06-02 — 컨센움직임서프쇼크 파서 컬럼 수정(219종목·155종목·123종목 정상 인식) + 텔레 발송 추가
- 2026-06-02 — 태린이 파이프라인 확장: 파서 2개 신규(한국ETF_RS·투자아이디어), 스케줄 등록(STOCKBRAIN_Daily_Ingest 07:50), 소르티노 자동 연결
- 2026-06-02 — Excel ingest 전체 실행 완료 (13개 파서): 텔레그램 10건 발송. SK하이닉스 TP 250→340만, 현대차 74→100만, 삼성전자 45→56만
- 2026-06-02 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·RS·쏠림지수·액티브ETF·일정·한국ETF_RS·투자아이디어 → ingest_report_2026-06-02.md
- 2026-06-02 — 세션 마무리: 투경해제공식 검증 + 태린이아빠 아이디어 보드 구축

## 2026-06-02 — 투경 해제공식 완전검증 + 아이디어 보드

### 투경 해제공식 확정 (다중소스 교차검증 완료)
- KOSDAQ 급등형: 오늘 < T-5종가×160% AND 오늘 < T-15종가×200% AND 오늘 ≠ 최근15일최고가
- KOSPI/불건전형: 오늘 < T-5종가×145% AND 오늘 < T-15종가×175% AND 오늘 ≠ 최근15일최고가
- T-5/T-15 = 오늘 기준 rolling (지정일 고정 아님). SK하이닉스 실제 사례로 검증.
- 3조건 중 하나라도 해당=이연 / 모두 해소=다음 영업일 해제
- 최초해제판단일 = 지정일로부터 10영업일 경과 후 첫날 (엑셀 파일 컬럼 확인)
- 판단마지막날(투경지정예고) / 최초해제판단일(투자경고종목) 개념 확인

### 투경 종목 현황 (2026-06-02 기준)
- 코리아써키트: 🟢 3조건 충족 → 6/3 해제 예상 (5/14~6/1 계속 최고가 갱신하다 오늘 해소)
- 제주반도체: 🟢 3조건 충족 → 6/3 해제 예상 (수식상 5/27부터 충족인데 실제 미해제 — 원인 미해결)
- 광전자·엠케이전자·타이거일렉: ⏳ 6/4~5 예정
- 심텍·티에스이: ⏳ 6/9~10 예정
- 미해결 이슈: fetch_투경.py rolling 계산은 맞는데 제주반도체 실제 미해제. KRX 내부 계산 확인 필요.

### 태린이아빠 투자아이디어 보드
- scripts/parse_idea_board.py 신규 — 엑셀 30개 시트 파싱 (섹터 30개, 종목 469개)
- wiki/외부인사이트/태린이아빠_투자아이디어.md 저장
- out/idea_board.html 생성 (2Q 현재이벤트·3Q다음분기·전체매트릭스·MSCI일정)
- 실용화 방향: 수급빈집×아이디어 교차필터 → 진짜 탑픽

### 개념 정리
- PER = 주가÷EPS. 섹터마다 적정 배수 다름 (바이오 50~100배 / 은행 4~8배)
- 리레이팅 = 배수 자체가 올라가는 것. LG이노텍: 광학주→AI기판주 리레이팅 진행 중
- 컨센서스상향(실적↑) vs 리레이팅(배수↑) vs TP상향(결과물)
- 태린이아빠 핵심: 밸류체인 소속≠수혜. 판가가 실제로 오른 놈만 먹는다.

- 2026-06-02 — Excel ingest 완료: 쏠림지수 → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 쏠림지수 → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 쏠림지수 → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 액티브ETF → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 일정 → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 액티브ETF → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 쏠림지수 → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 일정 → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 액티브ETF → ingest_report_2026-06-02.md
- 2026-06-02 — Excel ingest 완료: 쏠림지수 → ingest_report_2026-06-02.md
- 2026-06-02 — 소라티노 구현 완료: scan_sortino.py (Sortino Top 20 / Mansfield RS ≥70)
  [소라티노] 태린이아빠 코드 그대로 로컬 구현. 이미지와 100% 일치 확인. --tg 텔레 전송
  [다운로드] 소라티노ETF상대강도 + 특정업종쏠림지수국내 매일 자동 수집 추가
  [원리] 소르티노 = 연수익 / 하방편차. 3-6-12M 평균. 50일선 필터. 우상향 강한 섹터 탐지
  [주도업종시스템] 유동성컨셉 + RS필터 + 소르티노 3종 조합 완성
- 2026-06-02 — 세션 마무리: 태린이파일 자동화 + LG이노텍 분석 + 추정이익 카드뉴스 완성
  [스케줄] STOCKBRAIN_Daily_Download 오류 수정 / STOCKBRAIN_Daily_Ingest 신규 등록 (07:50)
  [스케줄] run_download.bat+run_ingest.bat 경로 수정(CH→TheRose) / setup_schedule.bat 신규 (집PC 이전용)
  [위키] LG이노텍 탑픽스코어 3→6점 업데이트 (수급빈집B·WWDC D-6·DB증권 185만 신고가)
  [viz_consensus.py] 풀 대시보드 — 다크테마, 45일필터, 범위바, 신고가뱃지, ☀️/🌙 테마토글
  [viz_card.py] 추정이익 카드뉴스 — 세로형 420px, TOP3, PNG저장, 텔레그램 전송 완성
  [카드뉴스] 희생구역(52px 다크배너)으로 텔레그램 상단 크롭 해결
  [명칭] 카드뉴스 제목 "추정이익 카드뉴스" 픽스
- 2026-06-02 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급·중소형주수급·가속화모멘텀·RS → ingest_report_2026-06-02.md
- 2026-06-02 — 세션 마무리: 영상 제작 파이프라인 + 소재찾기 루틴 확립
  [CLAUDE.md] 세션마무리 4단계 / /소재찾기 5단계 루틴 / 영상제작 프로세스 추가
  [소재분석] 젠슨황 방한 소재: 깐부회동 시즌2 + 5일 성수동 + LG씨엔에스 상한가
  [Gemini이미지] generate_jh_images.py 완성 — 씬별 프롬프트 + 인물 레퍼런스 → 이미지 5장 생성
  [Remotion] JH_Sample.tsx (30초 5씬) + LGcns_Scene.tsx (하이브리드 깐부회동+차트) 완성
  [방향확정] 스토리형 AI이미지 + 실사 하이브리드 방향. 이슈형=당일제작 / 분석형=Remotion
  [퍼미션] .claude/settings.json Playwright MCP 전체 자동승인 추가
- 2026-06-01 — Excel ingest 완료:  → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·가속화모멘텀·RS → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: RS → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: RS → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: RS → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 가속화모멘텀 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 중소형주수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 중소형주수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급 → ingest_report_2026-06-01.md
- 2026-06-01 — Excel ingest 완료: 추정이익변경·컨센움직임·수출·유동성·수급 → ingest_report_2026-06-01.md
- 2026-05-30 — 국민성장펀드 빌드업 영상 씬4~6 Remotion 완성 (녹음 전 버전):
  [GB04] GB04_Telegram — 1410프레임 (47초) / Phase1: 클라이맥스형 "저 어떻게 알았냐고요?" / Phase2: 텔레그램 브리핑 목업 4카드 (정책·리포트·유튜브·키워드) / Phase3: "전부 자동으로요." 클라이맥스
  [GB05] GB05_StockBrain — 1380프레임 (46초) / Phase1: STOCK BRAIN 브랜딩 + 4기능 2×2 카드 / Phase2: "따로 영상으로 찍어뒀습니다" + 📌 고정댓글 버튼
  [GB06] GB06_CTA — 930프레임 (31초) / Phase1: 다음 영상 예고 2카드 (주목섹터·수급빈집) / Phase2: 채널명 + 구독버튼 클로징
  [공통] HAS_AUDIO=false — 내일 녹음 후 m4a 넣고 Whisper 싱크 적용 예정
  [tsc] 기존 파일 미사용 경고 2개 뿐, 신규 파일 에러 없음
  [다음] 내일 녹음 후: 국씬4.m4a / 국씬5.m4a / 국씬6.m4a → Whisper 싱크 → GB03도 HAS_AUDIO=true로 전환
- 2026-05-30 — 에이전트직원 영상 씬1~씬4-7 Remotion 전체 완성:
  [씬2 공감] AG_S02_Empathy — 979+30f / 이모지40%+텍스트60% 균형 / 자막바 Whisper 싱크
  [씬3 선언] AG_S03_Declaration — 532+30f / 💼→👥10명→₩0 클라이맥스
  [씬4-1] AG_S04_1_Boss — 412+30f / 🧠 총괄 부채꼴 구조
  [씬4-2] AG_S04_2_Collect — 1660+30f / 📡 소스 흡수 + 타임스탬프
  [씬4-3] AG_S04_3_Supply — 725+30f / 🔍 500종목 스캔 + 🏚️빈집
  [씬4-4] AG_S04_4_Toppick — 550+30f / 🧠 8기준 체크리스트 + 7/9 스코어
  [씬4-5] AG_S04_5_Brief — 637+30f / 📋 4항목 그리드 + ☕한장
  [씬4-6] AG_S04_6_Deploy — 587+30f / 📨 → 텔레그램·카톡·웹 + 07:00
  [씬4-7] AG_S04_7_Others — 686+30f / ⚠️📅🧹 나머지 직원 3명
  [공통] 전 씬 마지막 +30프레임(1초) 여백 적용
  [스타일] 이모지(40%)+텍스트(60%) 균형 + 자막바 Whisper 싱크 규칙 확립
  [다음] 씬5 클라이맥스 ~ 씬8 CTA 녹음 파일 → 집PC에서 이어서
- 2026-05-30 — 국민성장펀드 빌드업 영상 씬1~2 완료 / 씬3 녹음 대기:
  [GB01] ✅ 완료 — "국씬1 수정.m4a" Whisper 싱크 (532프레임/17.72s)
    · Line2 텍스트: "넣지 마세요" → "청약하셨나요?" (대사 싱크 맞춤)
    · fadeOut 제거 (격자무늬 버그 수정)
    · 타이밍: f166 통계/f273 반전박스/f403 강조/f468 서브
  [GB02] ✅ 완료 — "국씬2.m4a" Whisper 싱크 (463프레임/15.44s)
    · 카드 내용 전면 교체: 3조건 → 혜택2(소득공제40%·정부손실방어) + 반전1(⚠️조건있어요)
    · 타이틀: "들으면 넣어야 할 것 같죠?"
    · 카드 등장: f60/f110/f257 (seg별 맞춤)
    · 반전 카드: amber색(#FFB800) 구분
    · fadeOut 제거
  [GB03] 🔲 녹음 대기 — Remotion 수치 수정 완료
    · 수치 검증: 4,254→4,231만원 / 4,800→4,831만원 / 546→600만원 차이
    · 절세 설명: "+317만원 포함 (세율 26.4%)"
    · 계산근거: 3,000만원×(1.06)^5-9.9%세금+소득공제환급317 = 4,231만원
    · fadeOut 제거
  [다음] GB03 녹음("국씬3.m4a") → Whisper 싱크 → 씬4~6 Remotion 제작
  [씬3 대본] 아래 참조 (정확한 수치 포함)
- 2026-05-30 — STOCK BRAIN 서비스 아키텍처 확정:
  [구독 서비스] Push 방식 우선 (텔레그램 봇). SaaS/앱은 나중 단계
  [기술] 크롤링·분류=서버(Python) / 요약·인사이트=Claude API(Haiku 80%+Sonnet 20%)
  [온보딩] 텔레그램 봇에서 채널 링크 등록 → 서버 자동 수집 → 결과 전송
  [비용] Gemini 무료로 시작 → 구독자 100명 이상 시 Claude API 전환
  [개인화] 공개 채널은 서버에서 직접 수집 (고객 계정 불필요)
  [주기] 기본 오전 8시 1회 / 옵션 오전+저녁 2회
- 2026-05-30 — STOCK BRAIN 서비스 기획 완료:
  [구조] 4개 모듈: 유튜브 요약 / 텔레그램 요약 / 뉴스 키워드 / 리포트 인사이트
  [상품] 개별 구독 9,900~14,900원 / 통합 Standard 29,900원 / Premium 49,900원 / 설치형 패키지 49만원~
  [채널 전략] 각 영상 시리즈 = 각 모듈 쇼케이스 → 판매 깔때기
  [기술] Playwright headful 자동 실행 + 자체 녹화(mp4) → Remotion 편집. OBS 불필요.
  [브랜드] STOCK BRAIN / 슬로건: "300개 정보 중 오늘 써먹을 3가지만"
  [다음] 유튜브 브리핑 모듈 개발 스펙 작성 예정
- 2026-05-30 — 모델 자동 분기 설정 완료: 단순작업(log·index·파일탐색)=Haiku 서브에이전트 / 분석·아이디어확장·WebSearch=Sonnet 직접처리. 실행 전 [Haiku]/[Sonnet] 분류 먼저 표시 후 처리.
- 2026-05-30 — 바이오 Tier 1 Phase 1 전체 완료 (Day 1~4): 8종목 stock 마스터 페이지 신규 생성/보강.
  [신규] stock_한미약품.md — GLP-1/MASH, 에페글레나타이드 허가 신청, MSD 기술이전
  [신규] stock_HLB.md — 리보세라닙 PDUFA 2026-07-23 D-Day 확인
  [신규] stock_셀트리온.md — 바이오시밀러 5조+, ADC 3종 2Q 중간결과 임박
  [신규] stock_삼성바이오로직스.md — CDMO 84만5천리터, ADC CDMO 2026Q1 개시, 수주 5조
  [신규] stock_유한양행.md — 렉라자 누적 3억달러 수령, J&J 1Q26 매출 +82%
  [보강] stock_알테오젠.md — 키트루다 SC 로열티 2%, 바이오젠 8676억 계약(2026-03-25)
  [신규] stock_리가켐바이오.md — LCB84 얀센 1상, 오노약품 계약, iM증권 200,000원
  [보강] stock_SK바이오팜.md — 엑스코프리 +52%, 흑자전환, 2026E 영업이익 4154억
- 2026-05-30 — .claude/settings.json에 WebSearch 자동허용 추가 (매번 승인 없이 실행)
- 2026-05-29 — 바이오 Tier 1 Day 1 완료: stock_한미약품.md + stock_HLB.md 신규 생성. WebSearch 교차검증 기반 10항목 표준 템플릿 적용. 수급·컨센 미입력(supply/ 필요). HLB PDUFA 2026-07-23 D-Day 확인.
- 2026-05-29 — 바이오 종목 딥리서치 계획 수립: Tier 1(8)·Tier 2(8)·Tier 3(12) 분류 + 표준 10항목 + 4 Phase 진행순서. raw/테마맵 참고 5장 분석 기반. → wiki/L5_섹터/바이오/바이오_종목딥리서치_계획.md
- 2026-05-29 — **2회차 영상 합의 5곳 적용 완료** — 다음 단계: 자료 캡처 7장 + Remotion 컴포넌트 작업 + 사용자 녹음
  [신규] channel/strategy/strategy_빈집원리.md — 채널 시그니처 4 Rule + 욕조 비유 + 빈집×주도 매트릭스 + 7근거 + 현대모비스 표본
  [수정] stock_현대모비스.md — 🏆 주도 종목 7근거 시그니처 표본 섹션 신규 추가 (7/7 충족)
  [수정] yt_2회차_대본.md — 13씬 → 14씬 (씬 4-0 신규). 6분 50초 → 7분 55초 (+65초)
    · 씬 2: 신고가 vs 눌림 둘 다 OK (+10초)
    · 씬 3: 욕조 비유 + 작동 원리 (+15초)
    · 씬 4-0: 빈집 × 주도 매트릭스 (+25초, 신규)
    · 씬 4-1: 주도 7근거 압축 박기 (+10초)
    · 씬 6: 빈집 + 주도 두 조건 동시 강조 (+5초)
  [키워드 강조] 주도·함정·진입 자리·욕조·수위·물 한 컵·신고가·눌림·시그니처 표본 등 추가
- 2026-05-29 — 세션 종료. 집PC 이어서 예정. 다음 작업: 바이오 종목별 심층 파악 (알테오젠·리가켐·한미약품·HLB 우선순위)
- 2026-05-29 — 바이오 Q1~Q10 딥리서치: 성공 ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8', 'Q9', 'Q10'] / 실패 []
- 2026-05-29 — wiki/스토리/wiki_성장_기록.md 신규: 유튜브 콘텐츠 소재용 시행착오 기록. 오늘 5개 에피소드 기록 (AI 창작 검증·규칙 리팩토링·위키먼저원칙·대장주누락·LS오기공시)
- 2026-05-29 — 전고체 테마 대장주×주가 교차검증 완료: 이수스페셜(457190) 12개월+88.8%·CNPC계약 당일+21.48% 실제 확인. 필에너지+13.18%. analysis_rules.md §0-1에 대장주선정→주가검증→교차검증 3단계 표준 프로세스 추가
- 2026-05-29 — 전고체 대장주 누락 수정: 이수스페셜티케미칼(황화리튬 Li₂S 원료 대장) 위키 추가. 누락 원인: "관련주" 광범위 검색으로 원료 레이어 미검색. analysis_rules.md §0-1 테마 대장주 크로스체크 규칙 신설
- 2026-05-29 — 2차전지_모니터링_지표.md 신규: 3대 선행지표 프레임 저장 (탄산리튬·알버말·EV수요). 현재 신호 🔴반등 확인 (리튬+50%·ALB EBITDA+148%·유럽EV+22%)
- 2026-05-29 — 2차전지 Q1~Q10 딥리서치: 성공 ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8', 'Q9', 'Q10'] / 실패 []
- 2026-05-29 — 방산_매출인식_타임라인.md 신규: 확정계약 기반 매출 인식 시점별 종목 정리 (상반기=천궁3국·하반기=폴란드K2+이라크+KF21양산). 계약 발표 시 폭발 종목 6개 정리 (KF-21 수출 첫계약 = 최강 촉매)
- 2026-05-29 — 천궁-II 밸류체인 위키 저장: stock_LIG넥스원(천궁 체인 추가) + stock_퍼스텍(신규) WebSearch 검증. 확정계약: 퍼스텍→LIG 사우디457억+이라크277억 / 한화시스템 이라크8600억 / 한화에어로 이라크6170억
- 2026-05-29 — 방산 Q9~Q10 재실행: 성공 ['Q9', 'Q10']
- 2026-05-29 — CLAUDE.md 구조 정리 완료: 1,352줄 → 237줄. 상세 규칙 3개 파일로 분리 (wiki/rules/analysis_rules.md / ingest_rules.md / page_templates.md)
- 2026-05-29 — CLAUDE.md + 메모리 규칙 추가: 질문 답변 순서 (위키 1차 → WebSearch 교차검증 → 합쳐서 답). 위키 = 구조·논리, WebSearch = 현재 상태·검증
- 2026-05-29 — 조선 Q1~Q10 딥리서치 완료 + 기존 sector_조선.md 보강. 3사 수치 추가 (HD 118억달러·삼성 54억달러·한화 34억달러 YTD). FLNG 독점·MSRA 방산 체인 정리. 검증 필요 항목 ⚠️ 표기. → sector_조선_Q10.md 신규 / sector_조선.md 업데이트
- 2026-05-29 — 전력기기 Q10 WebSearch 검증 완료: ✅ HD현대일렉(78.88억달러)·효성중공업(15.1조)·빅뷰티법·수출방향 / ❌ LS일렉 수주잔고 8.7조→실제 7.2조 / ⚠️ LS 오기공시 사건(5/27, 1.5조 부풀려→정정, 주가-9%)
- 2026-05-29 — 전력기기 Q1~Q10 딥리서치: 성공 ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8', 'Q9', 'Q10'] / 실패 []
- 2026-05-29 — CLAUDE.md 규칙 추가: 섹터 투자 논리 분류 (TYPE A 실적형/TYPE B 성장형/TYPE C 하이브리드). 탑픽 체크항목 TYPE별 가중치 차등·브리핑 TYPE 표기 의무화
- 2026-05-29 — 대기업 자율주행×로봇 크로스섹터 Q10 리서치 완료: ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8', 'Q9', 'Q10']
  [현대차] SDV+BD+RMAC 밸류체인 / [LG] CLOi+Isaac+RFM / [삼성] 레인보우 지분전략 / 3그룹 비교·연쇄구조
- 2026-05-29 — CLAUDE.md 규칙 추가: 섹터 딥리서치 표준 방법론 확립. Q1~Q10 표준구조 + 대기업 크로스섹터 Q10 + 꼬리에 꼬리 보완 원칙. 섹터별 현황 테이블 + 스크립트 경로 관리. 미착수 섹터: 전력기기·방산·2차전지·바이오·소비내수
- 2026-05-29 — CLAUDE.md 규칙 추가: 대내외 매크로 변수 분석 규칙 (행동원칙 13번). Layer A(국내정책·수급) / Layer B(금리·환율) / Layer C(글로벌매크로) 3레이어 체크 의무화. 섹터별 민감도 매핑표 추가. 탑픽 #6 정책이슈 항목 확장(국민성장펀드·밸류업·코스닥부양)
- 2026-05-29 — CLAUDE.md 규칙 추가: Gemini 리서치 사후 검증 (WebSearch 의무화). 자주 틀리는 패턴 4건 기록 (레인보우로보틱스 GTC2024 ❌ / 유진로봇 Isaac ❌ / 두산로보틱스 시점오류 ⚠️ / 로보티즈 Jetson ⚠️)
- 2026-05-29 — 로봇 Q5~Q10 재실행: 성공 ['Q5', 'Q6', 'Q7', 'Q8', 'Q9', 'Q10'] / 실패 []
- 2026-05-29 — 로봇·피지컬AI Q1~Q10 딥리서치 완료 (Q8 뉴스트리거·Q9 주도종목·Q10 연쇄구조)
- 2026-05-29 — 섹터 트렌드: 로봇·피지컬AI > 반도체·MLCC > 전력기기
- 2026-05-29 — CPU 추론 시대 테마 위키 반영:
  [스토리보드_반도체] 챕터7 "CPU 추론 시대" 신규 추가 (에이전틱AI·온디바이스AI·추론 메모리 체인)
  [stock_오픈엣지테크놀로지] NPU IP 추론 AI 핵심 업데이트 + 정책이슈 ✅
  [stock_삼화콘덴서] 밸류에이션 갭 플레이 패턴 저장 (삼성전기 급등 후 2배 사례)
  [memory] feedback_iterative_research.md 신규 — 꼬리에 꼬리 반복 질문 원칙
  [스크립트] gemini_semiconductor_q10.py에 Q11~Q14 후보 주석 추가
- 2026-05-29 — 반도체 Q10 위키 반영 완료:
  [밸류체인_마스터.md] 연쇄 구조 + 실제 시차 데이터 추가 (HBM체인·MLCC체인·파운드리체인·소부장리레이팅체인)
  [미국커플링_로직.md] 뉴스 트리거 × 주가 반응 패턴 테이블 추가 (12개 뉴스 유형·무반응 케이스·폭발 TOP3)
  [stock_SK하이닉스] 뉴스 반응 패턴 섹션 추가
  [stock_삼성전기] 뉴스 반응 패턴 + 주도주 이유 추가
  [stock_피에스케이홀딩스] 하이브리드본딩 옵션가치 + Q9 숨겨진 진주 반영
- 2026-05-29 — 반도체 Q1~Q10 딥리서치 완료 (Q8 뉴스트리거·Q9 주도종목·Q10 연쇄구조 신규 추가)
- 2026-05-29 — 추정이익 변경 ingest (리레이팅 + TP 상향): 16개 stock 파일 업데이트
  [리레이팅 상향] 11건: LS에코에너지(신한 Trading BUY→매수 +150%), 삼성생명(메리츠 Hold→Buy), 두산퓨얼셀(유진 HOLD→BUY +118%) 외
  [리레이팅 하향] 5건: 한미약품·한세실업(BUY→HOLD), 현대오토에버(Outperform→Underperform)
  [TP 이번 주 강력 컨센서스] 삼성전기(7개사·TP 170~220만), LG이노텍(6개사·TP 81~160만), 현대차(5개사), HD현대중공업(4개사), 솔루엠(3개사)
  [업데이트 파일] 삼성전기·LG이노텍·SK하이닉스·솔브레인·코미코(반도체) / LS에코에너지·솔루엠(테마) / LIG디펜스앤에어로스페이스·한화에어로스페이스·한국항공우주(방산) / 비에이치아이(원전) / HD한국조선해양(조선) 총 12개
  [스크립트] scripts/extract_rerating_v2.py 신규 — Rating/TP 주간 컨센서스 추적 포맷
- 2026-05-29 — **2회차 "현대모비스 종목 추적 시연" 기획 + stock 페이지 + 대본 1차** (집PC 작업): 다음 세션 트리거 = "현대모비스 2회영상 이어서"
  [stock] wiki/L5_섹터/자동차/stock/stock_현대모비스.md 신규 — 탑픽 6/9점 (B 반빈집 21% + 5/27 진입 그날). 자동차부품 X / 로봇·자율주행 코어 / 현대차계열 최저평가 리레이팅
  [대본] channel/yt/yt_2회차_대본.md 13씬 1차 (약 6분 50초). 핵심 메시지 "종목<타이밍" 4회 박힘. 키워드 민트 강조 마크다운 표시
  [영상 골격] 벤치마킹 영상(영상감독 호흡 사례 1.5분)의 9단계 설득구조 매핑 — 권위 디테일 1개 깊게 패턴. Remotion 한 번 제작 + 사용자 녹음 + Whisper 자동 싱크 흐름
  [Remotion 기존 자산 확인] ImgHeroScene·ImgSplitScene·ChartScene·7가지 스윕효과 다 만들어져 있음 — 자료 캡처 7장만 준비하면 새로 만들 컴포넌트 거의 없음
  [합의 미적용] 사용자 보강 요청 5곳: ① strategy_빈집원리.md 신규 ② stock_현대모비스 주도 7근거 섹션 ③ 대본 씬 2·3·4-0·4-1·6 → 다음 세션 첫 작업
- 2026-05-28 — **2강 "딸깍" 기획 + B1~B4 컷 제작** (집PC 작업): 다음 세션 트리거 = "2강 리모션 영상편집 이어서 할게"
  [기획서] channel/yt/yt_2강_딸깍_기획서.md — 하루 다큐 형식, 10분, Remotion only, 시그니처=시계+실제UI재현
  [방향 결정] 7단계 설득구조 폐기 → 시간순 다큐 채택. 4안 비교 → B(UI) 선택
  [Remotion] src/dakkak/ 8개 파일 (B1-B4 채택). Root.tsx 등록 완료. tsc 통과
  [잔여 작업] B1~B4 90~60초 확장 + OPENING/CH5~CH8/CTA 6개 컷 미제작
- 2026-05-28 — 이미지 시스템 + Remotion 차트씬 구축:
  [이미지 다운로드] scripts/download_images.py 신규 — Wikimedia Commons API 기반, 보고서 내용 분석→쿼리 자동 생성(--from-html/--from-text), 한국어→영문 변환 사전(KR_TO_EN), CC라이선스 자동 확인 + 출처_attribution.txt 생성
  [보고서 샘플] out/report_nvidia_sample.html — 젠슨황 히어로+프로필+NVIDIA로고 삽입, STOCK BRAIN 다크 테마
  [보고서 샘플] out/report_조선_20260528.html — 컨테이너선 히어로+LNG탱커 배너+조선소크레인 스플릿, 삼각축 호황 내용
  [Remotion] remotion-stock/src/scenes/ImgScene.tsx 신규 — ImgHeroScene(켄번스줌+오버레이텍스트), ImgSplitScene(좌이미지↔우불릿) 재사용 컴포넌트
  [Remotion] remotion-stock/src/ShipyardVideo.tsx 신규 — 조선섹터 3씬(히어로+LNG스플릿+종목스플릿)
  [Remotion] remotion-stock/src/scenes/ChartScene.tsx 신규 — 실제 차트이미지(KODEX조선ETF)+스캔라인+펄스서클+추세화살표 드로잉 애니메이션 (12초)
  [public] remotion-stock/public/images/ — ship_hero, lng_tanker, jensen_keynote, jensen_profile, chart_조선etf 추가
  [원칙] 모든 보고서/영상 생성 시 고정 매핑 금지, 내용 분석→동적 이미지 검색 적용
- 2026-05-28 — 반도체 미국커플링 DB 구축: 미국커플링_로직.md 신규(NVDA·MU·ASML·TSMC·AMD·Intel·Broadcom·LRCX/AMAT 8종목 한국 반응 매핑 + 브리핑 오류방지 체크리스트) + SK하이닉스·삼성전자·삼성전기 stock/ 파일에 미국 커플링 섹션 추가
- 2026-05-28 — sector_반도체.md 재구성 완료: Q1~Q7 원본(6.5MB) → 조선 섹터 구조 기반 정리본(17.7KB). 지속영향이벤트·타임라인·90일일정·소부장테이블·미중패권분석·종목포지션맵 포함
- 2026-05-28 — 반도체 Q4~Q7 재실행 완료: 성공 ['Q4', 'Q5', 'Q6', 'Q7'] / 실패 []
- 2026-05-28 — 반도체 섹터 Q1~Q7 딥리서치 완료 (Gemini Flash 연속 대화, 7개 질문)
- 2026-05-28 — 반도체 스토리보드 시스템 구축: 스토리보드_반도체.md(6챕터 대서사) + sector_briefing_반도체.html 스토리보드 연동 업데이트(챕터온도계·D-Day달력 추가) + report_반도체_20260528.html 심층리포트 생성(6챕터+주가구간평가+D-Day+리스크매트릭스) + CLAUDE.md 스토리보드 운영규칙 추가
- 2026-05-28 — 조선 섹터 추가 심층 분석 3건: MRO(미해군함정정비 MSRA·42건 발주) + 미해군신조(MASGA·NGLS·필리조선소·무인함 USV/UUV) + FLNG(삼성중공업 4기 10조 임박·크시리심스·코랄노르트) + 8대 이슈 전체맵. sector_조선.md 추가.
- 2026-05-28 — 조선 섹터 주가구간 평가 보고서 생성: out/report_20260528_조선섹터_주가구간평가.html (기존주주·예비주주 전략 + D-Day 달력)
- 2026-05-28 — 조선 섹터 심층 분석 3건 완료: ① 조선엔진×데이터센터 (HD현대힘센엔진 6271억·삼성중공업FDC) ② 핵추진잠수함 장보고-N (28.9조, 한화오션 ADD설계, 2030년대 중반 진수) ③ HD현대 원전 파운드리 (테라파워 나트륨SMR RES 우선협상자·NRC허가 2026-12). sector_조선.md 3개 섹션 추가.
- 2026-05-28 — fetch_투경.py 재설계 완료 (목록수집 제거 → 조건분석 전용). KRX API 필드 버그(mktId→marketEngName) 수정. 표시 버그(×60%→×160%) 수정. 재실행 결과: 제주반도체·코리아써키트 3조건 모두 해소 → 5/29 해제 예상. 투경관리.md·양 stock 파일 업데이트.
- 2026-05-28 — 투경 확인: 제주반도체·코리아써키트 스크립트 오판(네이버 15건 제한) → 실제 KIND 미해제. 심텍·티에스이 5/26 신규 지정·네이처셀·바이젠셀·아모텍 5/28 신규 지정 반영. fetch_투경.py 페이지네이션 버그 확인.
- 2026-05-27 — 리포트 ingest (115건) → 위키 반영: SK하이닉스·삼성전자·삼성전기·솔브레인·코미코·ISC 업데이트 + SNT다이내믹스·OCI홀딩스·SK·삼성물산·덴티움·한올바이오파마 업데이트 + 유니테스트·아이씨티케이·아모텍·삼성중공업·HJ중공업·비에이치아이·수산인더스트리·두산퓨얼셀·성일하이텍·솔루엠 신규 생성 (20종목). 반도체·방산 index 업데이트.
- 2026-05-27 — 섹터 캘린더 ingest: 매크로 19건 + 섹터 94건 → 16개 섹터 index.md 이벤트히스토리·콘텐츠기회 반영
- 2026-05-27 — 수급빈집 ingest: A=29 B=38 재진입=32
- 2026-05-26 — 업종수급 ingest: IT > 반도체와반도체장비 > 산업재

## 2026-05-27 (21차) — extract_유동성컨센.py 완성

**작업 유형**: 스크립트 신규 작성

### 변경 사항
- `extract_유동성컨센.py` 신규 작성
  - `raw/유동성 컨센등등.xlsm` → 7개 섹션 추출 → `raw/market/YYYYMMDD_유동성컨센_요약.md`
  - 섹션1: 수급빈집 (유동성컨셉 통합순위, 기관 유니버스 546종목 기준, A≥491/B≥410)
  - 섹션2: 2027년 컨센 신고가 (시트1+2 합산, 246종목)
  - 섹션3: 가속화모멘텀 상위 20종목 (스코어 기반 정렬)
  - 섹션4: 업종 1개월 컨센서스 (최종점수 기준 상위 25개)
  - 섹션5: 주도주 찾기 (시총600위내 + 수익률상위5% + MDD20%이내)
  - 섹션6: 코스피/코스닥 SIO (지수, 과매수과매도%, 상승하락 거래량)
  - 섹션7: 50일 신고가 (39종목)

### 오늘 데이터 (2026-05-22 기준)
- 수급빈집(A/B): 208종목
- 컨센신고가: 246종목
- 코스피 SIO: 85.4% (과매수) / 코스닥 SIO: 97.5% (강력 과매수)
- 주도주: 대원전선(+137.8%), 에스에이엠티(+117.8%), LG이노텍(+97.2%)

### 실행 방법
```
python extract_유동성컨센.py [--tg]
출력: raw/market/YYYYMMDD_유동성컨센_요약.md
```
## 2026-05-27 (28차) — 섹터 캘린더 수집 및 위키 반영

**작업 유형**: Gemini API 자동수집 + 위키 ingest

### 변경 사항
- `fetch_sector_calendar.py` 신규 작성 — Gemini 2.5 Flash + Google Search 그라운딩
  - 2단계 방식: Step1 매크로 일정 / Step2 16개 섹터별 개별 쿼리
  - 출력: `raw/캘린더/20260527_섹터캘린더.json`, `20260527_캘린더_요약.md`
- 수집 결과: 매크로 19건 + 섹터 이벤트 94건 (자동차 15, 바이오 13, 신재생 9 등)
- 16개 섹터 index.md 이벤트 히스토리 + 콘텐츠 기회 섹션 업데이트

### 주요 임박 이벤트 (HIGH)
- 2026-05-28: 한국은행 금통위 기준금리 결정
- 2026-05-28: 큐렉소 키움 Corporate Day
- 2026-06-02: ASCO 2026 (지아이이노베이션·온코닉), 알래스카 LNG 서밋
- 2026-06-12: SpaceX IPO 나스닥 상장 목표
- 2026-06-16: 미국 FOMC 금리 결정, ISS 2026 국제우주 컨퍼런스
- 2026-06-30: HLB FDA 허가 결정, LG에너솔 2Q 흑전, K-스틸법, 개소세 인하 종료
- 2026-07-01: EU 한국산 철강 관세 50% 상향 (⚠️ 리스크)

### 사용 방법
```
python fetch_sector_calendar.py              # 전체 16섹터
python fetch_sector_calendar.py --sectors 반도체,방산
python fetch_sector_calendar.py --tg        # 텔레그램 전송
```

---

## 2026-05-27 (27차) — 위키 섹터 구조 엑셀 기준 전면 재정렬

**작업 유형**: 위키 구조 개편

### 변경 사항
- **폴더 이름 변경**: `전력기기` → `전력` / `2차전지ESS` → `이차전지` (엑셀 watchlist 기준 통일)
- **신규 섹터 7개 생성**: 우주, 원전, 신재생, 화장품, 미용, 철강, 엔터 (index.md + stock/ 구조)
- **stock_한전기술.md** 전력 → 원전/stock/ 이동 (sector_map 기준 재분류)
- **sector_map.json 전면 갱신**: 16개 엑셀 섹터 기준 + 기존 AI소프트웨어·소비내수·테마이벤트 유지
- watchlist.json 기반 19개 섹터 구조 완성

### 최종 섹터 구조
**엑셀 16개 (daily)**: 반도체, 방산, 조선, LNG, 바이오, 우주, 로봇, 자동차, 이차전지, 전력, 원전, 신재생, 화장품, 미용, 철강, 엔터
**기존 유지 3개**: AI소프트웨어, 소비내수, 테마이벤트

---

## 2026-05-27 (26차) — fetch_투경.py 완성 + 투경 실제 분석 텔레그램 전송

**작업 유형**: 스크립트 버그 수정 + 실제 데이터 분석

### 변경 사항
- **영업일 계산 수정**: `RELEASE_ELIGIBLE_DAYS=14` → `business_days_elapsed()` 함수 (지정일 포함 inclusive, 10영업일)
- **멀티페이지 주가 수집**: `get_close_prices()` 1페이지(10건) → 최대 4페이지 순회 (20건+)
- **텔레그램 메시지 개선**: 유지 종목 37개 나열 제거 → 분석된 종목만 표시 + 미경과 N종목 요약

### 오늘 투경 분석 결과 (2026-05-27 장마감)
- 🟢 **제주반도체 (080220)**: 3조건 AND 모두 해소 → **5/28 해제 예상** (108,200원 / T5 112.8% / T15 190.8%)
- 🔥 **코리아써키트 (007810)**: ③최고가 1조건 미해소 → **5/28 신고가 미경신시 해제**
- 🔴 파인텍 (131760): T5/T15 479.2% — 장기 모니터링
- 🔴 단일가 3종목: 대원전선우·오션스바이오·피델릭스 (0일차, 오늘 신규)
- ⏳ 나머지 37종목: 10영업일 미경과 (대부분 5/27 신규 지정)

### 내일(5/28) 확인 사항
- 제주반도체: KRX 해제 공시 확인 → stock/ 페이지 투경 해제 처리 + 탑픽 페널티 복구
- 코리아써키트: 종가 확인 → 신고가 경신 여부로 해제/이연 결정

## 2026-05-27 (25차) — fetch_투경.py 전면 재설계 (Naver + 단일가 + stock_db)

**작업 유형**: 아키텍처 재설계

### 변경 사항
- **데이터 소스 전환**: KIND Selenium(매일) → Naver HTTP(매일) + KIND Selenium(주 1회 --kind)
- **단일가(투자위험) 추가**: type=risk 목록 수집 + 경과일 계산
- **stock_db.json 신설**: 지정일 영구 캐시 (code 키, des_date_warning/risk 저장)
- **신규 감지**: warning/risk 분리 (이전 목록 vs 현재 목록 code 비교)

### 일일 명령어
```
python fetch_투경.py          ← 매일 (Naver, 빠름)
python fetch_투경.py --tg     ← + 텔레그램
python fetch_투경.py --kind   ← 주 1회: KIND 지정일 갱신
```

### 텔레그램 메시지 4섹션
1. 🆕 신규 투경/단일가 지정
2. 🟢 해제 가능 (내일 해제 예상)
3. 🔶 해제 임박 (1조건 미해소, gap ≤ 10%)
4. 🔴 단일가 목록 (종목 + N일차)

---

## 2026-05-27 (24차) — fetch_투경.py 일일 루틴 + 텔레그램 완성

**작업 유형**: 기능 추가

### 신규 기능
- `--daily --tg` 명령어로 매일 1회 실행 완성
- **신규 종목 감지**: `raw/투경/투경_활성_최신.json` vs 오늘 목록 비교 → 신규 자동 탐지
- **해제 임박 분류** (`classify_imminence`):
  - 🟢 해제가능: 3/3 조건 해소
  - 🔥 임박: 1개 조건 미해소 + gap ≤ 10% or ③최고가 조건만 남음
  - 📍 근접: 1개 조건 미해소 + gap ≤ 25%
  - 🔴 유지중: 2개 이상 미해소
- **텔레그램 메시지** (`build_tg_message`): 신규/해제가능/임박/유지 4섹션
- `analyze_release()`에 `elapsed_days` 파라미터 추가 (메시지에 N일차 표시)

### 일일 명령어
```
python fetch_투경.py --daily      ← 분석만
python fetch_투경.py --daily --tg ← 분석 + 텔레그램 전송
```

---

## 2026-05-27 (23차) — 투경 해제 로직 확정 + 관련 파일 일괄 정리

**작업 유형**: 로직 확정 + 파일 정합성 정리

### 확정된 투경 해제 조건 (raw/투경해제 공식.xlsx 실증 검증)
- **코스닥**: 당일 < T-5×160% AND 당일 < T-15×200% AND 당일 ≠ 15일최고가
- **코스피**: 당일 < T-5×145% AND 당일 < T-15×175% AND 당일 ≠ 15일최고가
- ★ 3가지 모두(AND) 해소여야 해제. 하나라도 살아있으면 이연.
- ★ 사유유형(급등형/불건전형) 기준 폐기 → 시장(코스피/코스닥) 기준으로 교체

### 수정 파일 목록
1. `fetch_투경.py` — save_release_analysis() 헤더 주석 구버전 텍스트 수정
2. `wiki/L6_수급/투경관리.md` — 전면 재작성
   - 현재 투경 4종목(제주반도체·코리아써키트·파인텍·브이엠) 반영
   - 코스피/코스닥 해제 조건 표 작성
   - 2026-05-27 기준 각 종목별 해제 조건 현황 추가

---

## 2026-05-27 (20차) — 섹터 수급오실레이터 시스템 완성

**작업 유형**: 스크립트 전면 개편

### `watchlist_parser.py` 신규 작성
- `raw/내 관심종목.xlsx` → `watchlist.json` 자동 변환
- 16개 일일 섹터 × 서브섹터 계층 구조 파싱
- 섹터: 반도체(26서브/65종목) 방산 조선 LNG 바이오 우주 로봇 자동차 이차전지 전력 원전 신재생 화장품 미용 철강 엔터
- 종목 추가: 엑셀만 편집 후 `python watchlist_parser.py` 재실행

### `calc_oscillator.py` 전면 개편
- `--all`: 16개 섹터 전체 스캔 (10.6초)
- `--sector 반도체 조선`: 지정 섹터만 스캔
- 파일 자동 탐지: `외국인기관수급오실레이터*.xlsm` (최신 수정일 우선)
- 텔레그램 출력: 섹터별 메시지, 서브섹터 그룹핑, 빈집(A+B)만 표시
- 중복 종목 제거 (같은 섹터 내 여러 서브섹터에 등장 시 첫 번째만)

### 일일 명령어
```
python watchlist_parser.py          ← watchlist.json 재생성 (종목 추가 후)
python calc_oscillator.py --all --tg ← 16섹터 스캔 + 텔레그램 전송
python calc_oscillator.py --sector 반도체 방산 --tg ← 특정 섹터만
```

---

## 2026-05-27 (22차) — 투경 해제 공식 검증 + 스크립트 로직 수정

**작업 유형**: 공식 파일 검증 → 핵심 버그 발견 및 수정

### raw/투경해제 공식.xlsx 실증 검증 (3케이스 ALL 통과)
- 코스피 종목: 45%/75% 기준, 6/4 해제 → ①OK ②OK ③OK ✅
- 코스닥 종목1: 60%/100% 기준, 6/4 이연(최고가 조건 미해소) ✅
- 코스닥 종목2: 60%/100% 기준, 6/4 이연(T-15 조건 미해소) ✅

### 발견된 버그 2개

**버그1 (핵심 — 로직 오류)**
- 기존: `can_release = not (cond_t5 and cond_t15 and cond_high)` → OR 로직 (하나라도 해소 = 해제)
- 공식: **3가지 모두 해소(AND)여야 해제**
- 수정: `can_release = cond1_ok and cond2_ok and cond3_ok`
- 영향: 기존 코드는 최고가 조건만 미해소여도 해제로 잘못 판정 → 과대 낙관

**버그2 (분류 기준)**
- 기존: 사유유형(급등형/불건전형)으로 임계값 분류
- 공식: 시장(코스피/코스닥)으로 분류 (코스피 45%/75%, 코스닥 60%/100%)
- 수정: `MARKET_THRESH = {'KOSPI': (1.45, 1.75), 'KOSDAQ': (1.60, 2.00)}`
- 참고: 두 분류의 숫자값은 우연히 일치하나, 분류 기준 자체가 다름

---

## 2026-05-27 (21차) — fetch_투경.py 버그 수정 + 투경 종목 wiki 업데이트

**작업 유형**: 스크립트 버그 수정 + wiki 정확도 수정

### `fetch_투경.py` fetch_active() 버그 수정
- **버그**: SELECT(100건)를 `fnSearch()` 이후에 설정해 기본 15건만 수집되던 문제
- **수정**: SELECT 100건 설정을 `fnSearch()` 호출 전으로 이동 + JavaScript 직접 조작
- **추가**: 페이지네이션 루프 (최대 20페이지) — 100건 이상 활성 투경 전체 수집 가능
- 결과: 제주반도체(196번, 5/14 지정)·코리아써키트(195번, 5/14 지정) 누락 방지

### wiki 종목 페이지 투경 상태 정정
- `stock_제주반도체.md`: "투경 임박 위험" → "⛔ 2026-05-14 투자경고 지정 중" + 해제조건 분석
  - T-15 기준(117,800) 현재가(118,900) 1,100원 초과 — 5/28 하락 시 해제 가능
  - 탑픽 스코어 1점 → 0점 (-1 투경 페널티)
- `stock_코리아써키트.md`: 투경 지정 상태 누락 → ⛔ 추가 + 해제조건 분석
  - T-5(89,500)×160%=143,200 조건 해소. 15일 최고가 조건만 미해소(내일 경신 중단 시 해제)
  - 탑픽 스코어 1점 → 0점 (-1 투경 페널티)

---

## 2026-05-27 (19차) — 투경 해제조건 분석 + 종목 신규 등록

**작업 유형**: 신규 스크립트 + 종목 분석

### 투자경고 해제 조건 분석 시스템 (`fetch_투경.py`)
- `--active`: 현재 활성 투경 15건 수집 (KIND 투경탭)
- `--release`: KRX 시장감시규정 기반 해제 조건 자동 계산
  - 급등형: T-5 < 160%, T-15 < 200%, 최근15일 최고가 아님 → 해제
  - 불건전형: T-5 < 145%, T-15 < 175%, 최근15일 최고가 아님 → 해제
- 예측: 아이로보틱스·하나마이크론 — 10영업일(~6/3) 경과 즉시 해제 유력
- 썬테크 — 급등형이면 해제 가능, 불건전형이면 T-5 조건 아직 유지

### 신규 종목 wiki 등록 (요청 분석)
- `stock_제주반도체.md`: 코스닥 080220. 20일 +84% 개인 주도 급등. 투경 위험. 🟡 대기.
- `stock_한솔아이원스.md`: 코스닥 114810. CCL 소재. 기관 강매도 vs 외국인 강매수 충돌. ⚠️
- `stock_코리아써키트.md`: KOSPI 007810. 기관+외국인 5일 동시 매수 +90K/+115K. 신고가. 🟠 관심.

---

## 2026-05-26 (18차) — 수급오실레이터 원리·콘텐츠 논리 정리

**작업 유형**: 개념 정리 + 유튜브 콘텐츠 논리 구조화

### 수급오실레이터 공식 완전 분해
- 원시신호: `(기관+외인 순매수) / 시가총액` → MACD(EMA12-EMA26) → Signal(EMA9) → 오실레이터
- 빈집 논리 체인: 수급 공백 → 매도 오버행 없음 → 테마 촉매 시 저항 없는 상승
- 욕조 비유 + 30초 시청자 설명 시나리오 작성

### 핵심 인사이트 (콘텐츠용)
- 외인/기관 연속매수 중에도 빈집 가능: EMA 후행 특성 때문. **빈집 + 방향↑ = 최고 셋업**
- 신고가 + 빈집 가능: 개인 주도 vs 기관 주도 상승 구분법
- 연속매수(즉각 신호) vs 오실레이터(중기 방향) — 측정 대상이 다름, 교차 사용 필요
- 3단계 필터: 오실레이터 빈집 → 연속매수 확인 → 방향↑ 전환

### 솔직한 한계 정리
- 빈집 단독 = 근거 없음. 영구 빈집 소형주 다수 존재
- 백테스트 없음 — "논리적으로 맞다"와 "실제로 돈 된다"는 별개
- 시스템의 진짜 역할: **확률 높은 픽 찾기**보다 **구조적으로 불리한 진입(과매수) 피하기**
- 핵심 멘트: "오를 때 더 크게, 안 오를 때 덜 빠지는 구조"

---

## 2026-05-26 (17차) — 크롤링 브리핑 텔레그램 발송 스크립트 완성

**작업 유형**: 신규 자동화 스크립트 개발

### `send_crawl_brief.py` 완성
- **위치**: 프로젝트 루트 `send_crawl_brief.py`
- **입력**: `raw/크롤링 블로그뉴스유튭 요약/` 폴더 (날짜별 MD 파일)
- **기능**:
  - 오늘 날짜 파일 자동 탐지
  - 노이즈 필터링 (스벅·미스트롯·여행·음악 등 주식 무관 자동 제외)
  - 3분류 자동 판별: 뉴스묶음 / 유튜브 / 블로그
  - 중복 제목 dedupe
  - 섹터 태그 자동 집계 (반도체·조선·에너지·로봇)
  - 텔레그램 HTML 포맷 + 4096자 초과 시 자동 분할 발송
- **첫 발송 성공**: 2026-05-26 21:57 — 12건 (노이즈 4건 제외)

**사용법**:
```
python send_crawl_brief.py          ← 오늘 자동 발송
python send_crawl_brief.py --dry    ← 미리보기만
python send_crawl_brief.py --date 2026-05-25  ← 특정 날짜
```

---

## 2026-05-26 (16차) — 위키 파일 구조 정리 + 수급오실레이터 스크립트 완성

**작업 유형**: 파일 구조 일괄 정리 + 자동화 스크립트 신규 개발

### 테이블.md → 섹터index.md 병합 (`merge_table.py`)
- 12개 섹터 `테이블.md` 내용을 각 `{섹터}index.md`의 `## 📋 서브섹터 매핑` 섹션으로 병합 후 삭제
- 53개 `.md` 파일 내 테이블 링크 자동 업데이트
- 대상 섹터: 반도체·조선·방산·전력기기·바이오·로봇·2차전지ESS·소비내수·자동차·AI소프트웨어·테마이벤트·LNG

### index.md 파일명 변경 (`rename_layers.py`)
- L1~L6 레이어 + 외부인사이트 + wiki 루트 `index.md` → `{폴더명}index.md` 패턴으로 일괄 변경
- 변경 목록: 글로벌유동성index / 미국시장index / 한국시장index / 국제정세index / 섹터index / 수급index / 외부인사이트index / 위키index
- 11개 `.md` 파일 내부 링크 자동 업데이트 완료

### `calc_oscillator.py` 완성
- **위치**: 프로젝트 루트 `calc_oscillator.py`
- **공식**: `(기관+외인순매수)/거래대금` → MACD(12,26) - Signal(EMA9) = 오실레이터
- **검증**: SK하이닉스 오차 4.18e-09 ✅
- **백분위**: xlsm 사전계산 기준값(R7~R11 C12) 사용 → 단일 종목 조회 ~27초
- **다종목 비교**: 스페이스 구분으로 여러 종목 동시 조회 + 빈집순 비교표 출력
- **텔레그램**: `--tg` 플래그로 결과 즉시 전송 (.env BOT_TOKEN/CHAT_ID 사용)

**사용법**:
```
python calc_oscillator.py SK하이닉스 삼성전자 한미반도체 --tg
```

---

## 2026-05-26 (15차) — 반도체 섹터 대시보드 5/26 업데이트

**작업 유형**: `out/sector_dashboard_반도체.html` 데이터 갱신

**주요 변경**:
- 날짜 2026-05-24 → 2026-05-26
- 시장 요약: 단기조정 → 🔴 빅3 TP 역대최고 / 사이클 재확인
- 서브섹터 레이더: SK하이닉스·삼성전자 WARN→ACTIVE, 전공정(소재) ACTIVE 신규 추가 (5개 ACTIVE)
- 컨센서스: SK하이닉스 310만·삼성전자 490K·삼성전기 200만 + 테크윙/심텍/하나마이크론/티에스이 상향 반영
- 탑픽: 삼성전기 4→5점(리포트신고가), 덕산하이메탈 → 테크윙(어닝서프+247%)으로 교체
- 뉴스 타임라인: NH TP격상·신한SK 200만·테크윙 서프·소부장 재평가 5/26 기사로 전면 교체
- 히스토리 타임라인: 5/26 TODAY 항목 추가

---

## 2026-05-26 (14차) — 테마맵 기준 로봇·원전 섹터 테이블 종목 보완

**작업 유형**: 테마맵 참고 PNG 대조 → 누락 종목·서브섹터 테이블 추가

**로봇 테이블 업데이트** (`wiki/L5_섹터/로봇/로봇index.md`):
- 완성로봇: 현대오토에버 (467870), 현대모비스 (012330) 추가
- SI: 로보스타 (090360), 클로봇 (352480), 휴림로봇 (090220) 추가
- 감속기/구동계: 이랜시스 (054630), 삼현 (032960) 추가
- 액추에이터/모터: 하이젠알앤에이 (174900), 왕익홀딩스 (047770) 추가
- 협동로봇: 뉴로메카 (462870) 추가
- 물류로봇: 유진로봇 (056080) 추가
- 의료로봇: 미래컴퍼니 (049950) 추가
- 신규 서브섹터 추가: 방산로봇(아이쓰리시스템), 중기계/시제품(대동기어·TPC로보틱스), 신규진입(나우메카·재넥스로봇·티엑스알)

**원전 테이블 업데이트** (`wiki/L5_섹터/테마이벤트/테마이벤트index.md` 행#9):
- 현대건설 (000720) 대장 추가
- 한신기계 (105620), 미코 (059090), 일진파워 (094820), 이구산업 (025820), LS에코에너지 (229640) 추가

---

## 2026-05-26 (13차) — 6개 변화 파일 전체 wiki 반영 (추정이익·컨센·일정수주·투자아이디어·액티브ETF·페어트레이딩)

**작업 유형**: 일일 변화 파일 6종 ingest → 기존 stock 파일 업데이트 + 신규 stock 파일 생성

**추정이익 변화 반영**:
- `반도체/stock/stock_삼성전기.md` — 신한 TP 1M→2M, SK TP 1.5M→2M 상향. 리포트신고가 ✅, 탑픽 4→5점
- `반도체/stock/stock_SK하이닉스.md` — NH투자증권 TP 1.8M→3.1M 상향
- `반도체/stock/stock_삼성전자.md` — NH TP 310K→490K, 한화 TP 330K→390K 상향
- `방산/stock/stock_한화에어로스페이스.md` — 다올 TP 1.5M→2.04M 상향. 리포트신고가 ✅, 탑픽 5→6점
- `방산/stock/stock_한국항공우주.md` — 다올 TP 210K→250K 상향
- `반도체/stock/stock_LG이노텍.md` — 신규 생성. 하나 TP 700K→1.3M (+85.7%). 리포트신고가 ✅

**컨센 변화 반영**:
- `반도체/stock/stock_테크윙.md` — 1Q26 어닝서프 ✅ (실적 9.7B vs 컨센 2.8B). 탑픽 3→4점
- `반도체/stock/stock_티에스이.md` — 컨센상향 +76.44% (85.3→150.5십억원) 이벤트 추가
- `반도체/stock/stock_심텍.md` — 컨센상향 +29.75% (136.17→176.68십억원)
- `반도체/stock/stock_하나마이크론.md` — 컨센상향 +20.99% (251.6→304.43십억원)
- `로봇/stock/stock_에스피지.md` — 컨센상향 +31.71% (20.5→27십억원)
- `반도체/stock/stock_서울반도체.md` — 신규 생성. 1Q26 어닝서프 ✅ (흑자전환 서프라이즈)
- `반도체/stock/stock_기가비스.md` — 신규 생성. 컨센상향 +20.85%
- `반도체/stock/stock_DB하이텍.md` — 신규 생성. 컨센상향 +17.74%

**일정수주 변화 반영**:
- `조선/stock/stock_HD한국조선해양.md` — 신규 생성. 수주잔고 1Q26 89조원 QoQ +8.34%
- `조선/index.md` — 오늘의 한줄 수주잔고 업데이트

**투자아이디어 변화 반영**:
- `바이오/stock/stock_알테오젠.md` — 신규 생성. 2026 2Q~4Q Keytruda SC 로열티 모멘텀
- `소비내수/stock/stock_롯데관광개발.md` — 신규 생성. 2026 2Q~3Q 카지노·성수기
- `로봇/stock/stock_로보티즈.md` — 4Q 모멘텀 추가 (OPM 28%·CAPA 증설)
- `테마이벤트/stock/stock_현대건설.md` — 4Q 기업가치 리레이팅 모멘텀 추가
- `바이오/index.md` — 알테오젠 대장주 현황 추가

**액티브ETF 변화 반영**:
- `반도체/stock/stock_이오테크닉스.md` — ETF 2개 편입 이벤트 추가
- `반도체/stock/stock_심텍.md` — ETF 2개 편입 이벤트 추가
- `테마이벤트/stock/stock_SK스퀘어.md` — ETF 3개 편입 이벤트 + 컨센상향 +54.16% 추가
- `반도체/stock/stock_두산테스나.md` — 신규 생성. ETF 4개 편입 (공통 편입 1위)

**섹터 인덱스 업데이트**:
- `반도체/index.md` — 오늘의 한줄 + 대장주 현황 TP 최신화
- `바이오/index.md` — 알테오젠 추가
- `조선/index.md` — 수주잔고 업데이트

**페어트레이딩**: LS ELECTRIC vs LS — 스프레드 확대 신호 (현재 0.4447 > 평균 0.1652). stock 파일 미생성 (금일 기준 유의미한 신규 모멘텀 없음)

**신규 생성 파일 목록**: stock_LG이노텍, stock_서울반도체, stock_기가비스, stock_DB하이텍, stock_두산테스나, stock_알테오젠, stock_HD한국조선해양, stock_롯데관광개발

---

## 2026-05-26 (12차) — Gemini 리포트 자동화 파이프라인 가동 + 10건 ingest

**작업 유형**: extract_report.py 5종 폴더 라우팅 개편 + 샘플 10건 처리 + wiki 반영

**extract_report.py 개편**:
- 5개 폴더 자동 라우팅: 종목/산업/경제/시황/투자정보 폴더별 전용 프롬프트
- "원원" 중복 단위 버그 수정
- 리레이팅 판정 기준 프롬프트 강화
- 요약 MD 유형별 섹션 분리 출력

**오늘 처리 (Gemini Flash 추출)**:
- 종목보고서 2건: 파마리서치(TP 620,000 유지), SK스퀘어(TP 상향)
- 산업보고서 2건: 2H26 IT/전기전자 아웃룩(FC-BGA 쇼티지), 음식료 weekly
- 경제분석 2건: 이란·호르무즈 리스크 / 달러-원 환율 전망
- 시황 2건: Global Carbon Daily(유가 급락), 주간 증시 브리핑
- 투자정보 2건: 삼성전자·SK하이닉스 레버리지ETF, ETF 머니무브

**wiki 반영 (전체 10건)**:
- `바이오/stock/stock_파마리서치.md` 신규 생성 (종목보고서)
- `테마이벤트/stock/stock_SK스퀘어.md` 신규 생성 (종목보고서)
- `반도체/stock/stock_대덕전자.md` 신규 생성 (산업보고서)
- `반도체/stock/stock_삼성전기.md` — FC-BGA 쇼티지 최신이벤트 + 컨센서스 (산업보고서)
- `바이오/index.md` — 파마리서치 대장주 현황 (종목보고서)
- `소비내수/index.md` — 환율 안정·음식료 원가 완화 지속영향이벤트 (산업보고서)
- `L4_국제정세/index.md` — 이란/호르무즈 지정학 시나리오 추가 (경제분석보고서 2건)
- `L1_글로벌유동성/market_달러_환율_흐름.md` — 이란 협상 시나리오·일일추적 (경제분석보고서)
- `L3_한국시장/index.md` — 삼성전자 노사합의·엔비디아 호실적·WTI 급락 (시황보고서 2건)
- `반도체/stock/stock_삼성전자.md` — 레버리지ETF 최신이벤트 (투자정보보고서)
- `반도체/stock/stock_SK하이닉스.md` — 레버리지ETF 최신이벤트 (투자정보보고서)
- `반도체/index.md` — ETF 머니무브 콘텐츠 기회 (투자정보보고서)
- `전력기기/index.md` — ETF 머니무브 콘텐츠 기회 (투자정보보고서)

**CLAUDE.md 라우팅 규칙 추가**: 5종 리포트 유형별 wiki 반영 경로 명문화

**생성 파일**: `raw/report/요약/20260526_요약.md`

---

## 2026-05-25 (11차) — 투자아이디어정리 실제 ingest 실행 (반도체·방산 전체)

**작업 유형**: stock 파일 생성·업데이트 (투자아이디어정리.xlsx 반도체소부장·방산 시트)

**기존 파일 업데이트 (일정 섹션 분기 모멘텀 추가)**:
- `반도체/stock/stock_코미코.md` — 2Q: 미국 매출 본격 반영 / ESC 매출 증가, 3Q: TSMC 일본·유럽 대응
- `반도체/stock/stock_브이엠.md` — 2Q: DRAM/HBM 투자 본격화 / Poly·부품 Mix 개선, 3Q: 고객 확장
- `반도체/stock/stock_피에스케이.md` — 2Q: 삼성·SK 신규 Fab / 북미 리쇼어링, 3Q: 수주잔고 증가
- `전력기기/stock/stock_효성중공업.md` — 일정 섹션 신규 추가: 2Q 북미 생산 슬롯 / 3Q 멤피스 증설

**신규 반도체 stock 파일 생성 (10개)**:
- `이오테크닉스` (039030) — 레이저 마킹·HBM4 펨토초 커팅
- `이수페타시스` (007660) — 고다층 PCB·AI 서버, 수주잔고 +2.6배 역대최고
- `유진테크` (084370) — LPCVD/ALD 장비, DRAM Capex 재가속
- `티에스이` (131290) — Probe Card, DRAM/HBM 첫 확대
- `리노공업` (058470) — 테스트 소켓 핀, 2nm 공정 수요
- `테크윙` (089030) — HBM4 핸들러·큐브프로버
- `하나마이크론` (067310) — 후공정 OSAT, HBM 외주 확대
- `한솔케미칼` (014680) — ALD 전구체, DRAM/HBM 수요 최대
- `심텍` (036710) — GDDR7·서버 고층기판
- `삼성전기` (009150) — MLCC·FC-BGA 이중 레버리지

**방산 stock/ 폴더 신설 + 종목 파일 생성 (5개)**:
- `방산/stock/stock_한화에어로스페이스` (012450) — K9·천무, 수주잔고 118조 역대최고, 5/9점
- `방산/stock/stock_현대로템` (064350) — K2 전차, 수주잔고 역대최고, 5/9점
- `방산/stock/stock_LIG넥스원` (079550) — 천궁-II 수출, 수출비중 30% 상회 구간
- `방산/stock/stock_한국항공우주` (047810) — KF-21 양산·FA-50 글로벌
- `방산/stock/stock_풍산` (103140) — 탄약+신동 이중 레버리지

**신규 로봇 stock/ 폴더 + 종목 파일 생성 (5개)**:
- `로봇/stock/stock_로보티즈` (108490) — 다이나믹셀·AI Worker·데이터팩토리
- `로봇/stock/stock_레인보우로보틱스` (277810) — K-휴머노이드·삼성전자 파트너
- `로봇/stock/stock_에스피지` (073070) — 감속기·AMR 부품
- `로봇/stock/stock_현대오토에버` (307950) — Physical AI 플랫폼
- `로봇/stock/stock_현대무벡스` (319400) — 병원·물류 로봇

**신규 테마이벤트(원전) stock/ 폴더 + 종목 파일 생성 (2개)**:
- `테마이벤트/stock/stock_현대건설` (000720) — 글로벌 원전 EPC·미국·불가리아 착공
- `테마이벤트/stock/stock_두산에너빌리티` (034020) — 원전 기기·SMR·가스터빈

**소스**: `raw/투자아이디어정리.xlsx` 반도체소부장·방산·로봇·원전 시트 직접 추출

---

## 2026-05-25 (10차) — 외부인사이트 관리 시스템 신설

**작업 유형**: 신규 폴더·파일 생성 + CLAUDE.md 규칙 추가

**신규 파일**:
- `wiki/외부인사이트/외부인사이트index.md` — 소스 레지스트리 + 최근 핵심 인사이트 요약
- `wiki/외부인사이트/태린이아빠.md` — 포스팅 날짜별 누적 파일
  - 2026-05-22 수록: 주도업종(반도체·전력·자동차로봇·네트워크), 인텔CEO AI 4대병목, 5~10월 조정 시나리오

**CLAUDE.md 추가**:
- 위키 구조에 `외부인사이트/` 폴더 추가
- 외부인사이트 관리 규칙 섹션 신규 추가 (논리 보존 원칙·처리 체크리스트)

**운영 원칙**:
- 결론만 저장 금지 — 거시→섹터→종목 3계층 논리 구조 보존
- 새 포스팅: 날짜 섹션 추가 (덮어쓰기 금지)

---

## 2026-05-25 (9차) — 투자아이디어정리 ingest 규칙 추가

**작업 유형**: CLAUDE.md 규칙 추가

**소스 분석**: `raw/투자아이디어정리.xlsx` — 약 40개 시트, 섹터·종목별 분기 투자 모멘텀 DB

**CLAUDE.md 추가 내용**:
- `투자아이디어정리 일일 Ingest 규칙` 섹션 신규 추가
- 시트 → 섹터 매핑 테이블 (40개 시트 전체 분류)
- 9단계 처리 체크리스트 (분기 판단 → stock 일정 섹션 업데이트 → 일정재료 ✅)
- 분기 → D-? 환산 기준표 (2026 기준)

**핵심 연결**: 일정재료(#7) ← 현재 가장 비어있던 탑픽 항목을 이 파일로 자동 채움

---

## 2026-05-25 (8차) — stock 폴더 구조 재편 (섹터별 분류)

**작업 유형**: 파일 이동 + CLAUDE.md 경로 규칙 업데이트

**변경 전**: `wiki/L6_수급/stock/stock_*.md` (flat 구조)
**변경 후**: `wiki/L5_섹터/{섹터}/stock/stock_*.md` (섹터별 분류)

**이동 내역**:
- `L5_섹터/반도체/stock/` — 16개 (SK하이닉스·삼성전자·테스·파크시스템스·원익IPS·솔브레인·동진쎄미켐·코미코·원익머트리얼즈·피에스케이·피에스케이홀딩스·브이엠·CMTX·주성엔지니어링·덕산하이메탈·대한광통신)
- `L5_섹터/전력기기/stock/` — 1개 (효성중공업)
- `L6_수급/stock_index.md` — 인덱스 파일 L6 루트로 이동
- `L6_수급/stock/` 빈 폴더 삭제

**CLAUDE.md 업데이트**: stock 파일 경로 규칙 5곳 수정

---

## 2026-05-25 (7차) — 빈집 2중 확인 시스템 도입 + CMTX 추가

**작업 유형**: 시스템 설계 변경 + PS1 종목 추가 + 템플릿 업데이트

**변경 내용**:
- `raw/market/extract_유동성.ps1` — wikiStocks에 씨엠티엑스(CMTX) 추가 (종목명 미확정, TBD)
- `CLAUDE.md` — 수급흐름 섹션 템플릿 듀얼 시스템으로 변경
  - 📊 유동성 통합순위 빈집 (현재 수준 스냅샷)
  - 📈 수급오실레이터 빈집 (변화 방향/타이밍)
  - 🔴 종합 판정 (두 시스템 교차)
- `stock_index.md` — "유동성빈집 + 오실레이터" 2열 구조로 변경 (기존 "빈집등급" 단일 열 → 분리)
- `stock_CMTX.md` — 수급흐름 섹션 듀얼 구조 반영, 빈집 미매핑 상태 명시

**운영 원칙 변경**:
- 수급빈집 판단 = 유동성 통합순위(현재 수준) + 수급오실레이터(변화 방향) 동시 확인
- 진입 트리거: 두 시스템 모두 A/B 빈집 + 오실레이터 ↓→↑ 전환

**CMTX 잔여 과제**:
- 한국거래소 정확한 종목명 확인 후 extract_유동성.ps1 wikiStocks 업데이트 필요

---

## 2026-05-25 (6차) — 유동성 xlsm 일일 처리 시스템 구축

**작업 유형**: PowerShell 스크립트 신규 생성 + CLAUDE.md 규칙 추가 + 마스터 인덱스 생성 + 포맷 갱신

**신규 파일**:
- `raw/market/extract_유동성.ps1` — 유동성 xlsm → 요약 md 자동 추출 스크립트
  - 유동성 컨셉: Wiki 22종목 통합순위→빈집등급(A/B/C/D) 자동 판정
  - 2027 컨센 신고가: Wiki 종목 포함 여부 + 신고가 여부 자동 추출
  - 가속화모멘텀: Wiki 종목 + 군집 업종(주도섹터) 추출
  - 업종 컨센: 상위 10개 섹터 점수 추출
- `wiki/L6_수급/stock/stock_index.md` — 전체 탑픽 마스터 인덱스 (22종목 점수 일람)

**수정 파일**:
- `CLAUDE.md` — 유동성 xlsm 일일 ingest 규칙 섹션 신규 추가 (처리 체크리스트 + 빈집등급 변환 기준)
- `stock_덕산하이메탈.md` — 탑픽 스코어 포맷 갱신 (콘텐츠 아이디어→탑픽 스코어 3/9점)
- `stock_대한광통신.md` — 탑픽 스코어 포맷 갱신 (3/9점)
- `stock_주성엔지니어링.md` — 탑픽 스코어 포맷 갱신 (3/9점) + ⚠️ 충돌 섹션 일관성 수정
- `stock_효성중공업.md` — 탑픽 스코어 포맷 갱신 (3/9점)

**사용자 일일 루틴**:
```
1. 유동성 xlsm → raw\market\YYYYMMDD_유동성.xlsm 저장
2. PowerShell: .\raw\market\extract_유동성.ps1 -FilePath "..."
3. Claude: /ingest raw/market/YYYYMMDD_유동성_요약.md
```

**ingest 결과 (20260522 유동성 컨셉 기준)**:
- 전체 17개 stock 파일 수급빈집 ✅ 반영 완료
- 8/9점 탑픽: 삼성전자·SK하이닉스·동진쎄미켐·솔브레인
- 7/9점 탑픽: 피에스케이홀딩스·테스·원익머트리얼즈·CMTX
- Wiki 22종목 모두 A 또는 B 빈집 (C 정상 0개, D 과매수 0개)
- 신고가 추가: 주성엔지니어링(IBK)·효성중공업(NH) 리포트신고가 ✅

**미완료 (다음 작업)**:
- 조선 섹터 stock/ 파일 6개 생성 (HD현대중공업 등)
- CMTX 유동성 빈집 정확한 순위 확인 (스크립트 이름 매칭 점검)

---

## 2026-05-25 (5차) — 일정·수주잔고·투경관리 ingest 시스템 구축

**작업 유형**: 신규 위키 페이지 생성 + CLAUDE.md 규칙 추가 + stock 페이지 수주잔고 섹션 반영

**소스 파일**: `raw/일정 및 수주잔고.xlsx` (25년말~26년 / 투경관리 / 수주잔고 시트 3개)

**신규 파일**:
- `wiki/L6_수급/투경관리.md` — 투경예고·경고중·해제 이력 관리. 브이엠 2026-05-07 경고지정 반영
- `wiki/L6_수급/수주잔고_모니터.md` — 섹터별 1Q26 수주잔고 현황. 역대최고 6종목 확인
- `wiki/L6_수급/stock/stock_원익IPS.md` — 1Q26 수주잔고 역대최고(+4배). 신규 생성

**수정 파일**:
- `CLAUDE.md` — 일정·수주잔고·투경관리 일일 Ingest 규칙 섹션 신규 추가 (3시트 처리 체크리스트 포함)
- `stock_테스.md` — 수주잔고 1Q26(145,538백만원, +3배) 추가. 어닝서프 ✅ 업데이트 (4→5점)
- `stock_파크시스템스.md` — 수주잔고 1Q26(87,133백만원) 섹션 추가
- `stock_주성엔지니어링.md` — 수주잔고 1Q26(74,658백만원, -65%) ⚠️ 섹션 추가 + 충돌 감지

**1Q26 수주잔고 역대최고 종목 (확인 완료)**:
- 한화에어로스페이스 118,127,410백만원 / HD한국조선해양 89,093,027백만원
- 효성중공업 20,196,435백만원 / HD현대일렉트릭 11,437,600백만원
- 이수페타시스 573,743백만원(+2.6배) / 원익IPS 400,388백만원(+4배)

**투경관리 현황 (2026-05-25 기준)**:
- 경고중: 브이엠 (2026-05-07 지정)
- 경고예고: 없음 (브이엠은 이미 경고 전환)

---

## 2026-05-25 (4차) — 반도체 리포트 ingest 완료 (반도체.txt)

**작업 유형**: 리포트 ingest → L6 종목 마스터 페이지 신규 생성 + L5 섹터 업데이트

**소스 파일**: `반도체.txt` (2026-04-06 ~ 2026-05-21, 전진투자·하나·SK·iM·대신증권 리포트 5사 통합)

**신규 파일 (L6_수급/stock/)**:
- `stock_SK하이닉스.md` — TP 320만원(전진투자) ~ 175만원(하나). 2026E OP 245~271조원. HBM Capa 35%, M15X 70K/월 램프업
- `stock_테스.md` — PECVD 장비. M15X/P5 Capex 수혜
- `stock_피에스케이.md` — PR Strip. 1c nm 미세화 = 공정 횟수 증가
- `stock_피에스케이홀딩스.md` — HBM Descum/Reflow. HBM Capa 확대 직결
- `stock_파크시스템스.md` — AFM 계측. 1c nm·2nm GAA 공정 필수
- `stock_솔브레인.md` — 식각액 1위. HfO₂ 특허만료 수혜 + ASP 연동
- `stock_동진쎄미켐.md` — PR 국산화 1위. Mo 전구체 국산화 개발 중
- `stock_코미코.md` — 부품 세정 1위. 가동률 상승 = 세정 주기 단축
- `stock_원익머트리얼즈.md` — 특수가스 1위. NF3/WF6 공급계약 단가 상향
- `stock_브이엠.md` — Metal/Poly Etcher. **종목코드 확인 필요**
- `stock_CMTX.md` — 실리콘 미세분말. TP 210,000원, OP 703억원. **종목명·코드 확인 필요**

**수정 파일**:
- `wiki/L6_수급/stock/stock_삼성전자.md` (이전 세션 완성) — TP 50만원, 6/9점
- `wiki/L5_섹터/반도체/index.md` — 대장주 현황 TP 갱신 + 이벤트 히스토리 2026-04~05 전체 추가
- `wiki/L5_섹터/반도체/반도체index.md` — 일별 활성 로그 5/7 ~ 5/25 추가

**핵심 인사이트 반영**:
- 메모리 패러다임 전환: 사이클 → 전략 자산 (LTA Dual Market)
- SK하이닉스 HBM4E Vera Rubin 독점 가능성 95%
- 삼성전자 파운드리 4nm 100% 가동 회복 + 2nm GAA 수주 가시화
- 장비·소재 사이클: AMAT/LAM 수주 선행 → 국내 장비주 12~18개월 후행 수주 구조

**미확인 항목**:
- `stock_브이엠.md` 종목코드 — 사용자 확인 필요
- `stock_CMTX.md` 종목명·코드 — 사용자 확인 필요

---

## 2026-05-25 (3차) — L5 섹터 전체 구조 세팅

**작업 유형**: 신규 섹터 폴더 7개 생성 + L5 인덱스 전면 재편

**신규 파일**:
- `wiki/L5_섹터/로봇/index.md` + `테이블.md` — 10개 서브섹터 (완성로봇·감속기·협동로봇·AMR·의료로봇·AI두뇌 등)
- `wiki/L5_섹터/바이오/index.md` + `테이블.md` — 11개 서브섹터 (ADC·세포치료·GLP-1비만·CDMO·RDC·진단·AI신약 등)
- `wiki/L5_섹터/자동차/index.md` + `테이블.md` — 10개 서브섹터 (완성차·ADAS·자율주행SW·차량용반도체·EV인프라·수소차 등)
- `wiki/L5_섹터/LNG/index.md` + `테이블.md` — 9개 서브섹터 (LNG선·화물창단열재·설비선·플랜트EPC·강관·엔진 등)
- `wiki/L5_섹터/AI소프트웨어/index.md` + `테이블.md` — 10개 서브섹터 (AI플랫폼·에이전트·AI의료·보안·양자·메타버스 등)
- `wiki/L5_섹터/소비내수/index.md` + `테이블.md` — 10개 서브섹터 (K뷰티·식품·여행항공·면세·엔터·게임·패션 등)
- `wiki/L5_섹터/테마이벤트/index.md` + `테이블.md` — 12개 서브섹터 (정치·블랙테마·대왕고래·트럼프·코인·이란·코로나·조류독감 등)

**수정 파일**:
- `wiki/L5_섹터/섹터index.md` — 12개 섹터 전체 온도 현황표 + 자동반영 프로토콜 + 섹터 폴더 목록 전면 재편

**커버된 핵심 내용**:
- 반도체·조선 기존 구조 보완 없이 유지 (다 바꾸는 게 아니고 보완)
- 로봇: 테슬라 옵티머스·현대차 로보틱스 양대 축 + 에스비비테크·두산로보틱스 체인
- 바이오: GLP-1·ADC·바이오시밀러·CDMO 4개 핵심 테마
- 자동차: SDV·자율주행·차량용 반도체 국산화 트렌드
- LNG: 조선 섹터와 교차 추적 구조 (동일 종목 양쪽 반영)
- AI소프트웨어: AI에이전트·루닛·PQC양자암호 포함
- 소비내수: K뷰티 OEM·HYBE·크래프톤 중심
- 테마이벤트: 트럼프·블랙테마·대왕고래·금리사이클·조류독감 포함
- **자동반영 프로토콜 문서화**: 뉴스·리포트 ingest 시 테이블.md 자동 업데이트 규칙 명시

---

## 2026-05-25 (2차) — 조선 섹터 기초지식 세팅

**작업 유형**: 지식 베이스 구축 (리서치 보고서 4개, 2026-02~05 → 위키 이식)

**소스 파일**:
- `조선_섹터_통합_최종_리서치_보고서.md` — 삼각축 호황, 대형 3사 TP, 도크쇼티지, MASGA
- `2026_조선_섹터_대형_중형_브릿지_통합_보고서.md` — 브릿지 전략, 중형 2사 상세, 힘쎈엔진, SCC

**신규/수정 파일**:
- `wiki/L5_섹터/조선/밸류체인_마스터.md` (신규) — 7개 서브섹터 × 종목 × 역할 × 미국피어 × 투자트리거 전체 지도
- `wiki/L5_섹터/조선/조선index.md` (수정) — 12개 서브섹터 + 기술드라이버 × 서브섹터 연계 표 추가
- `wiki/L5_섹터/조선/index.md` (수정) — 대장주 현황·이벤트 히스토리·콘텐츠 기회 2026 리서치 기반 전면 갱신
- `wiki/L2_미국시장/market_한국페어맵.md` (수정) — 조선/해양방산 섹션 신규 추가 (HII·GD·Wartsila → HD현대중공업·한화오션·대한조선)

**커버된 핵심 내용**:
- 삼각축 호황: 상선(고선가·도크쇼티지) + 미국해양패권(MASGA) + AI전력(힘쎈엔진)
- 신조선가지수 184.64pt / 중고선가 208.78pt (신조 역전 = 쇼티지 극심)
- 2026 브릿지 전략: 1H 대한조선(27% 마진·PER 9.8배)·HJ중공업(772.9% 폭증), 3Q~ 대형주
- HII·GD → HD현대중공업·한화오션 MASGA 커플링 매핑
- Wartsila·GE베르노바 → HD현대중공업 힘쎈엔진 경쟁·대안 포지션
- 나무라조선(JP) → 대한조선 저평가 비교 (PER 19~21x vs 9.8x)
- 대한조선: SCC 수에즈막스 탱커 Pure Play, 순현금 1조, TP 156K(100% 상향)
- HJ중공업: 미 해군 MRO 교두보, LSF 고속상륙정 방산수출(텍스트론 대비 40% 저렴)

---

## 2026-05-25 — 반도체 기초지식 세팅

**작업 유형**: 지식 베이스 구축 (마스터 유튜버 영상 159개 압축본 → 위키 이식)

**신규/수정 파일**:
- `wiki/L5_섹터/반도체/밸류체인_마스터.md` (신규) — 8개 서브섹터 × 종목 × 기술역할 × 미국페어 전체 지도
- `wiki/L5_섹터/반도체/반도체index.md` (수정) — 기술드라이버 × 서브섹터 연계 표 추가
- `wiki/L2_미국시장/market_한국페어맵.md` (수정) — ASIC·유리기판·파운드리딜 상세 섹션 3개 추가

**커버된 핵심 내용**:
- HBM4 베이스다이 3사 전략 (SK하이닉스/삼성/마이크론)
- SOCAMM 추론형 메모리 밸류체인
- 삼성 파운드리 테슬라 22.8조 딜 → 낙수 체인
- ASIC 폭증 (브로드컴·마벨) → 가온칩스·이수페타시스·리노공업
- 유리기판 세와리불량·풀필도금·소부장 전체 체인
- 극저온식각·몰리브덴·하프늄 전공정 신소재
- 미국↔한국 커플링 7개 시그널 포인트

---

## 2026-05-24 — 세션 마감
> **오늘 시장**: 🟢 Risk-On | VIX 16.7 | DXY 99.3 | 10yr 4.56% | 원달러 1,521원
> Nasdaq +0.19% | SOX +1.99% | NVDA -1.90% | AMD +3.99% | IONQ +8.07% | RKLB +8.22%

### ✅ 완성된 것

**L1 글로벌유동성 (마무리)**
- wiki/L1_글로벌유동성/: fed_watch.md, market_vix.md, market_채권금리.md, market_달러_환율_흐름.md 신규
- out/L1_글로벌유동성.html: 티커 제거, shimmer 5s 1회, 해석 심화, NVDA 어닝서프 반영
- 수동업데이트.bat + 바탕화면 바로가기 생성

**L2 미국시장 (신규 완성)**
- wiki/L2_미국시장/market_한국페어맵.md — 11개 섹터 미국↔한국 페어 상세
- wiki/L2_미국시장/미국시장index.md — 재설계, 자동 업데이트 연동
- wiki/L2_미국시장/market_미국지수.md — 지수·ETF·빅테크 12종목 일일 추적
- out/L2_미국시장.html — 11개 섹터 페어 카드 대시보드

**자동화 확장**
- update_market_data.js: 11심볼 → 33심볼 (L2 페어 전체 추가)
- L2 wiki 2파일 + HTML 마커 자동 업데이트 섹션 추가
- 매일 07:00 KST L1+L2 전체 자동 업데이트 검증 완료

### ⏭️ 다음 세션 시작 시 (순서대로)
1. **GitHub 세팅** — 레포 생성 → push → Pages → Actions (집 PC 연동 + 공개 URL)
2. **L3 한국시장** — 코스피·코스닥·외국인기관 wiki + HTML
3. **L6 수급** — xlsm 오실레이터 연동 재개
- [작업] 섹터 대시보드 + 브리핑 카드 시스템 구축
  - out/sector_dashboard_조선.html 신규 — 조선 섹터 (10개 서브섹터, HII·GD·RTX·LMT 커플링)
  - out/briefing_반도체.html 완성 — 800px PNG배포용 (시그널스트립·픽순위·테마3열, print-color-adjust)
  - wiki/L5_섹터/ 구조 재편 — 반도체/조선/전력기기/2차전지ESS/방산 각 index.md + 테이블.md
  - channel/strategy/briefing_카드_디자인스펙.md 신규 — 레이아웃·CSS토큰·배포방법 문서화

---

## 2026-05-24 (2차) — 반도체 서브섹터 구조 구축 + 대시보드 업데이트

**작업 유형**: 섹터 구조 설계 + HTML 업데이트

**신규 파일**:
- `wiki/L5_섹터/sector_반도체_서브섹터.md` — 18개 서브섹터 × 대표종목 매핑 마스터 (일별 활성 로그 포함)

- 2026-05-28: [2차전지ESS] 섹터 딥리서치 완료 (Gemini 2.5 Flash + Google Search)
- 2026-05-28: [조선] 섹터 딥리서치 완료 (Gemini 2.5 Flash + Google Search)- 2026-06-04 ingest_crawl: sector 0개, stock 0개 wiki 업데이트
- 2026-06-04 ingest_crawl: sector 1개, stock 0개 wiki 업데이트
- 2026-06-04 ingest_crawl: sector 1개, stock 0개 wiki 업데이트
- 2026-06-04 ingest_crawl: sector 9개, stock 9개 코멘트 추가
- 2026-06-04 ingest_crawl(telegram): sector 16개, stock 21개 코멘트 추가
2026-06-04 | yt-trend 파이프라인(유튜브 제작가이드2) 완성. step1~5 전체 구현+실행. 수집→자막분석→소재추출→대본S1~S8. step2 당일시황 반영 프롬프트 수정. step1 12시간 윈도우로 변경.
2026-06-18 | 카카오EP1 S08·S09 대본 업데이트. S7·S8 녹화+음성 MP4 완성 (로컬). 남은 녹화: S2·S5·S9·S10·cold_open.
2026-06-21 | 스탁브레인 SaaS 대시보드 MVP 구현·배포 완료. FastAPI:8080 + 검정골드 5탭(브리핑/피드/통계/설정/관리자) + JWT(아이디pw+텔레매직링크). 서브에이전트주도 13태스크/30테스트/opus최종리뷰 통과. systemd 상시가동, 외부접속 검증완료(admin/stockbrain2026!). 뉴스 RSS 5→15개 확장+주식관련성 필터. 기존봇 무손상. 다음: UI 변경.
2026-06-22: 스탁브레인 대시보드 UI 개편 브레인스토밍 진행(80%). 3컬럼 확정(왼=구독자 소스별 네비/가운데=본문+액션형요약/오른=섹터종합). 위키=백엔드만, 비용=인제스트 선생성. 프롬프트 디벨롭·태린이·우측목업은 다음.

## 2026-06-22 (집PC·Opus4.8) — 피드/시그널 분리 배포 + 다운로드 보강
- 대시보드 2서비스 분리: `/feed`(Tier1~5 소스잠금) + `/signal`(3단 깔때기, 독립권한). 설계·계획·구현·라이브검증 완료. 서버커밋 3건, 테스트 36개 통과.
- 시그널 데이터: pipeline/build_signal_snapshot.py(태린이엑셀→스냅샷) + scripts/sync_signal.py(서버동기화). 실데이터 363종목.
- download_daily.py: 폴더접근 차단 시 텔레그램 자동보고 추가. mybox_links.json URL 갱신(월요일 변경분).
- 시그널 보강: 섹터태깅(sector_map.json 515 마스터, 미상42%) + 매일 백테스팅(backtest_signal.py: picks_log 누적→사후수익률 승률/점수별). /api/signal/backtest 배포. 가격원=한국상대강도(~150종목). runner=run_signal_daily.py(스케줄 미등록).
- STAGE1 매크로 실연동: fetch_macro.py(yfinance VIX·S&P·나스닥 → GO/경계/NO + 간밤이벤트 정량감지). 오늘 GO(미장+1.5%,VIX16.4).
- STAGE2 미국대장주 맵핑: 한국섹터 기준 미국 대장주 2~3개(반도체=NVDA·MU·AVGO 등) 등락 → 미장강세×빈집 교집합. run_signal_daily에 fetch_macro 선행 추가.
- [2026-06-22 회사PC] 위키 종합엔진 설계·구현(반도체 프로토타입). 원자→종목페이지 자동녹임: synth_qc/verify_gate/synth_engine/synth_rollup/synth_run (17테스트). 5종목 풍부갱신(출처+⚠️미검증 등급). 미완: 수율14%(날짜윈도우·섹터페이지실패·기타오분류 3구멍) + claude -p 페이지파괴→서브에이전트 직접쓰기 재설계 필요. 교훈: "쓸모(수율)" 먼저 검증, 과설계 금물. 상세 NEXT_SESSION.md.

## 2026-06-22 (회사PC·Opus4.8) — 대시보드 세션 (서버 배포)
- /feed 3컬럼+키워드 다이제스트 / /signal 깔때기+A/B백테스트 / 종목 통합카드(한줄판단+시그널+뉴스+리포트) / 텔레 명령봇(/go /signal) / crawling_bot_data→서버 매시간 동기화
- 미국대장주 매핑(fetch_macro), 클릭베이트·재료필터, 구글뉴스 실시간보충
- 전략결론: 잘만들어짐≠잘됨(외부검증0). 위키↔카드AI판단 연결=차별화 / 채널에 던져 검증 필요
- 상세 핸드오프: docs/HANDOFF_대시보드_2026-06-22.md / 주의: 서버에 개발자 동시작업

2026-06-23 저녁 | 텔레 종합 토큰폭발(420k) 원인규명: raw 444KB를 Opus메인이 직접 추출=범인. 해결=수신워커(Gemini/Haiku 격리). NEXT_SESSION에 집작업 todo 남김(0.SK하이닉스 양면반영).

##  — 딸깍 스튜디오 완성
- 버튼 하나로 아침 브리핑 카드 자동생성: 데이터→Gemini 히로이미지(폴백 그라데이션)→카드렌더→PNG→텔레전송, SSE 5단계 애니메이션 UI(트렌디 다크+골드)
- dashboard/server.py에 /studio 라우트 + scripts/{studio_data,gemini_image,card_render,studio_pipeline}.py, dashboard/studio.html
- 서브에이전트 TDD 7태스크 전부 통과(17 tests), 최종 opus 리뷰 READY TO MERGE, main 머지·push 완료
- 라이브 검증: 5단계 완주+텔레 전송 성공. Gemini 이미지는 429 쿼터소진→폴백 정상작동(예비키 GEMINI_API_KEY_2 자동전환은 후속)
- 접속: python dashboard/server.py → http://localhost:8090/studio

## 2026-06-30 — 인사이트 허브 → NotebookLM 다리 완성
- 가로검색 한 번 → 전 소스 발언이 NotebookLM 노트북으로 자동 투입(추출발언 .md + 원본 URL/유튜브, ①+㉢)
- dashboard/server.py: /api/insights/to_notebook(노트북생성+소스), /notebook_research(웹딥리서치 --auto-import), /notebook_card(report create) — nlm CLI subprocess
- dashboard/insights.html: 검색결과에 "📒 NotebookLM 노트북으로" 버튼바 + 결과모달(🔬리서치/🎴카드 다음단계)
- 라이브 검증: HBM(110발언→노트북, 리서치 +10소스, 브리핑리포트 생성), 조선(67발언→노트북) 실제 생성 확인
- spec: docs/superpowers/specs/2026-06-30-insights-notebooklm-bridge-design.md

## 2026-06-30 — NotebookLM 다리 v2: 허브 안에서 질문·리포트 (이탈 없이)
- 결과 모달에 💬질문(Q&A) 박스 추가 → nlm notebook query → 인용 달린 답변을 모달에 인라인 렌더(후속질문 conversation_id 유지)
- 🎴리포트: report create 후 폴링→download report(md)→모달에 인라인 표시
- 검색/노트북 키워드 토크나이저(_tokenize_query): 자연어 문장도 핵심 키워드 추출해 동작
- 엔드포인트 추가: /api/insights/notebook_query, notebook_card 확장(markdown 반환)
- 검증(API): 반도체 노트북 생성·질문 답변·리서치+10·리포트 전부 정상. 브라우저 캡처는 CDP 불안정

## 2026-06-30 — NotebookLM 다리 v3: 만들기(스튜디오)+드래그최적화+필터백엔드
- 🎨 만들기: /api/insights/notebook_studio {kind} → nlm infographic/slides/audio/video/mindmap create. 모달에 버튼행 추가(시작→Studio 확인)
- 모달 드래그 렉 해결: .modal-box transition .2s가 원인 → 드래그 중 transition:none + rAF 스로틀
- 질문 가드: "만들어줘" 입력 시 영어 사고과정 누출 차단(답변만 하도록 제약)
- 옵션 패널 백엔드: /notebook_preview(카테고리·기간 집계) + to_notebook 필터(cats/period/limit/split/include_urls). UI 와이어링은 다음
- 검증(API): preview 집계·infographic 시작 정상

## 2026-06-30 — NotebookLM 다리 v4: 옵션 패널 UI 완성
- 📒 버튼 → 옵션 패널: 소스 체크박스(카테고리별 건수)·기간 프리셋(전체/오늘/3일/7일+건수)·발언수·소스구성(묶음/분리)·원본링크 포함 → "노트북 만들기"
- openNotebookOptions(preview 집계 렌더)→createNotebookFromPanel→runCreateNotebook(opts 전송)
- 검증: 리포트+텔레+오늘 = 23건, .md에 텔레8/리포트2만(타카테고리 제외) 확인

## 2026-06-30 — NotebookLM 다리 v5: 고정창 + 인포/슬라이드 허브 인라인 표시
- 고정창: 모달 바깥 클릭으로 안 닫히게(✕로만) — 실수로 닫혀 작업 잃는 문제 해결
- 인포그래픽/슬라이드: 생성→완료 폴링→nlm download→/api/insights/artifact 서빙→모달에 <img>/<iframe> 인라인 (노트북 이탈 불필요)
- 오디오/영상은 시간 길어 시작→Studio 링크 유지
- 검증: 인포그래픽 create→download→serve(200/image-png/5.4MB) 정상

## 2026-06-30 — NotebookLM 다리 v6: 첫화면 브리핑바(A안) + 전체화면 2단 워크스페이스
- 첫화면: 소스칩(텔레/유튜브/리포트/뉴스/블로그)+기간 프리셋+키워드+🧠브리핑시작 (라이브러리 카드 유지=A안)
- 브리핑 시작 → 선택 소스로 노트북 생성 → 전체화면 워크스페이스 진입
- 워크스페이스: 좌(질문·리서치·리포트·만들기) / 우(넓은 결과 캔버스 — 답변·리포트·인포그래픽·슬라이드가 크게 카드로 쌓임)
- 검증: 삼성전자 브리핑 시작→워크스페이스→질문→오른쪽에 인용 답변 크게 렌더(브라우저 확인)

## 2026-06-30 — 다리 v7: Claude 직접대화창 + 스탁브레인 리브랜딩 + 결과물 한국어
- 워크스페이스 좌상단 🤖 Claude 직접대화(/api/insights/claude_chat, 노트북 자료를 컨텍스트로) + 그아래 🧠 스탁브레인 질문(인용)
- "NotebookLM" 명칭 → "스탁브레인"으로 리브랜딩(외부링크는 "원본 열기")
- 인포/슬라이드/오디오/영상 생성에 --language ko → 결과물 한국어
- Claude대화는 ANTHROPIC_API_KEY 필요(.env). 없으면 안내 메시지. 키 헬퍼 _env_key(.env 읽기)
- 미검증: 인포 한글 화면확인은 nlm studio status 일시블록으로 보류(--language ko는 문서옵션, 리포트 전례)

## 2026-06-30 — 다리 v8: 닫기 세션유지(이어보기) + Gemini 리서치 대화창
- 워크스페이스 닫아도 세션 유지 → 메인 우하단 "🧠 {label} 이어보기" 플로팅 버튼으로 복귀(캔버스 그대로). 새 브리핑 시작 시만 초기화
- 좌측 ♊ Gemini 리서치 대화창: /api/insights/gemini_chat (call_with_grounding=구글검색+출처, 노트북 자료 참고). GEMINI_API_KEY→_2 순차 폴백
- 검증: 엔드포인트 정상연결, 단 현재 두 키 모두 429 쿼터소진(리셋 시 작동). 이어보기/Gemini박스 UI는 다음 브라우저 확인

## 2026-06-30 — 다리 v9: 자료 누적 + 이전 브리핑 끌어오기(교차검색)
- 좌하단 📚 자료 목록(현재 노트북 소스 라이브) + "+ 이전 브리핑 끌어오기" 픽커
- 브리핑 영속 레지스트리(out/insights_notebook/registry.json) — 만들 때마다 등록
- /api/insights/notebooks(목록)·notebook_sources(현재소스)·notebook_merge(이전.md를 현 노트북에 소스추가→교차검색)
- 버그수정: _load_registry 이름충돌(기존 소스레지스트리 cat인자)→ _load_nb_registry/_nb_registry_add 개명
- 검증: A(삼성전자)·B(조선) 생성→레지스트리 등록→A를 B로 끌어오기 소스 1→2 교차검색

## 2026-06-30 — 다리 v10: studio 비동기 폴링(인라인 표시) + 브리핑 프리셋
- 인포/슬라이드: notebook_studio가 artifact_id만 빠르게 반환 → studio_poll로 프론트가 8s×32 폴링 → 완료 시 다운로드·인라인 표시(긴 프롬프트로 180s 초과해도 뜸)
- 프리셋 8종(클릭→스탁브레인 자동질문): 🌅아침/🌆마감/🔬종목/🏭섹터/📊시장/🕳️수급빈집/⚔️대장주/🆚교차비교
- 검증: studio_poll ready+file_url 정상

## 2026-06-30 — 다리 v11: 레퍼런스 이미지 첨부(자료/디자인) + 리모션 브랜드 디자인
- 만들기 영역에 🖼️ 이미지 첨부: 📎자료로(nlm source add) / 🎨디자인참고로(Gemini 비전이 스타일 추출→_NB_DESIGN 저장→인포/슬라이드/영상 생성 focus에 주입)
- /api/insights/upload_image (base64 JSON), _gemini_vision_style(키 폴백)
- 시각 결과물에 리모션 브랜드(_BRAND_DESIGN: 블랙+라임그린#AAFF00+골드#C8921A HUD) + 업로드 레퍼런스 스타일 결합
- 검증: 리모션톤 인포그래픽 실측(블랙+라임+골드 HUD), design 업로드 비전 스타일추출 정상

## 2026-06-30 — 다리 v12: 🔎리서치 탭(웹리서치 전용 모드) + 상단바 확대
- 소스 행에 🔎리서치 토글: 켜면 NotebookLM 웹 리서치(research start --auto-import) 추가. 소스 미선택+리서치만이면 크롤링 없이 웹자료로 노트북 생성→답변
- to_notebook research/no_crawl 분기, 워크스페이스 meta에 웹리서치 건수 표시
- 상단 브리핑바 max-width 880→1040, 패딩 확대
- 검증: 리서치전용(cats=[]+research) → atoms0+웹리서치10건 노트북 생성 정상

## 2026-06-30 — 다리 v13: Claude박스 삭제 + Gemini 인포그래픽(나노바나나2) + 슬라이드 폴링 연장
- Claude 직접대화 박스 제거(API키 필요해서)
- /api/insights/gemini_infographic: 노트북 내용 요약→이미지 프롬프트(브랜드+레퍼런스 결합)→Gemini 이미지(gemini-3-flash-preview-image=나노바나나2→2.5 폴백). 프롬프트 자유. 🍌버튼 추가
- 슬라이드 항상 실패 원인: type=slide_deck(폴링 정상)인데 NotebookLM 생성이 10분+ 매우 느림/멈춤 → 폴링창 슬라이드/영상 ~10분으로 연장
- 미결: Gemini 이미지생성 429 쿼터소진(두 키 모두). 코드 정상, 쿼터/유료키 필요

## 2026-07-01 — nlm 자동 세션유지(주기적 자동 재로그인)
- 서버 keepalive 스레드: 25분마다 nlm login --check → 만료 시에만 nlm login(전용 크롬 프로필로 무인 자동완료)
- 수동 🔄 재로그인 버튼 + /api/insights/nlm_relogin, /nlm_status(브라우저없이 유효성)
- 원리: nlm login이 nlm 전용 크롬 프로필(구글세션 유지) 사용 → 비번입력 없이 자동. 대시보드 켜져있으면 세션 안 끊김
- 검증: nlm_status valid:true

## 2026-07-01 — 🔥 오늘의 시그널 대시보드 (버즈 스파이크 + 합의/충돌)
- /api/insights/signals: asset(종목) 오늘 언급수 vs 최근8일 평균 → 스파이크·신규·추세, 소스 다채널(합의)/stance 충돌 플래그, 랭킹(다채널*2+오늘+스파이크)
- 메인 상단 "🔥 오늘의 시그널" 섹션: 종목·오늘N·평균대비추세·소스칩·배지·클릭시 그 종목 브리핑(sigBrief)
- 데이터: asset 96% 채워짐(깨끗). 미결: 종목 vs 매크로 구분(현재 asset 전부 표시)

## 2026-07-01 — 인제스트 백로그 연결 + 자동 원자추출 워커
- 진단: 크롤(원본)은 정상이나 raw→atoms.db 추출 백로그 1712개. 허브/시그널 얇았던 원인
- A: 오늘분 인제스트 완료(07-01: 50→105, 뉴스·리포트 반영). ingest_pending(Gemini gemini-3.1-flash-lite)
- C: dashboard 서버에 _ingest_worker 스레드 내장 — 10분마다 미처리 60개 자동추출(단일워커=중복없음). 백로그 서서히 소화 + 최신 유지
- 미결: 07-01 telegram/blog/yt가 pending에 안 잡힘(다른 경로?) — 후속 확인

## 2026-07-01 (2) — 대시보드 지인배포 + 뉴스매칭 시스템
- 배포: stockbrain1.duckdns.org (Lightsail+Apache프록시+SSL+로그인 admin/1234, 서버전용KIS키). 모바일 반응형·차트탭·캔들KIS폴백
- 릴레이: 서버 키움없음 → push_flow.py로 로컬 market_flow 전송(/api/push_market_flow)
- 뉴스: news_feed.py(섹터=네이버검색+must필수어, 종목=네이버증권API) + 백그라운드20분 + 뉴스탭/섹터클릭팝오버. 오매칭 must로 제거
- 콜아웃 백엔드(/api/callout·성과추적) 완료, 프론트 미연결. 장전예측엔진·기준봉 보류
- 2026-07-01 인사이트허브: 종목이슈(뉴스 상승원인+출처·날짜·원문링크)·종토방 subprocess격리·Gemini503폴백(_gemini_text 안정모델 자동전환)
- 2026-07-01 종목명 자동완성(2605종, 오타·약자별칭 ls일렉→엘에스일렉트릭)·표시명 브랜드교정(_DISPLAY_ALIAS)·코드기반조회·좌측패널 정리

## 2026-07-05 (집PC) — 전문가 인용 몽타주
stage1 엔진+스튜디오 서버배포(stockbrain1/yt/quote-studio). 서버 봇차단→Gemini call_video(gemini-2.5-flash) 폴백 해결. 장면수집 collect_scenes.py(로컬). 저장시 json다운로드 연결. git위생(atoms.db추적해제). 다음: stage2 스토리(산출물 A/B/C 결정 대기).

## 2026-07-06 (DESKTOP-T8CB1GG) — 촘촘한 그물(미귀속 강세 포착)
아침 브리핑 점검→ 미귀속 강세 시스템 전단계 배포. Phase1 스캐너(`/api/net/unattributed`, 침묵금지 silent_miss=0) / Phase2 관계그래프(edges 2홉, 귀속률 18→62%) / Phase2-2 LLM엣지(현대차→기아 실증) / Phase3 캐스케이드(`/api/net/hunt`, 신뢰등급) / Phase4 정밀도튜닝(min_graph_strength)·종토방인제스트코어(🟠)·`/net` 대시보드. 동시세션 git-hygiene가 atoms.db 유실→chroma 12,217건 복구(`rebuild_atoms_from_chroma.py`). 재인제스트로 strength 복원중(≥3 원자 0→200↑). net테스트 41통과. CLAUDE.md에 동시세션 안전커밋순서 명시. 다음: 재인제스트 잔여배치, 종토방 목록크롤 배선. 상세=NEXT_SESSION.md.
