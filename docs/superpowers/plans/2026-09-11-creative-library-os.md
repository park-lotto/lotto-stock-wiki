# Creative Library OS 구현 계획

- 전제: 장면꾸미기 UI 기능 추가는 잠시 멈춘다.
- 원칙: 기존 시스템을 버리고 다시 만들지 않는다. 어댑터로 읽고, 도메인별로 검증이 끝난 뒤에만 새 정본으로 전환한다.
- 첫 목표: 모든 라이브러리를 채우는 것이 아니라 **공통 계약 + 기존 도메인 연결 + 끝까지 실제로 작동하는 대표 완성 팩 1개**를 만든다.

## Phase 0 — 전수 실사와 정본 지도

### 작업

- 폰트, 장면/SFX, 모션, 장식, 자막, 대본, 음성, 브랜드의 실제 원장·생성물·소비 경로 조사
- 코드/DB/파일/서버/외부 공급처별 정본 표시
- 기존 ID → 공통 ID 매핑 초안 생성
- 파일 해시, 미리보기, 권리 증빙, 렌더 지원, 소유 범위 누락 목록 작성
- 폰트 수집 트랙의 gitignored 바이너리 영속 보관·백업·복원 계획 확정

### 산출물

- `inventory.json`
- `legacy-map.json`
- `source-of-truth.md`
- `rights-gap.csv`
- `compatibility-baseline.json`

### 완료 조건

- 대표 항목마다 실제 파일을 열고 실제 소비 경로까지 확인한다.
- 로컬과 서버 수치를 구분한다.
- 중복 레지스트리의 작성자와 우선순위가 명확하다.

## Phase 1 — 공통 코어와 읽기 전용 어댑터

### 파일 구조

```text
creative_library/
  schema.py
  catalog.py
  registry.py
  storage.py
  rights.py
  lifecycle.py
  compatibility.py
  resolver.py
  packs.py
  search.py
  usage.py
  schemas/
  adapters/
    legacy_fonts.py
    legacy_scene_assets.py
    legacy_motion_packs.py
    legacy_deco.py
    legacy_spines.py
    legacy_voices.py
```

### 작업

- 공통 ID·버전·상태·권리·출처·의존 관계 스키마
- content-addressed object store 인터페이스
- 연구 후보와 승인 릴리스 상태 분리
- legacy adapter 6종 이상
- metadata 검색과 constraint resolver
- `base_version + overrides + locks` 프로젝트 계약
- 결정 이유·탈락 이유 로그

### 완료 조건

- 기존 데이터 수정 없이 한 API에서 조회된다.
- 권한·승인·권리·파일 존재 조건을 우회하지 않는다.
- 기존 프로젝트의 legacy ID가 정상 해석된다.
- 같은 입력은 같은 resolved plan과 fingerprint를 만든다.

## Phase 2 — 품질 기준과 골든셋

### 작업

- 9:16 쇼츠 골든 영상/이미지/오디오 세트
- 짧은/긴 한글, 숫자·영문 혼합, 1~3줄 제목, 밝고 어두운 장면
- 폰트 fallback, 잘림, 외곽선 뭉침, 원본 글자·워터마크 잔여 검사
- 모션 속도 구분, 타점, 알파, 시간 길이 보존 검사
- 음성+BGM+SFX 실제 믹스의 loudness/peak/덕킹 검사
- 대본 사실 이탈 반례와 금지 주장 검사
- preview/export 이미지 및 시간축 비교

### 완료 조건

- 과거에 발생한 대표 사고를 의도적으로 재현했을 때 검사가 실패한다.
- 승인 샘플은 실제 모바일 크기로 사람이 확인한다.
- 자동 기준과 사람 평가가 모두 기록된다.

## Phase 3 — 회사 대표 스타터 팩

### 우선 채울 세트

- 한글 훅 타이포: 두껍고 눈에 띄며 투톤 포인트가 분명한 조합
- 본문 자막: 짧은/긴 문장과 영상 위/아래 안전영역 대응
- 레이아웃: 제품 시연, 문제→해결, 비교, 정보형
- 모션: 서로 동작이 명확히 다른 등장·강조·전환
- 효과음: 전환음 가족 3~5개, 임팩트 1~2개, 클릭/확인음과 반복 제한
- 대본: 문제→시연→차이, 발견→증거→결론 등 사실 비의존 구조
- 믹스: 음성 우선, BGM 덕킹, SFX 타점·피크 프로필

### 완료 조건

- 모든 항목에 실제 미리보기, 버전, 권리, 입력 조건, 금지 조건, 검수 결과가 있다.
- 같은 테스트 소재로 팩 간 비교가 가능하다.
- 폰트만 바꾼 조합이 아니라 타이포·레이아웃·모션·소리가 조화를 이룬다.

## Phase 4 — 장면꾸미기 UI와 자동 제작 연결

### 예상 연결점

```text
shopping_shorts/library_bridge.py
shopping_shorts/static/creative_library.html
shopping_shorts/static/creative_library.js
shopping_shorts/app.py
shopping_shorts/mix_pipeline.py
shopping_shorts/video_assemble.py
```

### 작업

