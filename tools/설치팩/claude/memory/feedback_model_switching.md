---
name: feedback-model-switching
description: 작업 복잡도에 따라 Haiku 서브에이전트 vs Sonnet 직접 처리 자동 분기
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f99cedc3-9610-4514-a79c-5adf85a06a97
---

## 규칙: 작업 복잡도 기반 모델 자동 분기

요청이 오면 **실행 전 분류 먼저** → `[Haiku]` or `[Sonnet]` 명시 후 실행.

**Why:** 사용자 요청. 비용 절감 + 속도 향상. 단순 작업에 Sonnet 쓰는 건 낭비.

**How to apply:**

### Haiku 서브에이전트로 위임할 것
- log.md 기록 (날짜·내용 포맷 맞춰 append)
- index.md 업데이트 (파일 목록 추가)
- 파일 존재 여부 확인 / 경로 탐색
- 단순 파일 읽기 (내용 파악, 요약 불필요)
- ingest 단순 라우팅 (데이터를 정해진 위치에 복사하는 수준)
- 날짜·형식 변환, 단순 계산

### Sonnet이 직접 처리할 것
- Q10 리서치 (WebSearch + 분석 포함)
- 섹터·종목 심층 분석
- 대본·스크립트 작성
- 전략 수립·의사결정
- WebSearch 교차검증
- 복잡한 ingest (신호 해석, 탑픽 판단, 충돌 감지 포함)
- HTML·영상 결과물 생성
- 새로운 wiki 페이지 구조 설계

### 판단 기준 요약
| 판단 기준 | 모델 |
|-----------|------|
| 정해진 포맷에 데이터 넣기 | Haiku |
| 분석·판단·창작 포함 | Sonnet |
| WebSearch 필요 | Sonnet |
| 충돌·이상 감지 필요 | Sonnet |

### 절대 실수 금지
- 메모리 파일 작성·저장 → **반드시 Haiku**
- MEMORY.md 인덱스 업데이트 → **반드시 Haiku**
- "내용 구성(Sonnet) → 파일 저장(Haiku)" 순서 고정
- Sonnet이 Write/Edit 툴로 직접 파일 저장하는 것 금지
