# 영상제작 위저드 5·꾸미기 — 상태 (핸드오프)

날짜: 2026-07-14 · 라이브: https://shoppingshorts.duckdns.org/produce (로그인)
> 관련 메모리: [[feedback_꾸미기_딸깍프리셋철학]] [[feedback_동시세션_커밋규칙]]

## ✅ 꾸미기 5단계 — 전면 업그레이드 완료·배포 (2026-07-14)

**A/B/딸깍/커스텀 (커밋순):**
- 폰트 7→**22종**(쇼핑팩토리 폰트, woff/woff2 변환, 한글명 ASCII 리네임) + ⭐베스트5 상단
- 폰트 **hover 실시간 프리뷰** 커스텀 드롭다운(각 항목 자기폰트 렌더)
- 미리보기 **340px** + 드래그 + **배경박스**(headcopy) + 레퍼런스 프리셋 16종
- **자막 스타일 분리**(폰트·색·크기·위치·외곽선·박스) + **자막 효과**(없음/페이드/슬라이드/팝, 프리뷰 애니메이션)
- **🎯 딸깍 완성스타일 14종**(원클릭: 헤드카피+자막+효과 한번에) + **미리보기 흰배경 기본**
- **커스텀 프리셋 저장**(내 프리셋, localStorage)
- ⚠️버그수정: `assemble`이 headcopy를 `_burn_captions`에 미전달하던 것 수정

**슬라이스 C (전부 완료):**
- `e87de516` **C1** 워터마크 닉네임 + 추가 텍스트(드래그)
- `2c9c1773` **C2** BGM 업로드 + 오디오 믹스(볼륨·루프·amix)
- `32d655c7` **C3** 이미지 오버레이(로고·뱃지, overlay±BGM filter_complex 조합)
- `0cdd5748` **C4** 프리뷰 실장면 배경(poster 엔드포인트, 흰배경↔실영상 토글)

## 렌더 파이프라인 (video_assemble.py)
- `_fixed_drawtext`(공용): 헤드카피·추가텍스트·워터마크. 폰트·색·크기·위치·외곽선·**박스**·alpha
- `_caption_drawtexts(style)`: 자막 폰트·색·박스·**효과**(alpha/y expr)
- `_burn_captions`: drawtext 체인 + **이미지 오버레이**(overlay) + **BGM**(amix) 조합별 filter_complex 빌더
- 배선: store(caption_style_json/deco_json) → app(/mix/settings, /mix/bgm, /mix/overlay, /mix/poster) → mix_pipeline.run_render(bgm·overlay _abspath 해석) → assemble

## ⏭ 남은 것 (선택)
- 자막 **정밀 동기화**(TTS word-timing, whisper 등) — 후순위
- 6·썸네일 / 7·SEO 단계(현재 스텁)
- deco 프리셋에 BGM/오버레이 기본값 묶기(딸깍 확장)

## ⚠️ 동시세션 주의
다른 세션이 렌즈·보이스·생성요소를 같은 워킹트리에 활발히 커밋 중. 커밋 규칙 [[feedback_동시세션_커밋규칙]]:
커밋전 status확인 → `git add -A` 금지·내 hunk만 격리(`git apply --cached`) → 원자적 add+commit+push.
