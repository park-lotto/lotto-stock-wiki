---
name: feedback-update-date
description: 위키 어느 파일이든 새 정보 추가 시 업데이트 날짜를 명시해야 함
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e558d4b-194a-4833-805b-0502580b3d26
---

모든 wiki 파일에서 새 정보를 추가하거나 기존 내용을 수정할 때 업데이트 날짜를 명시한다.

**Why:** 언제 추가된 정보인지 알아야 데이터 신선도와 히스토리를 추적할 수 있다.

**How to apply:**
- 섹터 index.md의 "오늘의 한줄" → `(YYYY-MM-DD 업데이트)` 괄호 명시
- 지속 영향 이벤트 추가 시 → "시작" 컬럼에 `YYYY-MM~` 날짜 기입
- 이벤트 히스토리 행 추가 시 → 날짜 컬럼 `YYYY-MM-DD` 필수
- stock/ 페이지 종합 스토리 → `> YYYY-MM-DD 기준:` 형식 유지
- 증권사 컨센서스 테이블 → "날짜" 컬럼 `YYYY-MM-DD` 필수
- 탑픽 콜아웃 업데이트 시 → 콜아웃 하단에 `> 마지막 업데이트: YYYY-MM-DD` 추가
- 섹터 index.md 기술적 분위기 표 덮어쓸 때 → 헤더에 `← YYYY-MM-DD 기준` 명시
