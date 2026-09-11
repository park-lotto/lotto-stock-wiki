---
name: project-5
description: 레퍼런스 랭킹을 인스타→5플랫폼 토글 확장. Phase1(틱톡 무료 자동랭킹) 라이브. Apify 금지·숏폼만·랭킹수집
metadata: 
  node_type: memory
  type: project
  originSessionId: 3a4e4fe8-65b3-4ceb-9dd8-a578fbdee899
  modified: 2026-07-24T09:05:14.979Z
---

쇼핑쇼츠 레퍼런스 랭킹(터진 숏폼 줄세우기)을 **인스타 전용 → 5토글**(인스타·유튜브·틱톡·
샤오훙슈·도우인)로 확장. 사장님 못박은 제약 3: **랭킹방식 수집 / 숏폼만 / 과금 없는 구조(Apify·건당과금 금지)**.

**실증(yt-dlp 실행, 2026-07-24)**: 틱톡 `tiktok:user` 채널목록 1회 호출로 조회수·좋아요·댓글·
timestamp·duration 전부 옴(무료) → 자동 랭킹 가능. 샤오훙슈·도우인은 프로필 extractor 없음
(`[generic]`/`Unsupported URL`) → "채널 훑기" 불가, 개별 URL 지표는 추출됨.

**아키텍처 = 하나의 랭킹화면, 두 레인**:
- 레인 A(인스타·유튜브·틱톡) = 채널 등록해두면 시스템이 훑음(지금 인스타 사용감).
- 레인 B(샤오훙슈·도우인) = 딥링크 검색(0원)으로 사람이 담기 → 담긴 URL yt-dlp 지표추출 → 담긴 것 안에서 랭킹.
- 강도지표: 속도=조회수÷경과시간, 참여밀도=(좋아요+댓글)÷조회수(팔로워 없이). 탭 라벨 유지, 툴팁에 플랫폼별 식.

**Phase 1 = 틱톡 자동랭킹 라이브**(main 4c9079466, SDD 트랙 레퍼런스랭킹개편):
- 틱톡 자동수집을 무료 yt-dlp 계정시드만으로. Apify 키워드검색은
  `service._collect_tiktok(include_paid_keywords=True)` 옵트인으로만 분리(삭제 아님, 발굴용).
- ★함정: 유료 끄면서 **월예산 지출게이트(add_tiktok_spend·budget_exceeded)가 무료수집을 429로
  막던** 버그 있었음 → 게이트 스킵. 단 **daily_limit(하루 횟수) 남용가드는 비용무관이라 유지**.
  유료 되살릴 때 복원법은 app.py collect docstring에 박아둠(est=n_lang×search_count×단가).
- 플랫폼 토글: 2026-07-21 "안 쓴다"고 `#platformTabs` display:none 숨겼던 걸 2026-07-24 사장님이
  직접 뒤집음 → 노출. 테스트도 숨김계약→노출계약으로 교체(test_ranking_platform_tabs).

**레퍼런스 채널 통합 관리페이지 `/refs` 라이브**(2026-07-24, main c8b2b144a, 관리자 전용):
사장님 "인스타처럼 등록해두고 쭉 뜨게, 관리페이지 엑셀식 등록". 인스타·유튜브·틱톡 3탭 +
여러 줄 붙여넣기 일괄등록 + 목록/삭제. **백엔드 신규 로직 0**(기존 API 재사용: 인스타
reference/register+discover/added+prune/remove, 틱톡·유튜브 seeds account). 사이드바 admin
전용 메뉴(ss-admin-only). route=voice_tune 패턴(게이트 정적라우트, mount 앞). 브라우저 검증 완료.
★함정: 틱톡 랭킹에 뜬 계정들(todaytable_kr 등)은 **옛 키워드검색 캐시**지 account 시드 아님 —
현재 틱톡 account 시드 0개. refs에서 @핸들 넣어야 계정 기반 무료수집 시작.

**/refs 인스타 관리 강화 라이브**(2026-07-24, main 07cb3eb7b): 사장님 "채널명·활동여부, 기본
저장분도, 관리 편하게, 정렬". 구독자수는 Apify 과금이라 사장님 제외 선택. 무료로 구현: **엑셀
기본+손등록 통합**(`/api/refs/instagram`=merge_tracked, 50→488개), **활동여부**(store.instagram_activity_map
=reel_history MAX(last_seen), 🟢활동중/🔴잠잠), 소스뱃지(기본/등록), 활동순 정렬, 검색. 표(칩→테이블).
★배포교훈: 동시세션 finish 데드락 → CLAUDE.md에 finish 전역 파일락 추가됨(자동 순번대기, kill·수동신호 불필요).
내가 _merge 폴더 rm→worktree stale, `git worktree prune`으로 복구(함부로 _merge 손대지 말 것).

**다음**: 틱톡 실등록 테스트(@핸들 붙여넣기→지금수집) / Phase2 유튜브 채널기반(공식 API, Shorts≤60s) /
Phase3 CN 담기랭킹. 설계: docs/superpowers/specs/2026-07-24-레퍼런스랭킹-5플랫폼확장-design.md
+2026-07-24-레퍼런스채널-통합관리페이지-design.md
[[reference_mix_stage_staleness_gap]] [[project_발음교정_전역사전_작업대]]
