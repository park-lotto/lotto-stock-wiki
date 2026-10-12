cd /tmp/ab; set -a; . /etc/shopping-shorts.env 2>/dev/null; set +a
export SS_HITS=/tmp/ab/raw/analysis/썰쇼핑_자막확장_2026-09-18/hits_subs.json
EX="이케아|다이소|코스트코|구글|아이소|옷장|점토|테이프|필름|복도"
run(){ echo "######## $1"; timeout 400 python3 tools/spine_presets/harvest_templates.py $1 --pattern "$2" --corpus hits --limit 30 --exclude "$EX" --apply 2>&1 | grep -E "^#|^\[|^  \+|APPLIED|수확 0|재료"; }
run 70 "예상 ?못|예측 ?못|몰랐던"
run 71 "의 실수"
run 72 "몰래"
run 73 "감탄한|놀란 천재"
echo HARVEST_DONE
