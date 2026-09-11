---
name: reference_shopping_shorts_scene_lab_verify
description: 숏템메이커 장면 편집 화면을 로그인 게이트 없이 실측하는 법 — /scene_lab.html?job=<잡ID> 단독 열기 + 스냅샷·복구. 미검증 배포 2회 사고 후 확보한 경로.
metadata: 
  node_type: memory
  type: reference
  originSessionId: 44ef7732-82ce-47c7-a6b9-70bda6010ebb
  modified: 2026-08-16T13:34:45.868Z
---

숏템메이커(`shoppingshorts.duckdns.org`)는 로그인 게이트가 있어 익명 `curl`로는 JS·화면을
못 받는다(로그인 페이지 HTML이 온다). 그래서 **화면 산출물을 검증 없이 배포하는 사고가
2026-08-16에 두 번 연속** 났다 — 사장님이 버그를 대신 잡아주셨다.

**해법: 사장님 크롬(claude-in-chrome)으로 장면 편집만 단독으로 연다.**

```
https://shoppingshorts.duckdns.org/scene_lab.html?job=<잡ID>
```

제작소(`/produce`) 상태를 안 건드리고 그 잡의 편집 화면만 뜬다. 잡 ID는 `/produce`를 열어
`iframe`의 `src`에서 얻는다.

**⚠️ `let`/`const` 최상위 선언은 `window`에 안 붙는다.** `DATA`·`lists`·`MAX_SHOT`을 읽으려면
그 프레임 스코프에서 평가해야 한다:

```js
const f = [...document.querySelectorAll('iframe')]
  .find(x => { try { return typeof x.contentWindow.autoFill === 'function' } catch(e){ return false } });
f.contentWindow.eval(`JSON.stringify({ ... DATA.beats ... })`)
```

**★사장님 편성을 건드리는 실험은 반드시 스냅샷 → 복구.** `render()`가 `saveWork`를 불러
서버에 저장되므로 복구까지 해야 원상태다:

```js
const snapL = JSON.parse(JSON.stringify(lists));
const snapA = JSON.parse(JSON.stringify(AUTOADD));
// … 실험 …
for (let k=0;k<lists.length;k++) lists[k] = snapL[k] ? snapL[k].slice() : [];
Object.keys(AUTOADD).forEach(k=>delete AUTOADD[k]);
Object.keys(snapA).forEach(k=>AUTOADD[k]=snapA[k].slice());
render();
```

끝나면 **내가 연 탭은 닫는다.** 실험 전 사장님 승인을 받아라(편성이 실제로 바뀐다).

관련: [[reference_scene_dup_by_desc_not_phash]] · [[feedback_self_verify_before_reporting]]
