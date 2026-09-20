---
name: reference_iframe_캐시버스터가_옛코드를_물린다
description: scene_lab iframe의 t= 값이 '페이지 로드 시각 1회 고정'이라 배포 전에 열어둔 탭은 옛 문서를 계속 실행한다 — "고쳤는데 안 된다"의 뿌리
metadata:
  type: reference
---

`produce.html`의 3단계 iframe 주소는 `?job=<id>&t=SCENE_LAB_BUST`인데,
**`SCENE_LAB_BUST = Date.now()`가 페이지 로드 때 한 번만** 정해진다(편집 중 화면이 튀지 않게 한 조치).

→ **배포 전에 열어둔 탭은 scene_lab 문서와 그 안의 filmroll.js를 옛 채로 계속 실행한다.**
필름을 접었다 다시 펼쳐도 같은 옛 스크립트로 인스턴스를 만들므로 증상이 똑같이 재현된다.

## 2026-08-28 실사고
새 기능(`_fitToRange`의 조각 맞춤 확대)이 "예외도 없이 호출조차 안 된다"고 판정했는데,
코드에는 막는 경로가 없었다(가드 5개가 전부 칸을 그리기 **전**에 있어, 칸이 그려졌다면
그 뒤 블록은 반드시 실행된다). 실제로는 **옛 스크립트를 보고 있었던** 것.

## 그래서
- "고쳤는데 안 된다"를 판정하기 전에 **그 탭이 실제로 실행 중인 코드**를 확인하라:
  `contentWindow.filmroll.toString()`에 새 코드 조각이 있는지 본다. 서버 파일 md5만으로는 부족하다.
- 판정 전에 **하드 리프레시(Ctrl+Shift+R)** 로 iframe 문서를 새로 받아라.
- ★숨은 iframe(0×0)에서는 `requestAnimationFrame`이 **돌지 않는다** — 3단계 패널이 접힌 채
  검사하면 "자동확대가 안 돈다"는 잘못된 결론이 나온다. 반드시 패널을 열고 재현하라.

관련: [[reference_revert가_남긴_localStorage]] · [[reference_조용한_폴백_파이프라인_되돌림]]
