# Creative Library OS 설계

- 작성일: 2026-09-11
- 상태: 구현 전 설계 확정안
- 범위: 회사의 조사·기획·대본·영상·그래픽·음향·배포·성과학습 전 공정
- 핵심 결정: 파일을 많이 모으는 저장소가 아니라, **검증된 재료·레시피·완성 팩을 같은 규칙으로 조합하고 결과를 다시 학습하는 제작 운영체계**를 만든다.

## 1. 왜 필요한가

현재 저장소에는 폰트, 장면 자산, 모션 팩, 효과 매칭, 자막 실측, 음성 프리셋, 대본 패턴, 브랜드 설정이 이미 존재한다. 그러나 정본과 형식이 나뉘어 있어 다음 문제가 반복된다.

- 미리보기와 실제 렌더 결과가 다르다.
- 연구용 레퍼런스의 글자·워터마크·사실이 결과물에 남는다.
- 폰트 파일 수는 많아져도 어떤 훅에 어떤 조합이 좋은지 알 수 없다.
- 효과음과 모션을 모아도 타점·속도·반복 제한이 없으면 품질이 낮다.
- 사용자가 고친 값을 다음 자동 배치가 덮어쓴다.
- 외부 인기 영상의 성과를 우리 효과의 성능처럼 오해할 수 있다.
- 라이선스 철회나 만료가 생겨도 어떤 결과물에 사용됐는지 역추적하기 어렵다.

따라서 회사 라이브러리는 검색 가능한 DAM, 실행 가능한 레시피 레지스트리, 품질 승인 시스템, 프로젝트 잠금파일, 성과 피드백을 함께 가져야 한다.

## 2. 이번 조사에서 직접 확인한 현재 기반

| 영역 | 현재 기반 | 확인된 빈틈 |
|---|---|---|
| 효과 채굴 | `shopping_shorts/effect_mining/`에 수집·분석·후보 파이프라인 존재 | 후보를 승인 레시피로 만드는 검수·배포 단계는 별도 필요 |
| 장면·SFX | `scene_assets`, `scene_match.py`, 장면 라이브러리 UI와 렌더 연결 존재 | 로컬 DB 자산은 0개이며 서버 현황과 구분 필요. 선택 정책도 실측 결론과 불일치 |
| 모션 | `motion_packs.py`, `motion_assets.py`, manifest와 알파 MOV 존재 | 완성 팩 2개, 실질 모션 2종 수준. 미리보기·렌더 능력 차이 명시 필요 |
| 데이터 효과 | Count/List/Impact/Callout 컴포넌트 존재 | 리스트 항목 추출 미완성으로 자동 발동 비활성 |
| 장면 틀 | `deco_frame.py`, `deco_templates.py`, `FULL_PRESETS`, `HC_PRESETS` | 여러 레지스트리와 생성 경로가 공존 |
| 자막 | 실측 JSON → 프리셋 생성 경로와 영상 합성 존재 | 글꼴 fallback, 긴 문장, 작은 화면, 렌더 동등성 자동 검사가 부족 |
| 폰트 | `fonts.json`, 정적 폰트 폴더, 별도 수집 트랙 존재 | 파일 보유와 실제 사용 권리·한글 범위·조합 품질·렌더 지원을 함께 판정해야 함 |
| 음성 | 보이스 프리셋·샘플·엔진 설정 존재 | 공개 프리셋과 계정/고객 전용 보이스 분리 필요 |
| 대본 | pattern/spine/style profile/사용 이력 기반 존재 | 표현 방식과 사실 자료가 섞였던 소재 이탈 사고 방지 계약 필요 |
| 브랜드 | production별 브랜드 JSON 존재 | 채널·캠페인·프로젝트 우선순위와 불변 스냅샷 필요 |
| 성과 | 외부 히트작 점수와 일부 사용 연결 존재 | 우리 결과물의 정확한 레시피 버전별 성과 학습이 없음 |

로컬 `reference.db` 읽기 전용 확인값은 `scene_assets=0`, `spine=0`, `pattern_item=37`, `pattern_source=13`, `script_usage=0`이다. 이는 서버 운영 DB 수치가 아니다.

## 3. 전체 라이브러리 지도

초기에 사용자가 언급한 폰트·효과음·장면효과·자막·대본은 전체의 일부다. 다음 18개 도메인을 공통 체계 안에서 다룬다.

