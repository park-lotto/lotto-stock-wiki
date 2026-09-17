"""격리 QA DB에 작업 전환용 두 job/work를 만든다."""
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shopping_shorts.store import Store

root = Path(__file__).resolve().parents[1]
work = root / ".tmp" / "scene-style-qa"
store = Store(work / "qa.db")
source = store.get_mix_job("scene-style-qa")
if not source:
    raise SystemExit("qa_scene_style_render.py를 먼저 실행하세요")

for suffix, scene_index, zoom in (("a", 1, 1.21), ("b", 2, 1.72)):
    job_id = f"scene-style-qa-{suffix}"
    if not store.get_mix_job(job_id):
        store.create_mix_job(job_id, source["urls"] or ["qa-local"], 3, "free")
    snapshot = {
        "mode": "story", "presetId": "t11", "sceneIndex": scene_index,
        "text": {"hook1": f"QA-{suffix.upper()}"},
        "effects": {str(scene_index): {"zoom": zoom}},
    }
    store.update_mix_job(job_id, edit_plan=source["edit_plan"], deco={"scene_style": snapshot})
    target = work / job_id / "s0"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(work / "source.mp4", target / "source.mp4")
    store.upsert_produce_work(
        f"qa-work-{suffix}", {"script": f"QA work {suffix}", "handoff": []},
        job_id=job_id, step=0,
    )
print("ok")
