# 렌더 점검 도구 (2026-09-22, 장면폰트 트랙)

"미리보기와 렌더가 다르다"를 짐작 말고 재는 도구. 전부 실제 코드 경로(가짜 응답 없음).

| 파일 | 하는 일 | 쓰는 법 |
|---|---|---|
| `run_compose.py` | 서버에서 받은 청소본 mp4 + `job956.json`(timeline·snapshot·headcopy)으로 `scene_style.compose`를 로컬에서 그대로 돌리고, 조각(part)마다 freezedetect·애니메이션·카메라를 표로 | `python run_compose.py <폴더> <태그> ['{"hookMotion":""}']` — 폴더에 `clean.mp4`·`job956.json` 필요 |
| `motion.py` | 조각마다 청소본 vs 최종 조각의 "연속 프레임 변화량"을 비교 — 장면꾸미기가 멈춤을 만들었나 판정 | `python motion.py <run_compose 폴더>` |
| `measure_like_renderer.py` | 렌더러(puppeteer)와 **같은 조건**(1920×2200 창, 미리보기 1080×1920 고정, qa=1)으로 편집기를 띄워 글자 크기·줄 수·잉크 폭을 잰다 | `python measure_like_renderer.py <work_base/scene-style-request.json 있는 폴더> <태그>` (8773 서버) |
| `hook.js` | 페이지에 넣으면 `fontSize` 대입마다 값과 호출 스택을 `window.__fs`에 쌓는다 — "누가 글자를 줄였나" 추적 | Playwright `pg.evaluate(open('hook.js').read())` 뒤 `show(i)` → `window.__fs` |

실측 기록은 `handoff/장면폰트.md` 2026-09-22 밤2·밤7 항목.
서버에서 timeline·snapshot을 뽑는 파이썬 조각은 핸드오프 밤2 항목 참고(Store → _beat_timeline → context_for).
