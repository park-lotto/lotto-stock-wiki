@echo off
REM 유튜브 릴레이 에이전트 — PC 주거용 IP로 유튜브를 받아 서버에 올린다.
REM 서버는 YT_RELAY_ENABLED=1 / YTDLP_PROXY 비움 상태여야 이 경로를 탄다(2026-08-11).
REM 이 창을 닫으면 제작소의 유튜브 소재 다운로드가 멈춘다.
cd /d "%~dp0.."
set YT_RELAY_SERVER=https://shoppingshorts.duckdns.org
set YT_RELAY_KEY=eAiqvdZ27K121kvDT0zhZ0o-tda5a6Nm
:loop
py -m shopping_shorts.youtube_relay_agent
echo [relay] 종료됨 - 10초 뒤 재시작
timeout /t 10 /nobreak >nul
goto loop
