# NEXT_SESSION

## ⭐ 최신 세션 (2026-07-08 · DESKTOP · 서버 배포 먹통 근본원인 해결 + 차트/투자자/뉴스 개선)

**🚨 여러 세션에 걸쳐 이월되던 "서버 자동배포 크론 먹통"의 진짜 원인을 찾아 해결했다.**
원인: 서버 로컬 git에 (1) stray staged 대시보드 html 3개(예전 핫패치 테스트 흔적, 이미 git 히스토리에 동일내용 있어 discard) + (2) 서버 크롤봇이 직접 써서 쌓인 미커밋 raw/out/output 데이터 **약 2,000개 파일**(2026-07-05~08)이 있었고, 이게 `git pull`을 매번 조용히 실패시켜 **2026-07-07 11:16 이후 커밋이 전부 서버에 못 감**(대시보드 다크토글·순환매감지기 배포 포함). `auto_deploy.sh`는 실패해도 알림이 없어 아무도 몰랐음.
처리: 서버 데이터를 로컬 커밋으로 보존 → origin/main과 merge(다른 PC/서버가 같은 날 각자 크롤링해 생긴 add/add 충돌 760여건은 "origin 쪽 유지"로 일괄해결) → 서버에 push 권한이 없어(credential 미설정) **git bundle로 로컬로 가져와 내 계정으로 push**하는 방식 확립 → 서버 `git pull`+`systemctl restart` 재확인, `/healthz` 정상.
**이 PC 로컬 저장소도 크롤봇이 실시간으로 raw/telegram 등을 계속 쓰고 있어 `git pull --rebase`가 매번 막힘** → **격리된 `git worktree add --detach`로 rebase/merge 후 push**하는 우회법 확립(메인 워킹트리 안 건드림, 재사용 가능한 패턴).

**① 차트 그리기 드리프트 버그 fix** (`dashboard/market.html`): 도형 좌표를 logical(막대 인덱스)로 저장해 일봉 데이터가 매일 최근 N봉만 갱신되며 인덱스 밀림 → 그린 패턴이 엉뚱한 자리(빈 미래공간)에 표시되던 버그. 실제 캔들 위 점은 날짜(time) 기반으로 저장하도록 전환, 레거시 그림은 로드 시 1회 자동 마이그레이션.

**② 투자자 순매수 상세** (`market.html`+`kiwoom_api.py`): 외인/기관/개인 막대에 최근~5분 방향성 화살표(▲▼) 추가. 카드 확장 시 "기관 세부"(금투/투신/사모/연기금/보험/은행/기타금융/국가) 막대 섹션 추가 — 키움 ka10051 응답에 이미 있던 필드를 그동안 안 쓰고 있었음.

**③ 시장상황 타임라인 멈춤 버그 fix (재발방지)**: `_gemini_text()`의 Gemini SDK 호출에 타임아웃이 없어, 네트워크 hang 시 이 함수를 쓰는 단일 백그라운드 스레드(`_poll_briefing` — 시장상황+순환매감지+시황브리핑 전부 처리)가 통째로 죽어 서버 재시작 전까지 안 살아났음(매일 반복 재현되던 원인). `ThreadPoolExecutor`+`future.result(timeout=45)`로 감싸 해결.

**④ 뉴스/시황 커버리지 확장**: `_STRONG_RE`/`_MATERIAL_RE`에 ADR·상장·관세·환율·금리·연준 등 매크로 키워드 추가(하이닉스 ADR 뉴스 누락 등 해결, 관심종목 매칭 필터는 유지돼 잡주 유입 없음). `_MACRO_RE` 신설 — 전쟁·지정학·금리 등 종목무관 매크로 헤드라인을 atoms.db ingest 없이 원문 뉴스피드에서 바로 뽑아 `_weather_tick` facts에 주입. 순환매 카드는 틱당 1건으로 제한(기존엔 매칭 전부가 major로 꽂혀 "시장상황" 12슬롯이 같은 테마로 도배됨). 뉴스 "중요" 배지 기준도 상위3/점수5→상위2/점수7로 강화.

**⏳ 다음 세션**:
1. 서버/로컬 모두 raw/ 크롤 데이터가 **여러 소스(서버 크론+PC 세션+실시간 봇)에서 동시에 같은 파일을 씀** → 구조적으로 계속 재발 가능. 근본 해결책(서버 crawl 결과를 커밋 안 하고 별도 저장소/DB로 분리? 혹은 파일명에 소스ID 포함해 경로 충돌 자체를 없애기?) 논의 필요.
2. 오늘 만든 매크로/전쟁 뉴스 감지(`_MACRO_RE`)가 실제 장중에 잘 잡히는지 라이브 관측 — 아직 실전 검증 안 됨(코드 로직만 확인).
3. 순환매 카드 "틱당 1건 제한"이 정말 다양성을 늘렸는지 며칠 관측.