1. 기획·전략: 대상 시청자, 문제, 목적, 소구점, 관점, 포맷, 브리프, 캠페인 규칙
2. 리서치·근거: 출처, 주장 카드, 제품 사실, 인용, 갱신일, 신뢰도, 사용 가능 범위
3. 훅·카피: 질문·역설·비교·발견·경고·고백형 훅, 제목, 서브카피, CTA
4. 대본·스토리: 비트 구조, 공개 순서, 감정 곡선, 호흡, 말투, 사실 슬롯, 금지 주장
5. 스토리보드·촬영: 샷 문법, 구도, 제품 시연 순서, 카메라 이동, 촬영 체크리스트
6. 영상·이미지 원재료: 자체 촬영, 정식 스톡, 제품 팩샷, 누끼, 배경, 텍스처, 3D
7. 폰트·타이포: 패밀리, 굵기, 한글 범위, 조합, 줄바꿈, 자간, 외곽선, 그림자, 강조
8. 브랜드·색상: 로고, 팔레트, 대비, LUT, 색보정, 채널 고유 시각·음향 성격
9. 레이아웃·그래픽: 프레임, 제목대, 정보 카드, 비교표, 배지, 화살표, 아이콘, 스티커
10. 모션·전환·VFX: 등장·퇴장·강조, 줌, 팬, 흔들림, 전환, 마스크, 입자, 속도 변화
11. 효과음·음악: 전환음, 임팩트, UI음, 환경음, 사운드 로고, BGM, 루프, 스템
12. 음성·믹싱: TTS/성우, 발음 사전, 쉼·감정·속도, 덕킹, 음량, 피크, 페이드
13. 자막·현지화: 분절, 단어 강조, 화자, 위치, 안전영역, 번역 톤, 숫자·단위 표기
14. 편집 리듬: 컷 밀도, 동작 홀드, J/L컷, 비트·단어 동기화, 반복 억제
15. 완성 제작 팩: 쇼핑·정보·리뷰·교육·브랜드·VSL·채널 시즌별 조합
16. 배포·포장: 썸네일, 커버, 제목·설명, 비율, 코덱, 안전영역, 자막 파일, 게시 메타
17. 검수·학습: 골든셋, 실패 사례, 회귀 테스트, 실험 가설, 선택·교체율, 성과
18. 제작 운영: 공급처, 생성 프롬프트, 모델·버전, 비용·시간 한도, 백업·복구·보존

폴더를 18개로 복제하지 않는다. 각 항목은 주 도메인 하나와 여러 제작 단계·목적·매체 태그를 가진다.

## 4. 핵심 데이터 모델

### 4.1 네 가지 객체

1. **Asset**: 폰트, WAV, MOV, PNG, SVG, LUT, 음성 샘플처럼 실제 파일이 있는 재료
2. **Recipe**: 입력을 결과로 바꾸는 실행 규칙. 훅 타이포, 자막, 전환, 믹싱, 대본 구조 등
3. **Pack**: 호환되는 에셋과 레시피를 정확한 버전으로 묶은 완성 조합
4. **Evidence**: 원본 레퍼런스, 분석 신호, 권리 증거, 검수, 실패, 사용·성과 기록

연구 원본과 고객에게 배포 가능한 에셋은 같은 상태값을 쓰지 않는다. 특히 `effect_mining`의 후보 승격은 연구 후보 생성이지 프로덕션 승인으로 해석하지 않는다.

### 4.2 공통 계약

```text
id, kind, domain, schema_version, version
name, description, tags, locale
owner_scope(company|tenant|project), owner_id, visibility
status, created_at, updated_at, supersedes
source_refs, rights_ref, review_refs
preview_refs, artifact_refs
input_schema, output_schema, parameters
capabilities, compatibility, dependencies(version pinned)
constraints, quality_profile_ref, legacy_refs
```

검색·권한·감사에 필요한 필드는 정규화한다. 도메인 고유 속성만 버전이 있는 JSON Schema 확장으로 둔다. 모든 것을 큰 JSON 한 칸에 넣지 않는다.

### 4.3 도메인별 필수 속성

- 폰트: family, weight, width, italic, variable axes, glyph coverage, renderer support, embedding rights
- SFX: duration, sample rate, channels, loudness, peak, attack, tail, semantic role, hit point, family
- 모션: target, in/out layers, timebase, duration range, speed range, displacement, alpha, handles, compositor
- 자막: segmentation, line limits, scale range, contrast, emphasis tokens, collision zones
- 대본: required fact slots, beat roles, reveal point, length range, prerequisites, forbidden claims
- 레이아웃: slots, anchors, safe area, min/max height, overflow policy, z-order
- 생성 레시피: provider, model version, seed, limits, validation, estimated cost; 비밀키는 저장 금지
- 성과: platform, channel, period, denominator, sample size, exact recipe/pack version, hypothesis

