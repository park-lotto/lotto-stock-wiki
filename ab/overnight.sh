#!/bin/sh
# 밤새 순차 실행 — 1차(run_ab)가 끝나기를 기다렸다가 2차(run_gate)를 잇는다.
# ★조용히 죽는 걸 막으려고 각 단계 rc를 chain.log에 남긴다.
cd "C:/Users/CH/Desktop/로또의 주식/.tracks/매칭오푸스AB/ab" || exit 1
export PYTHONIOENCODING=utf-8

echo "=== [1] run_ab 대기 시작 $(date +%H:%M:%S) ===" >> chain.log
# 1차가 아직 돌고 있으면 끝날 때까지 기다린다(진행파일이 total에 닿을 때까지).
while :; do
  done_n=$(py -c "import json;d=json.load(open('progress.json',encoding='utf-8'));print(d['done'])" 2>/dev/null || echo 0)
  tot_n=$(py -c "import json;d=json.load(open('progress.json',encoding='utf-8'));print(d['total'])" 2>/dev/null || echo 1)
  [ "$done_n" = "$tot_n" ] && break
  # 파이썬 프로세스가 사라졌으면 더 기다려봐야 소용없다.
  if ! ps -W 2>/dev/null | grep -q "python"; then
    echo "!! run_ab 프로세스 소실 (done=$done_n/$tot_n) $(date +%H:%M:%S)" >> chain.log
    break
  fi
  sleep 20
done
echo "=== [1] run_ab 종료 done=$done_n/$tot_n $(date +%H:%M:%S) ===" >> chain.log

echo "=== [2] run_gate 시작 $(date +%H:%M:%S) ===" >> chain.log
py -X utf8 run_gate.py --repeat 5 >> gate.log 2>&1
echo "=== [2] run_gate rc=$? $(date +%H:%M:%S) ===" >> chain.log

echo "=== [3] 리포트 생성 $(date +%H:%M:%S) ===" >> chain.log
py -X utf8 make_report.py >> chain.log 2>&1
echo "=== [3] 리포트 rc=$? $(date +%H:%M:%S) ===" >> chain.log
echo "=== 밤샘 전체 완료 $(date +%H:%M:%S) ===" >> chain.log
