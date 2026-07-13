# 영상제작 위저드 — 이어서 할 일 (핸드오프)

날짜: 2026-07-13 · 라이브: https://shoppingshorts.duckdns.org/produce (로그인)
> 모든 코드·폰트 **origin/main에 푸시 완료 + 서버 배포됨**. 집에서 `git pull origin main`이면 전부 받아짐.

## ✅ 완성된 단계 (8단계 위저드 `/produce`)

- **1·대본** — 3모드 전부 라이브 검증
  - 직접작성 / 우리믹스(도서관 선택→조합 or **1개 그대로 쓰기**) / 제미니 자동
  - 도서관(library)에서 "🎬 영상제작으로 보내기" → 우리믹스 탭 기본목록(picks)
  - 대본 생성은 key_vault 예비키풀 사용(전용키 소진 회피)
- **2·영상믹스** — given_script 매칭(확정대본→비트분할→소스영상 장면매칭). 비트별 **fit(1~5)** 약한매칭 ⚠️경고
- **3·자막제거** — VMake 토글(job settings). ※실제 VMake 제거는 API 스펙 미완(mock, 다른 트랙)
- **4·TTS** — 비트별 음성 프리뷰(매칭 파이프라인서 생성)
- **5·꾸미기(헤드카피)** — 완전 완료·실렌더 검증
  - 폰트 7종(배민주아/도현·티몬몬소리·지마켓·SUIT·프리텐다드·나눔) + 색·굵기·크기·외곽선
  - **스타일 프리셋 7종**(원클릭) + 미리보기 **드래그** 이동 + **정렬**(위/중/하/가운데)
  - video_assemble `_headcopy_drawtext`로 실제 영상에 구워짐(검증됨)

## ⏭ 다음 (미구현)

1. **6·썸네일** — 영상 프레임 선택 + 텍스트 오버레이 (스텁 상태)
2. **7·SEO** — 제목/설명/태그 AI 생성 (스텁 상태)
3. **8·최종검수** — 렌더 UI는 있음. 내보내기(CapCut export)는 미구현
4. (선택) woff 폰트 79종 → ttf 변환하면 어그로체 등 더 쓸 수 있음. 지금은 ttf/otf 7종만(렌더 일치)

## 파일 지도 (shopping_shorts/)

- `static/produce.html` — 위저드 UI 전체(8스텝, STATE.script/subtitleRemoval/headcopy)
- `static/library.html` — 도서관, "영상제작으로 보내기" 버튼
- `edit_plan.py` — build_edit_plan(given_script, fit), key_vault 라우팅(_vault_call)
- `script_generate.py` — generate_from_topic(제미니자동)·generate_mix(우리믹스)
- `video_assemble.py` — _headcopy_drawtext(헤드카피 굽기), static/fonts 로드
- `mix_pipeline.py` — run_mix_job/run_render (given_script·headcopy 관통)
- `store.py` — mix_jobs(given_script/headcopy_json 컬럼), produce_script_picks 테이블
- `app.py` — /api/produce/* (script/gemini·mix·picks·mix/start·mix/settings)
- `static/fonts/` — 번들 폰트 7종

## 집에서 시작 절차

```
git pull origin main          # 최신 코드·폰트 받기
# 라이브 확인: https://shoppingshorts.duckdns.org/produce (로그인)
# 이어서 6·썸네일 or 7·SEO 구현
```
