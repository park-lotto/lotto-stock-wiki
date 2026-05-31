@echo off
cd /d "C:\Users\CH\Desktop\로또의 주식"
.venv\Scripts\python.exe scripts\download_daily.py
.venv\Scripts\python.exe scripts\send_download_brief.py
