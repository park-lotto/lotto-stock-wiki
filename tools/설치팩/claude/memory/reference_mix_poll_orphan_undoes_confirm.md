---
name: reference_mix_poll_orphan_undoes_confirm
description: "믹스확정 눌러도 원래대로" = 고아 폴러가 매초 loadMixReview를 불러 미리보기 상태를 되돌린 것
metadata:
  type: reference
---

2026-08-20 실사고 (job 5cc26d85d648). 사장님 제보: "믹스확정을 누르면 안되고 다시 원래대로. 이거 계속그럼"

**증상만 보면 버튼이 안 먹는 것 같지만 실제로는 다 됐다**: `POST /api/produce/mix/preview` 200,
서버 `preview_status=ready`. 화면만 안내문으로 돌아가 있었다.

**뿌리**: `MIX_POLL` 전역에 `setInterval`을 넣는 곳이 3군데(produce.html 4195·6367·8382)인데
아무도 앞의 것을 안 죽였다 → 핸들 잃은 **고아 폴러**가 살아 매초 `loadMixReview()` 호출.
`loadMixReview`는 "새 매칭"을 전제로 끝에서
`PREVIEW_STATUS=null` + `clearInterval(PREVIEW_POLL)` + `++PREVIEW_GEN`을 한다
→ 로더·완성 영상 삭제 + 진행 중 요청까지 무효(GEN 불일치로 조용히 return). 확정이 구조적으로 불가능.

→ `setMixPoll(fn, ms)` 한 곳으로 묶어 예약 전 죽이기를 강제. 2차 방어로
`_renderMixReviewBody` 끝의 무조건 안내문 덮어쓰기를 '렌더 중'엔 건너뛴다.

## 다음에 같은 제보를 받으면
- "눌러도 안 된다" → **먼저 서버 로그에서 그 POST가 갔는지, DB 상태가 뭔지 본다.**
  이번엔 서버가 이미 성공해 있었다. 프론트 코드부터 뒤지면 오래 걸린다.
  (실측 명령: `journalctl -u shopping-shorts --since today --no-pager | grep -a 'POST /api'`
   — **`grep -a` 없으면 로그를 binary로 보고 통째로 놓친다.** 이번에 그래서 한 번 오판했다.)
- **매초 반복되는 GET이 보이면 폴러가 겹친 것.** 정상 간격(2.5초)과 대조하라.
- 같은 전역 타이머 변수에 `setInterval`을 넣는 곳이 2군데 이상이면 그 자체가 버그다([[reference_freeze_whackamole_root]]와 같은 병).

## produce.html 게이트 하네스 함정
`tests/test_produce_preview_gate.py`는 produce.html에서 **함수 부분집합만 잘라 node로 실행**한다
(`_JUMP_/_MIX_/_HELPERS_/_PREVIEW_` 4구간). 새 헬퍼를 그 범위 **밖**에 정의하면 호출부에서
`ReferenceError`가 나고, try/catch에 삼켜져 엉뚱한 테스트가 깨진다(실측: C3 재매칭 게이트).
새 함수는 슬라이스 안에 두어라. 관련: [[feedback_harness_invented_contract]]

같은 날 같은 페이지의 다른 사고: [[reference_구어체대본_문장분리_2덩이]]
