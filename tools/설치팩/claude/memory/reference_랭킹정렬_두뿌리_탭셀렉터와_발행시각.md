---
name: reference
description: "랭킹 \"최신순/조회수순이 안 갈린다\"의 뿌리 2개 — 기간 탭까지 잡은 class 셀렉터, 그리고 upload_ts가 한 건도 안 쌓이던 것"
metadata: 
  node_type: memory
  type: project
  originSessionId: 08ae91fe-61fa-4fbc-be1f-0484fdd62555
  modified: 2026-09-05T05:54:01.378Z
---

2026-09-05 사장님 제보 "유튜브 카테고리에서 최신순/조회수순이 안 나뉜다 / 기간 탭 누르고 최신순 누르면 안 된다".
증상은 하나처럼 보였지만 **뿌리가 둘**이었다.

**① 프론트 — 셀렉터가 다른 줄의 버튼까지 잡았다** (`shopping_shorts/static/index.html`)
`document.querySelectorAll('.tab')`가 기간 줄(`#spanTabs`) 버튼까지 잡아, 기간 탭을 누르면
`setTab(undefined)`이 함께 돌아 `STATE.tab`이 지워졌다 → `sortKey`가 전부 0을 돌려줘
**정렬이 통째로 사라진다**. `x.dataset.tab===t`가 `undefined===undefined`로 참이 돼
기간 버튼 4개가 전부 active로 켜지기도 했다. 고침 = `.tab[data-tab]` + `setTab`에 `if(!t) return`.

**② 데이터 — 발행시각이 한 건도 안 쌓였다** (`shopping_shorts/store.py::_record_history`)
`it["timestamp"]`만 봤는데 **수집 items에 그 키가 없다**(시간 필드는 `age_hours` 하나뿐).
실측: `reel_history.upload_ts` 채움 유튜브 9,203건 중 **0** / 인스타 4,287건 중 **0**.
그래서 기간 탭(`hits_since`)의 최신순이 `first_seen`(수집시각)으로 밀려났고, 유튜브는
하루 2회 수집이라 `first_seen`이 **값 2개뿐** → 최신순이 무효(화면이 전부 "7시간 전").
고침 = `_upload_ts_of`가 `수집시각 − age_hours`로 역산. **새 수집분부터** 채워진다.

**판정법**: 화면만 보지 말고 그 탭이 실제로 부르는 API를 브라우저에서 직접 fetch해
시간 필드 채움률을 세라(`/api/reference?platform=…&days=7`). 탭마다 들어오는 필드가 다르다.
⚠️ 비로그인 `/`는 랜딩 페이지라 **curl로 랭킹 JS를 판정하면 무효**다 — 로그인된 브라우저에서 봐라.

관련: [[reference_자동배포_시간창_2시6시]] · [[feedback_프로그램수정은_실제로_돌려보고_확실할때만]]
