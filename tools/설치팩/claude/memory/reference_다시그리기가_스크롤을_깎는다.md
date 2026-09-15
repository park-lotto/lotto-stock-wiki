---
name: ""
description: innerHTML 교체 순간 안에 있던 필름이 사라져 scrollLeft가 clamp된다 — 폭이 돌아온 뒤(2.9초) 되돌려야 한다
metadata: 
  node_type: memory
  type: reference
  originSessionId: 31b241c4-733c-4c4d-908f-3beff029e1d7
  modified: 2026-09-04T09:33:17.352Z
---

**"구간 재생하려고 눌렀더니 작업화면이 딴 데로 가 있다"(2026-09-04 고객 접수)의 뿌리.**

scene_lab `renderBand()`가 `#tbrow.innerHTML`을 갈아끼우는 순간, **칸 안에 펼쳐둔 필름(422px)이
통째로 사라져** 가로 스크롤 최대값이 줄고 브라우저가 `scrollLeft`를 그만큼 깎는다(clamp).
필름은 뒤에 다시 붙어 폭은 돌아오지만 **깎인 스크롤은 그대로 남는다** → 화면이 칸 반쯤 앞으로 밀린다.
라이브 실측(mix job fb62adf0aad0): 4608 → 4270 (−338px).

**함정 3개 — 여기서 다 걸렸다:**

1. **`innerHTML` 교체 자체는 스크롤을 안 지운다.** 첫 진단("교체하면 0으로 리셋")은 **틀렸고**
   라이브 실측으로 반증됐다(4692 → 4692). 깎이는 건 *내용이 줄었을 때만*이다.
   → 커밋까지 했다가 되돌렸다. 재현 없이 고치지 마라.
2. **복원을 `innerHTML` 직후에 한 번만 하면 안 먹는다.** 그 순간은 아직 좁아서 또 깎인다.
   실측: 폭이 돌아오는 것은 클릭 후 **약 2.9초 뒤**(영상 메타데이터 로드). 그때까지 지켜봐야 한다.
3. **`requestAnimationFrame`은 자동화/숨은 탭에서 멈춘다.** rAF로 짠 복원은 조용히 안 돌았다.
   `setInterval`로 감시해야 한다. (`window.__hits` 같은 카운터를 넣어 *실제로 발동했는지* 확인하라)

**재현 조건** — 아무 클릭이나로는 안 난다:
칸 안에 필름이 펼쳐져 있어야 하고(폭이 줄어들 거리가 있어야 함), 클릭은 **칸의 검정 빈자리**
(`.tbcuts` 배경 → `selBeat` + 구간 재생)여야 한다. `.tbcut`(조각 썸네일) 클릭으로는 안 난다.

**해법**: `_bandKeepScroll(row)` — 그리기 전 위치를 기억(한 클릭에서 첫 호출값만),
`scrollWidth - clientWidth >= keep`일 때만 되돌리고, 5초간 `setInterval`로 감시,
사용자가 끌거나 휠을 굴리면 즉시 손을 뗀다.

관련: [[reference_브라우저검증_인자형태와_타이머스로틀]] · [[reference_sticky슬롯_도구높이가_미리보기를_민다]]
· [[feedback_verify_before_claim_and_act]]
