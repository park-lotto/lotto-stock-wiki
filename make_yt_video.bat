@echo off
chcp 65001 > nul
cd /d "C:\Users\CH\Desktop\로또의 주식"
set PATH=C:\Users\CH\.local\bin;%PATH%

echo.
echo ============================================
echo  YouTube 영상제작 에이전트 시스템
echo ============================================
echo.

if "%~1"=="" (
    set /p IDEA="아이디어 입력: "
    .venv\Scripts\python.exe make_yt_video.py --idea "%IDEA%"
) else if "%~1"=="--resume" (
    .venv\Scripts\python.exe make_yt_video.py --resume %~2 %3 %4
) else (
    .venv\Scripts\python.exe make_yt_video.py --idea "%~1"
)

pause
