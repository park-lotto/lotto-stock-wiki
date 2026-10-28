# [서버용·읽기 전용] 관제 204 전후 비교 — 최근 작업의 화면 데이터로 서버 러너(screen_clips_runner.js)를
#   라이브 scene_play.js 와 새 scene_play.js 로 각각 돌려 칸별 컷(v,s,d,sd,fit)이 같은지 센다.
#   scp 새 scene_play.js → /tmp/p204/scene_play.js 후:  python3 ab_cuts.py 48
#   ★기존 작업은 컷 변화 0이어야 통과(새 기능은 표식 DATA.hand_cut 있는 새 작업만).
import sys, json, sqlite3, time, subprocess, tempfile, os
hours = float(sys.argv[1]) if len(sys.argv) > 1 else 48
INJECT = "inject" in sys.argv[2:]
LIVE = "/home/ubuntu/lotto-stock-wiki"
os.chdir(LIVE); sys.path.insert(0, LIVE)
from shopping_shorts import screen_clips as sc
DB = LIVE + "/shopping_shorts/data/reference.db"
db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - hours * 3600))
ids = [r[0] for r in db.execute("select job_id from mix_jobs where updated_at > ? and edit_plan_json is not null and edit_plan_json != '' order by updated_at desc", (since,))]
RUNNER = LIVE + "/shopping_shorts/screen_clips_runner.js"
JS = {"old": LIVE + "/shopping_shorts/static/scene_play.js", "new": "/tmp/p204/scene_play.js"}

def run(js, data):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(data, f, ensure_ascii=False)
    try:
        out = subprocess.run(["node", RUNNER, js, f.name], capture_output=True, text=True, timeout=60)
        return json.loads(out.stdout) if out.returncode == 0 else ("ERR", out.stderr[-300:])
    finally:
        os.unlink(f.name)

jobs = beats = diff_beats = fixed = errs = 0
for jid in ids:
    try:
        data = sc._scene_data(jid)
    except Exception as e:   # noqa: BLE001
        errs += 1; continue
    if not data or not data.get("beats"):
        continue
    a = run(JS["old"], data)
    if INJECT:                      # 검사가 실제로 차이를 잡는지 시험 — 새 코드에만 표식을 강제로 켠다
        data = dict(data, hand_cut=1)
    b = run(JS["new"], data)
    if isinstance(a, tuple) or isinstance(b, tuple):
        errs += 1; print("ERR", jid, a if isinstance(a, tuple) else b); continue
    jobs += 1
    fixed += sum(1 for x in data["beats"] if x.get("fixed_lens"))
    for k, (x, y) in enumerate(zip(a, b)):
        beats += 1
        if x != y:
            diff_beats += 1; print("DIFF", jid, k, json.dumps(x)[:200], "→", json.dumps(y)[:200])
print("jobs=%d beats=%d diff_beats=%d beats_with_fixed_lens=%d errs=%d" % (jobs, beats, diff_beats, fixed, errs))
