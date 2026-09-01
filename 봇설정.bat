@echo off
REM One-time setup for the Telegram work bot.
REM   Asks for the bot token, finds your chat_id, writes both into .env
REM Content is ASCII on purpose (same reason as track.bat): Korean in a .bat
REM breaks under codepage switches. Korean UI lives in tg_bot/setup_helper.py.
cd /d "%~dp0"
py -m tg_bot.setup_helper
pause
