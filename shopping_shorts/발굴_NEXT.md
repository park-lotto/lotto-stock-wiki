# 쇼핑쇼츠 채널 발굴·정리 — 이어서 할 일 (2026-07-12 저장)

라이브: https://shoppingshorts.duckdns.org → 사이드바 **🔎 채널 발굴·정리**
(로그인 후, 변경 반영 안 보이면 **Ctrl+Shift+R** 강력새로고침)

## ✅ 완성·배포됨
- **발굴 / 죽은채널 정리** 2탭
- **🔄 업데이트**: 6개 카테고리(`#주방템 #살림템 #인테리어 #자취템 #생활꿀템 #뷰티템`) 자동 검색
  - 한국어 붙은말 0건 → `#해시태그` 자동 폴백
  - **채널 단위**(채널당 댓글 최다 릴스 1개로 접음)
  - **백그라운드 잡**(즉시 반환 + 진행상황 폴링, 서버 재시작 내성)
- **지표 탭**: 전체(댓글)/속도(시간당)/가속/참여밀도 — 레퍼런스 랭킹과 동일
- **카드 표시**: 구독자수 · 최근N일 영상수
- **조절 3종(UI)**: 기간(2/3/7일) · 개수(40/80/120) · 누적모드(켜면 계속 쌓임, 새로고침 복원)
- **배지+필터**: 🔥핫(등급 🔥🔥🔥) · 🆕뉴(팔로워<1만) / 전체·핫·뉴 필터칩
- **목록추가**: DB(discovered_channels)에 저장 → collect()가 메인 랭킹에 편입(엑셀 원본 미변경)
- **죽은채널 정리**: 릴스 안 잡힌 엑셀채널 → 추적 제외(소프트삭제, 복구 가능)
- **검증 완료**: 엑셀 440개 vs 발굴 74곳 교집합 0 (= 엑셀에 없는 새 채널만 나옴 확정)

## ⚠️ 미결 — 내일 1순위
**팔로워/참여밀도 복구** (지금 구독자 0·참여밀도 0.00%로 뜸)
- 원인: Apify 팔로워 액터 2종(`apify~instagram-profile-scraper`, `apify~instagram-scraper`)이
  **유료 렌탈 체험 소진 → 403**. 17계정 전부. (코드 버그 아님, 외부 리소스)
- 방어는 돼 있음: 팔로워 실패해도 발굴은 정상(`discovery._safe_profiles`).
- **방향 선택 필요 (사용자 A/B/C 미결):**
  - **A(추천)**: 무료 — 인스타 공개 프로필 페이지 HTML의 `og:description`("N Followers, ...")를
    `requests`로 파싱해 followers 채우기. Apify 안 씀. **검증 필요**(IG 로그인월·429 차단 리스크).
    성공 시 `apify_client.fetch_profiles` 대체 → 참여밀도·🆕뉴배지 영구 복구.
  - **B**: 새 Apify 계정 추가(렌탈 체험 재생, 또 소진되는 임시방편)
  - **C**: 팔로워 포기(속도·댓글·가속만으로 운영)

## 그 외 남은 것
- 배지 기준값 튜닝: 뉴=팔로워<1만, 핫=등급🔥🔥🔥 (실사용 후 조정, 값은 discover.html 상단 상수/필터)
- 가속(accel)은 **2회차 업데이트부터** 값 참(snapshots 이력 필요) — 관찰
- (선택) 카테고리 추가: `app.py _DISCOVER_CATEGORIES` 한 줄 (#캠핑 #육아 #반려동물 등)

## 핵심 파일
- `discovery.py` — discover/discover_multi/merge_feeds/_rank_reels/_safe_profiles/find_inactive
- `discover_jobs.py` — 업데이트 백그라운드 잡(start/status), 청크 병렬수집
- `instagram_search.py` — search_channels + 해시태그 폴백 + _owner_username
- `apify_client.py` — fetch_profiles(팔로워, 현재 403), fetch_reels
- `app.py` — /api/discover, /api/discover/update(잡시작), /status, /feed, /prune/*
- `static/discover.html` — 발굴 UI(탭·조절·배지·필터·폴링)
- `store.py` — discovered_channels / removed_channels / discovery_feed

## 운영 메모
- 업데이트는 Apify 여러 번 호출 → 1~3분. 백그라운드라 화면 안 멈춤.
- 배포: 커밋 → `git push origin main` → 3분 크론 자동, 급하면 수동
  `ssh ubuntu@3.39.179.148` → `cd lotto-stock-wiki && git stash push -u -- raw/ && git pull --ff-only && sudo systemctl restart shopping-shorts`
  (SSH키: `C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem`)
- 서버 raw/ 크롤데이터가 pull 막으면 `git stash push -u -- raw/`로 대피 후 pull.
