---
name: feedback_partial_block_not_account
description: 크롤 소스 일부만 끊기면 계정/플랫폼 차단이 아니라 소스 자체 문제부터 의심
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2c4a2495-1d45-4499-8625-098c5179ec26
---

여러 소스(텔레 채널 등)를 크롤하는데 **일부만** 데이터가 끊기면, 계정 차단·플랫폼 shadow limit을 성급히 추정하지 말 것. 그런 차단은 보통 **계정 전체**에 걸린다.

**Why:** 2026-07-05, 텔레 21채널 중 2채널(realtime_stock_news·rocket_news1)만 7/3 이후 크롤 안 됨. 세션H가 "shadow limit 추정"으로 오진. 사용자가 "텔레 차단은 전체가 막히지 2채널만 선별 안 됨"으로 반박 → 재조사하니 **공개프리뷰(t.me/s/)도 7/3까지만** = 채널이 실제로 게시를 멈춘 것(휴면/폐쇄). 계정·크롤봇 멀쩡.

**How to apply:** 일부 소스만 끊기면 (1)그 소스의 **공개 접근**(로그인 없이 t.me/s/, RSS, 웹)으로 최신 상태 먼저 확인 (2)정상 소스와 대조 (3)공개도 끊겼으면 소스 자체 중단, 공개는 살아있는데 우리만 못 보면 그때 계정-소스 관계(개별 차단/이전) 의심. 세션H처럼 "공개프리뷰 활발" 같은 관찰은 실제 날짜를 찍어 검증. [[project_telegram_ingest]] [[feedback_self_verify_before_reporting]]
