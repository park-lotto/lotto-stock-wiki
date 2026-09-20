@echo off
REM Start the Telegram work bot.
REM   Runs on THIS PC and calls the local Claude subscription -> no API cost.
REM   Stop it with Ctrl+C in this window.
REM Content is ASCII on purpose: Korean in a .bat breaks under codepage
REM switches (same reason as track.bat). All Korean UI lives in tg_bot/run.py.
cd /d "%~dp0"
py -m tg_bot.run
pause
