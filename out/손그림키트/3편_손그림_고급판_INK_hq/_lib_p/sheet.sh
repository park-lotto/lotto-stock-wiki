#!/bin/bash
# usage: sheet.sh P6 [step_sec] [cols]
cd "$(dirname "$0")/../$1"
step=${2:-1}; cols=${3:-4}
rm -rf fr; mkdir fr
ffmpeg -v error -i out.mp4 -vf "fps=1/$step,scale=480:-1" fr/f%02d.png
n=$(ls fr | wc -l); rows=$(( (n+cols-1)/cols ))
ffmpeg -v error -y -i fr/f%02d.png -vf "tile=${cols}x${rows}:padding=4:color=white" -frames:v 1 sheet.jpg
echo frames=$n; ffprobe -v error -show_entries format=duration -of csv=p=0 out.mp4
