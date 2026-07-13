# 영상제작 위저드 5·꾸미기 — 이어서 할 일 (핸드오프)

날짜: 2026-07-14 · 라이브: https://shoppingshorts.duckdns.org/produce (로그인)
> 관련 메모리: [[feedback_꾸미기_딸깍프리셋철학]] [[feedback_동시세션_커밋규칙]]

## ✅ 완료·배포됨 (2026-07-14, 커밋 순서대로)

- `46c756b6` **슬라이스A**: 폰트 7→**22종**(쇼핑팩토리 폰트, woff/woff2 6개 ttf/otf 변환,
  한글파일명 ASCII 리네임 GBatang/GowunBatang/RIDIBatang/Kkubulim) + ⭐베스트5 상단 +
  미리보기 200→**340px** + **배경박스**(headcopy) + 레퍼런스 프리셋 16종
- `6bddd45e` **폰트 커스텀 드롭다운**: 마우스 hover 시 프리뷰 실시간 폰트 변경(각 항목 자기폰트 렌더)
- `1893a684` **슬라이스B**: **자막 스타일 분리**(자막 자체 폰트·색·크기·위치·외곽선·박스) +
  **자막 효과**(없음/페이드/슬라이드/팝) + 듀얼 프리뷰. ⚠️버그수정: `assemble`이 headcopy를
  `_burn_captions`에 미전달하던 것(헤드카피가 최종렌더에 안 구워짐) 수정 — 이제 headcopy·caption_style 둘 다 전달
- `6817550e` **🎯 딸깍 완성스타일 14종**(원클릭: 헤드카피+자막+효과 한번에, applyFullPreset) +
  **미리보기 흰배경 기본** + **효과 프리뷰 애니메이션**(CSS 반복재생)
- `aeaf09be` **커스텀 프리셋 저장**(내 프리셋, localStorage, applyConfig 공용)

렌더 지원(video_assemble): 헤드카피/자막 각각 폰트·색·크기·위치·외곽선·**배경박스**(box=1) + 자막 효과(alpha/y expr).
`caption_style`은 store(caption_style_json)→app(/api/produce/mix/settings)→mix_pipeline.run_render→assemble 배선 완료.

## ⏭ 남은 것 — 슬라이스 C (백엔드 필요, **다른 세션 끝난 뒤 진행**)

⚠️ **동시성 주의**: 2026-07-14 기준 다른 세션이 `app.py`·`video_assemble.py`·`mix_pipeline.py`·`store.py`에
렌즈발굴·보이스프리셋을 활발히 커밋 중이었음. 슬라이스C는 이 파일들을 크게 건드리므로,
**별도 git 워크트리에서 작업 후 병합** 권장(공유트리 churn 회피). 커밋 규칙: [[feedback_동시세션_커밋규칙]].

구현 대상(전부 /produce 5단계에 UI + video_assemble 렌더 + app.py 업로드 엔드포인트):
1. **이미지 오버레이**: PNG/JPG 업로드 → 영상 위 overlay(위치·크기). ffmpeg `overlay` 필터. 프리셋 4종(블랙/화이트 조합) 참고.
2. **워터마크 닉네임**: drawtext 워터마크(우하단 기본), 토글 + 텍스트/투명도.
3. **BGM 업로드**: mp3/wav/m4a → 오디오 믹스(TTS 나레이션 위에 덕킹). ffmpeg `amix`/`sidechaincompress`.
4. **추가 텍스트 블록**: 헤드카피 외 여러 텍스트를 각자 위치·스타일로(현재 headcopy 1개 → 배열화).
5. **프리뷰 실장면 배경**: 매칭된 소스클립 첫 프레임을 poster로 서빙하는 app 엔드포인트(`/api/mix/poster/{job}`) →
   produce.html `hcPreviewBg`(이미 DOM에 있음, display:none)에 세팅. 현재는 흰배경 기본.
6. (후순위) 자막 **정밀 동기화**(TTS word-timing) — whisper 등 필요.

## 파일 지도
`static/produce.html`(위저드 전체: FULL_PRESETS·HC_PRESETS·자막스타일·내프리셋·폰트피커) /
`video_assemble.py`(_headcopy_drawtext·_caption_drawtexts[style dict]·_burn_captions·assemble) /
`store.py`(mix_jobs.caption_style_json) / `app.py`(/api/produce/mix/settings) / `mix_pipeline.py`(run_render)

## 재개 절차
```
git pull origin main
# 다른 세션 backend 작업 끝났는지 확인(git log, app.py/video_assemble 안정?)
# 워크트리 생성 후 슬라이스C 1번(이미지 오버레이)부터 TDD로
```
