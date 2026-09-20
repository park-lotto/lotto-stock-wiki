---
name: project-daily-scenario
description: daily_scenario.py — 3소스 종합 시장 시나리오 생성 시스템. 포맷·말투·파이프라인 확정 내용.
metadata: 
  node_type: memory
  type: project
  originSessionId: 99a63751-9a86-453c-8a6e-a3fa6a185463
---

## daily_scenario.py 완성 (2026-06-05)

3개 소스를 종합해서 오늘의 시장 시나리오를 자동 생성한다.

**실행**: `python daily_scenario.py --date YYYY-MM-DD`
**출력**: `out/scenario_YYYY-MM-DD.md`

### 소스 구성
| 소스 | 경로 | 역할 |
|------|------|------|
| wisereport | `raw/wisereport/YYYY-MM-DD_parsed.json` | 증권사 공식 TP·의견 |
| 텔레그램 | `crawling_bot_data/YYYY-MM-DD/telegram/` | 시장 분위기·수급 |
| 블로그 | `crawling_bot_data/YYYY-MM-DD/blog/` | 개인 분석가 추론 |

### 확정 포맷 (브리핑 카드형)
```
━━━ YYYY-MM-DD 시장 브리핑 ━━━
📌 오늘 핵심 (3줄)
🔴 강세 종목 표 (종목명 | 목표주가 | 이유)
🔵 리스크 종목 표
⚠️ 리스크 불릿 3~5개
📅 챙길 일정
💡 시나리오 (강세/약세)
🎯 오늘 한 줄
```

### 말투 규칙 (확정)
- 주린이 눈높이 — ETF→펀드, TP→목표주가, 리밸런싱→비중조정
- Capex→설비투자, 지정학→전쟁·분쟁, 역성장→판매감소
- 말투: "~야", "~있어", "~예정이야" (딱딧한 명사형 금지)
- 한 줄 = 한 문장, 15자 이내 불릿

**Why:** 시청자(주린이 포함)가 바로 이해해야 유튜브 콘텐츠로 쓸 수 있다.
**How to apply:** 시나리오 생성 시 항상 이 포맷·말투 기준 적용. 프롬프트 수정 시 규칙 유지.
