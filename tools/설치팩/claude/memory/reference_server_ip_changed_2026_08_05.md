---
name: server-ip-changed-2026-08-05
description: "라이브 서버 IP는 자꾸 바뀐다(3.39.179.148 → 43.200.48.69 → 3.35.251.172). SSH 전에 nslookup으로 확인하라 — 옛 IP는 살아 있어도 '옛 서버'라 더 위험하다."
metadata:
  node_type: memory
  type: reference
  originSessionId: b99b6e41-511a-43a9-a658-330c51f97bf4
  modified: 2026-08-31T06:58:25.994Z
---

라이브 서버 IP는 **여러 번 바뀌었다**. 시간순:
`3.39.179.148` → `43.200.48.69`(2026-08-05) → **`3.35.251.172`**(2026-08-31 확인).

**Why:** 옛 IP가 죽어 있으면 타임아웃으로 금방 안다(2026-08-05: 그래서 1시간 낭비).
그런데 **2026-08-31에는 옛 IP(43.200.48.69)가 살아 있었다.** SSH도 붙고, `/home/ubuntu/
lotto-stock-wiki`도 있고, DB 파일도 있었다 — 다만 **몇 달 묵은 옛 데이터**였다.
그래서 "고객이 없다 / 작업이 다 정상이다 / 웹 프로세스가 안 떠 있다"는 **틀린 결론**이
그럴듯하게 나왔다. 죽은 IP보다 살아 있는 옛 IP가 훨씬 위험하다.

실제로 이날 김데릭 TTS 실패 조사에서 옛 서버의 `mix_jobs`를 보고 "실패 기록 없음"으로
헛다리를 짚었다. 진짜 서버에는 같은 시간대에 5개 계정이 동시에 실패한 기록이 있었다.

**How to apply:** SSH 하기 **전에** 항상 먼저:
```
nslookup shoppingshorts.duckdns.org      # duckdns가 유일한 진실
```
붙은 뒤에도 한 번 검증하라 — `git log --oneline -1`이 오늘 main과 맞는지,
`systemctl is-active shopping-shorts`가 active인지. 옛 서버는 커밋이 뒤처져 있고
웹 서비스가 inactive라 **두 줄이면 갈린다**.

키·경로·서비스 이름은 그대로([[reference_deploy_truth_branch_ssh]]).
IP를 CLAUDE.md·메모리에 **박아두지 마라** — 박는 순간 썩는다. nslookup이 정답이다.
