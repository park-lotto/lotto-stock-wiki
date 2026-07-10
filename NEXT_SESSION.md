# NEXT_SESSION

## ⭐⭐⭐ 최신 세션 (2026-07-10 · 쇼핑쇼츠 제품찾기 방향수정+정확도개선+5대플랫폼+속도개선)

**별개 프로젝트**: 쇼핑쇼츠 영상제작 자동화 SaaS. 코드 `shopping_shorts/`.

**중요 정정**: 전날 세션에서 "구매처 찾기"(SerpApi Google Lens로 쇼핑몰 검색)를 만들었는데, 이건 **목적을 잘못 이해한 기능**이었음 — 사용자가 원하는 건 짜집기용으로 **다른 사람이 만든 비슷한 제품 영상 찾기**지 쇼핑몰 링크가 아니었음. 전체 삭제(lens_shopping.py·SERPAPI_KEY·`/api/find/shop`·find.html 구매처 UI 전부 제거).

**이번 세션 완료** (전부 main 배포·라이브검증):
1. **5개 언어 키워드 실수집 확장** — "다른 프로그램보다 정확도 떨어짐" 피드백 원인 발견: Gemini가 ko/en/zh 3개어로 키워드 생성했는데 실제 검색엔 언어 하나만(플랫폼별 우선순위 1개) 써서 zh는 생성만 하고 버려지고 있었음. video_analysis.py를 ko/en/zh/ja/ru 5개어로 확장, app.py `/api/find/collect`가 5개 언어 전부 검색해 URL기준 중복제거 후 합치도록 수정.
2. **샤오홍슈(小红书) 실수집 신규 추가** — "틱톡 인스타 유튜브 더우인 샤오홍슈 5대플랫폼" 요청. Apify 액터 조사 결과 `zen-studio~rednote-search-scraper`(샤오홍슈)는 실제 키워드검색+video-only필터 정상 작동 확인, 반면 `natanielsantos~douyin-scraper`(더우인)는 흔한 키워드로도 0건 나와 신뢰도 낮음 판단 — **더우인은 보류**, 샤오홍슈만 연동.
3. **실수집 병렬화(성능)** — 5개 언어 순차검색+후보별 순차 Gemini채점이 실측 **27분+** 걸리던 걸 발견, ThreadPoolExecutor로 병렬화해 **3분47초로 단축(약7배)**. 병렬 채점 시 여러 스레드가 `shorts_gemini_state.json`(키로테이션 상태)을 동시에 건드릴 수 있어 comment_gen.py에 RLock 추가.

**⏳ 다음**:
1. 더우인 실수집 — 다른 Apify 액터 재조사 필요(현재 액터는 미신뢰)
2. 유사도 채점(score_candidate)도 대량 후보 시 여전히 병목 가능 — 필요시 배치/캐싱 검토
3. (이전 세션 이월) 인스타 해시태그 0건 키워드 폴백은 이미 완료됨

---

## ⭐⭐ 최신 세션 (2026-07-10 · SEO 구조분석→애드센스 사업, Phase1 완료·니치확정 보류중)

**별개 사업 구상**: 로또의 주식과 무관한 신규 사업 — 잘 만들어진 구글 SEO 페이지 구조분석 → 애드센스 광고 수익 사업. 설계 `docs/superpowers/specs/2026-07-09-SEO-애드센스-사업-design.md`(최신 상태 반영됨).

**Phase 1 완료** (커밋 `1a6a1fda`): 8개 니치(신용카드/정부지원금·부동산청약·IT활용팁·레시피·여행지·육아교육·반려동물·캠핑인테리어) 조사에이전트 병렬실행 → 각 니치 상위노출 사이트 원문HTML에서 `adsbygoogle` 직접확인 방식으로 구조분석 → 4축 스코어카드 산출. 순위: IT활용팁(3.75) &gt; 여행지·캠핑인테리어(3.5) &gt; 부동산·반려동물(3.0) &gt; 레시피(2.9) &gt; 육아(2.75) &gt; 신용카드(2.5). 세부는 스펙 문서 참고.

**⚠️ 사용자에게 명확히 전달한 한계**: 스코어카드의 "경쟁강도/CPC/정책리스크" 점수는 **실측 수익데이터가 아니라 일반 업계지식+정황추론**. 실제로 확인된 건 애드센스 스크립트 존재·광고배치·스키마마크업 등 구조적 사실뿐. CPC·실수익은 추정치임을 사용자가 인지하고 있음.

**⏸️ 현재 상태 — 사용자가 직접 시장정보(실제 수익후기 등) 더 가져오는 중, 니치 확정 보류.** 다음 세션 시작점:
1. 사용자가 가져온 정보 반영해서 8개 니치 스코어카드 업데이트 또는 니치 최종 확정
2. (선택) 미실행: "애드센스 수익 후기 [니치명]" 검색으로 실제 블로거 공개수익 사례 추가조사 — 제안했으나 세션 종료로 미실행
3. 니치 확정되면 → Phase 3(파일럿 워드프레스 사이트 구축: 키워드리서치→도메인/호스팅→WP셋업→AI콘텐츠파이프라인→초기글25~35개→애드센스신청→광고배치→60~90일검증) 상세 실행. 8단계 실행플랜은 이 세션 대화에 있음, 다음세션에 스펙문서에도 옮겨적을 것.

