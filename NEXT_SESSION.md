# NEXT_SESSION — VMake 자막제거 실스펙 채우기 (내일 회사서)

**날짜**: 2026-07-13 (집 PC) → 내일 회사서 VMake API 키/문서 확보 후 이어서

## ✅ 오늘 완료 — VMake 자막제거 연동 뼈대 (전부 커밋됨, push는 아직)

믹스된 최종 영상의 원본 하드섭을 VMake API로 제거하고 우리 자막을 굽는 기능.
흐름: **믹스(자막X) → VMake제거 → 우리자막**. 옵션 토글, 개인키 대시보드 저장.
설계: `docs/superpowers/specs/2026-07-13-쇼핑쇼츠-VMake자막제거-design.md`
계획: `docs/superpowers/plans/2026-07-13-VMake자막제거.md`

| 커밋 | 내용 |
|------|------|
| 86f770c5 | store: mix_jobs에 subtitle_removal/clean_video_path 필드+마이그레이션 |
| (4c40774e) | store: settings 테이블 + get/set_setting (키 저장) |
| 0fed5ff3 | vmake_client 서명 인증(추정 스펙) |
| 15c2c4c2 | vmake remove_subtitles 제출→폴링→다운로드(mock) |
| b983b360 | assemble → _render_mix + _burn_captions 분리 (+clean_fn 훅) |
| e8f53891 | run_render에 VMake 자막제거 단계+removing_subtitles 상태 |
| fb4f91f1 | 개인키 저장/조회 API + mix start subtitle_removal 플래그 |
| 47e0cc7e | 믹스 UI(mix.html)에 자막제거 토글+개인키 입력 |

**전체 테스트 241 passed**(신규 31). 실제 렌더 스모크로 assemble 분리 눈검증 완료.

## ⚡ 내일 바로 할 일: VMake 실제 API 스펙 채우기

`shopping_shorts/vmake_client.py`가 **모든 불확실 스펙을 격리**하고 있다. 지금은 조사 기반
**추정값**이고 mock 테스트로만 검증됨. 개발자 문서(open.vmake.ai, 로그인 뒤)를 보고 아래만 교체:

1. `_API_BASE` — 실제 베이스 URL (지금 `https://open.vmake.ai/api/v1` 추정)
2. `_sign()` — 실제 서명 알고리즘 (지금 HMAC-SHA256(secret, app_key+ts+nonce) 가정)
3. `_auth_headers()` — 실제 헤더 이름 (지금 X-App-Key/X-Sign/X-Timestamp/X-Nonce 가정)
4. `_submit()` — 자막제거 엔드포인트 경로·업로드 필드명 (지금 POST /video/remove-subtitles, files={file})
5. `_poll()` — job 조회 경로·상태 필드값·결과 URL 필드 (지금 GET /video/jobs/{id}, status/result_url)
6. 키 형식: 대시보드는 `app_key:secret` 형태로 저장 가정(`_split_key`). VMake 실제 발급 형태에 맞춰라.

교체 후:
- `python -m pytest shopping_shorts/tests/test_vmake_client.py -q` 통과 유지(mock이라 스펙 바뀌어도 통과 — 실제 검증은 아래)
- **실제 키 등록 → 진짜 소스로 1회 렌더** → 자막제거+우리자막 프레임 눈검증(로컬 ffmpeg 있음)
- 서버 배포 후 라이브 1건

### ⚠️ 최종 코드리뷰가 짚은 "옵션 ON 첫 실전 최우선 확인 2가지" (필수)
VMake 반환 영상의 아래를 반드시 확인하고, 미보존이면 `_burn_captions`(video_assemble.py) 보강:
1. **오디오 보존?** — 지금 `_burn_captions`가 `-c:a copy`로 in_video(=VMake출력) 오디오를 복사한다.
   VMake가 오디오를 빼거나 재인코딩하면 **TTS 나레이션이 무음**이 된다. 미보존이면 VMake출력
   오디오를 copy하지 말고 **원본 TTS 트랙을 재매핑**하도록 고쳐야 함.
2. **길이·fps 보존?** — 자막 타이밍(t0)은 TTS 길이 누적 기준. VMake가 길이/fps를 바꾸면 자막이
   밀린다(오디오 보존되면 나레이션과는 계속 맞아 체감은 작음). 길이 유지 여부 확인.
(그 외 사소: `_download`를 requests로 통일하면 결과 URL 인증/에러본문도 잡힘.)

## 사용자가 줄 것
VMake 결제 후 개발자 포털에서 발급한 **API 키** + 개발자 문서(엔드포인트/서명 스펙).

## ⚠️ 주의
- 브랜치 main 고정. `git add`는 shopping_shorts 파일만(-A 금지).
- 코드 커밋들은 이미 origin/main 반영됨(서버 자동배포 감지 가능). 핸드오프 문서만 push 남음.
- store.py에 다른 세션의 "S급 대본 위키(script_wiki)" 미커밋 변경 있음 — 내 것 아니니 건드리지 말 것.
- 자막 분할 로직은 계속 튜닝 대상: [[project_자막분할_원리]]
