---
name: channel-style-system
description: "대본 채널스타일 3각(메종/채이/스탠다드) trio 모드 라이브 — 후보 A/B/C 상이 스타일, 리라이트 2차패스가 본체"
metadata: 
  node_type: memory
  type: project
  originSessionId: b99b6e41-511a-43a9-a658-330c51f97bf4
  modified: 2026-08-05T12:49:08.097Z
---

2026-08-05 라이브. 사장님 지시 "상위 채널 분석해 대본 스타일 1·2·3"(메종홈디노가 1순위·본인 스타일).

**구조**: `shopping_shorts/style_profiles.py` — 채널별 실제 히트 대본 3편 전문 few-shot+가이드.
스타일1 메종(발견담·158만) / 2 chae2home(가족드라마·631만) / 3 home._.standard(유머목격담·286만).
`SCRIPT_STYLE` env: 기본 `trio`(1소스 후보 A/B/C에 상이 배정), maison/chae/standard 단일, off.

**Why(핵심 교훈)**: 생성 프롬프트에 스타일 지시를 넣는 것만으론 3바퀴를 밀어도 카피체를 못
벗었다 — 본체는 **리라이트 2차패스**(`single_source.apply_restyle`): 완성 나레이션을 few-shot
보고 문체만 재작성(covers·사실 고정, 길이/상투어/CTA보상 피드백 재시도 3회). 오프라인 40개
교정(40/40)에서 검증된 방식의 이식. 관계 프레임(시어머니가 물어봤다)은 원본에 없어도 허용,
성능·수치·구매처 사실은 금지 — 안 풀어주면 채이·스탠다드 스타일이 발현 자체가 안 된다.

**How to apply**: 추천 채점에 `style_penalty`(합쇼체 '니다' 종결·명령훅 감점) — 리라이트 실패
후보가 ★추천되는 걸 막는다. 검증은 서버 드라이런(build_scene_first_plan 직접 호출, DB 무기록)
반복으로 — 3라운드 9/9 성공 실측. 조용한 폴백 함정 2회: 길이 게이트(±40%)에 1.5배 팽창이
걸려 매번 원본 복귀 / restyle_prompt 문자열 연결 구문오류(finish 게이트가 차단).
잔여: 가명 지정 UI(TTS처럼), 믹스·도서관 엔진 확장, 채이 가족프레임 강화.
채널 원문 183개: `docs/어미교정/all_channel_scripts.json`. [[reference_silent_fallback_pipeline_undo]]
