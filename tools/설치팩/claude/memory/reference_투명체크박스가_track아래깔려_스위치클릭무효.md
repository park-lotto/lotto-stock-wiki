---
name: track
description: "2026-09-04 자막제거 스위치 \"활성화 안 된다\" 제보 다수 — 투명 .sw-input(absolute)이 뒤 형제 .sw-track(relative) 아래 깔려 스위치 클릭이 통째로 무효. label 밖으로 뺀 순간 드러남"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1ee330d2-571b-42ec-baae-cd176d6d1bfb
  modified: 2026-09-04T05:40:19.352Z
---

2026-09-04 자막제거 스위치를 제목 label 밖으로 옮긴 개편 뒤, 스위치를 눌러도 안 켜졌다.
투명 체크박스 `.sw-input`(absolute, opacity 0)이 DOM상 `.sw-track`(position:relative) 앞이라
뒤 형제가 위에 그려져 포인터가 span에 떨어졌다. 제목 글자(label for=)로만 켜져서
"어디를 눌러야 되는지 모르는" 상태. 판정 = `document.elementFromPoint(track 중앙)`이
`subToggle`이 아니면 무효. 수정 = `.sw-input{z-index:1}` (main b19eec736).

**Why:** 예전엔 label 안에 있어 label이 대신 눌러줘서 숨어 있던 결함. 배치를 바꾸면 stacking이 바뀐다.
박선정 고객 "자막제거 안 됨"(스위치 꺼진 채 렌더)도 이것으로 설명됐다.

**How to apply:**
- 커스텀 스위치/체크박스 UI를 옮기거나 래퍼를 바꿨으면 반드시 `elementFromPoint`로 클릭 수신 요소를 확인. 정적 CSS 검토·스크린샷은 못 잡는다.
- 브라우저 자동화 실클릭은 창 배율(dpr 0.75·2560폭)에서 좌표가 어긋난다 — 좌표 클릭 대신 hit-test로 판정하라.
- 회귀 테스트 `tests/test_sub_toggle_clickable.py`. 관련 [[reference_목록에만_적힌_예외는_아무것도_안막는다]]
