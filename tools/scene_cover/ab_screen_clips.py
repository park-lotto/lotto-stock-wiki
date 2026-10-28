# [서버용·읽기 전용] 관제 084 전후 비교 — old: 라이브 코드·저장 계획 / new: /tmp/p084(트랙 코드)로 같은 2단계 결과에서 계획을 다시 만들고 새 컷 규칙
#   tar czf - shopping_shorts | ssh 서버 "tar xzf - -C /tmp/p084" 후: python3 ab_screen_clips.py old 24; python3 ab_screen_clips.py new 24; python3 ab_summary.py
# 관제 084 전후 비교 — mode=old: 라이브 코드·저장된 계획 / mode=new: 새 코드로 같은 2단계 결과에서 계획을 다시 만들고 새 컷 규칙
import sys, json, sqlite3, time, subprocess, tempfile, os, copy
mode = sys.argv[1]; hours = float(sys.argv[2]) if len(sys.argv) > 2 else 24
ROOT = "/tmp/p084" if mode == "new" else "/home/ubuntu/lotto-stock-wiki"
os.chdir(ROOT); sys.path.insert(0, ROOT)
from shopping_shorts import app, edit_plan as ep, mix_pipeline as mp, script_lang
from shopping_shorts.store import Store
DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - hours * 3600))
ids = [r[0] for r in db.execute("select job_id from mix_jobs where updated_at > ? and edit_plan_json is not null and edit_plan_json != '' order by updated_at desc", (since,))]
orig = Store.get_mix_job
res = {}
for jid in ids:
    job = orig(Store(app.DB_PATH), jid)
    if not job or not (job.get("edit_plan") or {}).get("beats"):
        continue
    if mode == "new":
        ss = job.get("script_structure") or {}
        if not (ss.get("inherit_scenes") and ss.get("beat_sources") and (job.get("given_script") or "").strip()):
            continue
        src = script_lang.mute_foreign_speech(list((job.get("extract") or {}).values()))
        try:
            np_ = ep.build_inherit_plan(src, job["given_script"], ss["beat_sources"], structure=job.get("structure") or "template")
        except Exception as e:
            continue
        old_b = job["edit_plan"]["beats"]
        if not np_ or len(np_["beats"]) != len(old_b):
            continue
        for nb, ob in zip(np_["beats"], old_b):
            nb["target_seconds"] = ob.get("target_seconds")
        mp._trim_for_cut_rhythm(np_)
        job = copy.deepcopy(job)
        for nb, ob in zip(np_["beats"], job["edit_plan"]["beats"]):
            ob["primary"], ob["alternates"] = nb["primary"], nb["alternates"]
            ob["cut_rhythm"] = nb.get("cut_rhythm"); ob["phrase_sync"] = nb.get("phrase_sync", True)
            for k in ("clip_anchor",):
                ob.pop(k, None)
        job["edit_plan"]["cut_rule"] = "scenes_v2"
        Store.get_mix_job = (lambda j: (lambda self, x: j if x == j["job_id"] else orig(self, x)))(job)
    else:
        ss = job.get("script_structure") or {}
        if not (ss.get("inherit_scenes") and ss.get("beat_sources") and (job.get("given_script") or "").strip()):
            continue
    try:
        r = app.api_mix_scene_lab_data(jid)
        d = (r if isinstance(r, dict) else json.loads(r.body)).get("data")
    except Exception as e:
        continue
    if not d or not d.get("beats"):
        continue
    if mode == "new":      # 새 작업 흉내 — 옛 규칙으로 저장된 3단계 장면 목록·손 컷은 새 작업엔 없다
        for b in d["beats"]:
            b.pop("scene_override", None); b.pop("manual_cuts", None)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, default=str); tmp = f.name
    json.dump(d, open("/tmp/ab084_data_%s_%s.json" % (mode, jid), "w"), ensure_ascii=False, default=str)
    out = subprocess.run(["node", ROOT + "/shopping_shorts/screen_clips_runner.js", ROOT + "/shopping_shorts/static/scene_play.js", tmp], capture_output=True, text=True, timeout=60)
    os.unlink(tmp)
    if out.returncode != 0:
        res[jid] = {"err": out.stderr[-200:]}; continue
    res[jid] = json.loads(out.stdout)
json.dump(res, open("/tmp/ab084_%s.json" % mode, "w"))
print(mode, "작업", len(res))
