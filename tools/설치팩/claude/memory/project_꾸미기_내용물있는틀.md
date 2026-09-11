---
name: project
description: "자막꾸미기 템플릿을 빈 색띠에서 '내용물 있는 틀'로 전환 — 미리보기와 렌더가 같은 그림 파일을 쓰게 묶은 설계와 함정"
metadata: 
  node_type: memory
  type: project
  originSessionId: df6f9bcf-4f1b-4b43-b596-e8436d707878
  modified: 2026-08-18T14:09:54.553Z
---

숏템메이커 제작소 6단계 자막꾸미기. 기존 템플릿 12종은 `deco_templates.py`가 만든 **빈 색띠 PNG**뿐이라
사장님이 "실제와 다르다"고 지적 — 실제로 잘되는 유튜브 포맷은 띠 **안에** 채널명·☰🔍·[광고]·제목·조회수가 있다.
2026-08-18 `shopping_shorts/deco_frame.py` 신설로 A축(커뮤니티 UI) 라이브(`b1db32200`).

**핵심 계약**: 그림을 그리는 곳은 `deco_frame` **하나**. 미리보기(`GET /api/produce/frame.png`)와
렌더(`mix_pipeline._template_layer`)가 **같은 `cache_path(spec)` 파일**을 쓴다.
테스트 `test_pipeline_uses_same_file_as_preview`가 고정한다.

**Why:** 미리보기를 CSS로 흉내내면 언젠가 반드시 어긋나 "미리보기랑 다르게 나왔다"가 된다.
이 프로젝트에서 이미 여러 번 난 유형이다([[reference_silent_fallback_pipeline_undo]]).

**How to apply:**
- 틀 모양·색·치수를 바꿀 땐 `deco_frame.py`만 고친다. 화면에서 또 자르거나 그리지 마라(0순위-B).
- **폰트·색상·굵기·글씨 크기 조절을 새로 만들지 마라** — `produce.html` 스타일 탭
  `직접 다듬기 → 🎨 헤드카피 꾸미기`에 이미 다 있다. 사장님이 "없다"고 하시면 대개 **접힘 안 접힘**이라
  못 찾으신 것이니 노출만 고쳐라([[feedback_ttalkkak_senior_northstar]]).
- 헤드카피는 **2줄 고정**(`headcopy_gen.two_lines`, 26자/줄 13자). ★거른 **뒤에** 접으면 중복 제거가
  무력화된다(접기 전으로 검사·접은 뒤 저장 → 같은 문구 2번 통과). 반드시 접고 나서 `seen` 검사.
- `loadHeadcopySuggest` ~ `useHeadcopy` **사이에 `t.value=`를 쓰지 마라** — `test_headcopy_ui`가
  "추천이 자동채움 하지 않는가"를 소스로 검사하는 구간이다. 지우기 같은 함수는 구간 밖에 둔다.
  테스트를 느슨하게 고치는 게 아니라 코드를 옮겨라.
- PIL `rectangle`은 끝점 포함 — `bar_h`만큼 칠하려면 `bar_h - 1`.
- 색띠 12종과 틀은 **동시 사용 불가**(둘 다 전체화면 오버레이). 하나 고르면 다른 쪽을 비운다.

**남은 것**: 포맷 B(풀블리드+노랑 형광 훅), C(카드형 — **영상을 라운드로 축소 배치**해야 해서
오버레이만으론 안 되고 렌더 레이아웃 변경이 필요할 수 있다). 미검증=브라우저 실화면·실렌더 종단.
상세: `handoff/꾸미기.md`
