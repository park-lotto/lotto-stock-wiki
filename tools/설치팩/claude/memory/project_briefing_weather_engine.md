---
name: ""
metadata: 
  node_type: memory
  originSessionId: bef0f865-73ea-4703-b022-c6f64924acb0
---

대시보드 `/market`의 "실시간 브리핑" 패널 재설계 프로젝트. 브랜치 `feat/briefing-engine`(원격 push됨).

**정체성**: 관심종목만 보는 투자자에게 "지금 시장 전체 흐름"을 아침→지금 연속선상에서 판단까지 해주는 장중 시황 날씨예보. 단순묘사 X, 판단 O. 기존은 15분 고정타이머로 스냅샷 재묘사→맨날 비슷했음.

**설계 확정**:
- 출력 = **판정 배지 + 진화형 내러티브 + 오늘의 전환점 타임라인**.
- 갱신 = 이벤트 발생 시만(반복 원천차단) + 심박30분 + 페이즈변화.
- 모델 = **Opus/Sonnet를 Max 구독으로**(API 아님, `claude -p`). Phase0은 번갈아+major는 A/B. → [[reference_claude_max_on_server]]
- 디텍터 6종(순수로직): 투자자 부호전환·프로그램급변·지수분기점(신고저/반등/되돌림)·미선물·디커플링·**섹터급등(+2%p, top_movers+뉴스 동봉)**. 단위상수 명시, 첫런/동결/쿨다운/페이즈게이팅 가드.

**구현·배포 완료**(dashboard/): `briefing_phase`·`briefing_events`·`briefing_weather`·`briefing_digest`·`briefing_state` (32 pytest 통과). server.py `_poll_briefing`에 `_weather_tick()` 배선(`if curr` 바깥=주말/KIS다운에도 실행). market.html 패널 렌더.
**서버 E2E검증**: 이벤트 주입→디텍터 5개 감지→Opus 21초에 "🟢 반등, 외인 매수전환+반도체 급등" 판단형 브리핑(뉴스결합·다음분기점까지). weather_state·calib log·insight API 정상.

**Phase0 관측·보정**: 라이브 패널 반영(단일사용자 베타). 폰 텔레 다이제스트(major즉시/minor15분). `output/weather_calib/*.jsonl`에 매 발동 기록(models·events·verdict·noise_flag). 운영자 피드백→임계튜닝.

**월요일(07-06) 할 일**: 실장중 관측(잡힘/노이즈), 브라우저 렌더 확인(browsermcp 미연결로 오늘 미완), 임계튜닝(섹터+2%p/투자전환300억/반등되돌림0.6%/미선물0.4%p), 최종리뷰+main머지.

**리스크**: ① Max토큰 서버 스테일([[reference_claude_max_on_server]]) — 월요일 calib `models`로 Opus유지 vs Gemini폴백 관측. ② `feat/briefing-engine`에 다른PC calendar커밋4개 섞임([[feedback_shared_worktree_branch_check]]) — main머지 전 분리결정.

스펙 `docs/superpowers/specs/2026-07-04-시황-브리핑-엔진-design.md` / 계획 `docs/superpowers/plans/2026-07-04-시황-브리핑-엔진.md`.
관련: [[project_stockbrain_dashboard]] [[feedback_briefing_source_citation]] [[project_market_insight]]
