---
name: project-viz-tools
description: 시각화 도구 현황 — viz_consensus.py(풀 대시보드) / viz_card.py(추정이익 카드뉴스)
metadata: 
  node_type: memory
  type: project
  originSessionId: 7fa5ef7b-d21d-4c6f-8e81-14aa1c8c4da0
---

# 시각화 도구 현황 (2026-06-02 완성)

## viz_card.py — 추정이익 카드뉴스

**용도**: 추정이익변경 파일 → 종목별 목표주가 TOP3 카드뉴스 → PNG → 텔레그램

```bash
python scripts/viz_card.py LG이노텍 --tg        # 생성 + 텔레 전송
python scripts/viz_card.py LG이노텍 --png       # PNG만 저장
python scripts/viz_card.py LG이노텍 SK하이닉스 --tg  # 여러 종목
python scripts/viz_card.py --list              # 오늘 변경 종목 목록
```

**스펙**: 420px 세로형 / 45일 필터 / TOP3 / 희생구역(52px 다크배너로 텔레 크롭 흡수)
**카드 제목**: "추정이익 카드뉴스" (픽스)
**PNG 저장**: `out/card_{종목}_{날짜}.png`
**텔레 크롭 해결**: 맨 위 52px 다크배너(희생구역) → 텔레가 잘라도 제목 안 짤림

## viz_consensus.py — 풀 대시보드

**용도**: 종목별 TP 변화 전체 분석 (차트+타임라인+레이팅)

```bash
python scripts/viz_consensus.py LG이노텍
python scripts/viz_consensus.py --list
```

**스펙**: 100vh 스크롤없는 레이아웃 / 다크테마 / ☀️🌙 테마토글
**주요 기능**: 45일필터(오래된 TP 자동 제외) / 범위바 / 신고가🏆 뱃지 / 날짜순 정렬

**Why:** 추정이익변경 파일은 매일 가장 중요한 증권사 의견 변화를 담고 있음. 시각화로 직관적 파악.
**How to apply:** "카드뉴스", "TP 시각화", "목표주가 분석" 요청 시 이 도구들 바로 안내.
