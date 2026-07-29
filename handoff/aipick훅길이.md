# 핸드오프 — aipick훅길이 (은행/대본 품질 대개편)

- 날짜: 2026-07-26 (사무실 → 집 이어감)
- 트랙: `aipick훅길이` (폴더 유지, 최신 main 동기화됨)
- 라이브: shoppingshorts.duckdns.org / 서버 ubuntu@3.39.179.148 systemd `shopping-shorts`

## ✅ 오늘 완료 (전부 origin/main 라이브, 최신 = ba72b8030)

1. **AI PICK 스코핑** — `_load_work_sources`가 계정 전체 픽이 아니라 **현재 work.state.handoff**(담긴 영상)로 후보 한정. (홈테리어픽 오출 해결)
2. **훅 3역할 분담** — `bank_assemble.parts_block` 프롬프트: 벤치마킹형/트렌드반전형/3초임팩트형 (다이소 클론 방지)
3. **스파인 우승작 역설계 20종** — `scripts/seed_spines_v3.py` (v2 일반템플릿 대체). 서버 DB approved 24 = 학습5 + v3 20. source_count=10 마커로 승격게이트 통과.
4. **우승대본 few-shot 주입** — `bank_assemble.winners_block`: pattern_source 우승대본 전문을 **같은 카테고리** perf 상위로 생성 프롬프트에 예시 주입. (타 카테고리 오염 차단 — 청양고추↔주방가림막 불일치 해결)
5. **렌즈 월 한도 자동 스케일** — `app._lens_month_limit` = SerpApi 키 개수 × 100. 2키=200. (2번째 키 넣어도 100 고정이던 문제)
6. **30초 미달 근본원인 수정** — `edit_plan._scene_first_candidates`: per-beat 하한(char_target*0.85//6.5=22자)×6비트=132자로 총하한(145자)보다 낮아 구조적 23초 착지가 뿌리. → per-beat = char_target÷비트수(6~7비트 합=목표), 길이 대칭(짧으면 무조건 반려), 재생성 트리거 0.85→0.92.

## ⏭ 집에서 할 것 (검증 우선)

1. **★30초 실검증** — 라이브에서 대본 뽑아 3개 후보가 **27~33초(≈150~185자)**로 나오는지 눈으로 확인.
   - 나오면 → 30초 근본원인 해결 확정.
   - 여전히 짧으면 → `edit_plan._scene_first_candidates` 안의 남은 anti-length 문구(초반 "짧은 이야기다" 등)를 더 걷어내는 2차 조정. **표면 패치 말고** 실제 생성→측정→반영 루프로.
2. **few-shot·훅 실결과 확인** — 3개 훅이 서로 다른 결 + 같은 소재로 붙는지(오염 재발 없는지).
3. (선택) 스파인 v3가 너무 틀에 박히면 pending 강등. 백업으로 복원 가능.

## 🗄 백업 / 되돌리기
- 은행 전체 백업: 서버 `/home/ubuntu/lotto-stock-wiki/backups/bank_backup_20260726_190338.sql` + 로컬 `바탕화면\은행백업_20260726_190338.sql` (spine5/item3505/source315 시점)
- 참고 덤프: 바탕화면 `부품은행_덤프.txt`, `우승대본_카테고리별.txt`

## 📁 핵심 파일
- `shopping_shorts/bank_assemble.py` — parts_block(훅3역할)/winners_block(few-shot)/assemble_bank_context(4층)
- `shopping_shorts/edit_plan.py` — `_scene_first_candidates`(길이 지시), `build_scene_first_plan`(재생성 트리거 0.92)
- `shopping_shorts/app.py` — `_load_work_sources`(스코핑), `_lens_month_limit`(렌즈 한도)
- `shopping_shorts/scripts/seed_spines_v3.py` — 스파인 시드

## ⚠️ 측정 함정(반복 주의)
- `produce_works.state.script` = **소스 원문**(script_from_wiki와 동일), 생성 후보 아님. 생성 후보 길이는 여기서 못 잰다(카드에만 뜸, 미저장). 길이 검증은 라이브 카드로.
