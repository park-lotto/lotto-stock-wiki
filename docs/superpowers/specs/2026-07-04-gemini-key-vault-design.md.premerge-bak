# Gemini 키 보관함(Key Vault) 재설계

## 배경

Gemini 키 로테이션 로직이 5곳에 독립 구현되어 있었다(`atomizer.py`, `vector_db.py`,
`dashboard/server.py`, `daily_gemini_report.py`, `daily_scenario.py`). 그중
`atomizer`(일일 소진 추적)와 `vector_db`(분당 RPM 재시도)가 **같은 6개 키 풀을 공유하면서도
서로의 상태를 모르는** 구조라, 2026-07-04 오전 INGEST_KEY 0·1번이 일일 소진된 상태에서
임베딩이 남은 4개 키의 RPM까지 전부 태워 `[WARN] embed 실패` 경고가 반복 발생했다.

또한 `GEMINI_API_KEY` 하나가 대시보드 대화형 기능 + 30여 개 개별 스크립트(경쟁사 분석,
q10 시리즈, yt_trend 등) + 인제스트 폴백을 동시에 떠받치는 단일장애점이었고,
`dashboard/server.py`는 존재하지도 않는 `GEMINI_API_KEY_3/_4`를 참조하고 있었다.

실사용량 조사(원자 DB 실측) 결과:
- 텔레그램 채널 21개, 최근 한 달 17→21개로 증가 중 (JSON 한 줄 추가로 확장, 마찰 거의 없음)
- 하루 원자 생성량이 06-27일 100개 → 07-01일 1,171개로 **일주일 새 약 10배 성장**
- **임베딩은 원자 1개당 1콜**이라 하루 600~1,170콜로 물량의 핵심 병목. 아토마이즈(파일당 1콜)는
  하루 130~180콜로 상대적으로 가볍다
- 코드에 근거가 있는 레이트리밋: 분당 15건(RPM), 키당 일일 한도 약 500건(추정)
- 오늘 6개 키 중 2개가 이미 일일 한도 소진 — 병목이 이미 현실화된 상태

사용자가 신규 Gemini 키(Vertex AI Express Mode 계정, `AQ.Ab8R...` 형식) 10개를 확보해
기존 8개(6 로테이션 + 브리핑 2)와 합쳐 총 18개로 재배치하기로 했다.

## 목표

1. 실사용량 근거로 18개 키를 그룹별로 재배치 (임베딩이 최우선 병목이므로 최다 배정)
2. 로테이션 로직을 **하나의 중앙 모듈**로 통합 — 그룹·회전 상태를 한 곳에서 관리해
   atomizer/vector_db가 서로 모르고 충돌하는 문제, 5곳 중복 구현, dead key 참조,
   상태 파일 레이스 컨디션을 한번에 해소
3. 향후 채널/키가 계속 늘어나는 것을 전제로, `.env`에 `_N` 줄만 추가하면 코드 수정 없이
   자동으로 풀에 편입되는 구조로 설계 (하드코딩 리스트 제거)

## 최종 키 배분 (18개)

| 그룹 | env 변수 | 개수 | 용도 |
|---|---|---|---|
| GENERAL | `GEMINI_API_KEY` ~ `_4` | 4 | 대시보드 대화형(리서치·이미지·비전) + 30여 개 개별 스크립트 폴백 |
| INGEST (atomize) | `GEMINI_INGEST_KEY` ~ `_5` | 5 | 원자화 텍스트 생성 전용 (embed와 분리) |
| EMBED (신규) | `GEMINI_EMBED_KEY` ~ `_6` | 6 | 임베딩 전용 — 현재 최대 병목, 성장 추세 반영해 최다 배정 |
| BRIEFING | `GEMINI_BRIEFING_KEY` ~ `_3` | 3 | 대시보드 장중 브리핑 전용 |

`.env`에 이미 반영 완료 (2026-07-04).

## 아키텍처: `pipeline/atoms/key_vault.py`

