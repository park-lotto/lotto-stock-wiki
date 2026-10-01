# CTA표시 — 유튜브용 CTA 잘라내기가 '마무리'·'댓글유도' 칸에서도 되게 (2026-09-30, 관제 045)

김성현님(352) 오픈채팅: "유튜브 대본으로 하면 CTA 부분이 적용되지 않아 완성본에서 CTA 자르기가 안 된다 — 대본작성 단계에 CTA 버튼".
원인: CTA 판정이 역할 이름뿐(`_CTA_ROLES`). 썰 스타일(73·75)은 CTA 문구 칸을 '마무리'로 붙이고, 'call_to_action'·'댓글유도'는 목록에 없었다.
라이브 7일 473건 실측: 기존 CTA 287 / CTA 문구로 끝나는데 못 자름 35 / 없음 151.

## 주인 함수 / 결과물 검사
- 판단: `edit_plan._is_cta`(칸의 `cta_mark`가 역할 이름보다 먼저) · `guess_cta_index`(역할 → 마지막 줄 문구) ·
  `_looks_cta_text`(마지막 줄 전용, 댓글·프로필·남겨주·눌러·'키워드'라고 남겨) · `apply_cta_mark`(줄→칸, 수 같으면 번호/다르면 글자).
- 적용 자리: `mix_pipeline._plan_and_tts` 3.4 한 곳(모든 생성 경로가 지난다). 자를 지점은 기존 `video_assemble.cta_cut_sec` 그대로.
- 화면: 2단계 카드 줄마다 [📢 CTA](하나만 켜짐, 다시 누르면 해제). 처음 상태는 `POST /api/script/cta_guess`(서버 판정). 확정 시
  `STATE.script_cta_line/text` → mix start `script_structure.cta_line/cta_text`(-1=없음, 안 정하면 키 없음=서버 자동).
- 검사: tests/test_cta_mark.py 14건(옛 코드 13건 실패 확인) · tools/cta_mark_ui_check.py(produce.html 실제 함수 node 실행 7항목) ·
  라이브 473건 재측정: 기존 287 전부 동일, 새로 35건 전부 진짜 CTA 문구(오탐 0).

- ★2026-09-30 05시 라이브 검증 중 발견: `video_assemble._beat_timeline`이 cta_mark를 안 실어 표시가 자르기 직전에 사라졌다(저장위치≠읽기위치). 타임라인에 실음 + 칸→타임라인→자르기 경로 테스트(옛 코드 실패 확인).

## ⏭ 다음
- 배포 승인 후 라이브: 2단계에서 버튼 보이는지·누르면 켜지는지, 새 작업 렌더 뒤 cta_cut_sec 저장·9단계 '유튜브용' 잘라내기 길이=CTA 시작.
- 김성현님 3b4111969ac4·eef350b2e52e 는 옛 작업이라 표시 없음 → 새로 만들거나 다시 매칭해야 자를 수 있다.
