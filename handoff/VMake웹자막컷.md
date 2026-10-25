# VMake웹자막컷 — 핸드오프 (관제 270)

소유 트랙: VMake웹자막컷 — 이 파일은 이 트랙 세션만 수정한다.

## 2026-10-26 (PC: CH) — 웹 라인 VMake 규칙 "장면 편집 뒤 자막 있는 컷만"

### 사장님 지시
"VMake 를 쓰는 규칙은 어떤 영상이든 동일하다. 장면 편집 후 자막 있는 컷만." 웹 라인도 라이브까지. 다른 트랙도 실수 없게 CLAUDE.md 에 강하게.
칼카피·회원 MCP 쪽은 track/칼카피숏템엔진 7840b6288(tools/calcopy/vmake_clean.py)이 이미 처리.

### 실측(착수 전, 서버)
- 서버 env: SHORTS_CLEAN_FINAL=1 · SHORTS_CLEAN_SPAN=1 → 라이브 기본 경로는 완성본(확정 컷) 청소.
- 최근 14일 워커 로그 VMake 전송 495건: 골라 지우기 partial_in 282건(합 3,679초) · 완성본 mix_raw 187건(합 5,308초) · 증분 join_all 26건(66초).
  **원본 소스 통째 전송은 14일간 0건** — 소스별 경로는 옛 job(clean_sources 있음)에서만 열리는 잠복 경로였다.
- 청소본 357개: 파일 길이 − 컷 지도 합 ≤ 0.02초(허용 0.5초 근거). 증분 합본 21개: 길이 − (조각 합 + 조각당 1프레임) ≤ +0.028초.
- ★웹 라인·서버엔 **컷별 박힌 글자 자동 판정기가 없다**(grep 확인, 서버 cv2·onnxruntime 미설치, 칼카피 판정기 channelkit.vision 은 main 에 없음).
  웹 라인의 컷별 판정은 고객 '장면 고르기'(clean_cuts) 뿐 → 판정 없으면 확정 컷 전부(=완성본 길이)를 보낸다. 자막 없는 컷도 간다.

### 한 것
- 주인 `mix_pipeline.vmake_send_cuts(컷 지도, 선택)` + `vmake_allow_sec` + `vmake_sent_check`(검사 주인) + 보내기 직전 관문 `_vmake_gate`
  (`_vmake_clean(send={kind, allow, work})` — send 없으면/길이 넘치면/못 재면 업체 0 + ops_alert `vmake_send_gate`).
- 호출부: 완성본(allow = 컷 합) · 골라 지우기·덧지우기(allow = 고른 컷 합 + 구간당 1프레임) · 증분(allow = 조각 구간 합 + 조각당 1/30초).
  소스별 `_clean_one`·소스 합본은 send 없음 → 관문이 거절(원본 통째 길 폐쇄).
- `_clean_strategy`: 소스별 청소본이 지금 편성이 쓰는 소스를 **전부** 덮을 때만 "sources"(재사용, 업체 0), 아니면 "final". `SHORTS_CLEAN_FINAL` 스위치 폐지.
  `_ensure_clean_sources` 는 새로 지울 소스가 있으면 관문으로 멈춤(과금 전).
- 장부: job 폴더 `vmake_sent.json`(at·kind·file·sec·allow·tier). 검사 도구 `shopping_shorts/scripts/vmake_sent_check.py --root|--work`.
- 시험 `tests/test_vmake_send_rule.py` 5개 — ★옛 코드에서 첫 시험이 빨강(원본 20.0초 > 쓰는 2.0초) 확인 후 고침. 관련 706 green.
  옛 소스별 경로 시험 4개 삭제, 스위치 시험 3개는 '스위치로 안 열린다'로 바꿈, 다른 판단 시험 파일 7개는 관문 끔 fixture.
- CLAUDE.md 0순위-D(VMake)·0순위-E(진행 표시) · 관제/ownership.json 판단 등록 · wiki/rules/판단소유권.md 재생성.

### ⏭ 다음
- [ ] 컷별 박힌 글자 자동 판정을 웹 라인에 넣을지 — 사장님 결정 필요(서버에 opencv·onnxruntime·PP-OCR 모델 설치 + 칼카피 channelkit.vision 이 main 에 들어온 뒤 vmake_send_cuts 에만 교차).
  지금은 자막 없는 컷도 고객이 안 빼면 간다(라이브 실측: 39279d1d1438 19컷 중 눈으로 자막 있는 컷 7개).
