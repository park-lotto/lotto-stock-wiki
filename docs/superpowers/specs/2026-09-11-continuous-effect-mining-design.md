# 상시 쇼츠 효과 채굴 시스템 설계

## 목표

한 번 실행하고 끝나는 크롤러가 아니라, 별도 클라우드 워커가 계속 신규 숏폼을 발견하고 수집·정제·분석하여 효과 후보를 누적하는 기반을 만든다. 운영 서버는 완성된 효과팩만 소비하며 무거운 다운로드와 영상 분석은 맡지 않는다.

## 이번 트랙의 경계

이번 트랙은 다음 단계가 실제로 반복 실행될 수 있는 기반까지 만든다.

1. 등록된 수집 소스를 주기적으로 확인한다.
2. 발견한 영상은 정규화한 플랫폼 ID로 중복 제거한다.
3. `discover → acquire → measure → promote` 작업을 내구성 큐로 연결한다.
4. 작업 실패는 지수 백오프로 재시도하고 한도를 넘으면 dead 상태로 격리한다.
5. 다운로드된 영상에서 컷 경계와 모션 에너지를 결정론적으로 측정한다.
6. 효과 후보는 근거 영상·타임라인·분석기 버전을 잃지 않고 저장한다.
7. 워커 재시작 후에도 SQLite 상태에서 이어서 처리한다.

자막 OCR, 효과음 트랜지언트, Vision/LLM 의미 해석, 관리자 검수 화면, 효과 레시피 자동 제작은 후속 독립 트랙이다. 이번 기반의 작업 종류와 저장 형식에 플러그인으로 추가한다.

## 배치 구조

```text
별도 클라우드 워커
  scheduler 프로세스 ── due source를 discover 작업으로 등록
  worker 프로세스 N개 ── 역할별 작업 lease/heartbeat/retry
  SQLite(초기) ───────── source/item/job/signal/candidate/run
  object storage root ── 연구용 원본과 분석 산출물

운영 서버
  승인·버전 고정된 effect pack만 읽음
```

초기에는 추가 인프라 없이 검증할 수 있도록 SQLite를 쓴다. 작업 선점은 짧은 `BEGIN IMMEDIATE` 트랜잭션으로 직렬화한다. 워커 수와 데이터량이 SQLite 단일 writer 한계를 넘으면 같은 저장소 인터페이스 뒤를 PostgreSQL/Redis로 바꾼다.

## 데이터 모델

- `mining_sources`: 플랫폼, 검색 종류, 검색값, 실행 주기, 다음 실행 시각, 활성 여부.
- `mining_items`: 플랫폼 영상 ID가 유일키다. URL, 제목, 채널, 지표, 최초·최종 발견 시각, 로컬 미디어 경로를 가진다.
- `mining_jobs`: 작업 종류, payload, dedupe key, 상태, 시도 횟수, 다음 실행 시각, lease와 heartbeat, 오류를 가진다.
- `mining_signals`: 분석기 이름·버전별 구조화된 결과. 같은 버전은 덮어쓰지 않고 upsert한다.
- `effect_candidates`: 근거 item과 signal에서 파생된 장면전환·모션 피크 후보. 상태는 `candidate/reviewing/approved/rejected`다.
- `mining_runs`: 소스 실행별 발견·신규·실패 수와 오류를 기록한다.

## 작업 계약

모든 handler는 JSON payload를 받고 JSON 결과를 반환한다.

- `discover`: source ID → 플랫폼 커넥터 실행 → item upsert → 신규/갱신 item마다 `acquire` 등록.
- `acquire`: item ID → 미디어 다운로드 → 경로·해시 저장 → `measure` 등록.
- `measure`: item ID → 컷/모션 측정 → signal 저장 → `promote` 등록.
- `promote`: signal ID → 컷 밀도와 모션 피크를 후보로 변환.

큐의 dedupe key는 작업 의미를 포함한다. 예: `acquire:item:42`, `measure:item:42:signals-v1`. 완료된 동일 버전 분석은 다시 만들지 않는다.

## 실패와 회복

- 작업은 lease를 얻은 워커만 처리한다.
- 긴 작업은 heartbeat로 lease를 연장한다.
- 워커가 죽으면 만료된 lease를 scheduler가 queued로 돌린다.
- 실패는 `min(base * 2^(attempt-1), max_backoff)` 뒤 재시도한다.
- 최대 시도 횟수를 넘으면 dead로 보내며 자동으로 성공처럼 숨기지 않는다.
- 커넥터 하나가 막혀도 다른 플랫폼 작업은 계속 처리한다.
- 원본 삭제와 후보 삭제는 자동 연동하지 않는다. 근거 보존 기간 정책은 별도로 둔다.

## 수집 원칙

수집 원본은 연구 근거이며 고객 배포 에셋이 아니다. 고객에게 제공하는 것은 자체 제작한 효과 레시피 또는 사용 권리를 확인한 에셋뿐이다. 각 item에는 원본 URL·플랫폼·채널·발견 시각을 남겨 역추적 가능하게 한다.

## 운영과 관측

CLI는 `init`, `add-source`, `schedule`, `work`, `status`를 제공한다. 클라우드에서는 scheduler 하나와 worker 여러 개를 systemd 또는 컨테이너로 상시 실행한다. 상태 출력은 queued/running/retry/dead 수, 최근 처리율, source별 다음 실행 시각을 보여준다.

## 수용 기준

- 같은 source를 여러 번 schedule해도 동시에 discover 작업이 하나만 존재한다.
- 같은 영상 URL/ID를 반복 발견해도 item은 하나이며 지표와 last_seen만 갱신된다.
- 워커 종료 후 lease가 만료되면 다른 워커가 작업을 회수한다.
- 일시 오류는 backoff 후 재시도되고 영구 오류는 dead로 격리된다.
- 샘플 MP4를 처리하면 컷·모션 signal과 후보가 DB에 연결되어 남는다.
- 외부 API와 다운로드 없이도 가짜 connector/downloader로 전체 파이프라인 테스트가 가능하다.

