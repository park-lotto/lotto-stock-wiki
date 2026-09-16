---
name: reference-async
description: "async 핸들러가 blocking 호출로 이벤트루프를 멈추면 \"상대가 우리 URL을 못 읽는다\"는 남탓 에러로 나타난다 (Buffer SNS예약 2026-08-30)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 90d990ff-ad0f-4344-9269-d0723c7d1841
  modified: 2026-08-30T08:01:50.777Z
---

`api_buffer_schedule`이 **async인데** blocking urllib(`buffer_api.schedule_video`)을 그대로 불러,
createPost가 도는 **10초 동안 서버 전체가 정지**했다. 그 사이 Buffer가 영상 URL을 가지러 왔다가
응답을 못 받고 `Invalid post: Video could not be read from its URL`로 거절했다.
고침 = `await run_in_threadpool(...)` 한 줄.

## 왜 3번이나 오진했나 (Opus 세션 실패 기록)

증상이 "**상대(Buffer)가 우리 영상을 못 읽는다**"로 나와서, 계속 **영상·URL 쪽만** 팠다:
1. HEAD 404 → (이전 세션이 이미 고쳐둔 것) 아님
2. Range 미지원(starlette 0.36 FileResponse) → 실제 개선이지만 **원인 아님**
3. moov가 파일 끝(faststart 아님) → 실제 개선이지만 **원인 아님**

세 번 다 "그럴듯한 결함을 찾음 → 고침 → 사장님께 눌러보라고 요청 → 또 실패"를 반복했다.

## 결정적 단서를 잘못 읽었다

**앱 밖 스크립트로 직접 API를 쏘면 전부 성공**했다. 나는 이걸 "그럼 고쳐진 것"으로 읽었지만,
진짜 의미는 **"핸들러 경로에서만 실패한다 = 차이는 핸들러뿐"** 이었다.
→ ★**"내 시험은 되는데 화면은 안 된다"는 그 차이 자체가 답이다.** 거기부터 파라.

## 판정법 (다음에 3분 만에 잡는 법)

```
□ 로그의 시각을 대조하라 — 상대의 검증요청 도착 시각 vs 우리 응답 완료 시각
   실측: Buffer HEAD 도착 16:30:33 / 처리 완료 16:30:43 → 10초 묶였다가
         createPost 응답과 **정확히 동시에** 풀렸다 = 루프가 막혀 있었다는 지문
   (정상일 때는 HEAD+GET이 1초 안에 끝난다)
□ 앱 밖에서 같은 호출이 성공하면 → 코드가 아니라 **실행 맥락**을 의심하라
□ async def 핸들러 안에서 requests/urllib/subprocess를 직접 부르는 곳을 grep하라
```

## 남은 위험

같은 모양이 더 있을 수 있다 — async 핸들러에서 blocking 외부호출을 직접 부르는 곳 전수 점검이
필요하다(이번 grep에선 buffer 계열은 schedule 하나뿐, channels는 sync def라 안전).

관련: [[reference_silent_fallback_pipeline_undo]] · [[feedback_verify_before_claim_and_act]]
