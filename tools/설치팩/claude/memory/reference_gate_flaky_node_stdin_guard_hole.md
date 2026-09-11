---
name: reference_gate_flaky_node_stdin_guard_hole
description: track finish 게이트 간헐 실패 = pytest stdin 캡처 + node 직접 호출(WinError 6). 금지 가드가 소문자 변수를 놓치고 있었다
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0adb7c8d-6c08-4041-8cd0-3df6efc019b1
  modified: 2026-08-21T10:43:51.810Z
---

2026-08-21. `py tools/track.py finish`가 `test_mix_accepts_youtube_url` 등으로 헛돌고,
`-k "seo or thumb or title"`로 묶어 돌리면 2 failed + 2 errors가 났다(단독 실행은 전부 통과).

**원인**: `OSError [WinError 6] 핸들이 잘못되었습니다` — pytest가 stdin을 캡처한 상태에서
`subprocess.run([node, ...])`으로 node를 띄우면 윈도우에서 간헐 실패한다.
`shopping_shorts/tests/js_harness.py`가 `stdin=subprocess.DEVNULL` + 임시파일 실행으로
이미 막아 두었는데, 두 테스트가 하네스를 안 쓰고 node를 직접 불렀다.

**왜 가드가 못 잡았나** — 재발 차단용 `test_no_node_dash_e.py`의 정규식이
리터럴 `"node"`와 대문자 `NODE`만 봤다. 두 파일은 소문자 변수였다:

```python
node = shutil.which("node")
subprocess.run([node, "-e", script], ...)   # ← 가드를 그냥 통과
```

"네 번째 재발을 막겠다"고 만든 가드가 **변수 이름 하나로 무력화**돼 있었다.
패턴을 넓히자 곧바로 또 다른 파일(`test_work_save_job_guard_js.py`)이 새로 적발됐다.
→ 315 passed(전 2 failed·2 errors).

## 교훈
- **게이트가 간헐 실패하면 제품 코드보다 테스트 하네스를 먼저 의심하라.** 단독 실행으로
  갈라보면 1분 안에 판별된다(단독 통과 = 오염/환경, 단독 실패 = 진짜 회귀).
- **가드를 만들었으면 가드가 실제로 잡는지 시험하라.** 이 가드는 존재했지만 한 번도
  적발한 적이 없었다 — 잡을 수 없는 형태만 검사하고 있었기 때문이다.
- 새 JS 테스트는 반드시 `js_harness.run_js` / `run_js_proc`을 쓴다(stdin·32,767자 상한 동시 해결).
- ⚠️패치 스크립트에서 `\b` 같은 이스케이프를 일반 문자열로 넘기면 **제어문자(0x08)가
  파일에 박혀 정규식이 조용히 죽는다.** 실제로 이번에 한 번 당했다 — 패턴을 고쳤으면
  반드시 모듈을 import해 `search()`가 참인지 확인하라.

관련: [[reference_python_path_windows_stub]] · [[feedback_harness_invented_contract]]
