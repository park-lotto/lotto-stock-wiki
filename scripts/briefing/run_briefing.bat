@echo off
cd /d C:\Users\CH\Desktop\로또의 주식
call C:\Users\CH\Desktop\로또의 주식\.venv\Scripts\python.exe scripts/briefing/collect.py >> logs\briefing.log 2>&1
timeout /t 30 /nobreak
call C:\Users\CH\Desktop\로또의 주식\.venv\Scripts\python.exe scripts/briefing/bot.py >> logs\briefing.log 2>&1
call C:\Users\CH\Desktop\로또의 주식\.venv\Scripts\python.exe scripts/briefing/publish.py >> logs\briefing.log 2>&1
