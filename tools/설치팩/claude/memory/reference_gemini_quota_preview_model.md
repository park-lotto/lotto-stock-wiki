---
name: reference-gemini-quota-preview-model
description: "Gemini 프리뷰 모델(gemini-3-flash-preview 등)은 무료쿼터가 계정/프로젝트 달라도 거의 즉시 공유소진됨 — 안정판 모델로 우회"
metadata:
  type: reference
  originSessionId: 87e79444-d710-425a-bf55-a0adbde4852c
---

2026-07-05 `fetch_sector_calendar.py`의 이벤트 데이터가 몇 주째 0건이던 원인 진단 중 발견:
스크립트가 `model="gemini-3-flash-preview"`(프리뷰 모델)를 하드코딩하고 있었고, 이 프로젝트
GEMINI 키 18개(general4/briefing3/embed6/ingest5, `pipeline/atoms/key_vault.py` 그룹)를
전부 테스트해봐도 프리뷰 모델에서는 거의 동시에 429(RESOURCE_EXHAUSTED)를 맞았다.

**재현 확인**: 429를 맞은 바로 그 키로 안정판 모델(`gemini-2.5-flash`,
`gemini-3.1-flash-lite`, `gemini-2.5-flash-lite`)을 호출하면 즉시 정상 응답하고,
`google_search` 그라운딩 도구까지 실데이터를 정상 반환함. 즉 **쿼터 소진은 계정/키
문제가 아니라 프리뷰 모델 자체의 제약**이었다(정확한 내부 메커니즘은 불명 — 전역
공유쿼터인지, preview 티어가 원래 더 낮은지는 확인 못함).

**적용 원칙**: 이 코드베이스에서 새로 Gemini를 호출하는 코드를 작성하거나 429 쿼터
문제를 디버깅할 때, 모델명이 `-preview`로 끝나면 가장 먼저 안정판(`gemini-2.5-flash`
계열)으로 바꿔보고 재현되는지 확인할 것 — 키 로테이션(key_vault)이나 결제 플랜 확인보다
먼저 시도해볼 가치가 있음. 이 저장소에서 안정판은 이미 14곳 이상에서 쓰이고 있어
검증된 선택지임(`grep -c "gemini-2.5-flash" dashboard/*.py pipeline/**/*.py` 등으로 확인 가능).

**연결**: [[project_insights_redesign_v5]] (이 발견이 나온 작업), 관련 코드
`fetch_sector_calendar.py`(수정 커밋 dd72e7a4).
