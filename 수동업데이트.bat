@echo off
chcp 65001 >nul
title 로또의 주식 — 시장 데이터 수동 업데이트
echo.
echo  ┌─────────────────────────────────────────────┐
echo  │   로또의 주식 — 시장 데이터 수동 업데이트    │
echo  │   Yahoo Finance 11개 지표 실시간 수집        │
echo  └─────────────────────────────────────────────┘
echo.
cd /d "%~dp0"
node update_market_data.js
echo.
echo  ─────────────────────────────────────────────
echo  업데이트 완료! 아무 키나 누르면 창이 닫힙니다.
pause >nul
