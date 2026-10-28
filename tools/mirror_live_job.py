"""서버의 실제 job 한 건을 로컬 격리 DB로 그대로 옮긴다 — "로컬 = 서버와 같은 조건"으로 고치기 위한 도구.
  ★서버는 읽기만 한다(sqlite mode=ro, scp 받기만). 관리자 본인(customer_id=0) job만 허용한다.
  실행: py tools/mirror_live_job.py <job_id>      → .tmp/local-mirror/{mirror.db, mix_jobs/<job_id>}
  띄우기: py tools/serve_local_mirror.py          → http://127.0.0.1:8772/produce.html
"""
import json, sqlite3, subprocess, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shopping_shorts.store import Store

HOST = "ubuntu@shoppingshorts.duckdns.org"          # IP는 바뀐다 — 도메인으로 간다
REMOTE = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data"
KEY = (glob.glob("C:/Users/*/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem") or [""])[0]
MIRROR = ROOT / ".tmp" / "local-mirror"

def main(job_id):
    if not job_id.isalnum():
        raise SystemExit("job_id 형식이 이상하다")
    remote_py = f'''
import sqlite3, json
c = sqlite3.connect("file:{REMOTE}/reference.db?mode=ro", uri=True); c.row_factory = sqlite3.Row
job = c.execute("select * from mix_jobs where job_id=?", ("{job_id}",)).fetchone()
works = c.execute("select * from produce_works where job_id=?", ("{job_id}",)).fetchall()
print(json.dumps({{"job": dict(job) if job else None, "works": [dict(w) for w in works]}}))
'''
    out = subprocess.run(["ssh", "-i", KEY, "-o", "ConnectTimeout=15", HOST, "python3 -"],
                         input=remote_py.encode(), capture_output=True, check=True).stdout
    data = json.loads(out.decode("utf-8"))
    job = data["job"]
    if not job:
        raise SystemExit("서버에 그 job이 없다")
    if job.get("customer_id") != 0:
        raise SystemExit("관리자 본인(customer_id=0) job만 가져온다 — 고객 데이터는 로컬로 옮기지 않는다")
    folder = MIRROR / "mix_jobs" / job_id
    if not folder.is_dir():
        folder.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["scp", "-i", KEY, "-q", "-r", f"{HOST}:{REMOTE}/mix_jobs/{job_id}", str(folder.parent)], check=True)
    local_prefix = str(MIRROR / "mix_jobs").replace("\\", "/")
    fix = lambda v: v.replace(f"{REMOTE}/mix_jobs", local_prefix) if isinstance(v, str) else v
    db = MIRROR / "mirror.db"
    Store(db)                                           # 스키마는 앱이 쓰는 그대로 만든다
    con = sqlite3.connect(db)
    for table, rows, key in (("mix_jobs", [job], "job_id"), ("produce_works", data["works"], "work_id")):
        have = [r[1] for r in con.execute(f"pragma table_info({table})")]
        for row in rows:
            missing = [k for k in row if k not in have]
            if missing:
                print(f"⚠️ 로컬 스키마에 없는 서버 컬럼({table}): {missing} — 로컬 코드가 서버보다 옛것일 수 있다")
            cols = [k for k in row if k in have]
            con.execute(f"delete from {table} where {key}=?", (row[key],))
            con.execute(f"insert into {table} ({','.join(cols)}) values ({','.join('?'*len(cols))})", [fix(row[k]) for k in cols])
    con.commit()
    print(json.dumps({"job": job_id, "works": [w["work_id"] for w in data["works"]], "db": str(db),
                      "폴더파일수": sum(1 for p in folder.rglob("*") if p.is_file())}, ensure_ascii=False))

if __name__ == "__main__":
    main(sys.argv[1])
