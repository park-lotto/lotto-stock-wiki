#!/usr/bin/env bash
# 원본찾기 감시 루프 — origin_find run 이 죽으면(claude -p·크롬·yt-dlp 사고) 30초 뒤 다시 잇는다. 대기열이 비면 끝.
# 실행: bash tools/calcopy/origin_find_loop.sh   (로그 C:/숏템_칼카피/_origin/run.log 에 이어 쓴다)
cd "$(dirname "$0")/../.."
LOG="C:/숏템_칼카피/_origin/run.log"
while true; do
  PYTHONUTF8=1 PYTHONUNBUFFERED=1 py tools/calcopy/origin_find.py run --n 3000 >> "$LOG" 2>&1
  rc=$?
  echo "[loop] $(date +%H:%M) run 끝 rc=$rc" >> "$LOG"
  grep -q "대기열 비었음" <(tail -5 "$LOG") && break
  sleep 30
done
