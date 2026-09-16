---
name: reference_말속도_상수_4벌
description: 대본 길이 버그가 계속 되살아난 뿌리 — 말속도 상수가 코드에 여러 벌이라 고쳐도 다른 곳이 옛 수를 말한다
metadata:
  type: reference
---

한국어 말속도(자/초)가 쇼핑쇼츠 코드에 **여러 벌** 있다. 2026-08-18 "대본이 계속 40초로 나온다"를
세 번 고치고도 재발한 뿌리가 이것이었다 — 그리고 세 번째 수리에서 **내가 네 번째 사본(8.19)을
`script_gate`에 새로 박은 것**이 드러났다.

- `edit_plan._SYLLABLES_PER_SEC = 5.7` (성우 14명 실합성 측정) × `_speech_speed()` 1.44 = 8.208 ← **정본**
- `backbone.py:14` 별도 5.7
- `produce.html`의 JS 상수 (주석에 "둘 중 하나만 바꾸면 화면과 계획이 어긋난다"고 이미 경고돼 있었다)
- ~~`script_gate.SPEECH_CHARS_PER_SEC = 8.19`~~ → 2026-08-18 제거, `edit_plan` 값을 빌려 쓰게 단일화
  (모듈 `__getattr__` 지연평가로 import 순환 회피)

**How to apply:** 길이·초 계산을 새로 쓸 일이 생기면 상수를 적지 말고 `script_gate._speech_cps()`
(=edit_plan 값)를 부른다. 화면(JS)이 필요하면 서버 응답에 `cps`로 실어 보낸다 — 화면에 숫자를 박으면
배속을 튜닝한 날 화면·판정·계획이 서로 다른 초를 말한다.

**Why:** 같은 판단이 두 곳에 적히면 반드시 어긋난다(CLAUDE.md 0순위-B). 이 유형은 증상이
"고쳤는데 또 그러네"로 나타나 원인 추적이 오래 걸린다. 관련: [[feedback_deploy_discipline_during_incident]]
