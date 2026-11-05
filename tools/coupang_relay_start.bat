@echo off
chcp 65001 >nul
REM 쿠팡·틱톡 검색 도우미 자동 시작(관제 315, 2026-11-03).
REM 서버는 쿠팡(해외IP 차단)·틱톡(서버·헤드리스 차단)을 못 긁는다 — 이 PC가 대신 긁는다.
REM 11-03 실측: 도우미가 안 켜져 렌즈 틱톡 0건·쿠팡 요청 25건 대기. 그래서 로그온 시 자동 + 죽으면 10초 뒤 재시작.
REM 시작 프로그램 바로가기: tools\coupang_relay_install_startup.ps1
cd /d "%~dp0.."
:loop
py -X utf8 scripts\coupang_relay_client.py >> "%TEMP%\coupang_relay.log" 2>&1
echo [relay] exited - restart in 10s >> "%TEMP%\coupang_relay.log"
timeout /t 10 /nobreak >nul
goto loop
