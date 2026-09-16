---
name: project
description: "쓰레드(Threads) 수집 축 라이브 — 로그인 불필요(헤더가 열쇠), 담기 배선의 조용한 구멍, 다음 단계"
metadata: 
  node_type: memory
  type: project
  originSessionId: f37bf2c6-4eb9-4310-ba93-863338d326bc
  modified: 2026-08-17T13:57:52.683Z
---

2026-08-17 라이브(origin/main 9611fd3a3). 쓰레드 = 숏템메이커 다음 버전 축.
한 게시물에 **무자막 영상 + 한국어 말맛 캡션 + 쿠팡링크**가 한 세트로 들어있다(본문 1/2 + 이어진 글 2/2).

## 핵심 실측 (추측 금지 — 여기서 두 번 뒤집혔다)

- **로그인·프록시·브라우저 전부 불필요.** 익명 GET이 200/1,080,480B로 데이터를 다 준다.
  ★단 **헤더가 열쇠**: UA만 보내고 `Accept`·`Accept-Language`·`Sec-Fetch-*`·`Upgrade-Insecure-Requests`를
  빼면 메타가 알맹이 없는 껍데기를 준다. 내가 이걸로 "로그인 필요"라고 잘못 결론냈다.
- 데이터는 SSR HTML 안 Relay 페이로드(`<script type="application/json">`의 `__bbox`)에 인라인.
  노드는 경로 하드코딩 말고 **모양으로** 찾는다(`code` + `like_count`/`text_post_app_info`).
- **캐러셀(1/2·2/2)이 주력 모양** — 영상이 최상위 `video_versions`가 아니라
  `carousel_media[i]["video_versions"]`에 있다. 폴백 없으면 영상을 통째로 놓친다.
- yt-dlp 미지원(`threads extractor: NONE`) → `_download_threads`가 HTTP로 mp4 직접 받는다.
- CDN이 인스타와 동일(`scontent-*.cdninstagram.com`) → `/api/video` 프록시 그대로 재사용.

## 함정 (전부 에러 없이 조용히 잘못되던 것들)

1. **`_GRAB_MEDIA_HOSTS`에 없는 호스트는 조용히 버려진다** — cdninstagram 추가로 해결.
2. **`download_any` 화이트리스트에 없으면 담기는 성공하고 제작에서 100% 실패** — "담겼어요"가 거짓말이 된다.
   최종 리뷰 후 재현으로 잡았다. 새 플랫폼 붙일 때 **담기와 다운로드는 반드시 세트로** 확인하라.
3. **`"instagram.com" in url` 부분문자열**이 `cdninstagram.com`도 잡아 인스타 세션 경로로 오배송.
   호스트 판정은 `host == d or host.endswith("." + d)`로 통일(`_grab_platform` 방식).
4. **`_enrich_grab`은 화이트리스트 8키만 저장** — `video_url`은 저장 안 된다(호출부 확장 필요, 미해결).
5. 인스타 표(`channel_archive`·`reel_history`) 불가침 — `hits_since`가 `platform` 인자를 받고도
   SQL에서 안 써서, 섞으면 인스타 랭킹에 쓰레드가 조용히 흘러든다.

## 남은 일

- 히트작 문턱 **미정** — 200~300건 쌓은 뒤 분위수로(표본 5건으로 정하면 틀린다).
  쓰레드는 참여 규모가 인스타와 딴판(좋아요 4~15인데 조회 5,013).
- 후속 계획 2: 키워드 검색 수집 / 랭킹 탭 노출(`ranking.build_overseas_items` 재사용) / 매일 크론.
- 미검증: 계정 1개만 실측 · 담기→제작소 종단 · Playwright 폴백.

상세: `handoff/쓰레드수집.md`, 설계 `docs/superpowers/specs/2026-08-17-쓰레드수집-design.md`
관련: [[feedback_check_shape_before_string_ops]] [[reference_silent_fallback_pipeline_undo]]
