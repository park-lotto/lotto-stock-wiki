---
name: project_person_brain
description: 사람 브레인 — 채널 운영자 사고 복제. 태린이아빠 MVP 완성(페이지+자동섹션). 2단계=질의엔진
metadata: 
  node_type: memory
  type: project
  originSessionId: 354073ff-faf8-4cfe-8216-ac0dd26bb7f7
---

채널 운영자(태린이아빠 등)의 사고·행동·결과를 기록하고 그의 프레임워크로 접지 추론하는 **질의형 제2의 브레인**. `[발언]`(실제)/`[추론]`(프레임) 라벨로 할루시네이션 차단.

**설계/계획**: `docs/superpowers/specs/2026-07-02-태린이아빠-브레인-design.md` (5구성요소·4단계), `docs/superpowers/plans/2026-07-02-person-brain-mvp.md`

**✅ 1단계 MVP 완성 (2026-07-02)** — `pipeline/people/`:
- `registry.py`+`people.json`(사람→source_name 매핑, 태린이=["태린이아빠 주식투자","태린이아빠"])
- `people_query.py` `atoms_for(person, content_type=, days=, stance_only=)` — atoms.db를 source_name IN으로 필터
- `build_brain.py` — 브레인 페이지의 `<!-- AUTO:key -->` 마커 사이만 갱신(수동 뼈대 보존, 멱등)
- `wiki/people/태린이아빠.md` — §1~4 수동골격(실원자 근거), §5 라이브스탠스(35, 자동) §8 발언로그(40, 자동)
- tests/people 16개. main 커밋. 실행: `python -m pipeline.people.build_brain 태린이아빠`

**⚠️ 중요 교훈 — 원자 taxonomy 실제값**: content_type = `fact/opinion/analysis/data/news` (설계가 가정한 stance/method **없음**). 스탠스는 **`stance_key IS NOT NULL`**(태린이 61개, "source|섹터" 형식)로 식별. signal=neutral/bullish/bearish/catalyst/risk. → live_stance는 stance_only(stance_key)로 뽑음.

**✅ 대시보드 🧠 브레인 탭 (2026-07-02)** — `dashboard/brain.html` + `/brain`·`/api/brain/*`(server.py) + `pipeline/people/brain_view.py`(list_people·person_view). 왼쪽=채널 카드 나열(people.json), 클릭→오른쪽에 라이브 스탠스(stance_key 실시간)+최근발언(14일)+사고골격(MD §1~4 접기). "+채널 추가" 폼(POST /api/brain/people/add → people.json). 스탠스·발언은 atoms.db 실시간(새로고침 불필요). tests/people 20개. **채널 추가 = people.json 한 줄 or UI 폼**(단, 그 source_name이 이미 인제스트돼 원자가 있어야 함). 서버 재시작해야 라우트 반영(systemd/duckdns).

**✅ 일일 사고 루틴 (2026-07-02, 핵심)** — 사용자 피드백: "스탠스(결과)보다 '어떻게 사고하는가'(과정)가 가장 중요. 태린이는 매일 같은 루틴(미국장페어→피어앤그리드오실레이터→수급빈집→소라티노→리포트→TP신고가)". 실제 raw/telegram 07-02 포스트에서 추출 → `pipeline/people/routines/{name}.json`(철학4+4페이즈[전날밤·새벽·장전·장중]14스텝, 각 step=checks/question/rule/data_key). brain_view._routine()→person_view.routine. 브레인 탭 최상단 렌더(스탠스보다 위). data_key(osc·rs·consensus·tp) 스텝은 taerini_stock.json 자동채움 대상=📊배지. **다음: 오늘의 루틴 재구성**(루틴을 오늘 실데이터로 walk → "그가 오늘 이렇게 사고할 것"). 이게 2단계 질의엔진의 뼈대.

