@echo off
chcp 65001 >nul
cd /d "%~dp0"
git add state.json channel_layouts.json
git commit -m "장면꾸미기 작업대 값 저장 %date% %time:~0,5%" >nul 2>&1
git pull --rebase --autostash >nul 2>&1
git push
if %errorlevel%==0 (echo. & echo  ✅ 저장했습니다. 다른 PC에서 시작.bat을 누르면 이 값으로 열립니다.) else (echo. & echo  ❌ 올리기 실패 — 인터넷 연결을 확인하고 다시 누르세요)
echo.
pause
