"""(서버에서 실행) 최근 제작 job의 원본 재료 영상에서 소리만 뽑아 /tmp/ov/ 에 모은다 — 원음살리기 조사 1단계.

  python3 sample_sources.py [N=40] [DAYS=14] [PER_JOB=2]
출력: /tmp/ov/<md5앞12>.mp3 (16kHz 모노) + /tmp/ov/manifest.json (job·url·플랫폼·길이)
같은 원본(내용 md5)은 한 번만 센다 — 손님들이 같은 재료를 여러 번 돌리므로.
"""
import glob, hashlib, json, os, sqlite3, subprocess, sys, time

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 14
BASE = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data"
OUT = "/tmp/ov"
PER_JOB = int(sys.argv[3]) if len(sys.argv) > 3 else 2   # 한 job이 표본을 독차지하지 않게
os.makedirs(OUT, exist_ok=True)
db = sqlite3.connect(BASE + "/reference.db")
db.row_factory = sqlite3.Row
cols = [r[1] for r in db.execute("PRAGMA table_info(mix_jobs)")]
ts = "created_at" if "created_at" in cols else cols[0]
rows = db.execute("SELECT job_id AS id, urls_json, %s AS t FROM mix_jobs ORDER BY %s DESC LIMIT 2000" % (ts, ts)).fetchall()


def plat(u):
    u = (u or "").lower()
    for k in ("douyin", "instagram", "tiktok", "youtube", "xiaohongshu", "kuaishou", "bilibili"):
        if k in u:
            return k
    return "upload" if not u.startswith("http") else "other"


seen, man = set(), []
for r in rows:
    if len(man) >= N:
        break
    d = os.path.join(BASE, "mix_jobs", r["id"])
    if not os.path.isdir(d):
        continue
    try:
        urls = json.loads(r["urls_json"] or "[]")
    except Exception:
        urls = []
    taken = 0
    for i in range(12):
        if taken >= PER_JOB:
            break
        fs = [f for f in glob.glob(os.path.join(d, "s%d" % i, "*.mp4"))]
        if not fs:
            continue
        f = fs[0]
        h = hashlib.md5(open(f, "rb").read()).hexdigest()[:12]
        if h in seen:
            continue
        seen.add(h)
        u = urls[i] if i < len(urls) else ""
        if isinstance(u, dict):
            u = u.get("url") or ""
        mp3 = os.path.join(OUT, h + ".mp3")
        p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", f, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", mp3])
        if p.returncode or not os.path.exists(mp3):
            continue  # 소리 트랙 없는 재료
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3],
                                   capture_output=True, text=True).stdout.strip() or 0)
        taken += 1
        man.append({"h": h, "job": r["id"], "slot": i, "url": u, "plat": plat(u), "dur": round(dur, 1), "t": str(r["t"])})
        if len(man) >= N:
            break
json.dump(man, open(OUT + "/manifest.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(len(man), Counter(m["plat"] for m in man))
