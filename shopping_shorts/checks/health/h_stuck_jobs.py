"""진행 중으로 굳은 작업(B-47). job_queue running인데 heartbeat 5분 침묵(auto_deploy _worker_busy와 같은 기준),
mix_jobs 단계별(status/preview/clean/★fx — fx엔 staleness 가드가 없다, app.py:19056) 30분 초과."""
from datetime import timedelta
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "진행 중으로 굳은 작업", "every": "15m", "source": "job_queue / mix_jobs"}
ACTIVE = {"status": ("downloading", "extracting", "planning", "tts", "rendering", "removing_subtitles"),
          "preview_status": ("rendering",), "clean_status": ("cleaning",), "fx_status": ("queued", "running")}
STUCK_MIN = 30


def measure(ctx):
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_stuck_jobs", META["name"], None, None, detail=repr(e))]
    out = []
    try:
        silent = conn.execute(
            "SELECT COUNT(*) FROM job_queue WHERE state='running' "
            "AND datetime(heartbeat_at) < datetime('now','-5 minutes')").fetchone()[0]
        out.append(Sample("h_stuck_jobs::worker_silent", f"{META['name']} — 워커 침묵", silent, silent == 0,
                          detail=f"5분 넘게 하트비트 없는 running {silent}건", evidence_url="/admin/production"))
        cut = (ctx["now"] - timedelta(minutes=STUCK_MIN)).isoformat()
        for col, vals in ACTIVE.items():
            q = ",".join("?" * len(vals))
            n = conn.execute(f"SELECT COUNT(*) FROM mix_jobs WHERE {col} IN ({q}) AND updated_at < ?",
                             (*vals, cut)).fetchone()[0]
            key = col.replace("_status", "") if col != "status" else "mix"
            out.append(Sample(f"h_stuck_jobs::{key}", f"{META['name']} — {key}", n, n == 0,
                              detail=f"{STUCK_MIN}분 넘게 {vals} 상태 {n}건", evidence_url="/admin/production"))
    finally:
        conn.close()
    return out
