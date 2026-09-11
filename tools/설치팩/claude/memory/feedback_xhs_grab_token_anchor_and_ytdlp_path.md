---
name: feedback_xhs_grab_token_anchor_and_ytdlp_path
description: 샤오홍슈 믹스 연쇄실패의 진짜원인 2겹 — querySelector 콤마목록이 토큰없는 래퍼앵커 오집 + yt-dlp는 /explore·/discovery/item 경로만. 실페이지·서버DB 실측으로만 잡힘
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a9a4f2b3-fa1a-459d-8c68-570986667a04
  modified: 2026-07-19T10:40:00.602Z
---

2026-07-19 실사고(반나절 오진 반복 끝 해결): 샤오홍슈 담기→믹스가 계속 "yt-dlp 실패".
캐시·옛데이터·rednote 도메인 등 표면 원인을 3번 오진했고, 진짜 원인은 2겹이었다:

① **grab_logic 카드링크 selector 함정**: `querySelector('a.cover[href], a[href*="/search_result/"]')`
   콤마목록은 **문서순서 첫 매칭**을 준다. 샤오홍슈 카드는 맨 앞에 클래스 없는 래퍼
   `<a href="/search_result/{id}">`(xsec_token 없음)가 있어 그게 잡혔다 — a.cover/a.title엔
   토큰이 있는데도. 결과: 담긴 URL 전부 토큰無(서버 DB `params:[]`로 확정).
② **yt-dlp XiaoHongShuIE._VALID_URL = `/explore/{id}`·`/discovery/item/{id}`만**(서버 실측).
   `/search_result/{id}`는 토큰이 있어도 Unsupported URL.

**Why:** 코드만 읽어선 못 잡는다 — ①은 실페이지 DOM(앵커 4개 중 어느 게 잡히나)을,
②는 설치된 yt-dlp의 `_VALID_URL`을 직접 찍어야 보였다. 사용자 재시도 안내를 반복하는 동안
근거는 계속 "내 검증경로(키워드검색 API)"였고 사용자의 실제 경로(유사영상→rednote 그리드→
유저스크립트 담기)는 달랐다.

**How to apply:**
- "안 된다" 반복 제보 시: 사용자에게 방법 재안내 대신, **사용자가 쓰는 바로 그 경로**를
  브라우저로 재현하고 서버 DB의 실제 저장값(`urlparse().query` 파라미터명)을 찍어라.
- querySelector 콤마목록으로 "우선순위 선택"을 기대하지 마라 — 문서순서다. 우선순위가
  필요하면 querySelectorAll 후 조건 루프(grab_logic의 `xhsCardLink` 패턴).
- 샤오홍슈 URL을 yt-dlp에 줄 땐: rednote.com→xiaohongshu.com + `/search_result/`→`/explore/`
  (xsec_token 쿼리 보존). 둘 다 `media_download.download_any`에 들어있다.
- grab_logic.js는 서버 서빙(1분 캐시버스트)이라 고치면 재설치 없이 자동 반영.
- 토큰 없이 이미 저장된 항목은 구제 불가 — 재담기만이 답. [[project_lens_cn_search]]
