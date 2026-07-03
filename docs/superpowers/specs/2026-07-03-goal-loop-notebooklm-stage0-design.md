# 골-루프 Stage0 교체 — NotebookLM 기반 아침 브리핑 콘텐츠 생성

- 작성일: 2026-07-03
- 상위 스펙: `docs/superpowers/specs/2026-07-02-goal-loop-orchestrator-design.md` (아침 브리핑 골-루프 v1, 이미 완성·main 병합됨)
- 상태: 설계 확정 (구현계획 대기)

---

## 1. 배경 · 문제

골-루프 v1의 Stage0(데이터·1차 드래프트 생성)은 `daily_scenario.py`(단일 Gemini 호출)를 재사용했다.
실전 테스트 결과 두 가지 문제가 드러났다:

1. **품질 낮음**: 원천 데이터가 부실할 때 "새로운 소식이 없어서 돈 흐름이 멈춘 상태다" 같은
   막연하고 근거 없는 문장을 생성. 프로젝트 핵심 원칙(`feedback_briefing_source_citation`:
   "Claude 자체 판단 금지, 소스가 한 말 직접 인용+출처+날짜")을 만족 못함.
2. **단일 키 의존**: `get_gemini()`가 GEMINI_API_KEY 1개만 써서 429(쿼터초과) 시 그대로 실패.
   (2026-07-03 중간 조치로 6키 로테이션 추가 완료 — 이 문제는 별개로 이미 해결됨, 커밋 fdd54bf0)

사용자 결정: **daily_scenario.py 대신 이미 검증된 NotebookLM 파이프라인**(`인사이트허브→NotebookLM
다리`, HBM·조선에서 실사용 검증됨)으로 Stage0을 교체한다. NotebookLM은 실제 소스(오늘 크롤링된
텔레그램·리포트·블로그 원자)에 근거해 인용 달린 답변을 만들어 "소스 인용 원칙"을 구조적으로 만족한다.

---

## 2. 확정된 핵심 결정

| 항목 | 결정 |
|------|------|
| 카드 핵심 내용 | **크롤링 소스(텔레·리포트·블로그) 핵심 발언 요약** — 사장님 기존 소스인용 원칙과 일치 |
| 산출물 | **A(구조화 카드) + B(NotebookLM 심층 리포트) 매일 둘 다 자동 생성**. 카드에 리포트 링크 첨부 |
| 노트북 수명 | **매일 새 노트북** (전날 소스 삭제·재사용 안 함, YAGNI — 관리 단순) |
| A 생성 방식 | `notebook_query` 구조화 질문 — 기존 daily_scenario 포맷(📌🔴🔵⚠️📅💡🎯)과 동일하게 질문해
  기존 `studio_data._parse_sections` 파서·카드 렌더러·품질루프를 **무수정 재사용** |
| B 생성 방식 | `notebook_card`(report create, format="Briefing Doc") — 비차단(실패해도 A 발행엔 영향 없음) |
| 블라스트 반경 | 골-루프 v1의 오케스트레이터(품질루프·이상징후게이트·에스컬레이션·데몬)는 **무수정**.
  Stage0(콘텐츠 생성)만 교체 |

---

## 3. 아키텍처

```
[Stage0 — 신규] scripts/goal_loop/notebook_stage0.py
  1. build_notebook(date)
     → nlm_bridge._build_notebook_bundle(q="", cats=["telegram","report","blog"], period="today")
     → 원자 0건이면 빈 결과 반환 (C1 가드로 흘러감, 신규 코드 불필요)
     → 새 노트북 생성("[골루프] 아침브리핑 {date}") + 오늘 원자 소스 추가
  2. query_card_content(notebook_id, date)
     → notebook_query(질문 = daily_scenario와 동일 포맷·규칙 지시)
     → 답변 텍스트를 out/scenario_{date}.md에 저장 (기존 studio_data 파서가 그대로 읽는 경로/포맷)
  3. generate_deep_report(notebook_id, date)  [비차단]
     → notebook_card(report create, "Briefing Doc", ko) → 최대 150초 폴링 → 마크다운 저장
     → 실패/타임아웃 시 None 반환, 상위 로직은 계속 진행

[nlm_bridge.py — 신규, server.py에서 추출]
  순수 함수만(부작용 없음, import 안전): _nlm_exe·_run_nlm·_nlm_relogin_locked·_friendly_nlm_err·
  _build_notebook_bundle·_nb_fetch_rows·_nb_scope_label·_nb_cat_of·_nb_md_for_rows
  dashboard/server.py의 기존 6개 NLM 엔드포인트는 이 모듈을 import해서 사용(동작 동일, 위치 이동만)

[morning_brief.py — 수정]
  _ensure_scenario(date): daily_scenario.py 서브프로세스 호출
    → notebook_stage0.build_notebook + query_card_content 호출로 교체
  run_morning_brief(): notebook_url을 텔레 캡션에 첨부(정상 발행·에스컬레이션 공통)
                        + generate_deep_report를 비차단으로 호출, 성공 시 링크 추가
```

