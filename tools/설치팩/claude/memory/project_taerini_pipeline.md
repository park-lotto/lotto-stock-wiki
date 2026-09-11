---
name: project-taerini-pipeline
description: 태린이아빠 파일 기반 분석 파이프라인 — 완료/진행/예정 작업 현황
metadata: 
  node_type: memory
  type: project
  originSessionId: 7fa5ef7b-d21d-4c6f-8e81-14aa1c8c4da0
---

# 태린이아빠 파일 파이프라인 현황

**Why:** 태린이아빠 마이박스 공유 파일로 매일 수급·RS·가속화 자동 분석 → 텔레그램 전송

## ✅ 완료된 것

| 항목 | 파일 | 비고 |
|------|------|------|
| 마이박스 자동 다운로드 | `scripts/download_daily.py` | 매일 **20:10** 스케줄 (STOCKBRAIN_Daily_Download) |
| KIND 투경 크롤링 | `scripts/crawl_kind.py --tg` | 매일 20:10 (STOCKBRAIN_투경_Crawl) |
| 투경 해제 조건 판단 | `scripts/check_투경_해제.py --tg` | 매일 20:15 → 내일 시가베팅 후보 텔레 (STOCKBRAIN_투경_해제판단) |
| 와이즈리포트 수집 | `scripts/fetch_wisereport.py --tg` | 매일 07:30 (STOCKBRAIN_WiseReport) |
| 대형주 수급 오실레이터 | `ingest_excel.py` → `parse_수급오실레이터()` | 700종목, EMA MACD, 텔레 발송 |
| 중소형주 수급 오실레이터 | `ingest_excel.py` → `parse_중소형주오실레이터()` | 700-1400위 695종목, 텔레 발송 |
| 업종 오실레이터 | `scan_업종오실레이터.py` | 77개 업종 빈집 탐지, ingest에서 자동 실행 |
| 가속화모멘텀 | `ingest_excel.py` → `parse_가속화모멘텀()` | Q열(주당순이익1개+) TOP30, 텔레 발송 |
| RS 상대강도 | `ingest_excel.py` → `parse_rs()` | Mansfield RS 공식, 텔레 발송 |
| ingest 스케줄 등록 | STOCKBRAIN_Daily_Ingest | 매일 07:50 자동 실행 (2026-06-02 등록) |
| 추정이익 카드뉴스 | `scripts/viz_card.py` | TOP3, PNG 저장, 텔레 전송. `--tg` 플래그 |
| 풀 대시보드 | `scripts/viz_consensus.py` | 45일필터·범위바·테마토글·신고가뱃지 |
| 한국ETF RS | `ingest_excel.py` → `parse_한국ETF상대강도()` | Mansfield RS, 소라티노 파일 폴백, 텔레 발송 (2026-06-02) |
| 투자아이디어 | `ingest_excel.py` → `parse_투자아이디어()` | 현재+다음분기 트리거 97개 추출, 텔레 발송 (2026-06-02) |
| 소르티노 자동 연결 | `scan_sortino.py --tg` | ingest 실행 후 자동 subprocess 호출 (2026-06-02) |
| 쏠림지수 | `ingest_excel.py` → `parse_쏠림지수()` | 붉은선·MACD·오실레이터, 텔레 발송 |
| 액티브ETF | `ingest_excel.py` → `parse_액티브ETF()` | 비중 증가/감소 종목, 텔레 발송 |
| 일정 | `ingest_excel.py` → `parse_일정()` | D-7/D-30 이벤트, 텔레 발송 |
| 컨센움직임 | `ingest_excel.py` → `parse_컨센움직임()` | 파서 있음, 리포트만 (텔레 미발송) |
| 교차분석 | `_build_교차분석_tg()` | 수급빈집×RS×가속화 → 탑픽 자동 텔레 |

## 📋 파일별 용도

| 파일 | 용도 | 텔레 |
|------|------|------|
| 추정이익 변경.xlsm | Rating/TP 상향하향 → wiki 컨센 업데이트 + 카드뉴스 | ✅ viz_card.py --tg |
| 컨센움직임서프쇼크.xlsx | 컨센상향·서프라이즈·쇼크 | 리포트만 |
| 주요품목별수출정리.xlsx | 디램/낸드/HBM 등 9개 품목 수출 신호 | 리포트만 |
| 유동성체크(+가속화+신고가).xlsm | 컨센신고가 TOP10 + 가속화모멘텀 | ✅ 가속화 텔레 |
| 수급오실레이터(700).xlsm | 대형주 빈집A/B | ✅ 텔레 |
| 수급오실레이터(700-1400).xlsm | 중소형주 빈집A/B | ✅ 텔레 |
| 수급오실레이터(업종).xlsm | 77개 업종 빈집 | ✅ 자동 |
| 한국상대강도.xlsx | Mansfield RS 150종목 | ✅ 텔레 |
| 소라티노ETF상대강도.xlsx | Sortino Top20 + ETF RS (매일 갱신) | ✅ 텔레 |
| 한국ETF상대강도.xlsx | Mansfield RS ETF (갱신 안 되면 소라티노 파일 폴백) | ✅ 텔레 |
| 액티브ETF관리.xlsx | ETF 비중 증가/감소 | ✅ 텔레 |
| 특정업종쏠림지수국내.xlsx | 업종 쏠림지수 (붉은선) | ✅ 텔레 |
| 일정 및 수주잔고.xlsx | 실적일정·수주 D-7/D-30 | ✅ 텔레 |
| 투자아이디어정리.xlsx | 현재+다음분기 트리거 | ✅ 텔레 |

