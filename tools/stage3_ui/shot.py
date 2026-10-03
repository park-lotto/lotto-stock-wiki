# -*- coding: utf-8 -*-
"""3단계(영상대본MIX) 화면을 실제 job 재료로 띄워 캡처한다(관제 086 화면 정리 전/후 대조).

  py tools/stage3_ui/shot.py <job_id> <job_row.json> <out.png> [--check]
    job_id      : shopping_shorts/data/mix_jobs/<job_id>/ 에 재료가 있어야 한다(서버에서 복사)
    job_row.json: 서버 mix_jobs 행 — 격리 DB에 넣는다(로그인 게이트만 끈 실제 앱)
  --check : 효과음 패널·⋯ 메뉴·칸 🔇를 실제로 눌러 저장·반영을 잰다(check_panel 참조)
"""
import sys, json, tempfile, threading, time, sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from shopping_shorts.store import Store
from shopping_shorts import app as A

job_id, row_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
CHECK = "--check" in sys.argv
row = json.load(open(row_path, encoding="utf-8"))
_srv = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/"
_loc = str(ROOT / "shopping_shorts" / "data").replace("\\", "/") + "/"
row = {k: (v.replace(_srv, _loc) if isinstance(v, str) else v) for k, v in row.items()}
tmp = Path(tempfile.mkdtemp(prefix="stage3ui_")); db = tmp / "t.db"
st = Store(str(db))
con = sqlite3.connect(str(db))
cols = [r[1] for r in con.execute("pragma table_info(mix_jobs)")]
use = [c for c in cols if c in row]
con.execute("insert into mix_jobs (%s) values (%s)" % (",".join(use), ",".join("?" * len(use))), [row[c] for c in use])
con.commit(); con.close()
st.set_setting("sfx_pack_enabled", "1")
A.DB_PATH = str(db); A._AUTH_ON = False
import uvicorn
PORT = 8797
threading.Thread(target=lambda: uvicorn.run(A.app, host="127.0.0.1", port=PORT, log_level="warning"), daemon=True).start()
time.sleep(4)

from playwright.sync_api import sync_playwright
ok = True
def check(cond, msg):
    global ok
    print(("  ✅ " if cond else "  ❌ ") + msg); ok &= bool(cond)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1650, "height": 1250})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(f"http://127.0.0.1:{PORT}/produce.html", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    pg.evaluate(f"() => {{ MIX_JOB='{job_id}'; stepGo('mix'); try{{ loadMixReview(); }}catch(e){{}} }}")
    pg.wait_for_timeout(9000)
    fr = next((f for f in pg.frames if "scene_lab" in f.url), None)
    if fr is None:
        print("★ scene_lab iframe 없음"); b.close(); sys.exit(1)
    pg.screenshot(path=out, full_page=False)
    print("캡처:", out, "· 페이지 오류:", errs[:3])
    if CHECK:
        from check_panel import run
        ok = run(pg, fr, job_id, db, check, out) and ok
        print("페이지 오류:", errs[:3])
        print("결과:", "통과" if ok else "실패")
    b.close()
sys.exit(0 if ok else 1)
