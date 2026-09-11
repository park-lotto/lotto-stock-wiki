---
name: project-naverclip-collect
description: "네이버 클립 수집축(라이브) — HTTP 2번으로 조회수·mp4까지, yt-dlp 불가, 뷰티 분석 결과와 잔여 과제"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0c0b44d3-73e5-44eb-b7c0-bf881331084c
  modified: 2026-08-30T14:50:48.857Z
---

네이버 클립 = 레퍼런스 랭킹 **6번째 플랫폼**(2026-08-30 라이브, 관리자 전용 🟩 탭).
무료·로그인/프록시/브라우저 전부 불필요 — **HTTP 2번**이 전부다.

```
① 목록 s.search.naver.com/p/clip/4/api/tab/more?query=&ssc=tab.m_clip.all&start=N
② 상세 creatorhub-api.naver.com/api/v7.0/clipviewer/card?seedMediaId=<32자>
       → 정확 조회수·좋아요·댓글·발행시각 + mp4 직링크(1080x1920)
```

**★yt-dlp는 못 쓴다**(Unsupported URL). yt-dlp가 아는 `tv.naver.com/v/{clipNo}`는
**옛 서비스**고 지금 클립은 `clip.naver.com` + mediaId 기반의 별개 서비스다.

**함정**: sort 파라미터는 무시된다(인기순은 우리가 정렬) · 파서는 썸네일 URL을 앵커로
삼아야 한다(data-media-id 순서로 세면 vod 없는 껍데기와 어긋난다) · 상세로 정확값을
받은 뒤 **재정렬** 필요(목록은 반올림값) · mp4는 만료(hdnts=exp)가 붙어 보관 불가.

**규모**: 한 키워드 천장 약 500건 → 늘리려면 **키워드를 쪼갠다**. 뷰티 20개 = 2,935건/59초.

**뷰티 분석**: 중앙값 86회(53%가 100회 미만). ★**해시태그는 적을수록 터진다**
(1~2개 31.2% vs 8개+ 5.6%) · 45~60초가 15초 미만의 6배 · 쿠션 계열 태그 전멸(0%).
데이터랩 교차 → **속눈썹펌·올리브영이 수요 최상위인데 클립 터짐 0% = 기회 공백**.

**잔여**: 기본 키워드 20개 중 5개 0건(피부관리 등, 파서 의심) · 공백 분석 ·
카드 인라인 재생 검증. 상세는 [[handoff/네이버클립]].

관련: [[reference_썸네일화이트리스트_5번째반복]] ·
[[reference_레퍼런스랭킹_데이터저장은_settings테이블]] ·
[[project_레퍼런스랭킹_5플랫폼]]
