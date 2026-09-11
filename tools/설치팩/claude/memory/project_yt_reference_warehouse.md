---
name: project_yt_reference_warehouse
description: /yt/refs 레퍼런스 창고 — 터진 영상 검색·검증·해체·믹스. 소재발굴→해체→대본믹스 파이프라인
metadata: 
  node_type: memory
  type: project
  originSessionId: 9b4ea6d7-55f0-49dc-b491-ef08e9b82834
---

YT 대시보드의 **레퍼런스 창고** (`dashboard/yt_refs.html`, `GET /yt/refs`) — 검증된 터진 주식영상을 찾아 Gemini로 대본 전체분석하고 믹스해 우리 채널 대본 초안을 만드는 시스템. [[project_yt_planning_dashboard]]의 다음 단계.

**흐름**: 카테고리(10종, `scripts/yt_agents/yt_categories.json`) 또는 자유검색/URL → 검색+검증순위 → 🔬해체(Gemini 영상시청+댓글, 대본 전체분석) → 멀티선택 믹스 → 대본 초안.

**핵심 파일**:
- `scripts/yt_agents/hot_clips.py` — 검색·검증 엔진. `find_and_rank(queries, days, exclude_shorts, exclude_news, sort)`. 3순서(relevance+date+viewCount)×50개 긁어 dedup, MIN_VIEWS(3만) 하한으로 노이즈 제거.
- `scripts/yt_agents/clip_teardown.py` — Q10 해체(대본_전체분석·성공요인·대본등급·댓글페인포인트) + `mix()`.
- `scripts/yt_agents/gemini_client.py` — 18키 폴백 + `call_video()`(네이티브 유튜브 시청).
- 엔드포인트: `/yt/categories` `/yt/category_search` `/yt/keyword_search` `/yt/teardown`(SSE) `/yt/mix`(SSE) — server.py.

**검증 지표 (⭐추천 = 3개 교집합)**:
- **배수(view_per_sub)** + 판정 금맥 = 구독자 대비 터짐(소재가 캐리)
- **기여도(contribution_grade)** = 채널 평균 대비 이 영상이 유난히 터짐(제목·훅 통함). 채널평균은 필터통과 결과에만 병렬계산(비쌈).
- **콘텐츠(참여율=좋아요+댓글/조회수, 배치 3분위 상대평가)** = 썸네일빨 아닌 내용빨 → 대본 배울값
- velocity(views_per_day)·게시일·길이·쇼츠도 컬럼. 쇼츠판별=`/shorts/{id}` 리다이렉트(길이만으론 오판, 유튜브 쇼츠 3분까지).

**교훈**: 조회수/일조회수만 높은 건 대형채널·클릭빨. 뉴스채널(SBS 등)은 분석 레퍼런스 아님(_is_news_channel 제외). [[feedback_verify_with_real_data]] — 사용자가 실검색으로 표본작음·오래된것만·쇼츠미감지·뉴스노이즈 다 잡아냄.

**2026-07-05 대확장 (커밋 dcf9c7b6)** — 검색→해체→믹스 뒤에 **대본 생성 파이프라인** 추가:
- **🤖 AI 자연어검색**(`ai_search.py`, `/yt/ai_search`): 문장→키워드·정렬·필터 분석+재랭킹. 기존 직접검색 유지.
- **⭐추천점수 0~10**: 배수 강도(10x/5x/3x 가점)까지 반영(기존은 판정+기여도+참여율만). 게시일 정렬버그(sortStack push→unshift)도 수정.
- **🎬 스토리라인 설계도→✍️완성대본**(`story_builder.py`, `/yt/storyline`·`/yt/script`): `claude -p` Opus(Max구독)+Gemini폴백. 설계도=편집가능 textarea 2단계. 채널요약 "스탁브레인"으로 교체+억지말투 제거.
- **🔎 주장기반 리서치**(`research.py`, `/yt/research`): 스토리라인 **뒤** 배치. 설계도→핵심주장 추출→주장별 타겟리서치(최근3일 기사+원자DB+주가)→근거판정(충분✅/약함△/없음⚠️). 근거없는 주장은 대본에서 단정금지. 오염방지=최근기사만+주가정합성+우리자료우선. 소재 자동판정으로 켜고끄기.
- **해체 영상제한**: 임베드/지역/연령 제한 영상은 Gemini `call_video` INVALID_ARGUMENT(모델·해상도 무관) → 친절 에러. 일부 영상만 제한, 다른 영상은 정상.

**미결(내일)**: 서버 미배포(feat/briefing-engine, main 정리 후). /yt/refs 전체 1사이클 실브라우저 테스트(해체→믹스→스토리라인→주장리서치→대본, 대본이 ⚠️근거없는주장 약화하는지·억지말투 사라졌는지). 리서치 기사가 description 요약뿐 — 부족하면 핵심 1~2개만 본문크롤. 다음: 썸네일/제목 제작단계, 창고 영구저장 DB, Opus/Sonnet 검수레이어. [[reference_claude_max_on_server]]
