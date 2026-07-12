# 쇼핑쇼츠 — VMake 자막 제거 연동 설계

**날짜**: 2026-07-13
**대상**: `shopping_shorts/` 믹스 파이프라인 + 대시보드
**전제**: 사용자가 VMake(vmake.ai) 결제 후 개인 API 키를 발급받아 대시보드에 등록. 연동 코드는 우리가 구현.

## 배경 / 문제

믹스 소스(틱톡·인스타 등 크롤 영상)에는 원본 자막이 화면 중앙~중상단에 **박혀(하드섭)** 있고,
여러 소스를 믹스하면 자막 위치가 클립마다 제각각(가변)이라 고정 박스로 덮을 수 없다.
→ 진짜 "지우기"(AI 인페인팅)가 필요. 사용자가 검증한 방식 = **VMake API 자막 제거**.

경쟁 프로그램("쇼핑팩토리")은 `믹스 먼저 → 자막제거 → 대본 새 창작` 순서지만,
**우리는 다르다**: 레퍼런스 대본을 **각색**해 장면에 싱크 맞춘 뒤 믹스한다.

## 흐름 (충돌 없음 — 자막제거를 맨 뒤에)

```
다운로드 → 추출 → EDL(대본각색+싱크) → TTS → [사용자 확인] → 렌더 →
  ① 믹스: 영상+TTS만 합침 (우리 자막 안 굽음)
  ② [옵션 ON] VMake 자막제거 (백그라운드 job + 폴링, 5~15분)
  ③ 우리 자막 굽기 (하단 바 / 추후 중앙)
→ done
```

VMake 옵션 **OFF면 ②를 건너뛰어** 기존과 사실상 동일(`① → ③`).
자막제거는 반드시 **우리 자막을 굽기 전**의 깨끗한 믹스에 돌린다(안 그러면 우리 자막까지 지워짐).

## 컴포넌트 (독립·테스트 가능)

| 컴포넌트 | 역할 | 인터페이스 |
|---|---|---|
| `vmake_client.py` (신규) | VMake API 어댑터 — 업로드→job제출→폴링→결과 다운로드. 서명 인증(X-App-Key/Sign/Timestamp/Nonce) 캡슐화 | `remove_subtitles(video_path, api_key) -> clean_path` |
| `video_assemble.py` (수정) | `assemble`을 3개로 분리 | `_render_mix(plan, tts, sources) -> mix_raw.mp4`(자막X) / `_burn_captions(video, plan) -> final.mp4` / `assemble()`은 둘 조립 + VMake 훅 지점 |
| `mix_pipeline.py` (수정) | `run_render`에 자막제거 단계 삽입 + 상태 `removing_subtitles` | — |
| `store.py` (수정) | mix_job에 `subtitle_removal`(bool)·`clean_video_path`(str). `vmake_key`는 전역 settings | — |
| `app.py` (수정) | `/api/settings/vmake_key`(저장), mix start에 `subtitle_removal` 플래그 | — |
| 대시보드 UI (수정) | 개인키 입력란 + "자막 제거" 토글(스크린샷의 VMake/블러/인페인팅 카드) | — |

**핵심 격리**: `vmake_client.py`가 VMake API의 불확실한 부분(정확한 엔드포인트·job 폴링 스펙)을
한 파일에 가둔다. 나머지 코드는 "영상 경로 → 자막 지운 영상 경로" 인터페이스만 본다.
실제 API 스펙 확정 시 이 파일만 교체.

## 상태 & 데이터

**상태머신 (+1)**:
```
rendering → removing_subtitles → done      (VMake ON)
rendering → done                           (VMake OFF)
어느 단계든 예외 → failed + error(원인 문자열)
```

**mix_job 신규 필드**: `subtitle_removal`(bool, start 시 저장), `clean_video_path`(str, VMake 결과).
`vmake_key`는 job이 아니라 **전역 설정**(계정당 1개). store에 전용 settings 테이블이 없으므로
간단한 `settings(key TEXT PRIMARY KEY, value TEXT)` 테이블을 신설하고 `get_setting/set_setting`
헬퍼로 저장(`vmake_api_key` 키). 키는 평문 대신 최소한 로그·응답에 노출하지 않도록 주의.

**렌더 데이터 흐름**:
```
_render_mix → mix_raw.mp4 (영상+TTS, 자막 없음)
   [ON]  → vmake_client.remove_subtitles(mix_raw, key) → clean.mp4 (폴링)
         → _burn_captions(clean, plan) → final.mp4
   [OFF] → _burn_captions(mix_raw, plan) → final.mp4
```

## 에러 처리 (exit255 교훈 반영)

| 실패 지점 | 처리 |
|---|---|
| VMake 키 없음/무효 | job `failed` + "vmake 키 등록 필요". (사용자가 옵션 켰으므로 렌더 진행 안 함) |
| VMake 처리 실패/타임아웃 | 폴링 최대 대기(기본 20분) 초과 시 `failed`. **API 응답 본문을 error 필드에 저장** |
| 결과 손상 | `_probe_duration`으로 검증 |
| 배포 재시작 중 job 죽음 | 백그라운드 job으로 격리. VMake는 원격 처리라 우리는 폴링만 → 서버 재시작 영향 적음 |

**원칙**: 모든 subprocess/API 호출의 stderr·응답 본문을 로그+error에 남긴다(지난 exit255 때
stderr를 삼켜 원인 못 본 실수 반복 금지).

## VMake API 스펙 미확정 대응

정확한 엔드포인트·폴링 스펙이 로그인 뒤 문서라 불확실 → **인터페이스 우선**으로 구현:
- `remove_subtitles(video_path, api_key) -> clean_path` 시그니처 고정
- 내부는 조사로 확인된 **추정 스펙**으로 1차 구현:
  - REST `POST https://open.vmake.ai/api/v1/video/...`(자막제거 엔드포인트명 미확정)
  - 서명 헤더 4종: `X-App-Key`, `X-Sign`, `X-Timestamp`, `X-Nonce`
  - 업로드 → job id → polling(비동기) 패턴 가정
- **테스트는 API를 mock** — 실제 키 없이 파이프라인 로직 검증
- 사용자가 개발자 문서를 주면 엔드포인트·서명·폴링만 실제값으로 교체

## 테스트

- `vmake_client`: 서명 생성 단위테스트, 폴링(mock pending→done), 실패 응답 처리
- `mix_pipeline`: 자막제거 ON/OFF 분기, 상태 전이, 실패 시 error 저장(VMake mock)
- `video_assemble`: `_render_mix`(자막 없음)·`_burn_captions` 분리 동작
- 통합: 옵션 OFF면 기존과 동일 결과

## 범위 밖 (YAGNI)

- 블러·인페인팅 방식(스크린샷의 다른 두 카드) — 이번엔 VMake만. 추후 같은 인터페이스로 추가 가능.
- 우리 자막 중앙 배치 — 별도 작업(현재 하단 바 유지). 자막제거로 중앙이 깨끗해지면 그때.
- 소스별 개별 자막제거 — 맨 끝 1회 제거로 충분(크레딧 절약).