- 목적별 팩 선택과 큰 실제 미리보기
- 글자/화면/움직임/소리/대본 구성 요소 교체
- 크기·위치·색·속도 미세 조절과 저장
- 수동 수정 잠금, 팩 교체 diff, 되돌리기
- 같은 `ResolvedCreativePlan`을 preview와 export에서 사용
- 실제 렌더 견본과 근사 미리보기 표시

### 완료 조건

- 선택→수정→저장→재열기→렌더까지 값이 유지된다.
- 사용자 잠금값을 자동 배치가 덮지 않는다.
- 원본 글자·로고·워터마크, 겹침, fallback이 없다.
- Playwright로 UI를 직접 조작하고 실제 결과물을 눈으로 확인한다.

## Phase 5 — 상시 수집·후보·승인 파이프라인

### 작업

- 기존 `effect_mining`을 공통 후보함에 연결
- 폰트·SFX·모션·이미지·레이아웃 공급처별 importer
- 중복 제거, 출처·권리 증빙, 파생본 생성
- 검수 큐, 담당자, SLA, 재시도, 격리, 철회
- 승인 시 immutable release manifest 발행
- 수집 워커의 렌더 자원·API 비용 한도

### 완료 조건

- 자동 수집 항목이 승인 없이 고객 제작에 노출되지 않는다.
- 원본 레퍼런스와 배포 가능한 재구성 에셋이 분리된다.
- 승인·중단·철회 상태가 모든 소비 경로에 즉시 반영된다.

## Phase 6 — 성과학습과 추천 개선

### 작업

- 결과물별 exact pack/recipe/asset version과 render fingerprint 기록
- 플랫폼·채널·기간·분모·표본 수·재생구간 연결
- 선택률, 교체율, 수동 수정량, 재생성 비용, QA 실패율 기록
- retention 구간과 타임라인 이벤트 연결
- 동시 A/B 또는 통제 가능한 실험만 인과 학습에 사용
- 탐색/활용과 다양성·반복 억제 정책

### 완료 조건

- 성과 수치에서 사용한 정확한 구성으로 역추적된다.
- 외부 인기작과 자사 결과, 관찰 데이터와 실험 데이터를 구분한다.
- 추천 변경은 오프라인 재생과 회귀 검사를 통과한 뒤 릴리스한다.

## Phase 7 — 회사 전체 확장

### 확장 대상

- 긴 영상, 썸네일, 카드뉴스, 블로그, 리포트, 프레젠테이션
- 채널별 브랜드 팩, 캠페인 팩, 고객 개인 팩
- 플랫폼 export profile과 현지화
- 공급자/모델 교체 가능한 생성 레시피
- 외부 편집 도구용 manifest/timeline exporter

### 완료 조건

- 공통 core를 공유하고 도메인별 중복 DB·UI를 만들지 않는다.
- 각 출력물에 권리·버전·재현성·품질 로그가 남는다.

## 우선순위

1. Phase 0 실사
2. Phase 1 공통 계약과 어댑터
3. Phase 2 골든셋과 실패 방지
4. Phase 3 대표 팩 1개
5. Phase 4 장면꾸미기 연결
6. Phase 5 수집 자동화
7. Phase 6 성과학습
8. Phase 7 확장

수집 자동화를 코어·권리·검수보다 먼저 만들지 않는다. 그렇지 않으면 찾기 어렵고 쓸 수 없는 파일만 빠르게 늘어난다.

## 병렬 작업 스트림

코어 계약이 확정된 뒤 다음은 병렬화할 수 있다.

- A: 자산 실사·권리·스토리지
- B: 폰트/타이포/자막 골든셋
- C: SFX/음악/믹싱 골든셋
- D: 모션/전환/레이아웃 골든셋
- E: 대본/훅/사실 분리와 반례
- F: UI 팩 브라우저와 수정 잠금
- G: 사용·성과·실험 데이터 계약

단, schema/version/status/rights/resolver와 `ResolvedCreativePlan` 계약은 한 곳에서 결정한다.

## 담당 검수 원칙

- 아스트라 트랙: 구조, 데이터 계약, UI/렌더 동등성, 자동검사, 성과학습
- 페이블 트랙: 유료썸네일급 큐레이션, 장르별 미적 기준, 실패패턴과 금지 조합
- 승인 시 두 트랙의 의견만 기록하지 말고 실제 렌더, 모바일 캡처, 오디오 믹스, 검사 로그를 증거로 첨부
- 사장님이 원본 흔적과 기본 품질 오류를 대신 전수조사하는 상태는 완료가 아님

## 릴리스·롤백

- 도메인마다 읽기 어댑터 → shadow resolve → 제한 계정 → 대표 팩 → 기본 경로 순으로 전환
- 새 writer를 열기 전 기존 writer를 닫을 계획을 확정
- 모든 프로젝트는 pack lockfile을 가져 롤백 시 정확한 이전 버전으로 복귀
- 철회된 자산은 신규 사용 차단, 기존 결과물 영향 목록과 대체 후보 제공
- 실패 시 legacy 경로로 되돌리되 새 프로젝트의 수정값과 로그는 보존
