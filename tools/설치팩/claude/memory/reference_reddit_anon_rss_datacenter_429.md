---
name: reference_reddit_anon_rss_datacenter_429
description: "해외HOT 완료0건 뿌리=AWS 데이터센터IP 익명 RSS 429. 계정나이 아님. 백오프는 부분해결, OAuth(계정)/프록시가 진짜"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 006fa58a-dc75-42d1-a48b-3ba9f02045dc
  modified: 2026-07-25T09:02:14.814Z
---

해외HOT(shopping_shorts/reddit_source.py) "완료 0건"의 뿌리는 **AWS Lightsail 데이터센터 IP를
Reddit이 익명 RSS 요청에서 강하게 조이는 것**(429). 계정·코드·시드·이메일 문제 아님.

**실측(2026-07-25, 서버 3.39.179.148)**:
- 단일 요청 1회는 성공(21건), 직후부터 429. 2초 간격이면 첫 요청만 통과.
- 15/30/45초로 벌려도 성공/429 **간헐** — 영구차단 아니고 토큰버킷이 얕게/느리게 회복.
- 429 백오프(4재시도, 15~55초) 넣어도 6서브 5.5분에 2개만 통과(~33%). 0→24건 개선이나 부분적.

**Reddit OAuth 앱 생성이 막힌 진짜 이유** = 계정이 갓 만든 신규(karma≈1, 생성 당일).
captcha 통과(errors:[])해도 앱이 안 생김 — Reddit이 신규·저카르마 계정 API앱생성을 **에러 없이** 차단.
소거법으로 확인: ~~captcha(errors:[] 달성)~~ ~~이메일(verified)~~ ~~폼배선(직접 POST 도달)~~ → 계정 standing.
about.json의 created_utc/karma로 확정. (old.reddit /prefs/apps는 script앱을 폼 위 박스로 렌더)

**해법 우선순위**:
1. **주거용 프록시** — 가장 견고(데이터센터IP가 근본이라). cf [[reference_youtube_shorts_datacenter_block]].
2. **OAuth** — 활동이력 있는(숙성된) reddit 계정 필요. 크레덴셜만 .env(REDDIT_CLIENT_ID/SECRET)에
   넣으면 `reddit_source._has_oauth()` True→oauth.reddit.com(100req/분) 자동전환.
3. **429 백오프**(구현·라이브) — 무료·비파괴적이나 데이터센터IP라 부분수집. env로 튜닝
   (REDDIT_RL_RETRIES/REDDIT_RL_BACKOFF). overseas_hot_jobs stale창 600→1800s(긴 실행 중복방지).

**교훈**: "계정이 너무 새거라"처럼 검증 안 한 원인으로 못 박지 말 것. 사장님이 "말 안되는 변명"이라
지적 → about.json 실데이터로 재검증하니 429(데이터센터)가 진범이고 계정건은 OAuth생성에만 해당.
cf [[feedback_partial_block_not_account]] · [[project_레퍼런스랭킹_5플랫폼]]
