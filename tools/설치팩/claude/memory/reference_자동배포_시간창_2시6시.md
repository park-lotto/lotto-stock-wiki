---
name: reference-2-6
description: "서버 auto_deploy가 새벽 2~6시에만 배포한다 — \"3분 뒤 라이브\"는 더 이상 사실이 아니다"
metadata: 
  node_type: memory
  type: reference
  originSessionId: a7b67609-b922-4a13-9e8c-235d9cc95417
  modified: 2026-09-05T05:52:34.389Z
---

`deploy/auto_deploy.sh`가 **시간창 2~6시 밖에서는 배포를 미룬다**(2026-09-05 실측 로그:
`배포 대기(시간창 2~6시 밖) e860a27->01e8de0 — 급하면 [긴급] 커밋 또는 touch /home/ubuntu/DEPLOY_NOW`).
추가로 고객이 접속 중이면 **웹 재시작도 연기**한다(`웹 재시작 연기(고객 접속 중, 960초 경과)`).

즉 `track.py finish`가 "3분 뒤 라이브 반영"이라고 찍어도 **낮에는 반영되지 않는다.**
CLAUDE.md의 "push까지만 하면 3분 내 자동반영"도 이 시간창이 생기기 전 문장이다.

**즉시 배포하는 법 (고객 영향이 있으니 사장님 확인 후에만):**
- `touch /home/ubuntu/DEPLOY_NOW`
- 또는 커밋 메시지에 `[긴급]`

**그래서 0순위-A1(실제로 돌려보고 확실할 때만 "됐다")을 낮에는 못 지킬 수 있다.**
그럴 땐 "고쳤지만 라이브 실측은 못 했다 — 배포 시간창 때문"을 보고 첫 줄에 적고,
핸드오프에 다음 세션이 확인할 항목을 남긴다.

배포 상태 확인:
```
ssh -i C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem \
  ubuntu@$(nslookup shoppingshorts.duckdns.org | tail -2 | head -1) \
  "cd /home/ubuntu/lotto-stock-wiki && git log --oneline -1 && tail -6 /tmp/auto_deploy.log"
```
서버 IP는 계속 바뀐다 → [[reference_server_ip_2026_08_31]] 처럼 nslookup 먼저.
관련: [[feedback_프로그램수정은_실제로_돌려보고_확실할때만]]
