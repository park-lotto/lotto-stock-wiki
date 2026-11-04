#!/bin/bash
# 영상 칸 장면: 빌드·렌더 → ov.py 로 실제 영상 끼우기
set -e; cd "$(dirname "$0")"; D=$1; V=$2
py _tools_p6p10/build.py $D >/dev/null && py _hero_draft/hero_install.py $D/template >/dev/null
(cd $D/template && npx -y hyperframes@0.8.105 render . --fps 30 --workers 3 -o ../out.mp4 2>&1 | grep -E "rendered|rror" | grep -v Lint | head -3)
py ov.py $D $V
