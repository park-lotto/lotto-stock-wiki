# NEXT SESSION — 2026-06-09 집에서 이어서

**세션 요약 (2026-06-09 사무실)**
아침 브리핑 파이프라인 설계 — 태린이 파일 데이터 정의 작업

## 완료
- `pipeline/telegram_digest.py` 신규 — 텔레그램 날짜별 소스별 요약 뷰어
- `scripts/morning_sector_pick.py` 신규 — 유동성 교집합 섹터 → 빈집 종목 추출
  - 오늘: 반도체 8일 연속 → 빈집 12개
- `scripts/scan_sortino.py` 수정 — `--holdings` 플래그 추가 (ETF 구성종목 자동 서칭)
- 소라티노 분석 규칙 확정: ETF 구성종목으로 풀어서 종목 좁히기

## 파이프라인 설계 현황 (1번 파일 완료)

**확정된 3단계 흐름:**
```
① 유동성 컨셉 (사모+투신+연금 N일 연속 교집합) → 섹터 확정
② 소라티노 상위 ETF 구성종목 교차 → 종목 빈도 순 좁히기
③ 빈집 오실레이터 A/B → 최종 픽
```

**오늘 예시 결과:**
- 반도체 8일 연속 → RISE 네트워크인프라·KODEX 반도체 → 삼성전기·SK하이닉스·삼성전자 반복 등장
- 빈집 12개 후보 중 교집합 종목 추출 예정

## 미완료 — 집에서 이어서

### 1. 태린이 파일 2번~끝까지 데이터 정의
- 2번: 컨센움직임서프쇼크.xlsx
- 3번: 외국인기관수급오실레이터(700).xlsm (이미 calc_oscillator.py 있음)
- 4번: 액티브ETF관리.xlsx
- 5번 이후: 나머지

### 2. morning_sector_pick.py 3단계 통합
② 소라티노 ETF 구성종목 서칭 후 빈도 계산 추가
③ 빈집 필터는 이미 완료

## 관련 파일
- `scripts/morning_sector_pick.py`
- `scripts/scan_sortino.py`
- `pipeline/telegram_digest.py`