**재사용 포인트(변경 없음)**: `studio_data.get_briefing_data`, `card_render.*`, `quality.critique/revise`,
`verify.detect_anomalies`, `pending.*`, `viz_card.send_telegram_photo/message`, 08:00 데몬 게이트.

---

## 4. `notebook_query` 프롬프트 설계

daily_scenario.py의 기존 PROMPT 형식·규칙을 그대로 재사용(카드 파서 호환 유지):

```
📌 오늘 핵심 / 🔴 강세 종목 / 🔵 리스크 종목(있으면) / ⚠️ 리스크 / 📅 챙길 일정 / 💡 시나리오 / 🎯 오늘 한 줄
```
규칙: 숫자 없으면 쓰지 마라 / 전문용어 쉬운말 변환 / 형식 밖으로 나오지 마라(daily_scenario와 동일).

`notebook_query`는 이미 자체적으로 "출처·날짜 인용 강제, 소스에 없는 주장 금지" 가드를 프롬프트에
자동 부착하므로(server.py 기존 로직), 위 포맷 지시와 결합된다.

---

## 5. 에러 처리 (기존 안전장치 재사용표)

| 실패 지점 | 처리 | 신규 코드 필요? |
|---|---|---|
| 오늘 원자 0건 | 빈 문자열 반환 → `studio_data.get_briefing_data`가 빈 headline/lines 반환 → **C1 가드**(기존) 발동, 에스컬레이션 | 아니오 |
| nlm 로그인 만료 | `_run_nlm`의 기존 자동 재로그인 재사용, 실패 시 빈 결과 → C1 가드 | 아니오 |
| notebook_query 포맷 이탈(파싱 실패) | 파싱 결과 headline/lines 비면 **C1 가드**(기존) | 아니오 |
| B(심층리포트) 실패·타임아웃 | 비차단 — A 발행 계속 진행, 캡션에 링크만 생략 | `generate_deep_report`가 예외 흡수 |

---

## 6. 범위 (YAGNI)

### 이번 범위 (v1.1)
- `scripts/nlm_bridge.py` 추출 + server.py 기존 엔드포인트 재배선(동작 무변경)
- `scripts/goal_loop/notebook_stage0.py`: build_notebook·query_card_content·generate_deep_report
- `morning_brief.py`의 `_ensure_scenario` 교체 + 캡션에 노트북/리포트 링크 첨부
- 기존 오케스트레이터(품질루프·게이트·에스컬레이션·데몬)·daily_scenario.py 로테이션은 **무변경 유지**

### 이번 범위 아님 (후속)
- 노트북 소스 재사용/정리(매일 새 노트북이므로 불필요)
- B(심층리포트)를 카드 파서 스키마로 파싱(범위 밖 — 링크만 첨부)
- 다른 골(유튜브·투경)의 NLM 연동

---

## 7. 열린 항목 (구현 중 확정)
- `notebook_query` 실제 응답이 daily_scenario 포맷을 얼마나 안정적으로 지키는지 실측 후 프롬프트 튜닝
- 노트북 생성+소스추가+질의(A)+리포트(B) 전체 소요시간 실측 (예상: A 수십초, B 최대 150초)
- `_build_notebook_bundle`가 기대하는 카테고리 문자열(`telegram`/`report`/`blog`)이 오늘 원자 데이터의
  `source_type`과 정확히 일치하는지 확인
