# 서버에서: cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && python3 tools/editor_render_audit.py 7
# node 러너 경로는 shopping_shorts/screen_clips_runner.js 로 바꿔 쓸 것(원본은 /tmp/cbpatch/editor_clips.js)
# 최근 N일 job 전부: 라이브 편집 화면 코드(scene_play.js, node) 컷 vs 서버 렌더 컷(plan_beat_clips_for)
import json, subprocess, sys, sqlite3, collections
sys.path.insert(0, ".")
from pathlib import Path
from datetime import datetime, timedelta, timezone
from shopping_shorts import app, mix_pipeline as mp, video_assemble as va
from shopping_shorts.store import Store
days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
st = Store("shopping_shorts/data/reference.db"); con = sqlite3.connect("shopping_shorts/data/reference.db")
since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
root = Path("shopping_shorts/data/mix_jobs")
tot_j = tot_b = bad_b = 0; bad_jobs = collections.Counter(); kinds = collections.Counter(); ex = []; errs = 0
for (jid,) in con.execute("select job_id from mix_jobs where updated_at>=? order by updated_at desc", (since,)):
    job = st.get_mix_job(jid); plan = (job or {}).get("edit_plan") or {}
    if not plan.get("beats"): continue
    try:
        r = app.api_mix_scene_lab_data(jid); d = (r if isinstance(r, dict) else json.loads(r.body)).get("data")
        if not d: continue
        Path("/tmp/kgb/sl_a.json").write_text(json.dumps(d, ensure_ascii=False))
        ed = [r["c"] for r in json.loads(subprocess.check_output(["node", "shopping_shorts/screen_clips_runner.js", "shopping_shorts/static/scene_play.js", "/tmp/kgb/sl_a.json"], timeout=60).decode())]
        sd = mp._src_durs_for(job, root / jid)
    except Exception as e:
        errs += 1; continue
    tot_j += 1
    for b, e in zip(plan["beats"], ed):
        tp = b.get("tts_path")
        try: td = float(va._beat_effective_dur(b, tp)) if tp and Path(tp).exists() else 0
        except Exception: td = 0
        if td <= 0: continue
        tot_b += 1
        sv = [(c["video_id"], c["start"], c.get("src_dur") or c["out_dur"], c["out_dur"]) for c in va.plan_beat_clips_for(b, td, sd)]
        ev = []
        for c in e:
            rd = c["sd"] if c["sd"] is not None else c["d"]
            tot = sd.get(c["v"], 0) or 0
            if tot > 0: rd = min(rd, max(0.0, tot - c["s"]))     # 화면 finish 는 원본 끝으로 자른다
            ev.append((c["v"], c["s"], rd, c["d"]))
        ok = len(sv) == len(ev) and all(a[0] == x[0] and abs(a[1]-x[1]) < 0.05 and abs(a[2]-x[2]) < 0.1 and abs(a[3]-x[3]) < 0.1 for a, x in zip(sv, ev))
        if not ok:
            bad_b += 1; bad_jobs[jid] += 1
            k = ("컷수" if len(sv) != len(ev) else "영상/시작" if any(a[0] != x[0] or abs(a[1]-x[1]) >= 0.05 for a, x in zip(sv, ev)) else "길이")
            k += "|손컷" if b.get("phrase_sync") is False and b.get("manual_cuts") else ("|구절" if b.get("phrase_sync") else "|기타")
            k += "|리듬" if b.get("cut_rhythm") else ""
            kinds[k] += 1
            if len(ex) < 12: ex.append((jid, b["beat_idx"], k, [(x[0], round(x[1],2), round(x[2],2), round(x[3],2)) for x in ev], [(a[0], round(a[1],2), round(a[2],2), round(a[3],2)) for a in sv]))
print("== 대상 job %d · 칸 %d · 편집화면≠완성본 칸 %d · job %d (점검실패 %d)" % (tot_j, tot_b, bad_b, len(bad_jobs), errs))
for k, v in kinds.most_common(): print("  ", v, k)
for e in ex: print(e)
