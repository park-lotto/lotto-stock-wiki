---
name: feedback-briefing-date-verification
description: 브리핑 카드뉴스 작성 시 날짜 검증 의무화 — 검증 없으면 과거 데이터가 오늘 인사이트로 둔갑
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1304cd1d-ede1-4cfc-a9c6-022494b0537a
---

브리핑 카드뉴스(sector_briefing, 카드뉴스) 작성 전 반드시 날짜 검증 Step 0 실행.

**Why:** 검증 없이 위키 데이터를 그대로 넣으면 일주일 전 이벤트가 "TODAY'S 인사이트"로 들어가는 어처구니없는 리포트가 된다.

**How to apply:**
HTML 작성 전 아래 5가지 검증 통과 후에만 내용 삽입:
- V-1: 오늘 날짜(YYYY-MM-DD) 항목만 TODAY'S 섹션에
- V-2: 리포트는 오늘자 발행 리포트만 (어제 이전 = [n일전] 라벨 or 제외)
- V-3: 뉴스는 오늘 수신 채널의 오늘자 메시지만
- V-4: 이슈카드 TRIGGER = 아직 안 일어난 이벤트만 (지난 이벤트는 Stage 업데이트)
- V-5: 체크리스트 = 오늘·내일 확인 가능한 항목만 (이미 결과 난 것 제거)

규칙 위치: `channel/strategy/briefing_카드_디자인스펙.md` → "날짜 검증 규칙" 섹션
