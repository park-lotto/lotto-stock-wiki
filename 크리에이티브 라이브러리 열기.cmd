@echo off
cd /d "%~dp0"
py -X utf8 -m creative_library.viewer --repo "%~dp0."
if errorlevel 1 pause
