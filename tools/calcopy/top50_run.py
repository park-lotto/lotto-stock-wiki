# -*- coding: utf-8 -*-
"""채널 하나 → 조회 상위 50편 받기 → 1차 분석(analyze50) → 집계(summarize50) (관제 097, 2026-10-15).

    PYTHONUTF8=1 py tools/calcopy/top50_run.py <채널 주소> <약칭>
원본은 C:/숏템_칼카피/<약칭>/, 결과는 channel/<약칭>/. 끝나면 원장 2단계 기록.
"""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import calcopy_board as B

url, slug = sys.argv[1], sys.argv[2]
base = Path("C:/숏템_칼카피") / slug
base.mkdir(parents=True, exist_ok=True)
u = url.rstrip("/")
u = u if u.endswith("/shorts") else u + "/shorts"
d = json.loads(subprocess.run(["yt-dlp", "--encoding", "utf-8", "--flat-playlist", "-J", u], capture_output=True, encoding="utf-8").stdout)
E = sorted([e for e in d["entries"] if e.get("view_count")], key=lambda e: -e["view_count"])[:50]
(base / "top50.json").write_text(json.dumps([{"id": e["id"], "views": e["view_count"], "title": e.get("title", "")} for e in E], ensure_ascii=False, indent=1), encoding="utf-8")
B.set_step(slug, "1", "done", f"전체 {len(d['entries'])}편 중 조회 상위 50편({E[0]['view_count']:,}~{E[-1]['view_count']:,})", [],
           name=d.get("channel"), url=url, stats={"subs": d.get("channel_follower_count"), "total": len(d["entries"])})
(base / "top50.txt").write_text("\n".join("https://www.youtube.com/shorts/" + e["id"] for e in E))
# 받기: 50편을 yt-dlp 프로세스 DL_PAR 개로 나눠 동시에(10-18 — 옛 1프로세스 순차). 단계 초는 top50_time.json 에 자동 기록.
DL_PAR = int(os.environ.get("TOP50_DL_PAR") or 4)
import time
from concurrent.futures import ThreadPoolExecutor
t_dl = time.time()
urls = (base / "top50.txt").read_text().splitlines()
lists = [base / f"top50_part{i}.txt" for i in range(DL_PAR)]
for i, lp in enumerate(lists):
    lp.write_text("\n".join(urls[i::DL_PAR]))
def _dl(lp):
    return subprocess.run(["yt-dlp", "--encoding", "utf-8", "-q", "--ignore-errors", "-a", str(lp), "-f", "bv*[height<=1920][ext=mp4]+ba/b[ext=mp4]/b",
                           "--merge-output-format", "mp4", "--no-overwrites", "-o", str(base / "mp4" / "%(id)s.%(ext)s")]).returncode
with ThreadPoolExecutor(DL_PAR) as ex:
    rcs = list(ex.map(_dl, lists))
n_mp4 = len(list((base / "mp4").glob("*.mp4")))
(base / "top50_time.json").write_text(json.dumps({"download_sec": round(time.time() - t_dl, 1), "dl_par": DL_PAR, "mp4": n_mp4, "rcs": rcs}, ensure_ascii=False), encoding="utf-8")
B.set_step(slug, "2", "doing", "1차 분석 중(판독·받아쓰기·bench)", [])
subprocess.run([sys.executable, str(ROOT / "tools/calcopy/analyze50.py"), str(base)])
subprocess.run([sys.executable, str(ROOT / "tools/calcopy/summarize50.py"), str(base), str(ROOT / "channel" / slug)])
subprocess.run([sys.executable, str(ROOT / "tools/calcopy/sfx_pack.py"), str(base)])
n = len(list((base / "judge").glob("*.json")))
B.set_step(slug, "2", "done" if n >= 45 else "blocked", f"1차 분석: 판독 {n}/{len(E)}", [f"channel/{slug}/1차분석_갈래.json"])
print("끝", slug, n)
