@echo off
REM Open Claude Code inside a track worktree (.tracks\<name>).
REM   track.bat          -> pick from a numbered list
REM   track.bat <name>   -> open that track directly
REM Content is ASCII on purpose: Korean in a .bat breaks under codepage
REM switches. All Korean UI lives in tools/track_open.py, which handles it.
py "%~dp0tools\track_open.py" %*
if errorlevel 1 pause