**✅ 3버킷 구조 (2026-07-02)** — 사용자 정의: ①시장 인사이트 ②종목선정 프로세스 ③섹터·종목 재료. 목표="쌓고→꺼내쓰고→그대로 매매(시스템 복사)". **중대 발견: FACT/STANCE/METHOD 2층모델이 `content_type`이 아니라 `asset_level`에 저장됨** — asset_level 분포(태린이): stance61·stock57·sector57·method49·market4·macro2. 매핑: market/macro=①시장인사이트, method=②종목선정방법론(49!), stock/sector=③재료, stance=포지션. `atoms_for`에 `asset_levels`·`asset` 필터 추가. brain_view `market_insight()`·`methods()`·`materials(query)`. `/api/brain/{p}/materials?q=종목` 검색(꺼내쓰기). 브레인 탭에 3섹션+재료검색박스. tests/people 22.

**✅ 시스템 복사 = 오늘의 종목선정 퍼널 (2026-07-02)** — `pipeline/people/funnel.py`: 그의 규칙(수급빈집 osc.pct↓ × 컨센/TP up_count>down_count)을 `taerini_stock.json`(1374종목: name/osc{pct,trend,series}/tp{dir,up_count,down_count,target}/consensus/accel/etf) 오늘 데이터에 투명 적용. 임계값=`THRESHOLDS`(조정가능). 결과: 1374→빈집466→컨센44→상위20(삼성전자·SK하이닉스·현대백화점…). `brain_view.today_selection`(data_files 있는 채널만) + `/api/brain/{p}/selection`. 브레인탭 '🎯 오늘의 종목선정' 섹션. tests 26. **한계: RS/소라티노(주도섹터축) 이 파일에 없음 — 빈집×컨센만. 임계값=내 해석(튜닝 필요).**

**✅ 퍼널 RS(주도주) 축 추가 (2026-07-02)** — RS는 `유동성...데이터0701.xlsm`의 **'주도주찾기' 시트**(종목별 1M/3M 수익률, 구간별 상위=23종목). `pipeline/people/rs_data.py`(load_rs, mtime캐시, glob `raw/매일 엑셀넣을것/유동성*.xlsm`)가 파싱. funnel=빈집×컨센×**주도주**(3M모멘텀 우선정렬+🔥배지, `require_leader` 옵션). `select(rs=)` 주입으로 테스트 파일I/O 회피(30MB xlsm). tests 28. **근본원인 규명: RS/소라티노가 taerini_stock.json에 없던 건 `parse_rs`가 읽는 별도 상대강도 파일(종목상대강도데이터/etf상대강도데이터 시트)이 오늘 다운로드 안 됨**→"파일없음"에러. **소라티노=상대강도ETF 파일=여전히 미도착**(마이박스 다운로드 누락, download_mybox/mybox_links 점검 필요).

**✅ 검증 루프 (2026-07-02)** — `today_selection`이 퍼널 후보를 그가 최근 언급/스탠스한 종목과 대조: candidate.he_mentioned(✓), validation{matched,missed,hit_rate}. 놓친 종목=튜닝힌트. 라이브: 그 12언급 중 3일치(SK하이닉스·SK·삼성전자), 놓침=티에스이(탑픽)·삼성전기·파마리서치. UI 검증박스. tests 30.

**✅ 소라티노 축 + 다운로드 근본수정 (2026-07-02)** — **진짜 원인: `download_mybox.mjs`가 `python3`(Windows Store 스텁,exit49)로 압축해제 → zip은 받았는데 안 풀림** → 소라티노/RS 파일이 zip 안에 있는데도 폴더에 안 나타남. 수정: mjs에 실제 인터프리터 자동탐색(`resolvePython`, `C:/Users/TheRose/AppData/Local/Python/bin/python.exe` 우선, env MYBOX_PYTHON). 수동 압축해제(zipfile, 서브폴더 basename평탄화)로 114파일 추출 → `etf상대강도데이터.xlsx`(소라티노, 오늘자 46ETF)·`종목상대강도데이터.xlsx`(RS) 확보. "20260626" 폴더명은 주간라벨, 내용은 최신(latest_date=07-02). `pipeline/people/sortino_data.py`(scan_sortino.rank_sortino 재사용, mtime캐시)→오늘 주도섹터 Top(네트워크·반도체전공정·보험·은행·화장품). funnel 4축 완성: 빈집×컨센×주도주(RS)×**소라티노**(이름/섹터매칭 📊, 가점+정렬). 라이브: SK하이닉스(🔥📊)·삼성생명(📊보험). 소라티노 은행/보험 상위=그의 07-02 은행매수와 일치. select(rs=,sortino=) 주입 테스트. tests 32.

