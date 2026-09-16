---
name: reference_render_crash_looks_like_buffering
description: "탭·필터가 안 먹힌다 / 버퍼 같다" 제보는 콘솔부터 — 렌더가 결측 하나로 죽으면 화면이 얼어붙어 정확히 그렇게 보인다
metadata:
  type: reference
---

2026-08-17 숏템메이커 랭킹 제보: "이번 주 터진 것 누른 뒤 명예의전당을 눌러도 이동이 안
된다, 버퍼인가? 지표·카테고리도 안 먹는다." 증상이 넷인데 **원인은 예외 하나**였다.

```
TypeError: Cannot read properties of undefined (reading 'toFixed')
  at render (index.html:1509)   ← i.speed.toFixed(1)
```

기간(`hits_since`)·역대(`archive_hits`) 항목은 `build_items`를 안 거쳐 강도지표가 없는데
화면이 무조건 불렀다 → **첫 카드에서 render가 통째로 죽고 화면이 이전 상태로 얼어붙는다.**
데이터는 새로 받아오는데 그리지를 못하니 무엇을 눌러도 그대로였다.

**코드만 읽어선 못 잡았다.** 핸들러도 `loadLast`도 정상이라 몇 번을 봐도 맞게 생겼다.
크롬 MCP로 콘솔을 읽자 한 줄에 끝났다.

**처방은 두 겹으로**
1. 서버가 채운다 — `ranking.fill_intensity`(식은 `build_items`와 같은 정의, 한 곳에만)
2. 화면이 버틴다 — `_num`/`_pct`로 값이 없으면 `'—'`. **카드 한 장의 결측이 페이지를
   멈추면 안 된다.**

같은 날 같은 화면에서 이름 어긋남도 나왔다: 화면은 `i.thumbnail`인데 두 경로는 `thumb`으로
줘서 썸네일이 전부 검게 빔. **같은 것을 두 이름으로 부르면 한쪽이 조용히 빠진다.**

**그래서 지킬 것**
- "안 바뀐다/버퍼 같다/이동이 안 된다" → **브라우저 콘솔이 1순위**. 코드 정독은 그 다음.
- 목록을 그리는 코드는 항목 하나가 이상해도 나머지를 그려야 한다.
- 새 데이터 경로를 화면에 붙일 땐 **화면이 읽는 키를 전부 채웠는지** 먼저 확인한다
  (기존 경로와 필드 이름·유무가 다른 게 사고의 재료다).

관련: [[feedback_self_verify_before_reporting]] [[feedback_mockup_is_source_of_truth]]
[[reference_shopping_shorts_scene_lab_verify]]