---

## (이전) 최신 세션 (2026-07-09 · 집CH · 쇼핑쇼츠 자동화 ② 소통큐 완성)

**별개 프로젝트**: 쇼핑쇼츠 영상제작 자동화 SaaS (tubefactory급 A목표). 코드 `shopping_shorts/` (주식위키 무관). 메모리 `project_쇼핑쇼츠_자동화.md`.

**이번 세션 완료** (전부 main 병합·push, 유닛테스트 43개 통과):
- **기능 ② 소통 큐 완성** — ①수집 릴스에 직접 댓글달아 계정키우기 반자동. comment_gen.py(Gemini 캡션→댓글3개, key_vault재사용) / outreach.py(정렬3옵션: 최신·갓올라온터진·골디락스) / store확장(comment_drafts·commented·saved·last_run) / app확장(/api/outreach·comment/done·save·saved·thumb) / outreach.html(리스트+진행모드, 복사·새탭·완료토글). **자동 댓글·좋아요·팔로우 절대안함** — 사람이 붙여넣기·전송.
- **CTA 이벤트 댓글**: 캡션에 응모CTA 있으면 3중 2개 참여댓글.
- **랭킹 UI 개선**: 8열 촘촘그리드 + 보기/댓글참여/담기 3버튼.
- **수집결과 SQLite 영구저장**: _LAST 메모리캐시 제거 → 재시작해도 화면유지.
- **썸네일 서버프록시** (/api/thumb): 인스타 핫링크차단 우회, 실제이미지 뜸.
- 실전검증: 새 Apify토큰으로 10건 수집+댓글생성+썸네일 확인.

**추가 완료(세션 후반)**: 모바일 반응형(사이드바 가로바+카드 2열, @media 768/420). 임시 공유는
cloudflared 터널로 검증함 — `cloudflared tunnel --url http://localhost:8848` → *.trycloudflare.com
임시URL(PC·세션 살아있을 때만, 인증없음, 매번 URL바뀜). stockbrain(주식용)과 별개.

**✅ 서버 배포 + 로그인 — 완료됨(이 세션에서 확인)**: `https://shoppingshorts.duckdns.org` (nginx→127.0.0.1:8849, systemd `shopping-shorts`, dash_auth 쿠키 로그인 이미 동작 중). 자동배포는 주식위키와 동일 패턴(git push → 서버 크론 pull+재시작, 수동으로도 `git pull --ff-only && sudo systemctl restart shopping-shorts`).

**✅ 기능 ③ 소스매칭 — 대부분 완료(이 세션에서 구현+실증)**:
- 유튜브/틱톡/인스타 실수집 전부 실동작 확인(Apify 액터 3종: youtube search, `clockworks~tiktok-scraper`, `apify~instagram-hashtag-scraper`)
- 유사도 카드 시각화(초록테두리+✅일치뱃지 / 저매칭 흐리게)
- 버그수정 다수: Gemini 모델명(`gemini-3.5-flash`), 인스타 `resultsType=reels` 안 하면 사진만 나오던 문제, `/api/find/frame/*` 401(외부 크롤러 fetch 불가) → 인증예외 추가, `PUBLIC_BASE_URL`이 내부루프백(127.0.0.1:8848)으로 잘못설정 → 실도메인으로 수정
- **신규: SerpApi Google Lens "🛍️ 구매처 찾기"** — 프레임별 버튼 클릭 시 실제 판매 쇼핑몰(Amazon/eBay/Alibaba 등) 링크 검색. 실측: 프레임마다 매칭 편차 큼(배경 소품 오매칭 확인됨) → 자동전체수집 대신 프레임 수동선택 방식으로 설계.
- 알려진 한계: 인스타 해시태그가 정확일치라 Gemini가 뽑은 복합키워드(예: "무선헤어드라이어")로 검색하면 0건 나오는 경우 있음 — **미해결**: 키워드 폴백(짧은/일반적 키워드로 순차 재시도) 아직 미구현.

**⏳ 다음**:
1. 인스타 실수집 키워드 폴백 로직(길고 구체적인 키워드 실패 시 짧은 키워드로 재시도) — 0건 문제 근본해결
2. SerpApi 실사용 관찰 — 결제 발생하는 유료 API라 호출량 모니터링 필요(무료 100건 체험 중)
3. 알려진 개선: 인스타 썸네일 2주뒤 만료→필요시 로컬다운로드. Apify 무료$5한도 도달경험→테스트는 limit=5~10.

**실행**: `.env`에 APIFY_TOKEN. `cd 로또의주식 && python -m uvicorn shopping_shorts.app:app --port 8848` → http://127.0.0.1:8848 (랭킹) / /outreach.html (소통큐) / /find.html (제품찾기). 스펙/플랜: docs/superpowers/*/2026-07-0[89]-쇼핑쇼츠-*.

---

## (이전) 2026-07-07 · DESKTOP · 순환매 감지기 구현

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