## 5. 수명주기와 승인 문

```text
수집 → 분석 → 연구 후보 → 제작 초안 → 기술 검수
   → 미적 검수/내용 검수/권리 검수 → 승인 → 불변 릴리스
   → 관찰/성과 대기 → 유지·교체·중단·격리
```

자동 수집은 자동 승인이 아니다. 각 단계에 다음 검사를 둔다.

| 게이트 | 자동 검사 | 사람 검수 |
|---|---|---|
| 수집 | 해시 중복, 파일 무결성, 메타 누락 | 출처 적절성 |
| 기술 | 디코딩, 길이, 알파, 글리프, 코덱, 렌더러 호환 | 실제 재생·렌더 확인 |
| 권리 | 라이선스 ID, 만료, 지역, 임베딩·재배포 조건 | 증빙과 프로젝트 사용 가능성 |
| 의미 | 태그, 입력 조건, 금지 조건, 사실 슬롯 | 맥락 적합성·표절/잔여물 |
| 미적 | 잘림, 대비, 안전영역, 음량·피크, 반복 밀도 | 유료 썸네일급 시각·청각 평가 |
| 통합 | 동일 테스트 소재로 preview/export 비교 | 실제 모바일 크기, 전체 영상 확인 |
| 성과 | 사용 버전, 노출·분모, 기간, 데이터 누락 | 인과로 볼 수 있는 실험인지 판정 |

승인 근거는 이름이나 담당자 동의가 아니라 렌더·오디오·검사 로그·권리 증빙과 연결한다.

## 6. 정본·저장·버전 경계

초기 구현은 저장소에 독립 패키지 `creative_library/`를 두되 새 DB를 도메인마다 만들지 않는다.

- `effect_mining`: 원본 수집·신호·연구 후보의 정본
- 기존 `reference.db`: 현재 고객 작업, scene assets, spine 등 운영 데이터의 정본
- `creative_library`: 공통 등록·버전·권리·검수·검색·팩 릴리스의 정본
- 프로젝트: 적용한 pack/recipe 버전과 사용자 override/lock의 정본
- Git: 스키마, 코드, 자체 레시피 소스, 검사 규칙, release manifest
- 영속 객체 저장소: 해시 기반 바이너리 원본과 파생본. 서버 코드 디스크와 분리

고객 프리셋은 복사본이 아니라 `base_version + overrides + locks`로 저장한다. 공용 팩이 갱신돼도 이미 만든 프로젝트는 자동으로 달라지지 않는다.

## 7. 추천과 조합 원칙

추천은 LLM의 자유 생성이 아니라 **제약 우선 필터 + 점수화 + resolver 검증**으로 한다.

1. 승인, 권리, 소유권, 파일 존재, 엔진, 언어, 비율, 안전영역을 hard gate로 거른다.
2. 목적, 장면 역할, 브랜드, 에너지, 입력 재료 적합성으로 점수화한다.
3. 동일 효과·소리 반복과 과도한 효과 밀도를 억제한다.
4. 사용자 수정·잠금 필드를 절대 덮어쓰지 않는다.
5. 후보가 없으면 미적용 이유와 수집/생성 필요를 명시한다.
6. 존재하지 않는 ID나 미지원 효과는 resolver에서 거절한다.

최종 산출물 `ResolvedCreativePlan`은 장면꾸미기 UI와 자동 제작 파이프라인이 함께 소비한다. preview와 export는 같은 레시피·파라미터·타임라인을 사용한다. 근사 미리보기만 가능한 경우 반드시 표시하고 실제 렌더 견본을 제공한다.

## 8. 눈에 잘 안 보이지만 반드시 갖출 기반

