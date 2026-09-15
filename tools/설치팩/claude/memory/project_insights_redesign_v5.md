---
name: project-insights-redesign-v5
description: "인사이트 페이지 라이트테마+v5 1단레이아웃 리디자인 완성(2026-07-05) + 이벤트캘린더 실데이터 파이프라인 복구"
metadata:
  type: project
  originSessionId: 87e79444-d710-425a-bf55-a0adbde4852c
---

`dashboard/insights.html` 인사이트 페이지를 다크·골드 테마+2단(main-2col) 구조에서
애플라이트 테마+1단 구조(라이브러리→시그널→이벤트→리포트→기록)로 완전 리디자인 완료.
계획서: `docs/superpowers/plans/2026-07-05-insights-phase1-b2-촉매섹션-라이트테마.md`
(superpowers:subagent-driven-development로 진행, 구현+리뷰 전부 Opus).

**핵심 결정/교훈:**
- 목업(v5)은 마케팅 랜딩페이지고 실제 앱은 L0~L6 드릴다운+브리핑워크스페이스모달 등
  훨씬 풍부한 기능을 가짐 — "목업처럼 만들자"는 색상·타이포·카드모양 등 디자인 시스템
  이식이지, 목업 마크업을 그대로 붙여넣는 게 아님. 이 구분을 처음에 명확히 안 하면
  계속 "왜 목업이랑 다르냐"는 피드백 루프가 반복됨(이번에 여러 번 겪음).
- 목업의 스파크라인 차트는 실시계열 데이터가 없어 장식용 — [[feedback_briefing_source_citation]]
  원칙(지어내지 않기)에 따라 이식하지 않고, 대신 실데이터(spike/is_new)를 색배지로 강조.
- 사용자는 스크린샷+빨간 화살표/박스로 정확히 어느 부분을 지적하는지 표시하며 피드백을
  줌 — 애매하면 바로 물어보고(AskUserQuestion), 명확하면 바로 구현+브라우저검증+커밋.
- 반복 UI 피드백 패턴: 가운데정렬↔좌측정렬 왔다갔다(최종은 컴팩트화 후 가운데),
  "더보기" 버튼 위치는 카드그리드 아래보다 섹션제목 옆(같은 줄 우측)을 선호,
  가로스크롤 대신 고정열(5개or4개)+더보기/접기.

**연결**: [[project_briefing_weather_engine]] (같은 브랜치 feat/briefing-engine),
[[reference_gemini_quota_preview_model]] (이벤트캘린더 데이터 복구 중 발견),
[[feedback_shared_file_hunk_isolation]] (동시세션 커밋섞임 대응법).

**남은 것**: L1~L6 드릴다운·브리핑워크스페이스 모달은 색상토큰만 적용, 레이아웃 재설계는
범위 밖으로 남김. 시그널 발언 의미중복(어순만 바뀐 재작성 기사) dedup는 퍼지매칭 필요,
미해결.