단일 모듈이 아래를 전담한다:

- **동적 로딩**: `.env`에서 그룹별 `GEMINI_<GROUP>_KEY`, `_2`, `_3`... 넘버링을 순서대로 전부
  읽어들임(하드코딩 리스트 없음). 그룹: `general` / `ingest` / `embed` / `briefing`.
- **`get_client(group: str) -> genai.Client`**: 그룹의 현재 활성 키로 클라이언트 반환
  (키별 클라이언트 캐시 유지, 기존 패턴과 동일).
- **실패 모델 분리**:
  - *일일 소진* (atomizer 방식): 429 + "PerDay"/한도 문구 → 해당 키를 그날 하루 소진 처리,
    다음 키로 영구 교체, 상태를 파일에 기록.
  - *분당 RPM* (vector_db 방식): 429 + RPM 계열 문구 → 짧은 백오프 후 같은 키(또는 풀 전체)
    재시도, 일일 소진 기록은 남기지 않음.
  - 두 실패 모델이 **그룹별로 하나의 공유 상태**를 보고 판단하므로, 같은 그룹을 쓰는
    여러 소비자(예: EMBED 그룹의 vector_db)가 서로 다른 코드에서 중복으로 키를 소진시키지 않는다.
- **상태 파일**: 기존 `.gemini_key_state.json` 포맷을 그룹별로 확장. read-modify-write에
  파일 락(`msvcrt.locking` 기반 간단 락)을 추가해 동시 실행 레이스 컨디션을 제거.
- **알림**: 기존 텔레그램 알림 함수를 재사용, 그룹명을 포함해 통일된 포맷으로 발송.
- **드롭인 헬퍼**: `client(group)` 한 줄 호출로 `genai.Client(api_key=...)`를 대체할 수 있는
  얇은 함수 제공 — 마이그레이션 시 각 호출부를 1~2줄만 바꾸면 되게.

## 마이그레이션 범위 (티어)

- **필수** (이번 구현 범위): `atomizer.py`, `vector_db.py`(EMBED 그룹으로 전환),
  `dashboard/server.py`, `daily_gemini_report.py`, `daily_scenario.py`,
  `pdf_ingest.py`/`osc_ingest.py`(`keys[0]` 고정 제거, vault로 회전).
  동시에: `generate_jh_images.py`의 하드코딩된 API 키 리터럴 제거,
  `3pro_corner_test.py`의 존재하지 않는 `GEMINI_API_KEY_3` 참조 수정.
- **권장** (이번 구현에 포함, 시간 허용 시): 자주 실행되는 스크립트
  (`scripts/briefing/*`, `scripts/yt_*`, `scripts/sector_*`, `taerini_gemini_analyze.py`,
  `naver_news_analyze.py`, `pipeline/competitor_analyze*.py`, `미국장브리핑.py`,
  `장중섹터흐름.py`)를 `client("general")` 한 줄 호출로 전환.
- **스킵**: 일회성 테스트/실험 스크립트(`run_final_test.py`, `test_gemini_extract.py` 등)는
  그대로 `GEMINI_API_KEY` 직접 참조 유지 — vault가 그 이름을 계속 관리하므로 깨지지 않는다.

## 에러 처리

- 그룹의 모든 키가 소진되면: 기존과 동일하게 텔레그램 경보 발송 후 예외 발생(호출부가 처리).
- vault 모듈 자체의 결함(예: `.env` 파싱 실패)은 즉시 예외 — 조용히 빈 풀로 넘어가지 않는다.

## 테스트

- 그룹별 키 로딩(존재/누락 키 필터링)에 대한 단위 테스트
- 일일 소진 → 회전 → 상태 파일 기록 시나리오 테스트
- RPM 재시도 → 짧은 백오프 → 성공/전체 실패 시나리오 테스트
- 동시 두 프로세스가 상태 파일에 쓸 때 락이 걸리는지에 대한 테스트
