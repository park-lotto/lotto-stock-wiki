---
name: project_ttalkkak_dashboard
description: "딸깍 대시보드 — 버튼 하나로 오늘 시장 정리. 장전 버튼 1단계 완성, 장중(한투)·마감 남음"
metadata: 
  node_type: memory
  type: project
  originSessionId: c471b6f9-0e43-4ca2-8e64-a79a91d391d2
---

내부 도구(영상 콘텐츠용). 버튼 누르는 장면이 채널 콘텐츠. 구독자용 아님(인증 없음).

**버튼 3개** = 투자자 하루 흐름:
- 🌅 장전 "오늘 뭐 봐야해?" → ✅ **1단계 완성** (`dashboard/server.py` FastAPI:8090 + `index.html` 검정골드)
- 🔥 장중 "지금 왜 이래?" → 한투 API 연결 예정(2단계). 10분 워커→`data/intraday.json`, AI는 버튼 누를때만
- 🌙 마감 "내일은?" → 태린이 JSON화+일정 파일화(3단계)

**핵심 원칙**: 대시보드=새 수집기❌ / 이미 도는 자동화잡 산출물 모으는 표시레이어✅ (토큰폭발 방지). 데이터=`output/signal/signal_snapshot.json`(3단 깔때기). 주도섹터 로직=`build_signal_snapshot.py`의 `select_sectors_ab()`: 미장강세∩소르티노∩빈집.

**미해결**: 신호잡 자동화 멈춤(6/22후 4일, 수동복구함) / 섹터라벨 정합성([[feedback_sector_label_integrity]]). 상세=NEXT_SESSION.md, [[project_taerini_pipeline]] 연계.
