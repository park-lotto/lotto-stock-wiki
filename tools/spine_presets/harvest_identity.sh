cd /tmp/ab; set -a; . /etc/shopping-shorts.env 2>/dev/null; set +a
export SS_HITS=/tmp/ab/raw/analysis/썰쇼핑_자막확장_2026-09-18/hits_subs.json
EX="이케아|다이소|코스트코|구글|아이소|옷장|점토|테이프|필름|복도"
python3 - <<PY
import json,subprocess
for sid,name,pat in json.load(open("/tmp/identity_new.json")):
    print("########", sid, name, flush=True)
    subprocess.run("sleep 30; timeout 400 python3 tools/spine_presets/harvest_templates.py %d --pattern \"%s\" --corpus hits --limit 30 --exclude \"$EX\" --apply 2>&1 | grep -E \"^#|^\[|^  \+|APPLIED|수확 0|재료\"" % (sid, pat), shell=True)
print("HARVEST_DONE", flush=True)
PY
