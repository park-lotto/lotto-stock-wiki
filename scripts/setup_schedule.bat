@echo off
:: setup_schedule.bat — 이 PC에 스케줄 태스크 등록
:: 관리자 권한으로 실행: 우클릭 → 관리자로 실행

setlocal EnableDelayedExpansion

:: 프로젝트 루트 (이 스크립트의 부모 폴더)
set "ROOT=%~dp0.."
pushd "%ROOT%"
set "ROOT=%CD%"
popd

echo ==============================================
echo  STOCKBRAIN 스케줄 등록
echo  프로젝트: %ROOT%
echo ==============================================
echo.

:: Python
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

:: cmd로 디렉토리 먼저 이동 후 실행 (Start In 대체)
set "CMD_DL=cmd /c \"cd /d %ROOT% && \"%PYTHON%\" scripts\download_daily.py\""
set "CMD_IN=cmd /c \"cd /d %ROOT% && \"%PYTHON%\" scripts\ingest_excel.py\""

echo [1] 기존 태스크 삭제...
schtasks /delete /tn "STOCKBRAIN_Daily_Download" /f 2>nul
schtasks /delete /tn "STOCKBRAIN_Daily_Ingest"   /f 2>nul
echo     OK
echo.

echo [2] 다운로드 태스크 등록 (07:30)...
schtasks /create /tn "STOCKBRAIN_Daily_Download" /tr "%CMD_DL%" /sc daily /st 07:30 /rl highest /ru "%USERNAME%" /it /f
echo.

echo [3] Ingest+텔레그램 태스크 등록 (07:50)...
schtasks /create /tn "STOCKBRAIN_Daily_Ingest" /tr "%CMD_IN%" /sc daily /st 07:50 /rl highest /ru "%USERNAME%" /it /f
echo.

echo [4] 등록 확인...
schtasks /query /tn "STOCKBRAIN_Daily_Download" /fo TABLE 2>&1
schtasks /query /tn "STOCKBRAIN_Daily_Ingest"   /fo TABLE 2>&1
echo.

echo ==============================================
echo  완료! 내일부터 자동 실행됩니다.
echo  07:30 다운로드 → 07:50 분석+텔레그램
echo ==============================================
pause