**이월 노트 정정**: 아래 2026-07-07 세션 노트의 "서버 자동배포 크론 먹통"은 이번에 근본 해결됨(위 참고).

---

## (이전) 최신 세션 (2026-07-07 · DESKTOP · 순환매 감지기 구현)

어제 설계만 해뒀던 **순환매 감지기**를 구현·배포 완료. 4개 파일 main 커밋+push(post-commit 훅 자동배포).

**① 순환매 감지기 신설** (커밋 69b83905, 설계 0889446d):
- 신규 `pipeline/atoms/circulation.py` — strength_net 스타일 순수함수. `trigger_candidates`(atoms.db 강한호재 strength≥3), `mover_candidates`(히트맵+5%↑ 타섹터, 트리거섹터 제외), `detect`(게이트: **둘 다 있을 때만 LLM 호출**, 억지연결이면 빈결과 정상 — strength_net '침묵금지'와 반대). 13 유닛테스트 통과.
- `server.py` — `_circulation_tick()`을 **별도 스레드 대신** `_poll_briefing` 루프의 15분 게이트로 통합(같은 스레드가 weather state 소유 → 레이스 회피). LLM은 `_circ_gemini`(Gemini Flash 1차) — **Sonnet 교체 시 이 함수 하나만** claude -p로 바꾸면 됨.
- `market.html` — turning_points의 `type:"circulation"` 카드를 🔄로 기존 "시장상황 타임라인"에 노출(mkCard/routing/mapping 3줄). 예: "🔄 반도체 클러스터 착공 확정 → 성신양회 +16% → 건자재 2차수혜".

**② 시장상황 타임라인 테마당 3개제한 제거** (커밋 39a807c7): 같은테마 최신3개로 자르던 `_TIMELINE_THEME_CAP` 삭제 → 실이벤트 많으면 8개까지 채움(8초과=기존 접기). 단 그날 turning_point가 3개뿐이면 여전히 3개(데이터 볼륨 한계, UI 아님).

**⏳ 다음 세션 (이 작업 후속)**:
1. **순환매 감지기 라이브 검증** — 실서버에서 순환매 카드가 실제 뜨는지, Gemini가 인과를 **보수적으로** 판단하는지(억지연결 안 만드는지) 장중 관측. 품질 부족하면 `_circ_gemini`를 Sonnet(claude -p)으로 교체. market.html JS는 브라우저 하드리프레시(Ctrl+F5) 렌더확인.
2. **미검증 리스크**: 서버 atoms.db에서 trigger_candidates가 실제 트리거를 잡는지. 계속 0이면 min_strength=3이 서버 데이터엔 너무 높을 수 있음 → 튜닝.

**⚠️ 이월 주의(아래 테마토글 세션 미해결)**: **서버 자동배포 크론 먹통** — 서버 raw/ churn이 pull과 충돌. 이번 순환매 배포도 훅으로 push는 됐으나 **서버 반영은 raw 충돌로 막혀있을 수 있음**. 다음 세션에 서버 pull 상태 먼저 확인.

- 파일: `pipeline/atoms/circulation.py`·`test_circulation.py`, `dashboard/server.py`(_circulation_tick·_circ_gemini), `dashboard/market.html`. 설계 `docs/superpowers/specs/2026-07-07-순환매감지기-design.md`.

---

## (이전) 최신 세션 (2026-07-07 · 대시보드 다크/화이트 테마 토글 + 인사이트 애플 리디자인 배포)
**커밋 `c4666fe7` main push·서버 수동배포 완료.** 남은 커밋은 "내일 이어서".

