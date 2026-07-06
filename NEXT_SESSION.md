# NEXT_SESSION

## ⭐ 최신 세션 (2026-07-06 저녁 · DESKTOP · 대시보드 실장 튜닝)
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
