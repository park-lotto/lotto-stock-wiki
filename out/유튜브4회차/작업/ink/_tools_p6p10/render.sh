#!/bin/bash
# usage: render.sh P6  -> build + render(out.mp4) + check
cd "$(dirname "$0")"
s=$1
py build.py $s && py ../_hero_draft/hero_install.py ../$s/template && (cd ../$s/template && npx -y hyperframes@0.8.105 render . --fps 30 -o ../out.mp4 2>&1 | grep -E "MB|rror" ) && py check.py $s --tag after