- **부정 지식 라이브러리**: 못 쓰는 조합, 실패한 프롬프트, 낮은 신뢰도 자동 배치, 폰트 fallback, 워터마크 잔여, 시간축 사고
- **골든 테스트 세트**: 짧고 긴 한글, 숫자·영문 혼합, 어두운/밝은 영상, 빠른 장면, 조용한/복잡한 음향
- **회귀 고정값**: 승인된 대표 프레임·오디오 파형·타임라인과 허용 오차
- **관측성**: 어떤 추천 규칙이 무엇을 골랐고 왜 탈락시켰는지 설명 로그
- **재현성**: 모델·프롬프트·시드·도구 버전·파일 해시·렌더 fingerprint
- **비용 정책**: 생성·렌더 시간, GPU/CPU, 외부 API 비용 상한과 캐시
- **격리**: 고객·회사·프로젝트·연구 원본의 권한과 저장 경계
- **철회 처리**: 라이선스 만료·문제 발견 시 신규 사용 차단과 기존 결과물 영향 조회
- **복구**: DB 백업만이 아니라 바이너리 객체·manifest·권리 증빙까지 복원 검증
- **호환성 표**: FFmpeg/Pillow/브라우저/Remotion/CapCut 등 실제 지원 능력과 근사 여부
- **운영 용량**: 중복 제거, 파생본 보존 기간, 미사용 후보 정리, 핫/콜드 스토리지
- **실험 통제**: 한 번에 여러 변수를 바꾼 순차 비교를 A/B 결과로 학습하지 않기

## 9. UI 구조

사용자는 18개 도메인을 직접 관리할 필요가 없다.

- 홈: 목적별 완성 팩과 실제 결과물 썸네일
- 상세: 글자 / 화면 / 움직임 / 소리 / 대본 다섯 그룹
- 비교: 같은 대본·같은 미디어로 A/B, 모바일 실제 크기
- 조정: 핵심 변수만 즉시 조정하고 고급 항목은 접기
- 잠금: 수동 수정 요소 표시, 팩 교체 시 변경 예정 항목 미리 알림
- 관리자: 연구 후보 / 검수 대기 / 승인 / 중단을 분리
- 자산 카드: 권리, 엔진, 언어, 미리보기, 적용 예, 파생본, 사용 이력

소리에는 파형·타점·믹스 미리듣기, 폰트에는 짧은/긴 한글과 숫자 견본, 모션에는 속도 차이가 실제로 보이는 반복 미리보기, 대본에는 필요한 사실 슬롯과 좋은/나쁜 예시가 있어야 한다.

## 10. 표준과 외부 조사에서 반영한 원칙

- Adobe AEM Assets의 버전·중복·권리·메타데이터 기반 권한 원칙을 자산 운영에 반영한다.
- W3C Design Tokens 형식을 참고해 색상·간격·타이포 토큰을 도구 간 이식 가능한 값으로 둔다.
- OpenTimelineIO처럼 clip/track/transition/marker/metadata를 분리해 시간 레시피 교환 규격을 만든다.
- SPDX 식별자와 별도 상업 사용 조건을 함께 보존한다. 라이선스 이름만으로 특정 파일의 사용 권리를 추정하지 않는다.
- C2PA의 provenance 개념을 참고해 원본, 가공 단계, 도구·모델, 결과물 연결을 남긴다.
- EBU R128의 loudness/true peak/loudness range 개념을 오디오 QA 프로필에 쓰되, 플랫폼별 목표값은 별도 프로필로 관리한다.
- YouTube Analytics의 retention 지표는 정확한 영상·기간·구간과 연결하고, 외부 조회수는 우리 레시피 인과 성능으로 취급하지 않는다.

## 11. 절대 하지 않을 것

- 수집한 파일을 한 폴더에 넣고 파일명만으로 운영하지 않는다.
- 연구 레퍼런스 원본을 고객 팩에 포함하지 않는다.
- 도메인별 새 DB와 관리자 UI를 무작정 복제하지 않는다.
- 미리보기 전용 CSS와 실제 렌더 코드를 별도 판단원으로 두지 않는다.
- 승인 전 후보를 자동 제작에 노출하지 않는다.
- 프리셋 업데이트로 기존 프로젝트 결과를 조용히 변경하지 않는다.
- 권리 증빙 없는 무료/개인 배포 파일을 회사 공용으로 승인하지 않는다.
- 자동 추천 실패 시 임의의 fallback으로 영상을 오염시키지 않는다.

## 12. 완료 정의

회사의 라이브러리 기반이 만들어졌다고 부를 수 있는 최소 조건은 다음과 같다.

