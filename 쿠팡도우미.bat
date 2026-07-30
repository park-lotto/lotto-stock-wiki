@echo off
chcp 65001 >nul
title 쿠팡 검색 도우미 (숏템메이커)
cd /d "%~dp0"

REM 쿠팡은 한국 IP가 아니면 막는다 — 서버(AWS)는 못 긁는다. 그래서 이 PC가 대신 검색한다.
REM 이 창을 켜두면 숏템메이커 제작소의 "쿠팡에서 상품 찾기"가 동작한다. 닫으면 그냥 멈춘다.

if "%COUPANG_RELAY_TOKEN%"=="" (
  echo [설정 필요] COUPANG_RELAY_TOKEN 이 없습니다.
  echo   서버 /etc/shopping-shorts.env 의 COUPANG_RELAY_TOKEN 과 같은 값을 넣으세요.
  echo   예) setx COUPANG_RELAY_TOKEN "여기에토큰"   ^(넣은 뒤 이 창을 다시 여세요^)
  pause
  exit /b 2
)

py -X utf8 scripts\coupang_relay_client.py
pause
