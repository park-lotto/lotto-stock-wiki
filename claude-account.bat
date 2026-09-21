@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

:menu
cls
echo.
echo   ========================================
echo      Claude Code - Account Selection
echo   ========================================
echo.
echo     [1] Main account   (parklotto12@gmail.com)
echo     [2] Sub  account   (parklotto20@gmail.com)
echo.
echo     [Q] Quit
echo.
set "sel="
set /p sel="  Select (1/2): "

if /i "%sel%"=="1" goto main
if /i "%sel%"=="2" goto sub
if /i "%sel%"=="q" exit /b 0
goto menu

:main
rem Main account uses the DEFAULT location (%USERPROFILE%\.claude.json).
rem Do NOT set CLAUDE_CONFIG_DIR here - pointing it at ~\.claude makes
rem Claude look for ~\.claude\.claude.json, which does not exist.
set "CLAUDE_CONFIG_DIR="
echo.
echo   [Main] parklotto12@gmail.com
echo   config: %%USERPROFILE%%\.claude.json (default)
echo.
goto run

:sub
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude-sub"
echo.
echo   [Sub] parklotto20@gmail.com
echo   config: %CLAUDE_CONFIG_DIR%
echo.
if not exist "%CLAUDE_CONFIG_DIR%\.credentials.json" (
  echo   * Not logged in yet. Run /login inside Claude Code.
  echo.
)
goto run

:run
claude %*
endlocal