1. 기존 6개 이상 도메인이 한 API에서 검색되며 원래 정본은 유지된다.
2. 대표 완성 팩 1개가 기획→대본→장면→타이포→모션→음향→자막→렌더까지 재현된다.
3. 적용 버전·사용 파일·권리·사용자 수정·렌더 fingerprint를 역추적할 수 있다.
4. 동일 소재의 미리보기와 실제 렌더가 허용 오차 안에서 일치한다.
5. 워터마크·원본 글자·사실 이탈·폰트 fallback·음량·안전영역 회귀를 골든셋에서 잡는다.
6. 승인되지 않았거나 권리가 만료된 항목은 신규 추천과 렌더가 차단된다.
7. 결과 성과가 정확한 pack/recipe 버전으로 돌아와 추천 개선에 쓰인다.

## 13. 유료 썸네일급 품질 판정표

기술적으로 렌더됐다는 이유만으로 승인하지 않는다. 대표 팩과 장면 템플릿은 아래 항목을 각각 기록한다.

| 항목 | 승인 질문 | 즉시 탈락 사례 |
|---|---|---|
| 타이포 위계 | 1초 안에 핵심 단어가 먼저 읽히는가 | 모든 줄 굵기·크기·색이 같음 |
| 글자 형태 | 한글 획과 카운터가 뭉개지지 않는가 | 과도한 외곽선, 가짜 굵기, 가로 찌그러짐 |
| 포인트 | 강조색이 의미 있는 단어에만 쓰였는가 | 무작위 투톤, 낮은 대비, 색 과다 |
| 레이아웃 | 제목·본문·미디어·자막 자리가 명확한가 | 텍스트 겹침, 얼굴/제품 가림, 빈 공간 낭비 |
| 원본 독립성 | 남의 채널 흔적 없이 자체 결과물처럼 보이는가 | 채널명, 워터마크, 원본 자막·앱바 잔여 |
| 모션 구분 | 효과 이름마다 실루엣·속도곡선·타점이 다른가 | 줌펀치와 팝업이 사실상 같은 동작 |
| 음향 결합 | 모션 타점과 SFX가 맞고 음성을 방해하지 않는가 | 반복음, 늦은 타점, 피크, BGM 마스킹 |
| 일관성 | 폰트·색·모션·소리가 한 장르로 느껴지는가 | 좋은 재료를 무작위로 섞은 인상 |
| 수정성 | 핵심 조정이 쉽고 수동값이 보존되는가 | 재선택 때 위치·색·크기 초기화 |
| 실제 결과 | 작은 모바일 화면과 최종 렌더에서도 같은가 | 큰 편집 화면에서만 읽히거나 preview만 정상 |

템플릿 메타에는 최소한 `caption_slot`, `title_slots`, `forbidden_zones`, `face_risk`, `source_text_risk`, `watermark_risk`, `cleanup_required`를 둔다. `source_text_risk` 또는 `watermark_risk`가 해소되지 않은 후보는 승인할 수 없다.

## 14. 책임 분리

- 아키텍처·자동화 책임: 스키마, DB, 스토리지, UI, 렌더, 자동검사, 관측성, 성과학습
- 크리에이티브 책임: 타이포·색·구도·모션·음향의 완성도, 장르 적합성, 좋은/나쁜 예시, 승인 기준
- 권리 책임: 라이선스 증빙, 고객 사용·임베딩·수정·재배포 범위, 만료·철회
- 편집 책임: 실제 모바일 시청, 메시지 전달력, 과효과·반복, 대본 사실성

한 사람이 체크박스를 모두 통과시키는 방식보다 자동 검사 증거와 각 책임자의 판단을 합쳐 승인한다.

## 참고한 공식 자료

- Adobe Experience Manager Assets: https://business.adobe.com/products/experience-manager/assets/asset-management.html
- Adobe metadata-driven permissions: https://experienceleague.adobe.com/en/docs/experience-manager-learn/assets/governance/metadata-driven-permissions
- W3C Design Tokens: https://www.w3.org/community/reports/design-tokens/CG-FINAL-format-20251028/
- OpenTimelineIO: https://opentimelineio.readthedocs.io/en/latest/index.html
- SPDX License List: https://spdx.org/licenses/
- C2PA principles: https://spec.c2pa.org/principles/
- EBU R128: https://tech.ebu.ch/publications/r128
- YouTube Analytics metrics: https://developers.google.com/youtube/analytics/metrics
- Motion Array catalog/license: https://motionarray.com/ , https://motionarray.com/license/
- CapCut templates/effects: https://www.capcut.com/resource/capcut-template-videos , https://www.capcut.com/tools/video-effect-and-filter
