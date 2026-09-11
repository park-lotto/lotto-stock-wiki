---
name: project
description: "레퍼런스 영상 카드에 채널·지표·인기댓글·캡션 표시(렌즈+제작소). 유튜브 자동/비유튜브 관리자, 라이브"
metadata: 
  node_type: memory
  type: project
  originSessionId: c2be48e5-e426-4780-88c5-a0a716b6d58f
  modified: 2026-07-22T04:54:25.863Z
---

레퍼런스 유사영상(렌즈 패널)과 제작소 재료(mix_basket) 리스트의 영상 카드에 **출처 채널명·채널URL·구독자 / 조회·좋아요·댓글수·업로드일 / 인기댓글 상위 5 / 원문캡션 전체**를 표시. 2026-07-22 라이브(main `b88dd8c21`).

- **범위**: 유튜브=자동(뷰포트 진입 시 IntersectionObserver로 lazy `POST /api/enrich`, 무료 YouTube Data API+기존 `YOUTUBE_API_KEYS` 로테이션). 틱톡·인스타·샤오홍슈·도우인=**관리자(customer_id===0)만** "ℹ️ 정보 채우기" 버튼(Apify 유료라 비용통제). **비유튜브 실조회 Apify는 아직 스텁** — 버튼·게이트·배선만 있고 no_data 반환.
- **핵심 파일**: `youtube_client.enrich_youtube(url)`(videos+channels+commentThreads 합성, quota는 실제 403일 때만) / `store.source_enrichment` 테이블(url키 7일 TTL, mix_basket 안 건드림) / `app.py POST /api/enrich`(캐시우선·유튜브자동·비유튜브 force+`_require_admin`) / `renderEnrich`·`enrichCard`·`forceEnrich`는 index.html·produce.html **양쪽에 복제**(별도 페이지라 공유불가).
- **교훈**: produce.html의 로컬 `esc()`가 `"`를 안 escape해 `href="${esc(channel_url)}"` XSS방어가 무력이었음 → esc()에 `"`→`&quot;` 추가로 소스 하드닝(index.html esc는 원래 됨). 두 프론트 복제본은 seam 리뷰로 일관성 확인 필수.
- **후속**: ①비유튜브 Apify 실조회(같은 자리) ②유튜브 조회의 일시적 네트워크실패가 no_data로 7일 캐시되는 것 수정(quota처럼 비캐시). 둘 다 `app.py`/`youtube_client` 같은 지점.
- **미검증**: 라이브 실카드 1장(유튜브 자동표시+비유튜브 관리자버튼 클릭) 청감/눈확인은 배포 후 사람이 해야 함.

관련: [[project_lens_cn_search]] [[project_제작소_어긋남구제]] [[reference_local_tts_silent_mock_trap]]
