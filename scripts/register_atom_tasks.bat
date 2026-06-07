@echo off
chcp 65001 > nul
echo [STOCKBRAIN] 원자 DB 자동 파이프라인 Task Scheduler 등록 중...

set PYTHON=C:\Users\TheRose\AppData\Local\Python\bin\python.exe
set WORKDIR=C:\Users\TheRose\Desktop\로또의 주식
set XML_MORNING=%WORKDIR%\scripts\atom_task_morning.xml
set XML_EVENING=%WORKDIR%\scripts\atom_task_evening.xml

REM 아침 08:00 등록
schtasks /create /tn "STOCKBRAIN_Atom_Morning" /xml "%XML_MORNING%" /f
if %ERRORLEVEL% == 0 (
    echo [OK] STOCKBRAIN_Atom_Morning 등록 완료 (매일 08:00)
) else (
    echo [FAIL] STOCKBRAIN_Atom_Morning 등록 실패
)

REM 저녁 21:00 등록
schtasks /create /tn "STOCKBRAIN_Atom_Evening" /xml "%XML_EVENING%" /f
if %ERRORLEVEL% == 0 (
    echo [OK] STOCKBRAIN_Atom_Evening 등록 완료 (매일 21:00)
) else (
    echo [FAIL] STOCKBRAIN_Atom_Evening 등록 실패
)

echo.
echo 등록된 STOCKBRAIN 작업 목록:
schtasks /query /fo TABLE | findstr "STOCKBRAIN"

pause
