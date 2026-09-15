---
name: reference-auto
description: "\"auto: session changes\" 커밋이 남의 최신 작업을 옛 상태로 되돌린다 — 찾는 법, 복구할 때 테스트도 같이 되돌려져 있다는 것"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 4132c8ff-2b02-4536-8e2a-3f391b6f0c7e
  modified: 2026-09-02T06:36:34.672Z
---

`83be8aa62 "auto: session changes"`(2026-09-01 15:24)가 7개 파일을 **옛 상태로 통째 되돌렸다.**
다른 파일은 이후 재작업으로 회복됐지만 `pipeline/atoms/key_vault.py`만 9/2까지 남아 있었다
— 소진 잠금 TTL과 키 회전(`rotated`)이 통째로 사라진 채 라이브가 돌았다.

**찾는 법**: 되돌림 커밋이 지운 이름 중 지금도 없는 것을 뽑는다.
```
git log --oneline --all -S"def <함수명>" -- <파일>     # 언제 들어오고 언제 사라졌나
git show <되돌림커밋> -- <파일> | grep -E "^-def |^-_[A-Z_]+ ="
git grep -q "<이름>" origin/main -- <파일> || echo "여전히 없음"
```

**복구할 때 반드시**
- 되돌리기 **직전 커밋의 원문**으로 되살린다. 기억으로 다시 쓰면 주석에 담긴 실측 근거가 날아간다.
- ★**파일을 통째로 덮지 마라.** 되돌림 이후 정당하게 들어온 작업이 그 파일에 있다
  (이번엔 `pick_paced_key`·`seconds_until_quota_reset`·일일소진 분기). 덮으면 내가 같은 사고를 낸다.
  블록 단위로 골라 합쳐라.
- ★**테스트도 같이 되돌려져 있다.** 게이트가 "새로 깨진 테스트"를 알려주면 내 회귀로만 보지 말고
  되돌림 커밋이 그 테스트 파일도 만졌는지 봐라. 이번엔 `test_byok_gemini_wiring`이
  `sorted()`(집합 비교) → 순서 고정 비교로 되돌아가 있었다(회전이 살아나니 당연히 깨졌다).
- 옛 설계를 검사하는 채로 방치된 테스트가 있을 수 있다(`test_state_resets_on_new_day`는
  TTL 설계로 바뀐 뒤에도 "날짜 리셋"을 검사하고 있었다 — 기준선 실패 20건 중 하나).

**교훈 하나 더 — 복구했다고 증상이 낫는 건 아니다.**
회전을 되살렸는데 rpm은 13.9%→24.8%로 오히려 늘었다(실측). 진짜 원인은 따로 있었다:
`dashboard/server.py:_gemini_text`가 429에 대기 없이 `continue`로 키를 연타한다
(쇼핑쇼츠는 9/1에 `pick_paced_key`로 막았는데 대시보드는 그 처방을 못 받았다).
**복구 후 실측으로 증상이 실제 나았는지 확인하라.** 관련: [[reference_gemini_key_rotation_never_ran]]
