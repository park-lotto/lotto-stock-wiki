#!/bin/bash
# usage: bash rs.sh S02 s02  → 빌드·주인공 설치·렌더·1초 시트·음성 합본
set -e
cd "$(dirname "$0")"; D=$1; V=$2
py _tools_p6p10/build.py $D >/dev/null && py _hero_draft/hero_install.py $D/template >/dev/null
(cd $D/template && npx -y hyperframes@0.8.105 render . --fps 30 --workers 3 -o ../out.mp4 2>&1 | grep -E "rendered|rror" | head -5)
ffmpeg -v error -y -i $D/out.mp4 -vf "fps=1,scale=480:-1,tile=6x7" -frames:v 1 $D/sheet.jpg
ffmpeg -v error -y -i $D/out.mp4 -i ../voice/$V.mp3 -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k $D/${V}_av.mp4
echo "$D 끝"
