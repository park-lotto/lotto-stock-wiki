---
name: project_customer_delivery_model
description: 고객에게 Stock Brain 시스템 가치를 전달하는 3단계 구조 — 텔레채널→캐시봇→개인화
metadata: 
  node_type: memory
  type: project
  originSessionId: c6c7dbb7-e823-4b7d-88a8-c56a16363b14
---

## 고객 전달 모델 확정 (2026-06-07)

핵심 문제: 우리 시스템은 Claude Code 필요 → 일반 고객이 직접 쓸 수 없음.

**3단계 해법:**

### Stage 1: 텔레그램 채널 방송 (즉시 시작 가능)
- daily_scenario.py 결과를 채널에 매일 발송
- 구독자당 비용 = 0 (무한 스케일)
- 목적: 신뢰 구축 + 구독자 모수 확보

### Stage 2: 캐시 응답 봇 (Pre-compute 방식)
- 매일 오전 Claude Code가 분석 → 결과 캐시
- 봇은 캐시된 데이터만 전달 (Claude API 쿼리당 비용 없음)
- 질문 예: "오늘 수급빈집 상위 5개" → 미리 계산된 결과 즉시 반환

### Stage 3: 개인화 레이어 (Python 필터, Claude 불필요)
- 구독자 관심 섹터 등록 → Python 필터링
- Claude API 없이 처리 → 스케일링 비용 최소화

**Why:** Kakao/Telegram 봇 기반이면 고객이 Claude Code 없어도 시스템 가치 체험 가능. Real-time Claude API 방식은 쿼리당 비용이 구독자 수에 비례해 적자 위험.

**How to apply:** 텔레그램 채널 오픈이 첫 단계. 이미 assistant_bot 있으니 채널 발송 연동만 추가.

다음 액션: 텔레그램 채널 개설 → 채널 ID → bot.send_message(channel_id, ...) 연동

관련: [[project_stockbrain_service]] [[project_daily_scenario]]
