# 파이프라인 매일 건강검진 (daily_health) — 설계

- **날짜**: 2026-06-21
- **배경**: 매일 7AM `atom_pipeline.py`가 전체 인제스트를 자동 실행한다. "잘 돌아가는지"를
  사람이 매번 확인할 수 없으므로, **매일 건강검진을 자동화**해 버그를 잡고 개선점(별칭·외국주
  매핑 보강 대상)을 폰으로 받는다. 신호는 이미 깔려 있다(quote 플래그·미매칭/외국 로그·
  원자 수·pytest). 모으기만 하면 된다.
- **범위**: 전체 파이프라인 건강검진. 텔레그램·리포트·오실레이터·wiki 단계 전부.

---

## 1. 결정 사항 (brainstorming 확정)

| 항목 | 결정 |
|---|---|
| 산출 형태 | **폰/텔레그램 리포트 카드** (`send_telegram` 재사용) |
| 범위 | **전체 파이프라인** (리포트+텔레+오실+wiki 단계) |
| 드리프트 감지 | **결정론적만**(무료): pytest 회귀 + 데이터이상 + 에러. Gemini 골든 재실행 안 함 |
| 발송 정책 | **정상=한 줄 / 이상=상세** (하이브리드) |
| 실행 위치 | `atom_pipeline.py` **STEP6** (매일 끝에 자동) |

---

## 2. 아키텍처

```
atom_pipeline.py (7AM)
  STEP1~5 인제스트 … 각 단계 exit code를 run-log에 누적
  STEP6 daily_health.py
     ├ collect_signals()      → 오늘 지표 dict
     │    · run-log(단계별 성공/실패·에러)
     │    · atoms DB 소스별 원자 수
     │    · ingest flag 집계(quote 플래그 수)
     │    · 개선큐 신규(unmatched/foreign_unmapped 신규 줄)
     │    · pytest 결과
     ├ compare_to_baseline()  → 어제(health_history.json) 대비 이상 목록
     ├ render_card()          → 정상=1줄 / 이상=상세 텍스트
     ├ send_telegram(card)
     └ save_snapshot()        → 오늘 지표를 health_history.json에 (내일 비교용)
```

### 데이터 위치
- `out/health/{date}_pipeline.json` — atom_pipeline이 쓰는 단계별 run-log
- `out/health/{date}_ingest.jsonl` — ingest가 쓰는 per-파일 통계({source, file, atoms, flagged})
- `pipeline/atoms/health_history.json` — 일별 스냅샷(원자수·플래그율 등) 누적

---

## 3. 신호 수집 (collect_signals)

| 신호 | 소스 | 의미 |
|---|---|---|
| 단계별 성공/실패·exit | `{date}_pipeline.json` run-log | 크래시·중단 |
| 소스별 원자 수 | atoms DB `GROUP BY source_type` (오늘 date) | 추출량 |
| quote 플래그율 | `{date}_ingest.jsonl` 합산(flagged/atoms) | 할루시네이션 의심 |
| 개선큐 신규 | unmatched.log·foreign_unmapped.log 오늘 줄 수 | 별칭·매핑 보강 대상 |
| pytest 회귀 | `python -m pytest pipeline/atoms/ -q` 종료코드 | 코드 버그 |
| 에러 메시지 | run-log의 stderr 요약 | 런타임 실패 |

반환: `dict` (모든 지표 + date).

---

## 4. 비교·경보 (compare_to_baseline)

`health_history.json`의 어제 스냅샷과 대조. 경보 조건(임계 config화):

| 경보 | 조건 (기본값) |
|---|---|
| 🔴 단계 실패 | run-log에 exit≠0 단계 존재 |
| 🔴 pytest 실패 | pytest 종료코드 ≠ 0 |
| 🟠 원자 급감 | 소스별 원자수가 어제 대비 **-50%↓** |
| 🟠 플래그율 급등 | quote 플래그율 **>20%** |
| 🟡 개선큐 증가 | 미매칭/외국 신규 줄 존재(정보성) |

