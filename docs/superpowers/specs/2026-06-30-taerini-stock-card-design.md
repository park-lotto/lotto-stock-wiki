# 종목별 태린이 지표 — 대시보드 종목 카드 (설계)

- 날짜: 2026-06-30
- 대상: 딸깍 대시보드(STOCK BRAIN) — 섹터 히트맵 페이지(`dashboard/market.html`, `:8090`)
- 범위: 태린이 13개 파서 결과를 **종목코드로 조회 가능한 스냅샷 DB**로 저장하고, 차트 모달에 "태린이 지표" 패널로 표시
- 비범위(YAGNI): 교집합 신호 자동생성, 위키 종목페이지 녹이기, 전용 검색 패널 — 후속 별도 스펙. 쏠림지수·수출(업종/품목 단위)은 종목 카드에서 제외.

## 1. 배경 / 문제

태린이 13개 파서(`scripts/ingest_excel.py`)는 엑셀을 읽어 **텔레그램 텍스트로만 발송**(휘발성)한다. `main()`이 모든 파서 반환값을 `results` dict로 수집하지만(텔레그램 빌드에만 사용), 종목 단위로 조회할 수 없다. 대시보드에서 종목을 눌러도 그 종목의 수급 오실레이터·RS·컨센 TP·가속화·ETF비중·실적일정을 볼 수 없다.

## 2. 목표

- 종목 클릭(차트 모달) 시 그 종목의 태린이 지표를 한눈에 표시.
- 표시 항목: **수급 오실레이터 / 컨센 TP·움직임 / RS / 가속화·ETF비중·실적일정** (사용자 선택, 풀세트).
- 기존 파서·텔레그램 로직은 **수정하지 않음**(회귀 위험 0).

## 3. 데이터 흐름

```
태린이 엑셀(20:10 다운로드) → ingest_excel.main() 파서13개 → results dict
   └─[신규] build_stock_index(results) → 종목명→코드 정규화
        → pipeline/taerini_stock.json (일 1회 스냅샷)
            └─[신규] GET /api/taerini_stock?code= → 차트 모달 "📊 태린이 지표" 패널
```

신규 구성요소는 3개뿐: **집계기 1 · 엔드포인트 1 · 모달 패널 1**.

## 4. 컴포넌트

### 4.1 집계기 `build_stock_index(results)` — `scripts/ingest_excel.py`

- 위치: `main()`이 `results`를 모은 직후 호출(텔레그램 발송 단계와 독립).
- 종목명 → 코드: 기존 KRX 코드맵(`KRX_CODES`) + alias(현대차→현대차 등 서버 `_SEARCH_ALIASES`와 동일 정책). **미매칭 종목명은 `meta.unmatched`에 기록**(조용히 버리지 않음 — 위키 원칙 [[feedback_no_adhoc_page_creation]] 정신).
- 파서별 → 필드 매핑:
  | 파서 결과 키 | 카드 필드 | 추출 값 |
  |---|---|---|
  | 수급 / 중소형주수급 | `osc` | macd, signal(신호문구), rank |
  | RS | `rs` | value, rank |
  | 추정이익변경 | `tp` | target, prev, change_pct, dir(상향/하향) |
  | 컨센움직임 | `consensus` | type(컨센상향/서프라이즈/쇼크), change_pct |
  | 가속화모멘텀 | `accel` | group, score, rank |
  | 액티브ETF | `etf` | action(비중증가/감소), delta |
  | 일정 | `schedule` | event, date, dday |
- 부분 빌드: 일부 파서가 `{"error":...}`여도 나머지 필드로 채운다.
- 원자적 쓰기: temp 파일 → `os.replace`.

### 4.2 스냅샷 `pipeline/taerini_stock.json`

```json
{
  "date": "2026-06-30",
  "stocks": {
    "247540": {
      "name": "에코프로비엠",
      "osc":   {"macd": -0.42, "signal": "데드크로스", "rank": 612},
      "rs":    {"value": 0.78, "rank": 140},
      "tp":    {"target": 330000, "prev": 360000, "change_pct": -8.3, "dir": "하향"},
      "consensus": {"type": "쇼크", "change_pct": -12.0},
      "accel": {"group": "주당순이익1개+", "score": 0.61, "rank": 22},
      "etf":   {"action": "비중감소", "delta": -0.3},
      "schedule": {"event": "실적발표", "date": "2026-07-29", "dday": -29}
    }
  },
  "meta": {"built_at": "ISO8601", "stock_count": 0, "unmatched": []}
}
```
- 각 필드는 그 파서 결과에 종목이 있을 때만 존재(없으면 키 생략).

### 4.3 엔드포인트 `GET /api/taerini_stock?code=` — `dashboard/server.py`

- 반환: `{date, found, stock:{...}}`. 파일 없거나 코드 미수록이면 `{found:false}` (HTTP 200, 500 아님).
- 캐시: 파일 mtime 기반(또는 60초 TTL). 스냅샷은 일 1회 갱신이라 무겁지 않음.

### 4.4 종목 카드 패널 — `dashboard/market.html` (차트 모달)

- 위치: 차트 모달 내 시간대/지표 버튼 줄 **아래 접이식 "📊 태린이 지표" 패널**.
- `openStockChart(code,name)` 시 fetch. 종목 전환 시 갱신.
- 한 줄 압축 표시 예:
  `수급 데드크로스(612위) · RS 0.78(140위) · TP 33만↓(-8.3%) · 컨센 쇼크 · 가속 0.61(22위) · ETF 비중↓ · 실적 D-29`
- 색상: 오실레이터 신호·TP방향·컨센 타입에 빨강/초록. 없는 항목은 "—".
- 데이터 없으면 "태린이 미수록". `date`가 오늘 기준 2영업일+ 지났으면 회색 + 날짜 강조(오래된 데이터 경고).

## 5. 갱신주기

- 일 1회(기존 `STOCKBRAIN_Daily_Ingest` 07:50). 별도 스케줄 추가 없음.
- 카드에 스냅샷 `date` 항상 표기 → 사용자가 신선도 인지.

## 6. 에러 처리

- 파서 부분 실패: 나머지 필드로 부분 빌드.
- 종목명→코드 미매칭: `meta.unmatched`에 누적(silent drop 금지).
- 엔드포인트: 파일 부재/미수록 코드 → `found:false` graceful.
- 모달 패널 fetch 실패: 패널만 "지표 로드 실패", 차트는 정상 동작.

## 7. 테스트

1. **집계기 단위**: 샘플 `results` dict → 기대 JSON. 종목명→코드 매핑(현대차 alias) 케이스, 미매칭이 `unmatched`로 가는지.
2. **엔드포인트**: 존재 코드 → 레코드 / 미존재 코드 → `found:false` / 파일 부재 → `found:false`.
3. **골든 종목 실빌드**: 실제 엑셀로 build 후 골든 종목(예: 에코프로비엠)의 필드가 채워지는지.
4. **모달 표시**: 코드로 차트 열었을 때 패널 렌더 + 데이터 없는 종목은 "미수록" 표시.

## 8. 향후(별도 스펙)

- 교집합 신호 자동생성(주도업종×컨센상향, ETF비중↑×수급빈집).
- 위키 L6 종목페이지 자동 녹이기(히스토리 누적).
- 종목/업종 검색 전용 패널.
- 다른 두 시스템: 크롤링 뉴스 종목연결, 배팅 검증 시스템(예측→실제결과 추적).
