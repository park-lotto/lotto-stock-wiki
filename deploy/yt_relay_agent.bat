@echo off
REM YouTube relay agent keep-alive runner (2026-08-31)
REM WHY: AWS server is bot-blocked by YouTube; this PC has a residential IP
REM and downloads on the server's behalf. If this stops, customers' step-1
REM video extraction stops. Incident 2026-08-30: died 22:18, found 23:23.
REM The loop restarts the agent if it exits - that is the point.
REM NOTE: ASCII only. cmd.exe reads this as CP949; non-ASCII breaks parsing.
REM NOTE: project path has Korean chars, so it is passed via pushd with
REM short-name expansion instead of being typed literally.

set "PY=C:\Users\CH\AppData\Local\Python\bin\python.exe"
set "YT_RELAY_KEY=eAiqvdZ27K121kvDT0zhZ0o-tda5a6Nm"
set "LOG=C:\Users\CH\yt_relay_agent.log"

REM YouTube bot-check cookies (2026-08-31). yt-dlp cannot read Chrome cookies

REM (App-Bound Encryption, Chrome 127+). Export from a logged-in Firefox profile:

REM   py -m yt_dlp --cookies-from-browser firefox --cookies yt_cookies.txt --skip-download URL

REM If the file is missing, yt-dlp runs without cookies exactly as before.

set "YTDLP_COOKIES_BROWSER_YOUTUBE=firefox"
REM (file snapshot fallback - browser-direct above wins when Firefox is present)
set "YTDLP_COOKIES_YOUTUBE=C:\Users\CH\yt_cookies.txt"

pushd "%~dp0.."

:loop
echo [%date% %time%] agent start >> "%LOG%"
"%PY%" -m shopping_shorts.youtube_relay_agent >> "%LOG%" 2>&1
echo [%date% %time%] exited (code %errorlevel%) - restarting in 15s >> "%LOG%"
timeout /t 15 /nobreak > nul
goto loop