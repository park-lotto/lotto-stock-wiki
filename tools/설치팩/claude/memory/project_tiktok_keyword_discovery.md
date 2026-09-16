---
name: project_tiktok_keyword_discovery
description: "쇼핑쇼츠 틱톡 키워드검색 발굴 — 무료불가 실증, Apify B2 채택, 노브3개 설계확정 코드만 남음"
metadata: 
  node_type: memory
  type: project
  originSessionId: abb8cd30-fe11-4ef5-9039-9f03ddef7111
---

쇼핑쇼츠 레퍼런스 랭킹에 **틱톡 키워드검색 발굴** 추가 (2026-07-13 설계확정, 미구현).

**실증된 사실 (재조사 금지):**
- 틱톡 무료 발굴 불가: yt-dlp `/search`=Unsupported URL, `/tag`=차단(No working app info). **계정방식·개별영상 yt-dlp만 됨.**
- B1(무료 로그인 크롬 자동화): claude-in-chrome으로 검색 24개 수확 실증했으나 Playwright설치+로그인+봇취약+**운영자전용(고객불가)** → 폐기.
- **B2(Apify) 채택**: `clockworks/tiktok-scraper`, `searchQueries` 키워드검색 지원, **$1.70/1,000건**(30개=5센트), 월 $5무료=~2,900건. 서버·고객 공용.

**설계 (노브3개, 기본값 조정가능):** 검색당개수(기본60→우리필터 top30) / 사용자 하루수집횟수(기본10) / 월예산상한 킬스위치(기본$5). 인스타 apify_client.py·JWT 재사용.

**이미 배포됨**: 틱톡 Phase2 **계정시드** 방식(커밋 c43c0042, 서버 active). 이번 건은 그 위에 키워드검색 얹기. 상세 핸드오프=repo `NEXT_SESSION.md` 🅒 트랙. 관련 [[project_쇼핑쇼츠_자동화]] [[project_shopping_shorts_discovery]] [[reference_deploy_truth_branch_ssh]]
