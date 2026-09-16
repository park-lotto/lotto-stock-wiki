---
name: feedback_check_shape_before_string_ops
description: 하루에 같은 유형으로 라이브 500을 세 번 냈다 — 값의 타입을 확인하지 않고 .strip()을 부른 것. 새 데이터를 하류로 흘릴 땐 받는 쪽부터 확인
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 053a5ce9-6039-4b81-9dd4-3eb72b569b08
  modified: 2026-08-16T13:39:14.834Z
---

2026-08-16, 라이브(숏템메이커)에서 **같은 유형의 500을 하루에 세 번** 냈다.
증상은 매번 똑같았다: 화면엔 "네트워크 오류"만, 대본은 한 줄도 안 나옴.

| 자리 | 값의 진짜 모양 | 내가 한 것 |
|---|---|---|
| `body["work_id"].strip()` | 클라이언트 입력 — dict가 올 수 있다 | 타입 확인 없이 호출 |
| `(ex.get("source_brief") or "").strip()` | **dict**(product/role/core/summary) | 문자열로 가정 |
| `(body.get("job_id") or "").strip()` | 클라이언트 입력 | 같은 함수 3줄 위에 또 |

**Why:** 두 번째가 핵심 교훈이다. 그건 **잠자던 버그**였다 — 옛 스냅샷엔 그 필드가
없어서 안 터지다가, 내가 "담긴 영상 전부를 재료로" 넣으면서 캐시의 **진짜 값**이
하류로 흘러들자 드러났다. 새 기능이 새 버그를 만든 게 아니라, **새 데이터가 낡은
가정을 깨뜨린 것**이다.

**How to apply:**
- **새 데이터 경로를 열기 전에 받는 쪽부터 읽어라.** 하류가 그 모양(dict/str/list/None)을
  견디는지 확인하지 않으면, 지금까지 값이 비어 있어서 안 터지던 코드가 그 순간 터진다.
- 클라이언트가 준 값(`body[...]`)에 문자열 메서드를 바로 부르지 마라 —
  `x.strip() if isinstance(x, str) else ""`.
- **부가 기능이 본 기능을 막지 않게 하라.** 재료 보강은 "있으면 좋은 것"이지 대본 생성을
  죽일 이유가 없다 → try로 감싸고 실패하면 종전 재료로 계속.
- 같은 패턴이 앱 전체에 10곳 더 있다(`(body.get("x") or "").strip()`). 한가할 때 일괄 정리.
- ★사고 뒤엔 **전수 리뷰를 남에게 맡겨라.** 페이블 리뷰가 내가 못 본 5건을 더 찾았고,
  그중 하나는 **내가 그날 만든 기능이 통째로 죽어 있던 것**(`DouyinBusy`가
  `except Exception`에 삼켜져 도달 불가)이었다. 만든 사람은 자기 코드를 못 본다.

관련: [[feedback_verify_before_claim_and_act]] · [[reference_douyin_download_headless]] ·
[[feedback_self_verify_before_reporting]]