반환: `list[dict]` (각 {level, code, msg}). 빈 리스트 = 정상.

---

## 5. 리포트 카드 (render_card)

**정상(경보 0건) — 한 줄:**
```
✅ 건강검진 2026-06-21 정상 — 5/5 단계, pytest 81 pass, 원자 리포트+12·텔레+22
```

**이상(경보 ≥1건) — 상세:**
```
⚠️ 건강검진 2026-06-21 — 경보 2건
🔴 STEP3.5 telegram 실패 (exit=1)
🟠 텔레 원자 급감: 22→3 (-86%)
🟡 보강큐: 미매칭 5 · 외국주 3
[정상 단계] 리포트·오실·wiki ok / pytest 81 pass
```

`send_telegram()`(calc_oscillator) 재사용. parse_mode HTML.

---

## 6. 선행 훅 (소규모)

이 설계가 새로 필요로 하는 최소 변경:

1. **`atom_pipeline.py` run-log**: `run()`이 (label, exit, stderr요약)을 리스트에 누적 →
   파이프라인 끝에 `out/health/{date}_pipeline.json` 기록. STEP6에서 daily_health 호출.
2. **ingest flag 집계**: `telegram_ingest`·`report_ingest`가 파일별 {source, file, atoms,
   flagged}를 `out/health/{date}_ingest.jsonl`에 append (1줄). 기존 flag 계산 재사용, 출력만 추가.

> 둘 다 기존 로직에 "쓰기 1줄" 추가 수준. 인제스트 동작 자체는 안 바뀜.

---

## 7. 컴포넌트 분리 (테스트 용이)

| 함수 | 입력 | 출력 | 테스트 |
|---|---|---|---|
| `collect_signals(date)` | 파일·DB | 지표 dict | 픽스처 run-log·jsonl로 |
| `compare_to_baseline(today, history)` | dict 2개 | 경보 list | 순수함수 단위테스트 |
| `render_card(metrics, alerts)` | dict·list | str | 정상/이상 분기 단위테스트 |
| `save_snapshot(metrics, path)` | dict | — | 임시파일 |

`send_telegram`·pytest 실행은 테스트 안 함(부작용). 순수 로직만 TDD.

---

## 8. 검증/테스트
- `compare_to_baseline`: 원자 -50%→🟠, 플래그 21%→🟠, exit=1→🔴, 정상→빈 list.
- `render_card`: 경보 0→한 줄(✅), 경보≥1→상세(⚠️).
- `collect_signals`: 픽스처 run-log·ingest.jsonl·임시 로그로 지표 추출.
- 로그/DB/스냅샷 파일은 임시경로 격리(운영 안 건드림) — 기존 패턴 준수.

---

## 9. 기존 자산 통합

| 자산 | 역할 |
|---|---|
| `calc_oscillator.send_telegram` | 텔레 발송 재사용 |
| `verify_telegram`·`verify_questionnaire` | flag 계산 출처(집계만 추가) |
| `unmatched.log`·`foreign_unmapped.log` | 개선큐 소스 |
| `atom_pipeline.py` | STEP6 추가 + run-log |
| pytest `pipeline/atoms/` | 회귀 신호 |

---

## 10. 범위 밖 (후속)
- Gemini 골든셋 재실행 드리프트 감지(주간) — 비용 절충 후속
- 자동 개선(별칭·매핑 자동 후보 적용) — 지금은 보강큐 "표시"만
- 웹 대시보드(스탁브레인 대시보드는 별도 작업)
- 추세 그래프(주간 원자수 추이 등)

---

## 11. 미해결/결정
- health_history.json 보관 일수 → 최근 14일 롤링(파일 비대 방지)
- 경보 임계값(−50%·20%)은 config 상수 → 운영하며 튜닝
- pytest를 매일 도는 게 느리면(현재 3초) STEP6에서 그대로, 느려지면 분리
