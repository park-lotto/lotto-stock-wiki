---
name: project-channel-insight-system
description: "채널 인사이트 시스템 — pass2 구조, channel_registry, wiki/insights/ 위치와 목적"
metadata: 
  node_type: memory
  type: project
  originSessionId: 91ffa4ec-5353-481c-bcd1-ac8345690306
---

텔레그램 채널 인제스트를 팩트(Pass 1)와 사고방식(Pass 2) 두 갈래로 처리하는 시스템.

**구조:**
- `pipeline/channel_registry.json` — 채널별 type/pass1/pass2/specialty/trust 등록
- `scripts/ingest_crawl.py` — pass2:true 채널은 Gemini로 사고방식 추출 → `wiki/insights/{채널}.md`
- `wiki/insights/` — 채널별 인사이트 누적 파일 + `_consensus.md`

**채널 타입:**
- A: 증권사 공식 (pass2 불필요)
- B: 고급 큐레이션 (pass2 불필요)
- C: 개인 섹터 전문가 (pass2 선택)
- D: 인사이트·흐름형 (pass2 필수)

**Why:** 팩트는 섹터/종목에 흘려보내고, 배우고 싶은 사람의 사고방식(분석공식·시그널패턴·콜히스토리)을 별도 누적해 Claude가 "그 사람처럼 분석해줘" 요청에 답할 수 있게 함.

**How to apply:** 채널 목록 받으면 channel_registry.json에 등록 후 인제스트 실행. pass2:true 채널만 wiki/insights/ 생성.

**미완료:** 채널 목록 등록 대기 중 (사용자가 크롤링 폴더에 채널 추가 후 문항지 작성 예정). _consensus.md 자동 집계 로직 미구현.
