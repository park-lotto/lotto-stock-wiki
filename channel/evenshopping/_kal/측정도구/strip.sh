#!/bin/bash
# strip.sh mp4 t0 n step out  (window y591-1810 scaled to 180x366, tiled n x 1)
mp4=$1; t0=$2; n=$3; step=$4; out=$5
ffmpeg -v error -y -ss $t0 -i "$mp4" -vf "fps=1/$step,crop=1080:1220:0:590,scale=180:203,tile=${n}x1" -frames:v 1 "$out"
