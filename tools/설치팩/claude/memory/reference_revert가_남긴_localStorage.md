---
name: reference_revert가_남긴_localStorage
description: 코드를 되돌렸다 다시 올려도 브라우저에 남은 localStorage 값이 이겨서 옛 화면이 계속 보인다 (촘촘히=body.tight 사례)
metadata:
  type: reference
---

**"고객만 옛 화면"의 원인이 서버 버전이 아닐 수 있다.** 2026-08-28 실사고:

- 2026-08-26 16:18 `a6a5b95f0`이 track/필름롤러 병합을 통째로 Revert → 고객 3단계가 옛 배치로 돌아갔다.
- 그 기간에 고객이 `[▤ 넓게]`를 누르면 `sceneLab:tight='0'`이 **브라우저에 저장**된다.
- 2026-08-28 09:00 `fc67c8460`으로 코드를 다시 올렸지만 **저장값이 기본값을 이겨서** 계속 옛 배치.
  `body.tight`가 꺼지면 `#topband > #playerhost`(미리보기를 훅 옆으로) 규칙이 안 걸리고,
  `#rollbay:empty{min-height:0}` + `::before{display:none}`로 필름 펼칠 자리도 사라진다.

**교훈**
- 화면 차이를 보면 **서버 파일부터 실측**하라(ssh md5 / grep). 같으면 원인은 클라이언트에 남은 상태다.
- localStorage는 **배포로 못 지운다.** 되돌림·재배포로 오염됐으면 `<키>Reset:<날짜>` 도장을 두고 **딱 한 번** 걷어낸다.
  두 번 하면 사용자가 스스로 바꾼 뜻을 뺏는다.
- Revert를 할 때는 "그 사이 사용자 브라우저에 무엇이 저장되나"까지 봐야 한다.

관련: [[reference_미리보기_pv쿠키_되돌리기]] · [[reference_share_link_memory_dies_on_restart]]
