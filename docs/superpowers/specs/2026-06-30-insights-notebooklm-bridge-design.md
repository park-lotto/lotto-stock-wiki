# 인사이트 허브 → NotebookLM 다리 (Design)

날짜: 2026-06-30 / 상태: 승인됨(①+㉢) / PC: 집

## 목적
인사이트 허브에 모인 크롤링 자료(youtube·telegram·blog·report·news, atoms.db)를
NotebookLM 리서치 + 카드(인포그래픽/리포트) 생성의 **자동 소스 공급원**으로 사용한다.
"종목 한 번 검색 → 전 소스 발언이 NotebookLM 노트북으로" = 허브의 가로질러 찾기 철학과 직결.

## 확정 선택
- **묶음 단위 ①**: 종목/키워드 가로검색 묶음 (search q 기준).
- **넣을 자료 ㉢**: 추출발언(검증된 사실) + 원본 URL/유튜브 링크 둘 다.

## 아키텍처
서버(FastAPI server.py)가 `nlm` CLI를 subprocess로 직접 호출 → 브라우저 버튼 하나로 완전 자동.
(MCP 경유 아님. nlm CLI는 login·notebook·source·studio·research 전부 지원, 인증은 프로필 default.)

```
검색 q ──▶ POST /api/insights/to_notebook {q, research?, card?}
  1. atoms.db: content/asset LIKE %q% (LIMIT 200) 수집
  2. 카테고리/소스별 그룹 → 추출발언 .md 1개 작성 (발언+stance+출처+날짜+deeplink)
     → out/insights_notebook/{safe_q}_{date}.md
  3. distinct URL 수집: youtube deeplink → --youtube / 그 외(blog,news,report) → --url (각 최대 20)
  4. nlm notebook create "[허브] {q} · {date}" --json → notebook_id
  5. nlm source add {id} --file {md}            (추출발언 = 그라운딩 사실)
     nlm source add {id} --youtube ... --url ... (원본)
  6. return {ok, notebook_id, url, atoms_n, url_n}
```

research/card는 Phase 3에서 별도 엔드포인트(`nlm research`, `nlm studio`)로 분리 —
둘 다 수십 초~분 단위라 노트북 생성과 분리해 비동기 버튼으로.

## 엔드포인트
- `POST /api/insights/to_notebook` body `{q, research:false, card:false}` → 노트북 생성+소스투입.
- (Phase 3) `POST /api/insights/notebook_research` `{notebook_id, q, mode}`.
- (Phase 3) `POST /api/insights/notebook_card` `{notebook_id, artifact}` artifact=infographic|report.

## UI (insights.html)
검색 결과 패널 상단에 `📒 NotebookLM 노트북 만들기` 버튼 (hits>0 일 때).
결과: 노트북 URL 링크(새 탭) + Phase3에서 🔬딥리서치 / 🎴카드 버튼.

## 안전/제약
- nlm 미인증 시: 503 + "터미널에서 nlm login" 메시지.
- 매칭 0건: 400 "해당 키워드 발언 없음".
- URL 과다 방지: 카테고리별 cap. 추출발언은 전량 .md 1개로.
- subprocess: shutil.which('nlm'); 타임아웃 60s(create/add는 --wait 미사용으로 빠름).

## 검증
Phase1: 실제 "HBM" 호출 → NotebookLM에 노트북 생성·소스 2건 이상 붙는지 URL로 확인.

## 단계
1. 백엔드 to_notebook + 번들 빌더 (+실제 HBM 검증) ← 지금
2. 프론트 버튼
3. research/card 엔드포인트 + 버튼
