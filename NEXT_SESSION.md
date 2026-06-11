# NEXT SESSION — 2026-06-11 집에서 이어서

**세션 요약 (2026-06-11 사무실)**
섹터 시그널 파이프라인 설계 + 비즈니스 방향 확정

## 완료
- 하나마이크론 리포트 V_FINAL 추출 결과 검증 (test_hanma.json) — 5개 항목 CLEAN
- 기존 MD 요약 vs 제미나이 추출 비교 → 기존 요약이 수치 오류 있음 확인
- 비즈니스 모델 확정: 강의 판매 + 구독 서비스
- 핵심 컨셉 확정: "요약이 아닌 추출" → 할루시네이션 없음 = 와우 모먼트
- 섹터 마스터 파이프라인 구조 설계 (3개 파일)

## 미완료 — 집에서 이어서

### 1. 섹터 시그널 파이프라인 3개 파일 구현
```
pipeline/sector_signal/sector_signal_ingest.py
  — PDF 받아서 제미나이 추출 → JSON 저장
  — 모델: gemini-3.1-flash-lite (기본값)

pipeline/sector_signal/sector_master_update.py
  — 저장된 JSON들 → 섹터별 업황 컨센서스 집계
  — 섹터 마스터 MD 자동 갱신

pipeline/sector_signal/stock_wiki_update.py
  — JSON → 종목 wiki 페이지 날짜별 누적 추가
```

### 2. run_final_test.py 모델 업데이트
- `gemini-2.5-flash-lite` → `gemini-3.1-flash-lite` 로 교체

### 3. 이전 세션 미완료 (계속 밀림)
- 태린이 파일 2번~끝까지 데이터 정의
- morning_sector_pick.py 3단계 통합 (② 소라티노 ETF 구성종목 빈도 계산)

## 핵심 비즈니스 방향 (이번 세션 확정)
```
유튜브 (무료 쇼룸)
  → "내 시스템 이렇게 작동합니다" 공개
  → 영상 구조: 불신 자극 → 시스템 증거 → 짠 결과 → 자동화 선언

강의 (1회 30~50만원)
  → 1강: 텔레봇 뉴스 자동수집
  → 2강: 유튜브 채널 자동요약
  → 3강: 증권사 리포트 AI 추출 ← 지금 만드는 것
  → 4강: 태린이 파일 + AI 교차분석
  → 5강: 아침 브리핑 자동생성
  → 6강: 위키 복리 시스템

구독 서비스 (월정액)
  → 시스템 결과물 텔레그램 배달
```

## 관련 파일
- `pipeline/sector_signal/prompt_v_final.py` — 추출 프롬프트 완성본
- `run_final_test.py` — 7개 리포트 검증 스크립트
- `test_hanma.json` — 하나마이크론 추출 결과
- `pipeline/sector_signal/` — 파이프라인 구현 폴더
