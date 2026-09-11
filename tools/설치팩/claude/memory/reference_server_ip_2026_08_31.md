---
name: reference_server_ip_2026_08_31
description: 쇼핑쇼츠·스탁브레인 서버 IP가 3.35.251.172로 또 바뀌었다 — 옛 IP로 SSH하면 죽은 인스턴스에 붙는다
metadata:
  type: reference
---

2026-08-31 실측: `shoppingshorts.duckdns.org` → **3.35.251.172**.
메모리·CLAUDE.md에 적힌 43.200.48.69로 SSH하면 **다른 인스턴스**에 붙는다 —
그쪽은 shopping-shorts가 inactive이고 포트 8849 리스너도 없어서
"서비스가 죽었다"로 **오진하기 딱 좋다**(이번에 실제로 그렇게 봤다).

**SSH 전에 항상 `nslookup shoppingshorts.duckdns.org` 로 현재 IP를 확인하라.**
IP는 이미 두 번 바뀌었다(3.39.179.148 → 43.200.48.69 → 3.35.251.172).

키: `C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem`
제작 job은 `shopping-shorts` 유닛이 아니라 **worker 유닛**에서 돈다 —
로그는 유닛 지정 없이 `sudo journalctl --since ... | grep -a` 로 훑어라.

관련: [[reference_server_ip_changed_2026_08_05]] · [[reference_deploy_truth_branch_ssh]]
