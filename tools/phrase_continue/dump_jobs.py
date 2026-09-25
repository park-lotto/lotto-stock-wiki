# -*- coding: utf-8 -*-
"""라이브 서버에서 **읽기만** 해서 최근 작업을 떠 온다 — check_phrase_continue.py의 입력.
  (서버, repo 폴더에서) python3 tools/phrase_continue/dump_jobs.py <일수> <출력.sqlite>

mix_jobs 행을 그대로 새 sqlite에 복사하고, 같은 파일 안 durations 표에 영상·음성 실제 길이(ffprobe)를 적는다.
원본 영상 파일은 안 가져온다(용량) — 길이만 있으면 미리보기·렌더 계획을 똑같이 다시 짤 수 있다.
"""
import sys, json, sqlite3, glob, os, subprocess, datetime
days, out = float(sys.argv[1]), sys.argv[2]
SRC = "shopping_shorts/data/reference.db"
src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
schema = src.execute("select sql from sqlite_master where name='mix_jobs'").fetchone()[0]
since = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)).isoformat()
rows = src.execute("select * from mix_jobs where updated_at>? and edit_plan_json is not null", (since,)).fetchall()
cols = [r[1] for r in src.execute("pragma table_info(mix_jobs)")]
if os.path.exists(out): os.remove(out)
dst = sqlite3.connect(out)
dst.execute(schema)
dst.execute("create table durations(job_id text, kind text, key text, sec real)")
def probe(f):
    try:
        return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f],
                                    capture_output=True, text=True, timeout=20).stdout.strip() or 0)
    except Exception:
        return 0.0
n = 0
for r in rows:
    jid = r[cols.index("job_id")]
    base = f"shopping_shorts/data/mix_jobs/{jid}"
    if not os.path.isdir(base): continue
    dst.execute(f"insert into mix_jobs values ({','.join('?'*len(cols))})", r)
    for d in sorted(glob.glob(f"{base}/s*/")):
        vid = os.path.basename(d.rstrip("/"))
        fs = [f for f in glob.glob(f"{d}*.mp4")]
        if fs: dst.execute("insert into durations values (?,?,?,?)", (jid, "src", vid, probe(fs[0])))
    plan = json.loads(r[cols.index("edit_plan_json")] or "{}")
    for b in plan.get("beats") or []:
        tp = b.get("tts_path")
        if tp and os.path.exists(tp):
            dst.execute("insert into durations values (?,?,?,?)", (jid, "tts", tp, probe(tp)))
    n += 1
dst.commit()
print("jobs", n)
