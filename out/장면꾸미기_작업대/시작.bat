@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] 최신 값 받는 중...
git pull --ff-only
echo [2/2] 작업대 켜는 중... (브라우저가 열립니다. 이 창은 닫지 마세요)
start "" http://127.0.0.1:8766/
py server.py
