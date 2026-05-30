@echo off
cd /d "c:\Users\TheRose\Desktop\로또의 주식"
python night_watch.py >> "out\night_logs\scheduler.log" 2>&1
