---
name: reference
description: 최종렌더 네모X(두부)의 원인은 깨진 파일이 아니라 영문 전용 폰트를 한글 목록에 넣은 것 — 파일 존재만 보는 검사는 못 잡는다. 판정은 .notdef 마스크(Pillow)
metadata: 
  node_type: memory
  type: reference
  originSessionId: 72660647-e585-4eb7-ab22-38a0922ff213
  modified: 2026-08-26T07:29:17.692Z
---

2026-08-26 사장님 제보 "폰트 받았는데 최종렌더하니 네모에 x". 원인은 **깨진 파일이 아니라
분류 오류**였다. `OkMallangW.ttf`('옥 말랑')는 OKFont가 낸 **영문 전용** 폰트로 글리프 81개에
한글이 0자다. 파일 자체는 정상 TTF라 브라우저도 ffmpeg도 오류 없이 로드했고, 목록·렌더가
모두 "static/fonts에 파일이 있는가"만 보고 있어서 세 층을 전부 통과한 뒤 고객 영상에서
처음 드러났다. 눈누 `Ok Mallang W`(font_page/1796)·`B`(1795) **둘 다 "형태: 영문"** —
한글판 옥말랑은 없다.

**Why:** "파일이 있다 = 쓸 수 있다"가 아니다. 폰트는 **파일 존재와 글리프 존재가 별개**고,
없는 글자는 오류가 아니라 조용한 `.notdef`로 그려진다. 실패가 예외로 안 드러나므로 검사를
직접 심지 않으면 영원히 고객이 먼저 발견한다. 25KB라는 크기만 보고 "파일 손상"으로 첫
진단을 냈다가 틀렸다 — **크기·이름은 증거가 아니다.**

**How to apply:**
- 폰트 문제엔 파일이 아니라 **글리프를 봐라**. 판정: 없는 글자는 모두 같은 `.notdef`로
  그려진다 → PUA 문자(`U+F8FF`·`U+E05C`) 두 개의 마스크가 같으면 그게 `.notdef`이고,
  어떤 글자의 마스크가 그것과 같으면 그 글자는 없는 것. **Pillow만으로 정확히 된다**
  (fontTools는 `requirements.txt`에 없다 — 서버 의존성 늘리지 마라).
- 라이브 구현: `video_assemble._missing_glyphs()` / 폰트 해석 단일 출구 `_font_ref()`
  (자막 `_resolve_seg_font` + 헤드카피 `_fixed_drawtext`가 같은 판단을 따로 적고 있던 것을
  통합 — 0순위-B), 목록 가드 `tools/sync_fonts.py::_check_hangul()`,
  테스트 `shopping_shorts/tests/test_font_glyph_fallback.py`.
- 새 폰트 추가: 파일 넣고 `fonts.json` 한 줄 → `py tools/sync_fonts.py`. 한글 없으면 거기서
  막힌다. 영문 전용이면 `"latin": true` + 이름에 '영문' 표기(사장님이 고르기 전에 보이게).
- **공백(U+0020)은 검사에서 제외**하라. 빙그레·리디바탕은 공백 글리프가 없지만
  `_lacks_space_glyph` 우회가 이미 처리한다 — 여기서 폴백시키면 고른 글꼴이 통째로 바뀐다.

관련: [[reference_gate_flaky_node_stdin_guard_hole]](이날 게이트도 단독 통과=오염이었다) ·
[[reference_silent_fallback_pipeline_undo]] · [[feedback_self_verify_before_reporting]]
