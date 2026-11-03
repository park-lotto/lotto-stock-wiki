"""플랫폼별 CTA 판 실제 렌더 점검(서버 사본, 라이브 무변경). 사용(서버): set -a; eval "$(sudo cat /etc/shopping-shorts.env)"; set +a; python3 tools/cta_variants_run_check.py <job_id> [cta|full]
판 영상과 본편을 ffmpeg psnr 로 대조하면 cta 방식은 CTA 앞까지 inf(같은 그림)여야 한다."""
# 서버 사본에서 run_render 를 그대로 돌려 판을 만든다(라이브 DB·폴더 무변경)
import sys, os, json, sqlite3, shutil, time
sys.path.insert(0, ".")
JID = sys.argv[1]; MODE = sys.argv[2] if len(sys.argv) > 2 else "cta"
ROOT = "/tmp/f1"; LIVE = "shopping_shorts/data"
os.makedirs(ROOT + "/jobs", exist_ok=True)
db = ROOT + "/ref.db"
if not os.path.exists(db):
    src = sqlite3.connect(f"file:{LIVE}/reference.db?mode=ro", uri=True); dst = sqlite3.connect(db); src.backup(dst); dst.close(); src.close()
shutil.rmtree(f"{ROOT}/jobs/{JID}", ignore_errors=True)
shutil.copytree(f"{LIVE}/mix_jobs/{JID}", f"{ROOT}/jobs/{JID}", ignore=shutil.ignore_patterns("final*.mp4", "capcut*"))
live_dir = os.path.abspath(f"{LIVE}/mix_jobs/{JID}"); tmp_dir = f"{ROOT}/jobs/{JID}"
c = sqlite3.connect(db)
for col in ("edit_plan_json", "deco_json", "thumbnail_json"):
    v = c.execute(f"select {col} from mix_jobs where job_id=?", (JID,)).fetchone()[0]
    if v: c.execute(f"update mix_jobs set {col}=? where job_id=?", (v.replace(live_dir, tmp_dir), JID))
c.commit(); c.close()
from tools.gate_modules import load_patch_modules
load_patch_modules(os.environ.get("PATCH_DIR","/tmp/pb6"))
import importlib.util, shopping_shorts
_sp = importlib.util.spec_from_file_location("shopping_shorts.cta_variants", "/tmp/pb6/cta_variants.py")
_m = importlib.util.module_from_spec(_sp); sys.modules["shopping_shorts.cta_variants"] = _m; _sp.loader.exec_module(_m); shopping_shorts.cta_variants = _m
from shopping_shorts import mix_pipeline as mp, cta_variants as cv
from shopping_shorts.store import Store
cv.save_config(Store(db), JID, 0, {"tts_mode": MODE, "items": [{"key": "insta", "on": True, "text": "궁금하면 댓글에 링크 남겨주세요, 바로 보내드릴게요."}, {"key": "profile", "on": True, "text": "프로필 링크에서 확인하세요."}]})
t0 = time.time()
mp.run_render(JID, db, ROOT + "/jobs", skip_clean=True)
print("총", round(time.time() - t0, 1), "초")
print(json.dumps(cv.read_status(f"{ROOT}/jobs/{JID}"), ensure_ascii=False))
print(Store(db).get_mix_job(JID).get("status"))
