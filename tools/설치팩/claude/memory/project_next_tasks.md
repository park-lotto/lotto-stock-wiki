---
name: project-next-tasks
description: 다음 세션에서 이어서 할 작업 목록 (언제든 꺼내기용)
metadata: 
  node_type: memory
  type: project
  originSessionId: f99cedc3-9610-4514-a79c-5adf85a06a97
---

## 이어서 할 작업 (2026-05-30 저장)

### 1순위: STOCK BRAIN MVP
- [ ] 유튜브 브리핑 모듈 개발 스펙 작성
- [ ] Playwright headful 자동 녹화 버전 구현
- [ ] 텔레그램 봇 온보딩 설계 (채널 링크 등록 플로우)
- [ ] 첫 영상 촬영 ("AI가 오늘 유튜브 다 봤다 #1")

### 2순위: 크롤링 자동화
- [ ] 마이박스 나머지 링크 2개 받아서 download_mybox.mjs 완성
- [ ] 매일 오후 8시 자동 실행 스케줄러 등록
- [ ] raw/ 파일 감시자 구현 (자동 ingest 트리거)

### 3순위: RAG 서비스화
- [ ] ChromaDB 설치 + 위키 임베딩
- [ ] Claude API 연동 (Haiku 80% + Sonnet 20%)
- [ ] Gemini 무료 티어로 초기 비용 0원 구조 구현

### 4순위: 바이오 위키 (집PC 하던 것)
- [ ] Tier 2 종목 딥리서치 (8종목)
- [ ] Tier 3 종목 진행

### 참고
- MCP: fetch·sqlite·memory 설치됨 (세션 재시작 후 활성화)
- post-commit hook: 커밋 시 자동 푸시 설정됨
- 모델 분기: 단순작업=Haiku / 분석·창작=Sonnet
