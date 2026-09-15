---
name: project
description: "제작소 대본↔영상 어긋남(fit≤2) 구제 — 스왑버튼 라이브, 후속 4단계 사다리"
metadata: 
  node_type: memory
  type: project
  originSessionId: 99346f73-9607-46ca-88ad-07026351ebbe
  modified: 2026-07-19T06:56:35.720Z
---

제작소(shopping_shorts produce)에서 대본 비트의 바탕영상이 말과 어긋날 때(`fit≤2`) 60대 사용자가 대본 재작성·소스 추가 없이 고치게 하는 작업.

**핵심 설계 결론**: 닭-달걀(믹스먼저 vs 대본먼저)은 순서 문제가 아니라 정보단절. **대본 먼저(2번) 유지** + 앞에 인벤토리 + 뒤에 채움. 자동구제 사다리 = ①alternates/소스 스왑 ②글자카드 ③요소짤(장면라이브러리 역할짤) + 완성도 신호등 + 역할패스 카테고리우선.

**중요**: 모든 비트는 항상 바탕영상(primary) 보장(매칭실패 비트는 edit_plan.py에서 드롭) → "검은 빈 비트" 없음. 진짜 문제는 fit 낮은 바탕. `fit`(1~5)은 이미 계산·표시됨(produce.html). 스왑 백엔드 `POST /api/mix/adjust`도 이미 존재(전체 인벤토리서 seg 교체).

**①스왑버튼 = 라이브(2026-07-19, 최초 origin/main 22785e772)**. SDD 4태스크: `GET /api/mix/segments/{job}`(후보목록)·`GET /api/mix/seg_thumb/{job}/{seg}`(중간프레임 캐시)·adjust가 스왑 시 `fit=None`(경고 자동해제)·produce.html 시니어 피커(fit≤2 빨간버튼→썸네일 탭=교체). 60대용: 탭=선택, 슬라이더·타이핑 없음.

**②완성도 신호등 = 라이브(2026-07-19, origin/main 62bf04861)**. produce.html `renderCoverageSignal(beats)` — 편집안 맨위 🟢(fit≥4/스왑=null)·🟡(3)·🔴(≤2) 집계 + 빨강이면 "빨간N칸만 [다른 화면으로] 바꾸면 완성"/전초록 "다 좋아요". node테스트(test_mix_coverage_signal_js).

**후속 우선순위**(미착수, ③은 사장님 실사용 피드백 후 착수로 결정): 3)[글자카드]=아무 seg도 안 맞을 때 affiliate_target 타이포 오버레이(**영상합성 백엔드 변경, 문구/스타일 선택 갈림**) 4)`scene_match._role_pass`에 `product_category` 같은카테고리 우선(식품짤이 뷰티영상에 박히는 것 차단) 5)라이브러리 역할×카테고리 격자 채우기.

관련: [[project_shopping_shorts_code_audit]] · [[feedback_ttalkkak_senior_northstar]] · [[feedback_whole_branch_review_catches_seams]] · 스펙/계획 = repo `docs/superpowers/specs|plans/2026-07-19-제작소-*`
