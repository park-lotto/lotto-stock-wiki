---
name: reference-not-cid
description: "쇼핑쇼츠에서 `if not cid`로 로그인을 판정하면 관리자(cid==0)가 자기 기능을 못 쓴다 — 정본은 _verify_session의 None 여부"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 426a4b65-f139-431f-bc85-a001e6d21692
  modified: 2026-09-02T06:09:17.980Z
---

쇼핑쇼츠에서 **로그인 판정을 `if not cid:`로 쓰면 안 된다.** 관리자(사장님)는
`customer_id == 0`이라 falsy에 걸려 **자기 기능이 통째로 막힌다**.

`_cid(request)`는 로그인 여부를 알려주지 않는다 — 인증 게이트를 안 거치는 경로에서도
`LEGACY_CUSTOMER_ID`(=0)를 폴백으로 준다(app.py `_cid` docstring). 즉 **비로그인도 0,
관리자도 0**이라 값만 봐서는 못 가른다.

정본은 `/api/grab`이 쓰는 방식:

```python
cid = _verify_session(request.cookies.get("dash_auth")) if _AUTH_ON else 0
if cid is None:                     # ★None만 비로그인. 0은 정상 로그인(관리자)
    return ...로그인 필요...
```

**2026-09-02 실사고**: 볼채널등록 API 2곳(`/api/fav_channel/add`, `/api/fav_channel/grab`)을
`if not cid`로 짰다가 사장님 계정에서 "로그인이 필요합니다"가 떴다. 문법검사·TestClient로는
안 잡혔고 — **브라우저에서 직접 눌러보고서야** 드러났다. 사이드바에는 "관리자·전 기능·무제한"이
멀쩡히 떠 있어서 화면만 보면 로그인된 상태로 보인다.

관련: [[reference_shopping_shorts_admin_dual_identity]] (관리자=cid0에 데이터가 다 있다),
[[feedback_self_verify_before_reporting]], [[project_볼채널등록_개인채널즐겨찾기]]
