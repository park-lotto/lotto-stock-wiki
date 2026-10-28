#!/bin/bash
# 뜯기 배치 점검(제미나이 없음): 목록의 mp4 마다 check_layout.py → <출력접두>.part_NN.jsonl/.log
# usage: tools/calcopy/engine/analyze4_check/runbatch.sh <목록.txt(mp4 한 줄씩)> <출력접두(예: /tmp/x/base)> [동시수=4]
# ★동시 수는 4 이하(2026-10-16 페이블: 12개 동시에 PC CPU 100% → 다른 담당 작업이 기어감). 1편 2~8분.
set -e
LIST="$1"; OUT="$2"; N="${3:-4}"
[ "$N" -gt 4 ] && N=4
TREE="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$TREE"
rm -f "$OUT".*.jsonl "$OUT".*.log
P="$(dirname "$OUT")/parts_$(basename "$OUT")"; mkdir -p "$P"; split -n r/$N -d "$LIST" "$P/part_"
for p in "$P"/part_*; do
  k=$(basename "$p")
  (PYTHONUTF8=1 py tools/calcopy/engine/check_layout.py --json="$OUT.$k.jsonl" $(cat "$p") > "$OUT.$k.log" 2>&1) &
done
wait
rm -rf "$P"
echo done