**✅ B 퍼널 v2 튜닝 (2026-07-02)** — 진단: 그는 '빈집 AND 컨센'만 안 봄(삼성전기=빈집아냐+판가재료, 티에스이=리포트탑픽). funnel `mode="his"`(기본): **주도(RS주도주 ∪ 소라티노섹터) 필수 → 그 안에서 빈집/컨센 가점**. `mode="strict"`=옛 빈집ANDgroup. `stock_sector_map.json`(name→섹터 1057)로 소라티노 섹터매칭 확대. funnel 단계=독립신호카운트(주도풀·빈집·재료·게이트·상위). **적중률 0.15→0.25**(티에스이·삼성전기 신규포착). 남은튜닝: 파마리서치=컨센up1down1이라 require_up_gt_down에 걸림(주도주는 완화 여지). tests 32.

**서버 재시작 방법(로컬)**: 대시보드=`python.exe dashboard/server.py` (127.0.0.1:8090, 실제 인터프리터). 재시작=`Get-NetTCPConnection -LocalPort 8090`로 PID→Stop-Process→Start-Process(-WorkingDirectory 프로젝트, -WindowStyle Hidden). 코드 바꾸면 재시작해야 반영.

**✅ 적중률 이력/자동수렴 토대 (2026-07-02)** — 사용자 개념질문("정교화하면 계속 정교해지나? 완벽할때까지 계속"). 답: 구조(로직)는 영구, 임계값은 흔들림. 100%완벽 불가(정성적 픽=사람영역)지만 점근수렴 가능. 핵심=손튜닝 아니라 자동수렴. `pipeline/people/track.py`(snapshot/history/trend): 매일 퍼널 vs 그의 실제픽 적중률 스냅샷→`pipeline/people/validation/{person}/{date}.json` 누적. `/api/brain/{p}/trend`+브레인탭 막대추세. 오늘 0.25 첫기록. tests 36. **후속: track snapshot 일일 스케줄 등록해야 누적됨** + 이력쌓이면 임계값 백테스트 자동튜닝.

**✅ 사고복제 심화 + 2축 대시보드 + 자동수렴 (2026-07-02)** —
- **브레인탭 2축 구조**: 축① 📊데이터→통계→종목선정결과(파란밴드) / 축② 🧠인사이트·사고추적·복제(보라밴드). 상단 축맵. `.band a/b` CSS.
- **오늘의 루틴 재구성**(`routine_today` + `/routine_today`): 정적루틴 data_key스텝을 오늘지표(빈집466·컨센81·소라티노섹터)로 채움 🟢. 루틴이 오늘값으로 자동교체.
- **시장인사이트 실질화**(6→27): 그의 시장판단이 method/stance/sector에 흩어져 있어 `_MARKET_KW`(주도업종·현금·지수·금리·달러·이평선·소라티노 등) 내용기반 수집. routine_today '오늘 그의 시장판단'(0→8).
- **일일 스냅샷 자동화**: atom_pipeline STEP7=`track 태린이아빠`(r() 비파괴). 매일 적중률 이력 누적→추세→자동수렴. = '완벽할때까지 계속' 자동가동.
- **서버 재시작**: `Get-NetTCPConnection -LocalPort 8090`→PID→Stop/Start-Process. 로컬 :8090 상시가동.

