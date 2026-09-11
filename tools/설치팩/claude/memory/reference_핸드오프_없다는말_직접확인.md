---
name: reference_핸드오프_없다는말_직접확인
description: 핸드오프의 "그 함수는 없다"를 믿지 마라 — 틱톡 수집은 이미 있었고 4줄 삭제로 끝났다. 배포 확인은 mtime vs 프로세스 기동시각으로
metadata:
  type: reference
---

**"X 기능이 없어서 못 한다"고 적힌 기록을 만나면, 그 X를 직접 열어봐라.**

실사고(2026-08-25, 챌린지관리): `handoff/챌린지관리.md`에 **"틱톡은 단건 조회 함수가
없다(tiktok_client는 계정 단위뿐)"** 라고 적혀 있었고, 그래서 "다음 할 일 = 틱톡 단건
수집기 신규 개발"로 잡혀 있었다. 실제로는 **`probe_grab_meta`가 처음부터 틱톡 oEmbed
폴백을 갖고 있었다**(`media_download.py:104`). 챌린지 수집부가 스스로
`if platform == "tiktok": skipped` 로 막고 있었을 뿐 — **차단 4줄 삭제로 끝났다.**

실측: `@tiktok/video/7106594312292453675` → thumbnail·title·channel ✅ / views ❌.

같은 세션에서 두 번째 사례: "참가자 등록 UI가 없다"고 단정했다가 grep으로 정정
(`admin.html:278`에 버튼이 이미 있었다). **화면 하나만 보고 "없다"고 말하지 마라 —
그 API를 부르는 곳을 전부 grep하라.**

## 배포 반영 확인은 이렇게 (셋 중 앞의 둘은 못 쓴다)

| 방법 | 결과 |
|---|---|
| `openapi.json` grep | **0바이트다.** 라우트 유무를 못 가른다 |
| HTTP 상태코드 | 인증이 먼저 잡아 **없는 경로도 401**. 판별 불가 |
| ✅ `app.py` mtime **<** 웹 프로세스 기동시각 | 이거면 새 코드가 떠 있다 |

`systemctl show shopping-shorts -p ActiveEnterTimestamp --value`

## `auto_deploy.sh`는 웹 재시작을 미룬다

**고객 접속 중이면 최대 30분(`MAX_DEFER_SEC=1800`) 연기**한 뒤 강제 재시작한다.
그동안 **정적파일(HTML/JS)만 반영되고 파이썬은 옛 코드**인 구간이 생긴다 →
"화면은 바뀌었는데 버튼이 안 먹는다"의 정체. 손대지 말고 기다리면 된다.

## Windows에서 JS 문법검사 거짓 통과

`node --check <(sed ...)` 는 **프로세스 치환이 안 먹어** `MODULE_NOT_FOUND`가 나는데,
뒤에 `&& echo OK`를 붙이면 **통과처럼 보인다**. 임시파일로 써서 검사하고 `exit=$?`를 봐라.
관련: [[reference_gate_flaky_node_stdin_guard_hole]]

관련: [[feedback_verify_before_claim_and_act]] · [[reference_deploy_truth_branch_ssh]]
