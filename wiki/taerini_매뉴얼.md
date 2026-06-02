# 태린이아빠 파일 파이프라인 매뉴얼

> **목적**: 주도업종 안에서 수급 빈집 종목을 자동으로 골라내기 위한 데이터 파이프라인
> **업데이트**: 2026-06-02

---

## 전체 구조

```
[마이박스 자동 다운로드 07:30]
        ↓
raw/매일 엑셀넣을것/ 에 엑셀 저장
        ↓
[자동 ingest 07:50]
        ↓
수급빈집 + RS + 가속화 결과 → 텔레그램 전송
```

---

## 1. 파일 목록 및 역할

| 파일명 | 폴더(마이박스) | 역할 | 자동처리 |
|--------|--------------|------|---------|
| 추정이익 변경.xlsm | 아메리카노 | Rating/TP 상향·하향 추적 | ✅ ingest_excel.py |
| 컨센움직임서프쇼크.xlsx | 아메리카노 | 컨센 상향·서프라이즈·쇼크 탐지 | 리포트만 |
| 수급오실레이터(700).xlsm | 카페라떼 | 대형주 700종목 빈집A/B 탐지 | ✅ ingest_excel.py |
| 수급오실레이터(700-1400).xlsm | 카페라떼 | 중소형주 682종목 빈집A/B 탐지 | ✅ ingest_excel.py |
| 유동성체크(+가속화+신고가).xlsm | 카페라떼 | 컨센신고가 TOP10 + 가속화모멘텀 | ✅ 가속화 텔레 |
| 한국상대강도.xlsx | 눈꽃빙수 | Mansfield RS 150종목 | ✅ ingest_excel.py |
| 특정업종쏠림지수국내MMDD.xlsx | 눈꽃빙수 | 업종 쏠림지수 | 미개발 |
| 소라티노ETF상대강도MMDD.xlsx | 눈꽃빙수 | 소르티노 Top 20 주도업종 판단 | 미개발 |
| 일정 및 수주잔고.xlsx | 아메리카노 | 실적일정·수주 | 미개발 |
| 액티브ETF관리.xlsx | 눈꽃빙수 | ETF 비중 관찰 | 미개발 |
| 투자아이디어정리.xlsx | - | 태린이아빠 아이디어 | 미개발 |

---

## 2. 스크립트 명령어 목록

### 자동 실행 (스케줄 등록됨)

| 시간 | 작업명 | 명령어 |
|------|--------|--------|
| 07:30 | STOCKBRAIN_Daily_Download | `python scripts/download_daily.py` |
| 07:50 | STOCKBRAIN_Daily_Ingest | `python scripts/ingest_excel.py` |

### 수동 실행

#### 다운로드 (download_daily.py)
```bash
# 전체 다운로드
python scripts/download_daily.py

# 폴더별 개별 다운로드
python scripts/download_daily.py --ame      # 아메리카노만
python scripts/download_daily.py --cafe     # 카페라떼만
python scripts/download_daily.py --bingsu   # 눈꽃빙수만
python scripts/download_daily.py --yt       # 유튜브만
python scripts/download_daily.py --debug    # 브라우저 보이게 실행
```

#### 엑셀 ingest (ingest_excel.py)
```bash
# 전체 처리 (수급+RS+가속화 텔레 전송)
python scripts/ingest_excel.py

# 실제 파일 수정 없이 결과만 미리보기
python scripts/ingest_excel.py --dry-run
```

#### 업종 오실레이터 스캔 (scan_oscillator.py)
```bash
# 65개 업종 빈집 탐지 (수동 실행 필요)
python scripts/scan_oscillator.py
```

#### 추정이익 카드뉴스 (viz_card.py)
```bash
# 종목 카드뉴스 HTML 생성
python scripts/viz_card.py LG이노텍

# PNG 저장
python scripts/viz_card.py LG이노텍 --png

# 여러 종목 한번에
python scripts/viz_card.py LG이노텍 SK하이닉스

# 텔레그램 전송
python scripts/viz_card.py LG이노텍 --tg
```

#### 풀 대시보드 (viz_consensus.py)
```bash
# 전체 컨센서스 대시보드 HTML 생성
python scripts/viz_consensus.py
```

---

## 3. 출력 결과

| 스크립트 | 출력 위치 | 내용 |
|---------|----------|------|
| ingest_excel.py | 텔레그램 + `raw/ingest_report_{날짜}.md` | 수급빈집A/B + RS + 가속화 TOP30 |
| scan_oscillator.py | 텔레그램 | 업종별 빈집 순위 |
| viz_card.py | `out/card_{종목}.html` + PNG | 목표주가 카드뉴스 |
| viz_consensus.py | `out/consensus_dashboard.html` | 45일 컨센서스 풀 대시보드 |

---

## 4. 빈집 등급 기준

| 등급 | 기준 | 의미 |
|------|------|------|
| A 완전빈집 | 하위 10% 이하 | 외인·기관 거의 없음 → 진입 시 탄력 극대 |
| B 반빈집 | 하위 10~25% | 빈집 후보 |
| C 정상 | 25~75% | 일반 |
| D 과매수 | 상위 25% 이상 | 이미 외인·기관 가득 |

---

## 5. 탑픽 판단 로직

```
주도업종 (소르티노 + 유동성컨셉 + RS)
        ↓
수급 빈집 (오실레이터 A/B)
        ↓
가속화모멘텀 + 컨센 상향까지 겹치면 → 탑픽
```

**8개 교집합 점수 (총 9점)**:
| 점수 | 기준 |
|------|------|
| 2점 | 수급 빈집 (필수) |
| 1점씩 | 수출🔴 / 판가이슈 / 어닝서프 / 컨센신고가 / 미국커플링 / 정책 / D-30 일정 |

> 수급빈집 없으면 나머지 다 맞아도 후순위

---

## 6. 집PC 세팅 방법

```bash
git pull
scripts/setup_schedule.bat   # 관리자 권한으로 실행
```

---

## 7. 미개발 (다음 할 것)

| 기능 | 설명 |
|------|------|
| 교차분석 | 수급빈집 × RS × 가속화 → 탑픽 후보 1개 메시지 자동추출 |
| 업종 오실레이터 자동화 | scan_oscillator.py 매일 스케줄 추가 |
| 소르티노 자동화 | scan_sortino.py --tg 스케줄 추가 |
| 액티브ETF 파서 | ETF 비중증가 × 수급빈집 교집합 탐지 |
| 추정이익 카드뉴스 자동화 | 매일 아침 주요 종목 자동 생성 |

---

*이 파일은 작성 중 — 섹션별로 채워나가는 중*
