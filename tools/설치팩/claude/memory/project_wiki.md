---
name: project-wiki
description: "로또의 주식 위키 시스템 현황 — L1·L2 완성, L3~L6 미착수"
metadata: 
  node_type: memory
  type: project
  originSessionId: 980e9131-f52d-4056-b15d-67c10dd48f74
---

# 로또의 주식 위키 프로젝트 현황

**완성된 레이어**:
- **L1 글로벌유동성** ✅ 완성
  - wiki/L1_글로벌유동성/: index.md, fed_watch.md, market_vix.md, market_채권금리.md, market_달러_환율_흐름.md
  - out/L1_글로벌유동성.html — 민트 대시보드 (shimmer 5s 1회, 티커 없음)

- **L2 미국시장** ✅ 완성 (2026-05-24)
  - wiki/L2_미국시장/: index.md, market_한국페어맵.md, market_미국지수.md
  - out/L2_미국시장.html — 11개 섹터 페어 카드 (미국↔한국 레이아웃)
  - 11개 페어: AI반도체(NVDA→SKH)·메모리(MU)·장비(AMAT/LRCX)·PCB(MRVL)·우주방산(RKLB/LMT)·전력(ETN/VRT)·비만(LLY/NVO)·전기차(TSLA)·양자(IONQ/QBTS)·연료전지(BE)·태양광(FSLR/ENPH)

**자동화 인프라**:
- update_market_data.js: 33심볼 → L1 wiki 5파일 + L2 wiki 2파일 + HTML 2개 + dashboard.md + log.md
- 수동업데이트.bat + 바탕화면 바로가기
- Windows Task Scheduler: 07:00 KST 매일

**출력물 (out/)**:
- L1_글로벌유동성.html ✅, L2_미국시장.html ✅
- sector_dashboard_조선.html ✅, briefing_반도체.html ✅

**L6 수급 연동 완성 (2026-05-25)**:
- `raw/market/extract_유동성.ps1` — 유동성 xlsm → md 요약 자동 추출 (UTF-8 BOM 필수)
- 17개 stock/ 파일 수급빈집 ✅ 반영 완료 (20260522 기준)
- stock_index.md: 탑픽 마스터 인덱스 (점수순 정렬)
- 탑픽 결과: 8/9점 4종목(삼전·SKH·동진·솔브레인), 7/9점 4종목
- 조선 섹터 stock/ 파일 6개 미생성 (HD현대중공업 등) — 다음 세션 우선과제

**미착수**: L3 한국시장 HTML / L4 국제정세 / 조선 stock/ 6개 파일 생성

**일일 루틴 (완성)**:
```
1. 유동성 xlsm → raw\market\YYYYMMDD_유동성.xlsm 저장
2. .\raw\market\extract_유동성.ps1 -FilePath "..."  (PS1은 UTF-8 BOM 필수)
3. Claude: /ingest raw/market/YYYYMMDD_유동성_요약.md
```

**Why:** 주식 트레이딩 + 유튜브 채널 콘텐츠용 자동 수집·분석 시스템.
**How to apply:** 조선 stock/ 파일 6개 생성이 다음 우선과제. PS1 파일 수정 시 항상 UTF-8 BOM으로 재저장 필요.
