#!/bin/bash
# usage: render.sh P1  -> build + render + sheet
cd "$(dirname "$0")"
python3 build.py $1 && (cd $1/template && npx -y hyperframes@0.8.105 render . --fps 30 -o ../out.mp4 2>&1 | grep -E "MB|rror:") && python3 sheet.py $1
