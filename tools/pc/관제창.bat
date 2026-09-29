@echo off
REM Main control window: Claude Code with the Telegram channel.
REM Talk to it from Telegram; it dispatches work to track sessions.
REM Content is ASCII on purpose (see track.bat).
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
REM Guard: kills Telegram pollers started by any other Claude session (they steal messages).
start "telegram-guard" /min powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%USERPROFILE%\telegram-guard.ps1"
claude --channels plugin:telegram@claude-plugins-official --settings "%USERPROFILE%\claude-telegram-on.json" %*
if errorlevel 1 pause
