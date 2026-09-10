@echo off
powershell.exe -NoProfile -File "%~dp0open_static_result.ps1" -HtmlPath "%USERPROFILE%\Desktop\AI Shorts\outputs\loop_earplug_missing_scenes\compare.html" -Port 8899
if errorlevel 1 pause
