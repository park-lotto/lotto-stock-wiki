"""대본과 어긋난 TTS 비트를 찾아 다시 뽑는다(2026-08-19 실사고 수습).

증상: 미리보기에서 "tts가 우리 대본을 읽고 딴소리한다".
원인: 어떤 리라이터가 beat["narration"]만 갈아치우고 재합성을 안 했다.
      렌더는 _synthesize_beats(skip_existing=True)가 자동으로 고치지만,
      미리보기는 tts_path를 그대로 틀어 옛 소리가 들렸다.

판정은 mix_pipeline.tts_matches_narration 한 곳만 쓴다(0순위-B).

    python tools/fix_tts_drift.py            # 조사만(기본) — 아무것도 안 바꾼다
    python tools/fix_tts_drift.py --fix      # 어긋난 비트만 재합성
    python tools/fix_tts_drift.py --fix --job <job_id>
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shopping_shorts import mix_pipeline                      # noqa: E402
from shopping_shorts.store import Store                       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="실제로 재합성한다(없으면 조사만)")
    ap.add_argument("--job", help="이 잡만")
    ap.add_argument("--db", default=os.environ.get(
        "SHORTS_DB", "shopping_shorts/data/reference.db"))
    ap.add_argument("--work", default="shopping_shorts/data/mix_jobs")
    a = ap.parse_args()

    store = Store(a.db)
    rows = store.list_mix_jobs() if hasattr(store, "list_mix_jobs") else None
    if rows is None:                       # 헬퍼가 없으면 직접 읽는다
        import sqlite3
        con = sqlite3.connect(a.db)
        rows = [r[0] for r in con.execute(
            "SELECT job_id FROM mix_jobs WHERE edit_plan_json IS NOT NULL")]
    else:
        rows = [r["job_id"] for r in rows]
    if a.job:
        rows = [j for j in rows if j == a.job]

    bad = []
    for jid in rows:
        job = store.get_mix_job(jid)
        plan = (job or {}).get("edit_plan") or {}
        for b in (plan.get("beats") or []):
            if not mix_pipeline.tts_matches_narration(b):
                # 파일이 실제로 있을 때만 '어긋남' — 없으면 그냥 미합성이다
                if b.get("tts_path") and Path(b["tts_path"]).exists():
                    bad.append((jid, b["beat_idx"]))

    print("어긋난 비트 %d개 / 잡 %d개" % (bad and len(bad) or 0,
                                          len({x[0] for x in bad})))
    for jid, bi in bad:
        print("   %s beat%s" % (jid, bi))
    if not bad or not a.fix:
        if bad:
            print("\n--fix 를 붙이면 위 비트만 다시 뽑는다(다른 비트는 안 건드린다).")
        return

    for jid, bi in bad:
        job = store.get_mix_job(jid)
        print("재합성: %s beat%s …" % (jid, bi), flush=True)
        mix_pipeline.resynth_one_beat(jid, bi, dict(job.get("voice") or {}),
                                      a.db, Path(a.work))
        job2 = store.get_mix_job(jid)
        beat = next(b for b in job2["edit_plan"]["beats"] if b["beat_idx"] == bi)
        print("   → %s" % ("OK" if mix_pipeline.tts_matches_narration(beat) else "여전히 어긋남"))


if __name__ == "__main__":
    main()
