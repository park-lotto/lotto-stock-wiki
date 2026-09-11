---
name: project-oscillator-extraction
description: calc_oscillator.py 완성 — 수급오실레이터 계산+텔레그램 전송 스크립트
metadata: 
  node_type: memory
  type: project
  originSessionId: 4e558d4b-194a-4833-805b-0502580b3d26
---

`calc_oscillator.py` 완성 및 검증 완료 (2026-05-26).

**Why:** 매일 엑셀 xlsm에서 수급오실레이터를 뽑아 관심 종목 빈집 등급을 빠르게 확인하기 위해

**How to apply:** 새 세션에서 오실레이터 관련 작업 시 이 스크립트가 이미 완성되어 있음을 인지

## 스크립트 위치
`C:\Users\TheRose\Desktop\로또의 주식\calc_oscillator.py`

## 사용법
```
python calc_oscillator.py 종목1 종목2 종목3 --tg
```
- 다수 종목 동시 조회 + 빈집순 비교표 출력
- `--tg` 플래그: 결과를 텔레그램으로 자동 전송
- 소요시간: 약 27초 (4종목 기준, Excel COM 오버헤드)

## 공식 확인 완료
- `signal = (기관순매수 + 외인순매수) / 거래대금`
- `oscillator = MACD(12,26) - Signal(EMA9 of MACD)`
- EMA k값: K12=2/13, K26=2/27, K9=2/10
- 데이터: R15~R91 (77 거래일), 700개 종목
- 검증: SK하이닉스 오차 4.18e-09 ✅

## 백분위 기준값 위치 (xlsm 사전계산)
- `수급오실레이터` 시트 R7~R11, C12
- R7: 상위10%(p90), R8: 상위25%(p75), R10: 하위25%(p25), R11: 하위10%(p10)
- 단일/소수 조회 시 이 값으로 빠르게 등급 판정

## 텔레그램 설정
- `.env` 파일에 BOT_TOKEN, CHAT_ID 저장됨
- `send_telegram()` 함수가 HTML 포맷으로 전송

## 데이터 소스 시트
- `시가총액`: 거래대금
- `외국인매수데이터`: 외인 순매수 (R9=종목명, R8=코드, R15~R91=데이터)
- `기관매수데이터`: 기관 순매수
