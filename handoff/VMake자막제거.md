> **소유 트랙**: VMake자막제거 — 이 파일은 VMake자막제거 트랙 세션만 수정한다. 다른 트랙은 읽기만.
> 원본: NEXT_SESSION.md에서 2026-07-15 분리. 규칙: `handoff/README.md`

## 🅑 VMake 자막제거 실스펙 채우기 (다른 트랙 — 내일 회사서)

**날짜**: 2026-07-13 (집 PC) → 내일 회사서 VMake API 키/문서 확보 후 이어서

### ✅ 완료 — VMake 자막제거 연동 뼈대 (전부 커밋됨)
믹스된 최종 영상의 원본 하드섭을 VMake API로 제거하고 우리 자막을 굽는 기능.
흐름: **믹스(자막X) → VMake제거 → 우리자막**. 옵션 토글, 개인키 대시보드 저장.
설계: `docs/superpowers/specs/2026-07-13-쇼핑쇼츠-VMake자막제거-design.md` / 계획: `docs/superpowers/plans/2026-07-13-VMake자막제거.md`

### ⚡ 내일 바로: VMake 실제 API 스펙 채우기
`shopping_shorts/vmake_client.py`가 **모든 불확실 스펙을 격리**. 지금은 추정값+mock. open.vmake.ai(로그인) 문서 보고 교체:
1. `_API_BASE`(추정 `https://open.vmake.ai/api/v1`) 2. `_sign()` 서명 알고리즘 3. `_auth_headers()` 헤더명 4. `_submit()` 엔드포인트·업로드 필드 5. `_poll()` job 조회·상태·결과URL 필드 6. 키 형식(`app_key:secret` 가정, `_split_key`).
교체 후: mock 테스트 유지 + **실제 키 등록 → 진짜 소스 1회 렌더** → 자막제거+우리자막 프레임 눈검증(로컬 ffmpeg) → 서버 라이브 1건.

### ⚠️ 최종 코드리뷰가 짚은 "옵션 ON 첫 실전 필수 확인 2가지"
VMake 반환 영상에서 반드시 확인, 미보존이면 `_burn_captions`(video_assemble.py) 보강:
1. **오디오 보존?** — 지금 `-c:a copy`로 VMake출력 오디오 복사. VMake가 오디오 빼거나 재인코딩하면 **TTS 나레이션 무음**. 미보존이면 원본 TTS 트랙 재매핑.
2. **길이·fps 보존?** — 자막 타이밍(t0)은 TTS 길이 누적 기준. VMake가 길이/fps 바꾸면 자막 밀림.
(사소: `_download`를 requests로 통일하면 결과 URL 인증/에러본문도 잡힘.)

**사용자가 줄 것**: VMake 결제 후 API 키 + 개발자 문서(엔드포인트/서명 스펙).
