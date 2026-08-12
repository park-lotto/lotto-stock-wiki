#!/usr/bin/env bash
# 마스터 v3 마감 — 새 자막 스타일 렌더가 다 끝나기를 기다렸다가 붙이고, 무음 틈을 줄인다.
# 순서: S1·S4 완료 대기 → S5-2 재렌더 → concat(무손실) → 무음 트림
set -u
cd "$(dirname "$0")/.."
OUT=out
SCALE=1.3333333333333333

# 새 스타일 렌더 기준 시각(이보다 오래된 파일은 옛 스타일이다)
CUT=$(date -d '2026-08-12 13:50' +%s)

fresh() { [ -f "$1" ] && [ "$(stat -c %Y "$1")" -ge "$CUT" ]; }
playable() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" >/dev/null 2>&1; }

echo "[1/4] S1·S4 새 스타일 렌더 대기"
while ! { fresh $OUT/S1-ColdOpen_4k.mp4 && playable $OUT/S1-ColdOpen_4k.mp4 \
       && fresh $OUT/S4-Build_4k.mp4    && playable $OUT/S4-Build_4k.mp4; }; do
  sleep 30
done
echo "  → 완료"

echo "[2/4] S5-2 재렌더(plate/calm 스타일)"
if ! fresh $OUT/S5-2-Edit.mp4; then
  npx remotion render VSL-S5-2-Edit $OUT/S5-2-Edit.mp4 \
    --scale=$SCALE --crf=15 --concurrency=3 || exit 1
fi

echo "[3/4] 통합 concat (재인코딩 없음)"
ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $OUT/concat.txt \
  -c copy -movflags +faststart $OUT/VSL_전체통합_v3.mp4 || exit 1
ffprobe -v error -show_entries format=duration -of csv=p=0 $OUT/VSL_전체통합_v3.mp4

echo "[4/4] 무음 틈 줄이기"
py tools/trim_silence.py $OUT/VSL_전체통합_v3.mp4 $OUT/VSL_전체통합_v3_컷.mp4 --keep 0.09

cp $OUT/VSL_전체통합_v3_컷.mp4 "/c/Users/TheRose/Desktop/VSL_최종.mp4" && echo "바탕화면에 VSL_최종.mp4 복사 완료"
