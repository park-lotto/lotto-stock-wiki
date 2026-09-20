---
name: reference_회원키가_제작에_안쓰였다
description: 회원 제미니 키 49개가 등록만 되고 제작에 안 쓰였다 — 합류가 웹 startup에만 걸려 워커는 한 번도 안 함
metadata:
  type: reference
---

2026-08-31 실사고(고객 5명 제작 불가).

**구조**: 제미니는 공용 풀(2026-08-24 사장님 정책) — 회원 키를 회사 풀에 합류시키고
회원은 무료로 쓴다. 합류는 `app.py:_resync_pools`가 한다.

**함정**: 그게 `@app.on_event("startup")`에만 걸려 있었다. 그런데 **영상 제작 job은
worker.py(별도 프로세스)에서 돈다** — 워커는 FastAPI 앱을 안 띄우니 startup이 없다.
실측: 웹 유닛엔 `[keypool] 제미니 사장님 12 + 회원 44 = 56`이 찍히는데
**워커 유닛 12개엔 24시간 0건**. 회원 키가 등록만 된 채 놀았다.

**진단법**: `sudo journalctl --since '24 hours ago' -o with-unit | grep -a keypool`
→ 웹에만 있고 워커에 없으면 이 함정이다.

**같이 확인할 것**
- 죽은 사장님 키: 401 `bound service account is deleted or disabled` (그날 6개)
- `_MAX_KEYS_PER_GROUP=30` — `.env`의 `GEMINI_API_KEY_31+`은 **조용히 무시**된다
  (100번대로 붙이면 아예 안 읽힌다 — 그날 실수했다)
- 키 소진 상태파일 `pipeline/atoms/.gemini_key_state.json`(gitignore) 리셋은
  즉시 반영되지만 **죽은 키까지 되살린다**

**응급 조치(배포 없이)**: 회원 키를 복호화해 `.env`의 `GEMINI_API_KEY_N`(N≤30)에
직접 넣으면 워커가 즉시 쓴다. 실측 사용가능 11 → 34개, 6연속 실패하던 고객이 바로 성공.

관련: [[reference_edl_plan_empty_rpm_429]] · [[reference_edl실패라벨은_사후추측이다]] · [[project_gemini_key_ops_2026_08_04]]
