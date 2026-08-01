# 태깅QA게이트 — handoff

## 왜 하는 일인가

`script_extract`는 Gemini가 준 태깅을 **스키마만 통과하면 무조건 채택**했다. 프롬프트엔
실사고로 쌓인 지침이 많은데(0초 훅 강제·받아쓰기·오인 금지·change/is_key/shot_role)
그게 지켜졌는지 확인하는 코드가 한 줄도 없었다. 슬롯 기반 화면조합(대본퀄v3)이 이 태깅
위에 전부 서 있으므로, 여기가 틀리면 위층이 아무리 정교해도 결과물이 나쁘다.

설계 전문(3층 구조): `scratchpad/태깅QA게이트_솔루션설계_2026-08-01.md`
※ scratchpad는 세션 임시폴더다 — 내용이 필요하면 아래 요약으로 충분하다.

---

## ✅ 완료 (2026-08-01, 커밋 `5c9f33986`, 집PC) — Layer 1

- **`shopping_shorts/tag_qa.py` 신설** — `validate_extract(result, duration) -> (score, flags)`
  - 7개 검사: ①훅 0초 ②커버리지(75%/꼬리85%) ③시간정합(역전·겹침·범위) ④받아쓰기
    ⑤full_text 일치 ⑥shot_role/change/is_key 분포붕괴 ⑦scene_desc 복붙·부실
  - 가중 감점(합 1.0), flags는 한국어 한 줄 — 그대로 재시도 프롬프트에 실린다
  - 무자막 영상 면제: text가 다 비어도 `product_benefits`가 있으면 ④ 감점 안 함
  - 순수 계산(모델 호출 0, 비용 0원)
- **`script_extract.py` 배선**
  - `_video_duration`: 프레임수÷fps (★`format=duration`은 오디오 꼬리가 붙어 커버리지가
    부당하게 낮게 나온다 — scene_cut 주석의 실측 근거). 실패 시 None → 길이검사만 스킵
  - `_qa_retry_decision`: 점수 <0.6이면 flags를 프롬프트에 얹어 **딱 1회** 재호출
  - `_pick_better_extract`: 재시도분이 더 나쁘면 첫 결과로 되돌림(재시도가 품질을 깎지 않게)
  - `_attach_qa`: 결과에 `tag_qa{score,flags,retried}` 기록. **결과 자체는 절대 안 바꿈**
  - 재시도 중 API가 죽거나 루프가 소진돼도 첫 결과를 살려 반환 (fail-open 관철)
- 테스트 19개 신규 전부 green (`test_tag_qa.py` 10 + `test_tag_qa_wiring.py` 9)
  - 배선 테스트는 Gemini를 안 부른다 — 판단 로직을 순수 함수로 분리해 그것만 검증

**검증 실측**: 기존 스위트 3064 passed / 14 failed → **기준선(내 변경 전)도 동일하게
실패** 확인 완료(`git stash` 대조, 같은 8건 + numpy 파일). **새 실패 0건.**
⚠️ `test_sub_region.py`는 numpy 미설치로 수집 자체가 안 된다(집PC 환경 이슈, 기존 문제).

---

## ⏭ 다음 (회사에서 이어서)

### 1. Layer 3 — `tools/tag_audit.py` (권장 우선)
DB 소스 N개(기본 20) 샘플 → 저장된 세그에 `validate_extract` 돌려서 **score 분포 ·
최빈 flags · 최악 5건 video_id**를 표로 출력. 코드는 이미 다 있으니 조회+집계만 붙이면 된다.

**왜 먼저인가**: 대본퀄v3의 Task 7(실측 job 생성 검증) **전에** 한 번 돌려두면, 실측
결과가 나빴을 때 "슬롯 문제인가 태깅 문제인가"를 가르는 기준선이 된다. 지금은 태깅층이
좋은지 나쁜지 **아무도 숫자로 모른다**.
⚠️ 집PC 트랙 폴더는 DB가 비어 있다(gitignore) — 회사 PC나 서버 DB로 돌려야 의미 있다.

### 2. Layer 2 — 프레임 대조 스팟체크 (플래그, 기본 OFF)
`scene_desc`가 실제 화면과 맞는지는 텍스트 검증으론 불가능하다(눈이 필요).
- 세그 3개 샘플(첫 세그=훅 + is_key 1 + 완성/after 1) → 각 중간시각 프레임 1장 ffmpeg 추출
- lite 모델 **1회 호출**로 "이 이미지가 이 묘사와 맞나?" verdict(맞음/부분/틀림)
- 정확도 평균을 `tag_qa.frame_score`로 **기록만** (재추출 트리거는 실측 후 결정)
- 설정키 `tag_qa_frames_enabled`(기본 0), `_frame_flag_on()`과 같은 패턴

### 3. 관측성 (작음)
- job 로그에 `tag_qa: 0.82 (flags: 커버리지 68%)` 한 줄 — "이상한 영상" 원인 추적용
- 결과 dict가 통째로 JSON 저장되는 경로면 `tag_qa`가 공짜로 따라간다. **먼저 확인하고**
  안 되면 그때만 컬럼 추가(`clean_regions_json` 추가 때와 같은 패턴)

### 4. 아직 finish 안 함
Layer 1만으로도 배포 가치는 있으나(회귀 0, fail-open), Layer 3까지 묶어 한 번에
`py tools/track.py finish 태깅QA게이트` 하는 편이 깔끔하다. 급하면 지금 finish해도 안전.

---

## 스코프 밖 (건드리지 마라)

- `mix_pipeline.py`가 `extract_auto`를 우회해 `extract_script`를 직접 부르는 기존 불일치
  (B1 프레임추출 플래그가 믹스 경로엔 적용 안 됨). **인지만 하고 이번엔 안 고친다** —
  QA 배선을 `extract_script` 안에 뒀으므로 이 우회 경로도 QA는 자동으로 받는다.
- 검증 실패를 이유로 추출 결과를 버리는 코드 — fail-open 원칙 위반.

## 관련

- 대본퀄v3 코드리뷰(F1~F6): `scratchpad/대본퀄v3_코드리뷰_2026-08-01.md`
  — 그 트랙의 F1(문장 그룹핑 순서)·F2(target_seconds 무시)가 태깅QA보다 우선순위 높다