**✅✅ 질의 엔진 완성 = 핵심 비전 달성 (2026-07-02)** — `pipeline/people/persona.py`:
- `stock_verdict(person, stock)`: 그의 퍼널규칙을 종목에 적용 → 판정(탑픽후보/관심/관망/기준밖) + `[데이터]`/`[추론]`/`[발언]` 라벨. `decide_verdict` 순수함수. 라이브: 티에스이→탑픽후보(발언 '7월 탑픽' 일치), 파마리서치→관심(소라티노), 카카오→기준밖.
- `market_verdict(person)`: 최근7일 신호분포+현금/이평선이탈 언급 → 공격/방어/중립·선별. `decide_posture` 순수함수. 라이브: 중립·선별(섹터갈아타기, 07-02 은행갈아타기 일치).
- LLM 없이 결정론적(할루시네이션 0). `/api/brain/{p}/ask?q=` + `/market_verdict`. 브레인탭 상단 질의박스+'지금 시장은?' 버튼. 색라벨(데이터파랑/추론보라/발언초록). tests 44.
- **→ 원래 4질문 모두 답함**: ①이럴때 어떻게(종목판정) ②오늘 아침 뭘(루틴재구성) ③이 종목 어떻게 분석(퍼널) ④비중 높일까낮출까(시장판정).

**✅ 2호 채널 복제 = 범용 스키마 검증 (2026-07-02)** — 발언만 있는 채널(데이터파일 없음) 지원. `stock_verdict` 사람별 게이트: `get_person(person).data_files` 없으면 taerini 대신 그들 원자 발언으로 판정(found_in_data=False, 신호기반 긍정/부정/중립). market_verdict·person_view·3버킷은 이미 사람불문(원자기반). **pokara61** 등록(people.json, data_files 없음): 버킷 다 작동(스탠스5·방법4·재료40·시장40), 종목선정은 '데이터없음' 우아하게 처리. 대시보드 사이드바에 2채널. **= 채널=people.json 한 줄로 브레인 복제.** tests 46.

**로드맵 완료**: A데이터✅ B퍼널v2✅ C검증+이력+자동스냅샷✅ D루틴재구성✅ E질의엔진✅ +2호채널✅. **핵심 비전 전부 달성.** 남음(폴리시/확장): 비중산출·매도규칙감시·LLM자연어·현금언급탐지정확도·채널 더 추가. 서버 :8090 상시(재시작=Get-NetTCPConnection 8090→Stop/Start-Process).(persona.py, 뼈대+검색원자+데이터→그로서 답변)+대시보드 질문창 / 3단계=매일저널·트랙레코드·아침브리핑 / 4단계=2호 채널 복제. Minor정리(dict인덱싱 취약·타입주석·relations DRY·캐싱).

**주의**: 이 작업트리는 동시 세션이 브랜치전환+main auto-push → feature 브랜치 격리 불가, main 기준으로 작업. 서브에이전트는 지정파일만 git add. 관련: [[project_telegram_ingest]] [[project_taerini_pipeline]] [[project_wiki_synth_engine]] [[feedback_shared_worktree_branch_check]]

**🔗 원자추출 프로파일 재설계와의 접점 발견 (2026-07-02, 별도 세션)** — 텔레그램 채널
온보딩 스킬(`.agents/skills/channel-onboard/`) 시험 중 태린이아빠 주식투자 채널의 하루치
글을 시간순 추적하다가, 사용자가 "이 사고과정 계속 추적하면 태린이 사고를 가져올 수
있는거 아니냐"고 질문 → 확인해보니 `pipeline/people/routines/태린이아빠.json`(4단계
정적 루틴)이 이미 그 개념을 구현해놨고, 내가 수동 추적한 반도체 사고체인(전날밤 메타뉴스
인지→이평선관찰→새벽 종합판단글→DRAM ETF확인→예상가체크→실행→로테이션)이 이 루틴
스텝과 거의 1:1로 일치함을 확인. **진짜 갭**: routine.json은 07-01/07-02 이틀 수동분석
정적 템플릿이고 persona.py/funnel은 osc·RS·소라티노 숫자데이터로만 오늘을 채움 —
텔레그램 원문에서 매일 자동추출되는 `daily_prep_note`/`position_changes`(질문지 설계중,
NEXT_SESSION.md에 v2 프롬프트 있음) 슬롯이 있으면 "오늘 그가 실제로 뭐라 판단했는지"
원문 근거가 atoms.db에 자동으로 쌓여서 persona.py가 더 풍부하게 답할 수 있음.
**미결정**: 이 신규 질문지를 사람브레인 데이터소스로 바로 연결할지, 온보딩만 먼저
마무리(등록)하고 연결은 나중에 할지 — 다음 세션에서 사용자 확인 필요.