**한 일**:
1. **인사이트 애플 리디자인을 드디어 main에 반영** — 7/5에 완성했던 애플 화이트 리디자인이 `archive/briefing-engine` 브랜치에만 있고 main엔 없었음(그래서 라이브가 계속 옛 다크골드였던 것). 이번에 main으로 가져오면서 `err()` 재시도버튼 버그 수정(retryFn.toString()을 onclick에 직접 박아 함수소스가 화면에 새던 것 → 전역 핸들러 참조로 교체).
2. **전 대시보드 공통 다크/화이트 토글** (insights/market/net 3페이지):
   - `:root` 토큰 + `prefers-color-scheme` 기본 + `[data-theme]` override + `localStorage 'sb-theme'` 공유(한 곳서 바꾸면 전 페이지). 우상단 🌙/☀️ 버튼. FOUC 방지 부트스크립트.
   - insights: 118 하드코딩색 토큰화(검은 애플 CTA버튼은 다크에서 골드로 반전되는 `--cta-bg/--cta-fg` 전용토큰). 다크팔레트는 옛 다크골드 재사용(토큰명 동일).
   - market(213KB): 크롬 회색램프(#888/#555/#333…)만 `--m-tx*/--m-bd*/--m-elev*` 토큰화(라이트=반전), 채도높은 히트맵 셀은 양테마 공용이라 그대로. 라이트=GitHub풍.
   - net: GitHub 라이트 팔레트.
   - 검증: 라이트/다크 헤드리스 스크린샷으로 눈 확인(회귀 없음, CTA 반전·가독성 OK).
3. **어제(7/6~7/7) 만든 인사이트 결과물 로컬로 회수** — 라이브 사이트에서 만든 노트북/브리핑/인포그래픽은 **서버에만** 저장되고 자동배포는 pull(단방향)이라 로컬로 안 옴. tar-over-ssh로 `out/insights_notebook/` 서버→로컬 동기(67→97개).

**⏳ 내일 이어서 (미커밋 다수)**:
- **미커밋 상태**: M 448 / ?? 148 / D 1 (대부분 out/insights_notebook 회수분 + raw 크롤 churn). `git add -A 금지`(규칙6), 필요한 것만 선별 커밋.
- **🚨 서버 자동배포 크론 먹통** — 서버 크롤봇이 수정한 `raw/*` tracked 파일이 들어오는 커밋과 충돌해 `git pull` 막힘(Aborting). 그래서 이번엔 **3파일만 `git checkout origin/main -- dashboard/{insights,market,net}.html`** 로 수동배포함. **근본해결 필요**: 서버 raw/ churn을 git에서 정리(서버 raw를 stash/discard 하거나, raw/를 서버에서 untrack)해야 앞으로 push→자동반영 복구됨.
- (선택) market 라이트모드 히트맵 셀 미세폴리시 — 셀은 채도라 대체로 OK지만 원하면 라이트 전용 톤 조정.
- SSH키: `C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem`, 서버 `ubuntu@3.39.179.148`.

---

## (이전) 최신 세션 (2026-07-06 저녁 · DESKTOP · 대시보드 실장 튜닝)
하루 종일 대시보드 튜닝. 모든 코드 main 커밋·서버 배포 완료(local==origin).

**① 배포 인프라 정비(+사고복구)**: "장시작 차트깨짐" fix가 안 먹힌 근본원인 = **fix를 feat브랜치에 커밋했는데 서버는 main만 추적**. → main 통일, `feat/briefing-engine→archive/briefing-engine` 은퇴(113커밋 보존), `.gitattributes`로 CRLF봉인, **자동배포 크론(`deploy/auto_deploy.sh`, 3분, push만하면 자동반영)**, 서버 고아커밋 복구(백업브랜치 incident-backup-20260706). 메모리 `reference_deploy_truth_branch_ssh`.

**② 뉴스/시장상황 타임라인 대개편**(market.html·server.py·briefing_collect.py): HH:MM수정, 뉴스당일필터, **2타임라인 분리(시장상황/뉴스이슈)**, 8-up 크기통일, **강한 텔레원문 직접노출(`_surface_strong_news`: 속보·특징주·확정 원문+출처+섹터)**, 관심종목매칭(`_match_stock` 한글경계·이닉스⊂하이닉스 오탐제거), 거버넌스제외, **중복제거(같은종목통합+N더)**, **중요도=오늘상승기여도(pct)→맨앞🔥고정**, 출처없는 ai_brief 제외, date필터.

**③ 차트팝업**: 등락률%표시(일/분/월/주), ESC닫기, 우/하 엣지 리사이즈.

**⏳ 다음 세션 (설계완료·구현대기)**:
1. **순환매 감지기** ← 사용자 관심 큼. 결론=화살표맵 불필요, **섹터맵(버킷)+Claude지식+"트리거뉴스+실제급등 둘다" 게이트**. 트리거뉴스↔타섹터급등 매칭+근거서술 (예: 반도체클러스터확정→시멘트 성신양회+16%→"건자재 2차수혜" 카드).
2. **P1 공시형 enrich**: DART `계약금액÷연매출=호재강도` 자동. 기가비스 실데이터 실현확인(연매출524억 조회성공, 계약금액은 공시본문 1콜 더). 목업 artifact 있음.
3. **P2 이벤트형**(이벤트캘린더 연동 D-day·시나리오) / **P3 여론형**(ai_brief 출처링크·근거게이트).

> 참고: 내 `_surface_strong_news`(강한뉴스 원문노출)와 아래 다른세션의 `cause_hunt`(원인 캐스케이드 귀속)는 상보적 — 다음 세션에 연계 고려.

---
## (다른 세션, 같은 날 아침) 미귀속 강세 "촘촘한 그물"

- **날짜:** 2026-07-06 (PC: DESKTOP-T8CB1GG)
- **세션 요약:** 아침 첫 브리핑 점검에서 출발 → **"촘촘한 그물"(미귀속 강세 포착 시스템)** 전 단계를 설계·구현·배포. 히트맵 상위 강세 중 **이유를 못 찾은 강세를 침묵시키지 않고 최우선 경보**로 올리는 이중망.

## ✅ 완료 (전부 main 배포됨)
- **Phase 1 스캐너** — `GET /api/net/unattributed`. 침묵금지(silent_miss=0)·정렬반전·신뢰등급. (`pipeline/atoms/strength_net.py`)
- **atoms.db 복구** — 동시세션 git-hygiene가 atoms.db(0바이트) 유실 → chroma에서 12,217건 재구성. (`scripts/rebuild_atoms_from_chroma.py`)
- **Phase 2 관계그래프** — `edges.py`(atom_edges·섹터시드·2홉 related_assets) + 그래프-홉 연계귀속. **2홉 정규화로 귀속률 18%→62%.**
- **Phase 2-2 LLM엣지** — `edge_extract.py` 정밀 관계추출(근거원자). 라이브 실증 현대차→기아.
- **Phase 3 캐스케이드** — `cause_hunt.py` + `GET /api/net/hunt`. 공시→뉴스→텔레→종토방→추론, 신뢰등급. 없으면 "전 소스 침묵".
- **Phase 4** — 정밀도 튜닝 `min_graph_strength`(가짜 62% 정직화), 종토방 인제스트 코어(`jongtobang_ingest.py` 🟠), `/net` 대시보드(`dashboard/net.html`).
- **CLAUDE.md** — 배포규칙 6번 "동시 세션 안전 커밋 순서(커밋→pull --rebase→push, add -A 금지)" 추가.
- 검증: net 유닛테스트 41개 통과. 라이브 스캔 귀속률 62%(strength≥3 복원 후).

## ⏳ 미완료 / 다음 세션
1. **재인제스트 잔여 배치** — `py scripts/atom_pipeline.py` 반복 실행(미처리 파일 소진까지). strength_score 완전 복원용.
2. **종토방 라이브 목록크롤** — nids 수집 크롤 미구현(Naver 종토방 목록 API 비공개→네트워크탭 발굴 필요). 코어(`jongtobang_ingest.py`)는 준비됨, 목록만 배선하면 캐스케이드 🟠 활성.
3. **/net 브라우저 렌더 확인** — 실서버 `stockbrain1.duckdns.org/net`에서 눈으로 확인(데이터 계약은 검증됨).
4. **정밀도 후속** — 재인제스트 완료 후 min_graph_strength 최적값 튜닝.

## 📁 관련 파일
- 코드: `pipeline/atoms/{strength_net,edges,edge_extract,cause_hunt,jongtobang_ingest,rebuild_atoms_from_chroma}.py`, `dashboard/{server.py,net.html}`
- 문서: `docs/superpowers/specs/2026-07-06-미귀속강세-촘촘한그물-design.md`, `docs/superpowers/plans/2026-07-06-미귀속강세-{scanner-phase1,phase2-관계그래프}.md`
- 엔드포인트: `GET /api/net/unattributed`, `GET /api/net/hunt`, 페이지 `/net`

## ⚠️ 주의
- 이 워킹트리는 공유 — 커밋 전 `git branch --show-current`=main, `git add -A` 금지(크롤데이터 섞임).
- baseline 테스트 실패 1건 `test_questionnaire_to_atoms`(삼성전자→반도체 vs 기타 stale, 이번 작업과 무관).

---
## (이전 세션 미완 — 유실 방지 포인터) 전문가 인용 몽타주 (2026-07-05)
stage1 엔진+스튜디오 배포 완료. **다음: stage2 스토리(산출물 A/B/C 결정 대기).** 설계: `docs/superpowers/specs/2026-07-05-전문가인용몽타주-design.md`.
