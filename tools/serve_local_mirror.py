"""mirror_live_job.py가 옮겨온 **서버 실제 job**으로 앱을 로컬에 띄운다(127.0.0.1:8772).
  가짜 QA job(serve_scene_style_qa.py, 8768)과 다르다 — 여기는 서버의 실제 대본·자막 시간표·영상이다.
  로그인 게이트만 끈다. 그 밖의 코드는 서버와 같은 것을 그대로 돌린다."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shopping_shorts import app as module
import uvicorn
work = Path(__file__).resolve().parents[1] / ".tmp" / "local-mirror"
if not (work / "mirror.db").exists():
    raise SystemExit("먼저 py tools/mirror_live_job.py <job_id>")
module.DB_PATH = str(work / "mirror.db"); module._MIX_WORK_DIR = work / "mix_jobs"; module._AUTH_ON = False
if __name__ == "__main__":
    uvicorn.run(module.app, host="127.0.0.1", port=8772, log_level="warning")
