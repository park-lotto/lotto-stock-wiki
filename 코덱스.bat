@echo off
REM Open Codex inside a track worktree (.tracks\<name>).
REM   codex.bat          -> pick from a numbered list
REM   codex.bat <name>   -> open that track directly
REM ASCII on purpose: Korean in a .bat breaks under codepage switches.
py "%~dp0tools\track_open.py" --agent codex %*
if errorlevel 1 pause
