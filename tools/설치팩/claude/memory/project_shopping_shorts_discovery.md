---
name: project_shopping_shorts_discovery
description: "쇼핑쇼츠 '채널 발굴·정리' 페이지 — 엑셀 밖 새 채널을 카테고리로 발굴. 완성·배포. 미결=팔로워 403"
metadata: 
  node_type: memory
  type: project
  originSessionId: ffbe2be1-0c02-4e33-959f-96e14e143043
---

쇼핑쇼츠 대시보드(shoppingshorts.duckdns.org)에 **채널 발굴·정리** 페이지 신규 구축·배포 완료(2026-07-12). 사용자가 준 엑셀 벤치마킹 목록(440채널) **밖의 새 채널**을 카테고리로 발굴한다.

**동작:** 🔄업데이트 → 6개 해시태그 카테고리(#주방템 등) 인스타 릴스 검색 → 게시 채널 추출 → 엑셀+발굴추가 채널 제외(중복0 검증됨) → 최근 48h~7일 릴스 수집 → 채널당 대표 릴스 1개 → 기존 랭킹엔진(댓글·속도·가속·참여밀도)으로 정렬. 백그라운드 잡+폴링(재시작 내성). 조절 3종(기간/개수/누적), 🔥핫·🆕뉴 배지+필터, 죽은채널 추적제외(소프트).

**교훈:**
- 검색 액터(data-slayer~instagram-search-reels)는 붙은 한국어("주방템")에 0건, **해시태그("#주방템")는 정상** → 폴백 필수.
- 발굴 결과 판별: **속도(지금뜨는)+참여밀도(작은데터지는)**가 핵심. 대형채널 댓글많은 건 당연.
- **팔로워는 릴스데이터에 없음** → 프로필 액터 필요한데 `apify~instagram-profile-scraper`·`apify~instagram-scraper` 둘 다 **유료 렌탈이라 계정 체험 소진 시 403**(소진≠일반 토큰 402). 트레드밀. 부가데이터 실패가 전체를 죽이지 않게 방어(_safe_profiles) 필수.

**미결(내일):** 팔로워/참여밀도 복구 방향 A(무료 IG 프로필 메타태그 파싱, 추천)/B(새계정)/C(포기) 선택 대기. 상세 핸드오프: repo `shopping_shorts/발굴_NEXT.md`.

관련: [[project_쇼핑쇼츠_자동화]] [[reference_deploy_truth_branch_ssh]] [[feedback_confirm_literal_feature_intent]]
