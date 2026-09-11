---
name: reference_gemini_key_rotation_never_ran
description: 제미니 키 12개가 있어도 1개만 쓰고 있었다 — 페이서를 만들어놓고 호출부 15곳이 옛 함수를 부르던 사고(2026-08-18)
metadata: 
  node_type: memory
  type: reference
  originSessionId: c46bf31a-3df5-4ecf-be48-8b015e97a2e9
  modified: 2026-08-18T14:08:29.450Z
---

`comment_gen._current_key_and_idx()`가 늘 `live[0]`을 돌려줘, **키가 12개여도 1번 키만** 때렸다.
라운드로빈 + 분당간격 페이서 `_next_live_key_and_idx`를 2026-08-06에 만들어놓고도
**실호출부 15곳**(script_extract·script_generate·edit_plan·similarity·structure_analyze·태거…)이
전부 옛 함수를 부르고 있어서 페이서가 통째로 놀았다. 주석에는 "2026-07-23에 고쳤다"고 적혀 있었다.

**증상 위장**: 1단계 자동분석은 동시 3개로 도는데 셋이 같은 키를 때려 분당 한도(키당 5건)에
바로 걸렸다. 그래서 동시성 상한을 3으로 묶어둔 근거 주석이 "429가 몰린다"였는데 — 진짜 원인은
동시성이 아니라 **키를 안 나눈 것**이었다. 잘못된 원인 진단이 상수에 굳어 있었다.

**고침**: `_current_key_and_idx` 본문을 페이서에 위임(0순위-B — 키를 고르는 판단은 한 곳).
호출부 15곳이 자동으로 따라온다. 이론 처리량 분당 5건 → 60건.

**함정**: 커서가 전역 상태가 되면서 "키1 소진 → 키2" 류 테스트가 **단독은 통과, 묶으면 실패**했다.
`tests/conftest.py`에 autouse 픽스처로 `_rr_cursor`·`_key_last_used` 리셋을 넣어 막았다.

**교훈**: "고쳤다"는 주석이 아니라 **호출부를 grep해서** 실제로 그 함수를 부르는지 확인하라.
새 함수를 만들고 옛 함수를 남겨두면 아무도 새 것을 안 쓴다.

관련: [[feedback_no_unverified_flag_in_live]] · [[reference_shorts_key_403_permission_denied_rotation]] · [[project_gemini_key_ops_2026_08_04]]
