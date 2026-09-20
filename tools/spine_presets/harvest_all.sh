cd /tmp/ab; set -a; . /etc/shopping-shorts.env 2>/dev/null; set +a
export SS_HITS=/tmp/ab/raw/analysis/썰쇼핑_자막확장_2026-09-18/hits_subs.json
EX="이케아|다이소|코스트코|구글|아이소|옷장|점토|테이프"
run(){ echo "######## $1"; timeout 400 python3 tools/spine_presets/harvest_templates.py $1 --pattern "$2" --corpus hits --limit 30 --exclude "$EX" $3 2>&1 | grep -E "^#|^\[|^  \+|^  x|APPLIED|수확 0|재료|미적용"; }
run 60 "개발자도|무릎" --apply
run 65 "당황" --apply
run 69 "하나면|요놈" --apply
run 68 "단돈|원이면|만 원" --apply
run 67 "충격" --apply
run 66 "답답|짜증|스트레스" --apply
run 56 "원래 이렇게|원래는|활용법" --apply
echo HARVEST_DONE