## 스케줄 (2026-06-02 확정)

```
[저녁 — 내일 준비]
20:10 STOCKBRAIN_Daily_Download  → download_daily.py (마이박스 태린이 파일)
20:10 STOCKBRAIN_투경_Crawl      → crawl_kind.py --tg
20:15 STOCKBRAIN_투경_해제판단   → check_투경_해제.py --tg (시가베팅 후보 알림)

[아침 — 장 시작 전]
07:30 STOCKBRAIN_WiseReport      → fetch_wisereport.py --tg
07:50 STOCKBRAIN_Daily_Ingest    → ingest_excel.py (전체 파서 + 텔레 10건+)

[사용자 직접]
뉴스·텔레·블로그·한투API         → 사용자 완성
```

## 집PC 이전 방법
```
git pull
scripts/setup_schedule.bat  (관리자 권한으로 실행)
```

## 🔁 2026-07 태린이 파일 개편 대응 (커밋 2c2e3b4)

태린이아빠가 마이박스 파일명/구조를 개편 → `ingest_excel.py` 파서 find_excel 패턴 재매핑 완료.
**마이박스 링크는 매주 변경** → `scripts/mybox_links.json`의 naver.me 3개(ame/cafe/bingsu)만 갱신하면 됨
(`download_mybox.mjs`가 JSON 읽음, "전체 내려받기"가 하위폴더 재귀 다운로드 → basename 평탄화).

| 파서 | 옛 파일 → 새 파일(시트) |
|------|------|
| parse_컨센움직임 | 컨센움직임서프쇼크 → **투자픽업용** (컨센상향/하향/서프라이즈/쇼크) |
| parse_유동성체크·parse_가속화모멘텀 | 유동성체크 → **카페라떼 회원용 종목피킹** (컨센신고가/가속화모멘텀/유동성 컨셉 시트 통합) |
| parse_rs | 한국상대강도 → **종목상대강도데이터**(종가) + **etf상대강도데이터**(데이터=소라티노) 둘 다. irp/해외본 제외 |
| parse_추정이익변경 | 크롤링본(TP시트없음) 제외 → **날짜본(0701)** 선택 (tp 0→207 해결) |
| parse_액티브ETF | 액티브ETF관리 → **액티브ETF를 관찰하자** (+시트 코스닥액티브2,배당성장) |
| 컨센흐름 그래프 | ✅ parse_컨센흐름 → pipeline/taerini_consensus.json (종목별 주간 12MF/FY1/FY2 영업이익 컨센). 영업이익 시트=Fwd.12M, fy1=당해, fy2=차년. r8=코드·r15+=날짜/값(날짜 아니면 break) |

검증: taerini_stock.json 645종목, 커버리지 osc222·tp207·consensus370·accel144·rs37·etf26.

## 📊 /market 차트모달 '투자 참고지표' 패널 (구 태린이 지표, 커밋 18acbc9)
- 세로 패널(270px) + 접기/펼치기 토글(◀/▶, localStorage). 접으면 차트 전체폭.
- 지표별 인라인+hover툴팁: 수급빈집(빈집A/B·과매수+%ile)·RS(정규화)·TP(증권사·발표일)·컨센(변화%·기준일)·가속(그룹)·ETF비중(±%p)
- build_stock_index: tp에 brokerage·date, consensus에 date 추가
- **컨센흐름 차트 오버레이**: /api/taerini_consensus → 주가 위에 영업이익 컨센 라인(별도축), 표시/숨김 토글 + 12MF/FY1/FY2 전환. 일봉+ 에서만(_isIntraday 제외).
- 파일: dashboard/market.html(_taeriniHtml·_toggleTaerini·_cf* 함수), dashboard/server.py(/api/taerini_consensus)

## ⚠️ 주의사항

- 업종 수급 오실레이터 해석: 양수 높음 = "이미 수급 들어온 업종 (빈집 아님)", 음수 낮음 = "업종 빈집"
  - 종목 빈집과 동일 계산. "수급 강하다" 아니라 "수급 유입 중" or "수급 공백"으로 표현해야 함
- 한국ETF상대강도 파일: 태린이아빠가 갱신 안 하면 soratino 파일로 자동 폴백 (10일 기준)
- scan_업종오실레이터.py 라벨 수정 필요: "수급 강한 업종" → "수급 유입 중 업종"

## 🔲 다음 할 것

| 기능 | 내용 |
|------|------|
| 유튜브 화두 TOP5 텔레 | scout_yt_hot.py 스케줄 등록 |
| 3단계×4단계 자동 연결 | ETF RS 상위 업종 종목만 탑픽 필터 |
| 아침 전체 요약 텔레 | 07:30 전체 브리핑 한 메시지로 |

**How to apply:** "태린이 파일", "교차분석", "카드뉴스", "인제스트", "스케줄" 언급 시 이 메모리 참조
