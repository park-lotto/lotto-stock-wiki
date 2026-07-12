# NEXT_SESSION — 이어서 할 일 (2트랙 병행)

> ⚠️ 두 작업 트랙이 병행 중. 각자 자기 트랙만 이어서. main 고정, `git add`는 자기 파일만(-A 금지).

---

## 🅐 쇼핑쇼츠 "대본 위키(도서관)" — 2026-07-13 (집 PC) 대량 진척

라이브: **https://shoppingshorts.duckdns.org** (서버 `ubuntu@3.39.179.148`, systemd `shopping-shorts`)
전부 커밋·푸시·배포 완료. 최신 **HEAD 4fc04971** (서버 동일). 로컬 SSH키: `C:\Users\CH\Desktop\LightsailDefaultKey-ap-northeast-2.pem`

### ✅ 오늘 완료
1. **레퍼런스 랭킹 개선** — 카드 채널명 옆 🔗 링크복사 / 썸네일 클릭 인라인 재생(`/api/video` 프록시, 인스타 핫링크 우회).
2. **카테고리 2단 구조**(유형=비법형/제품형/혼합형 → 세부주제) + **AI 캡션 분류**
   - `categorize.py`: 캡션 우선 점수제(채널명 태그도배 오분류 해결) + 채널명은 강한 장르어만.
   - `ai_categorize.py`: 수집 시 Gemini가 캡션 의미로 재분류(주), 키워드는 폴백. `service.collect`에 통합.
3. **대본추출** — 카드 📝 → download_video + `script_extract`(Gemini) → 세그먼트+전체대본 모달. 캐시 `script_extracts`. 0초 훅 누락 프롬프트로 해결. 모달은 이동식(드래그)·논블로킹.
4. **대본 위키(도서관)** — 핵심 신규:
   - store: `script_wiki` 테이블. app: `/api/wiki/save·list·remove·video·generate`.
   - `structure_analyze.py`: 대본→구조(훅유형·hook_line·**화자**·**주변인물**·스토리라인·**전개방식**·**발상전환**·**어필포인트**·**tone(말투·어미)**·비트·설득장치·왜).
   - `library.html`: 원본영상 **인라인 재생**(영구보관 `data/wiki_media`, `/api/wiki/video` Range지원) + 강화 구조분석 나란히.
   - **생성(적용) Phase A** — `script_generate.py`: 요소별 **유지/변형 토글** + 모드 **A(같은주제 변주)/B(내주제 이식)** → 20초 초안 N개. 도서관 카드 🎬 "이 구조로 생성" 모달.
   - 스모크 검증: "주변인물만 변형" → **농원 언니 / 김밥집 이모님** 등 자연스러운 초안 생성 확인. (사용자 핵심 요구 = 주변인물 자연스러운 스토리텔링 재현 OK)

### ⏭ 내일 이어서 (우선순위)
1. **모드 B(내 제품 이식) 실사용 테스트** — 제품 하나 넣어 품질 확인, 생성 프롬프트 튜닝.
2. **믹스(Feature B)** — 도서관 카드 체크박스 → 2~3개 S급 선택 → 강점 조합(훅=A·전개=B·주변인물=C) → 생성. (`/api/wiki/mix` + `script_generate.generate_mix`)
3. **스타일 라이브러리** — 뽑아둔 `tone`(말투·어미)들을 모아 조합(사용자 요청 "스타일 규정을 만들어놓고 샘플 조합").
4. S급 더 담아 구조분석·생성 품질 점검(현재 위키 3개).

### 파일 지도
`shopping_shorts/`: categorize.py, ai_categorize.py, script_extract.py, structure_analyze.py, script_generate.py, store.py, app.py / `static/`: index.html(랭킹), library.html(도서관)

### ⚠️ 배포 주의 (오늘 실제로 겪음)
서버 자동배포(3분 크론)가 **텔레그램 크롤봇의 `raw/telegram` 실시간 쓰기 + `pipeline/atoms/autopilot_state.json` dirty**로 `git pull --ff-only`이 계속 막혀 서버가 옛 커밋에 정체됐음.
→ 수동배포는 **`git fetch && git reset --hard origin/main && sudo systemctl restart shopping-shorts`** 로 강제정렬(raw는 봇이 재생성하니 손실 무해). 근본해결은 `deploy/auto_deploy.sh`를 reset 방식/skip-worktree로 손봐야 함.
관련 메모리: [[project_쇼핑쇼츠_자동화]] / [[reference_deploy_truth_branch_ssh]]

---

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
